#!/usr/bin/env python3
"""
Simple API Server for Orderflow Dashboard
Serves dashboard and provides REST API for agent data
"""

import http.server
import socketserver
import json
import os
import sys
import sqlite3
from urllib.parse import urlparse, parse_qs
from datetime import datetime

PORT = 8100
DB_PATH = "/tmp/trading-desk/database/orderflow.db"
WWW_DIR = "/tmp/trading-desk/dashboard"

class OrderflowHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WWW_DIR, **kwargs)
    
    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/' or path == '/index.html':
            self.serve_file('/index.html')
        elif path.startswith('/api/'):
            self.handle_api(path)
        else:
            self.serve_file(path)
    
    def serve_file(self, path):
        """Serve a static file"""
        full_path = os.path.join(WWW_DIR, path.lstrip('/'))
        if os.path.exists(full_path):
            self.send_response(200)
            if path.endswith('.html'):
                self.send_header('Content-Type', 'text/html')
            elif path.endswith('.js'):
                self.send_header('Content-Type', 'application/javascript')
            elif path.endswith('.css'):
                self.send_header('Content-Type', 'text/css')
            self.end_headers()
            with open(full_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404)
    
    def handle_api(self, path):
        """Handle API requests"""
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        symbol = query.get('symbol', ['ES'])[0]
        timeframe = query.get('timeframe', ['5min'])[0]
        
        conn = sqlite3.connect(DB_PATH)
        
        if '/api/exhaustion' in path:
            self.handle_exhaustion(conn, symbol, timeframe)
        elif '/api/bars' in path:
            self.handle_bars(conn, symbol, timeframe)
        elif '/api/agents' in path:
            self.handle_agents(conn)
        elif '/api/absorption' in path:
            self.handle_absorption(conn, symbol, timeframe)
        elif '/api/volume' in path:
            self.handle_volume(conn, symbol, timeframe)
        elif '/api/delta' in path:
            self.handle_delta(conn, symbol, timeframe)
        elif '/api/liquidity' in path:
            self.handle_liquidity(conn, symbol, timeframe)
        elif '/api/trend' in path:
            self.handle_trend(conn, symbol, timeframe)
        elif '/api/volume_profile' in path:
            self.handle_volume_profile(conn, symbol, timeframe)
        elif '/api/vwap' in path:
            self.handle_vwap(conn, symbol, timeframe)
        elif '/api/footprint' in path:
            self.handle_footprint(conn, symbol, timeframe)
        else:
            self.send_error(404)
        
        conn.close()
    
    def handle_exhaustion(self, conn, symbol, timeframe):
        """Get exhaustion data"""
        cursor = conn.execute("""
            SELECT bar_time, score, details FROM agent_scores
            WHERE symbol = ? AND timeframe = ? AND agent_name = 'exhaustion'
            ORDER BY bar_time DESC
            LIMIT 5000
        """, (symbol, timeframe))
        rows = cursor.fetchall()
        
        history = []
        for row in rows:
            try:
                details = json.loads(row[2]) if row[2] else {}
            except:
                details = {}
            history.append({
                'bar_time': row[0],
                'score': row[1],
                'components': details
            })
        
        history.reverse()
        
        latest = history[-1] if history else None
        if latest:
            sys.path.insert(0, '/tmp/trading-desk')
            from agents.exhaustion_agent import ExhaustionAgent
            agent = ExhaustionAgent(DB_PATH)
            interp = agent._interpret(latest['score'])
            latest['interpretation'] = interp
        
        self.send_json({
            'symbol': symbol,
            'timeframe': timeframe,
            'latest': latest,
            'history': history,
            'bar_count': len(history)
        })
    
    def handle_bars(self, conn, symbol, timeframe):
        """Get bar data"""
        cursor = conn.execute("""
            SELECT bar_time, open, high, low, close, volume, delta
            FROM bars
            WHERE symbol = ? AND timeframe = ?
            ORDER BY bar_time DESC
            LIMIT 100
        """, (symbol, timeframe))
        rows = cursor.fetchall()
        
        bars = []
        for row in rows:
            bars.append({
                'bar_time': row[0],
                'open': row[1],
                'high': row[2],
                'low': row[3],
                'close': row[4],
                'volume': row[5],
                'delta': row[6]
            })
        
        bars.reverse()
        self.send_json({'bars': bars})
    
    def handle_agents(self, conn):
        """Get enabled agents"""
        cursor = conn.execute("SELECT name, description, enabled FROM agents")
        rows = cursor.fetchall()
        agents = [{'name': r[0], 'description': r[1], 'enabled': bool(r[2])} for r in rows]
        self.send_json({'agents': agents})
    
    def handle_absorption(self, conn, symbol, timeframe):
        """Get absorption data"""
        cursor = conn.execute("""
            SELECT bar_time, score, details FROM agent_scores
            WHERE symbol = ? AND timeframe = ? AND agent_name = 'absorption'
            ORDER BY bar_time DESC
            LIMIT 5000
        """, (symbol, timeframe))
        rows = cursor.fetchall()
        
        history = []
        for row in rows:
            try:
                details = json.loads(row[2]) if row[2] else {}
            except:
                details = {}
            history.append({
                'bar_time': row[0],
                'score': row[1],
                'direction': details.get('direction', 'NEUTRAL'),
                'components': details.get('components', {})
            })
        
        history.reverse()
        
        latest = history[-1] if history else None
        if latest:
            sys.path.insert(0, '/tmp/trading-desk')
            from agents.absorption_agent import AbsorptionAgent
            agent = AbsorptionAgent(DB_PATH)
            interp = agent._interpret(latest['score'])
            latest['interpretation'] = interp
        
        self.send_json({
            'symbol': symbol,
            'timeframe': timeframe,
            'latest': latest,
            'history': history,
            'bar_count': len(history)
        })
    
    def handle_volume(self, conn, symbol, timeframe):
        """Get volume data"""
        cursor = conn.execute("""
            SELECT bar_time, score, details FROM agent_scores
            WHERE symbol = ? AND timeframe = ? AND agent_name = 'volume'
            ORDER BY bar_time DESC LIMIT 5000
        """, (symbol, timeframe))
        rows = cursor.fetchall()
        
        history = []
        for row in rows:
            details = json.loads(row[2]) if row[2] else {}
            history.append({
                'bar_time': row[0], 'score': row[1],
                'volume': details.get('volume', 0),
                'components': details.get('components', {})
            })
        history.reverse()
        
        latest = history[-1] if history else None
        if latest:
            sys.path.insert(0, '/tmp/trading-desk')
            from agents.volume_agent import VolumeAgent
            agent = VolumeAgent(DB_PATH)
            latest['interpretation'] = agent._interpret(latest['score'])
        
        self.send_json({'symbol': symbol, 'timeframe': timeframe, 'latest': latest, 'history': history, 'bar_count': len(history)})
    
    def handle_delta(self, conn, symbol, timeframe):
        """Get delta data"""
        cursor = conn.execute("""
            SELECT bar_time, score, details FROM agent_scores
            WHERE symbol = ? AND timeframe = ? AND agent_name = 'delta'
            ORDER BY bar_time DESC LIMIT 5000
        """, (symbol, timeframe))
        rows = cursor.fetchall()
        
        history = []
        for row in rows:
            details = json.loads(row[2]) if row[2] else {}
            history.append({
                'bar_time': row[0], 'score': row[1],
                'direction': details.get('direction', 'BALANCED'),
                'delta_value': details.get('delta_value', 0),
                'components': details.get('components', {})
            })
        history.reverse()
        
        latest = history[-1] if history else None
        if latest:
            sys.path.insert(0, '/tmp/trading-desk')
            from agents.delta_agent import DeltaAgent
            agent = DeltaAgent(DB_PATH)
            latest['interpretation'] = agent._interpret(latest['score'], latest.get('delta_value', 0))
        
        self.send_json({'symbol': symbol, 'timeframe': timeframe, 'latest': latest, 'history': history, 'bar_count': len(history)})
    
    def handle_liquidity(self, conn, symbol, timeframe):
        """Get liquidity data"""
        cursor = conn.execute("""
            SELECT bar_time, score, details FROM agent_scores
            WHERE symbol = ? AND timeframe = ? AND agent_name = 'liquidity'
            ORDER BY bar_time DESC LIMIT 5000
        """, (symbol, timeframe))
        rows = cursor.fetchall()
        
        history = []
        for row in rows:
            details = json.loads(row[2]) if row[2] else {}
            history.append({
                'bar_time': row[0], 'score': row[1],
                'direction': details.get('direction', 'NEUTRAL'),
                'components': details.get('components', {})
            })
        history.reverse()
        
        latest = history[-1] if history else None
        if latest:
            sys.path.insert(0, '/tmp/trading-desk')
            from agents.liquidity_agent import LiquidityAgent
            agent = LiquidityAgent(DB_PATH)
            # Get bar data for interpretation
            conn2 = sqlite3.connect(DB_PATH)
            bar = agent._get_bar(conn2, symbol, timeframe, latest['bar_time'])
            prev = agent._get_previous_bars(conn2, symbol, timeframe, latest['bar_time'], 20)
            conn2.close()
            latest['interpretation'] = agent._interpret(latest['score'], bar or {}, prev)
        
        self.send_json({'symbol': symbol, 'timeframe': timeframe, 'latest': latest, 'history': history, 'bar_count': len(history)})
    
    def handle_trend(self, conn, symbol, timeframe):
        """Get trend data"""
        cursor = conn.execute("""
            SELECT bar_time, score, details FROM agent_scores
            WHERE symbol = ? AND timeframe = ? AND agent_name = 'trend'
            ORDER BY bar_time DESC LIMIT 5000
        """, (symbol, timeframe))
        rows = cursor.fetchall()
        
        history = []
        for row in rows:
            details = json.loads(row[2]) if row[2] else {}
            history.append({
                'bar_time': row[0], 'score': row[1],
                'direction': details.get('direction', 'NEUTRAL'),
                'components': details.get('components', {})
            })
        history.reverse()
        
        latest = history[-1] if history else None
        if latest:
            sys.path.insert(0, '/tmp/trading-desk')
            from agents.trend_agent import TrendAgent
            agent = TrendAgent(DB_PATH)
            conn2 = sqlite3.connect(DB_PATH)
            bar = agent._get_bar(conn2, symbol, timeframe, latest['bar_time'])
            prev = agent._get_previous_bars(conn2, symbol, timeframe, latest['bar_time'], 30)
            conn2.close()
            latest['interpretation'] = agent._interpret(latest['score'], bar or {}, prev)
        
        self.send_json({'symbol': symbol, 'timeframe': timeframe, 'latest': latest, 'history': history, 'bar_count': len(history)})
    
    def handle_volume_profile(self, conn, symbol, timeframe):
        """Get volume profile data"""
        cursor = conn.execute("""
            SELECT bar_time, poc, val, vah, vah_poc, val_poc, total_volume, details
            FROM volume_profile WHERE symbol = ? AND timeframe = ?
            ORDER BY bar_time DESC LIMIT 5000
        """, (symbol, timeframe))
        rows = cursor.fetchall()
        
        history = []
        for row in rows:
            details = json.loads(row[7]) if row[7] else {}
            history.append({
                'bar_time': row[0], 'poc': row[1], 'val': row[2], 'vah': row[3],
                'vah_poc': row[4], 'val_poc': row[5], 'total_volume': row[6],
                'interpretation': details.get('interpretation', ''),
                'direction': details.get('direction', 'NEUTRAL')
            })
        history.reverse()
        
        latest = history[-1] if history else None
        self.send_json({'symbol': symbol, 'timeframe': timeframe, 'latest': latest, 'history': history, 'bar_count': len(history)})
    
    def handle_vwap(self, conn, symbol, timeframe):
        """Get VWAP data"""
        cursor = conn.execute("""
            SELECT bar_time, vwap, deviation_points, deviation_pct, direction, details
            FROM vwap_data WHERE symbol = ? AND timeframe = ?
            ORDER BY bar_time DESC LIMIT 5000
        """, (symbol, timeframe))
        rows = cursor.fetchall()
        
        history = []
        for row in rows:
            details = json.loads(row[5]) if row[5] else {}
            history.append({
                'bar_time': row[0], 'vwap': row[1], 'deviation_points': row[2],
                'deviation_pct': row[3], 'direction': row[4],
                'score': details.get('score', 0),
                'interpretation': details.get('interpretation', '')
            })
        history.reverse()
        
        latest = history[-1] if history else None
        self.send_json({'symbol': symbol, 'timeframe': timeframe, 'latest': latest, 'history': history, 'bar_count': len(history)})
    
    def handle_footprint(self, conn, symbol, timeframe):
        """Get footprint analysis"""
        sys.path.insert(0, '/tmp/trading-desk')
        from agents.footprint_agent import FootprintAgent
        agent = FootprintAgent(DB_PATH)
        
        cursor = conn.execute("""
            SELECT DISTINCT bar_time FROM raw_footprint
            WHERE symbol = ? AND timeframe = ?
            ORDER BY bar_time DESC LIMIT 100
        """, (symbol, timeframe))
        bar_times = [row[0] for row in cursor.fetchall()]
        
        history = []
        for bar_time in bar_times:
            result = agent.analyze_footprint(symbol, timeframe, bar_time)
            history.append(result)
        history.reverse()
        
        latest = history[-1] if history else None
        self.send_json({'symbol': symbol, 'timeframe': timeframe, 'latest': latest, 'history': history, 'bar_count': len(history)})
    
    def send_json(self, data):
        """Send JSON response"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

def main():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    with socketserver.TCPServer(("", PORT), OrderflowHandler) as httpd:
        print(f"Orderflow Dashboard running at http://localhost:{PORT}")
        print(f"API at http://localhost:{PORT}/api/exhaustion?symbol=ES&timeframe=5min")
        print("\nPress Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped")

if __name__ == "__main__":
    main()
