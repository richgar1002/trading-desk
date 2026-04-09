#!/usr/bin/env python3
"""
Economic Calendar Dashboard
Pulls live data from Forex Factory and generates HTML + MD dashboards
"""

import requests
from datetime import datetime, timezone
import time
import json
import os

# Try to import bs4, install if missing
try:
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess
    subprocess.run(['pip', 'install', 'beautifulsoup4', '-q'])
    from bs4 import BeautifulSoup

# Timezone conversion
from zoneinfo import ZoneInfo

# Config
CENTRAL_TZ = ZoneInfo("America/Chicago")
UTC_TZ = ZoneInfo("UTC")
FOREX_FACTORY_URL = "https://www.forexfactory.com/calendar"
OUTPUT_DIR = os.path.expanduser("~/.hermes/cron/output")
HTML_OUTPUT = f"{OUTPUT_DIR}/economic_dashboard.html"
MD_OUTPUT = f"{OUTPUT_DIR}/economic_dashboard.md"

# Impact levels
IMPACT_COLORS = {
    "high": "#ff4444",
    "medium": "#ffaa00", 
    "low": "#44bb44"
}

def get_central_time():
    return datetime.now(CENTRAL_TZ)

def fetch_forex_factory_calendar():
    """Fetch economic calendar from Forex Factory"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(FOREX_FACTORY_URL, headers=headers, timeout=30)
        response.raise_for_status()
        return parse_calendar_html(response.text)
    except Exception as e:
        return {"error": str(e), "events": []}

def parse_calendar_html(html):
    """Parse Forex Factory calendar HTML"""
    soup = BeautifulSoup(html, 'html.parser')
    events = []
    
    # Find calendar table
    tables = soup.find_all('table', class_='calendar__table')
    
    if not tables:
        return {"error": "Could not find calendar table", "events": []}
    
    current_date = None
    
    for table in tables:
        rows = table.find_all('tr', class_='calendar__row')
        
        for row in rows:
            # Date detection
            date_cell = row.find('td', class_='calendar__date')
            if date_cell:
                date_span = date_cell.find('span', class_='date')
                if date_span:
                    date_text = date_span.get_text(strip=True)
                    if date_text:
                        current_date = date_text
            
            # Skip if no date
            if not current_date:
                continue
                
            # Parse event details
            try:
                cells = row.find_all('td')
                
                # Impact
                impact_cell = row.find('td', class_='calendar__impact')
                impact = "low"
                if impact_cell:
                    if impact_cell.find('span', class_='impact--high'):
                        impact = "high"
                    elif impact_cell.find('span', class_='impact--medium'):
                        impact = "medium"
                
                # Time
                time_cell = row.find('td', class_='calendar__time')
                time_text = ""
                if time_cell:
                    time_span = time_cell.find('span')
                    if time_span:
                        time_text = time_span.get_text(strip=True)
                
                # Currency
                currency_cell = row.find('td', class_='calendar__currency')
                currency = ""
                if currency_cell:
                    currency = currency_cell.get_text(strip=True)
                
                # Event name
                event_cell = row.find('td', class_='calendar__event')
                event_name = ""
                if event_cell:
                    event_span = event_cell.find('span', class_='title')
                    if event_span:
                        event_name = event_span.get_text(strip=True)
                
                # Previous
                previous_cell = row.find('td', class_='calendar__previous')
                previous = ""
                if previous_cell:
                    previous = previous_cell.get_text(strip=True)
                
                # Forecast
                forecast_cell = row.find('td', class_='calendar__forecast')
                forecast = ""
                if forecast_cell:
                    forecast = forecast_cell.get_text(strip=True)
                
                # Actual
                actual_cell = row.find('td', class_='calendar__actual')
                actual = ""
                if actual_cell:
                    actual = actual_cell.get_text(strip=True)
                
                if event_name:
                    events.append({
                        "date": current_date,
                        "time": time_text,
                        "currency": currency,
                        "event": event_name,
                        "impact": impact,
                        "previous": previous,
                        "forecast": forecast,
                        "actual": actual
                    })
                    
            except Exception as e:
                continue
    
    return {"events": events}

def get_next_high_impact(events):
    """Find next high impact event"""
    now = get_central_time()
    current_time_str = now.strftime("%H:%M")
    
    for event in events:
        if event.get("impact") == "high":
            event_time = event.get("time", "")
            if event_time and event_time != "":
                return event
    return None

def generate_html(events, next_high=None):
    """Generate HTML dashboard"""
    now = get_central_time()
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trading Dashboard - Economic Calendar</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a0f;
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid #333;
        }}
        .header h1 {{
            color: #00d4ff;
            font-size: 24px;
        }}
        .header .time {{
            color: #888;
            font-size: 14px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 20px;
        }}
        .panel {{
            background: #12121a;
            border-radius: 10px;
            padding: 20px;
            border: 1px solid #222;
        }}
        .panel h2 {{
            color: #00d4ff;
            font-size: 16px;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .sessions {{
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
        }}
        .session {{
            flex: 1;
            padding: 15px;
            background: #1a1a25;
            border-radius: 8px;
            text-align: center;
        }}
        .session .label {{
            color: #666;
            font-size: 11px;
            text-transform: uppercase;
        }}
        .session .status {{
            font-size: 14px;
            margin-top: 5px;
            color: #888;
        }}
        .session.active .status {{
            color: #00ff88;
        }}
        .session.closed .status {{
            color: #ff4444;
        }}
        .next-event {{
            background: linear-gradient(135deg, #1a1a25 0%, #252535 100%);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            border-left: 4px solid #ff4444;
        }}
        .next-event .label {{
            color: #888;
            font-size: 11px;
            text-transform: uppercase;
        }}
        .next-event .event-name {{
            color: #fff;
            font-size: 18px;
            margin: 10px 0;
        }}
        .next-event .event-time {{
            color: #00d4ff;
            font-size: 24px;
            font-weight: bold;
        }}
        .next-event .countdown {{
            color: #888;
            font-size: 12px;
            margin-top: 5px;
        }}
        .countdown-box {{
            display: inline-block;
            background: #ff4444;
            color: #fff;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 12px;
            margin-left: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th {{
            text-align: left;
            padding: 10px;
            color: #666;
            font-size: 11px;
            text-transform: uppercase;
            border-bottom: 1px solid #333;
        }}
        td {{
            padding: 12px 10px;
            border-bottom: 1px solid #1a1a25;
            font-size: 13px;
        }}
        tr:hover {{
            background: #1a1a25;
        }}
        .impact-high {{
            color: #ff4444;
            font-weight: bold;
        }}
        .impact-medium {{
            color: #ffaa00;
        }}
        .impact-low {{
            color: #44bb44;
        }}
        .impact-dot {{
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 5px;
        }}
        .impact-dot.high {{ background: #ff4444; }}
        .impact-dot.medium {{ background: #ffaa00; }}
        .impact-dot.low {{ background: #44bb44; }}
        .actual {{
            color: #00d4ff;
        }}
        .previous {{
            color: #888;
        }}
        .forecast {{
            color: #ffaa00;
        }}
        @media (max-width: 768px) {{
            .grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Trading Dashboard</h1>
        <div class="time">{now.strftime('%A, %B %d, %Y %I:%M %p CT')}</div>
    </div>
    
    <div class="sessions">
        <div class="session {'active' if 17 <= now.hour < 24 or now.hour < 0 else 'closed'}">
            <div class="label">Asian</div>
            <div class="status">{'ACTIVE' if 17 <= now.hour < 24 or now.hour < 0 else 'CLOSED'}</div>
        </div>
        <div class="session {'active' if 2 <= now.hour < 8 else 'closed'}">
            <div class="label">London</div>
            <div class="status">{'ACTIVE' if 2 <= now.hour < 8 else 'CLOSED'}</div>
        </div>
        <div class="session {'active' if 7 <= now.hour < 17 else 'closed'}">
            <div class="label">New York</div>
            <div class="status">{'ACTIVE' if 7 <= now.hour < 17 else 'CLOSED'}</div>
        </div>
    </div>
    
    <div class="grid">
        <div class="left">
            <div class="panel">
                <h2>Next High Impact</h2>
"""
    
    if next_high:
        html += f"""
                <div class="next-event">
                    <div class="label">{next_high.get('date', '')}</div>
                    <div class="event-name">{next_high.get('event', '')}</div>
                    <div class="event-time">{next_high.get('time', '')} CT</div>
                    <div class="label">{next_high.get('currency', '')}</div>
                </div>
"""
    else:
        html += """
                <div class="next-event">
                    <div class="event-name">No high impact events today</div>
                </div>
"""
    
    html += """
            </div>
            
            <div class="panel" style="margin-top: 20px;">
                <h2>Trading Rules</h2>
                <ul style="color: #888; font-size: 12px; line-height: 1.8; padding-left: 20px;">
                    <li>Avoid trading 30min before/after high impact</li>
                    <li>Wait for confirmation after events</li>
                    <li>Watch for fake outs around events</li>
                    <li>Check actual vs forecast for direction</li>
                </ul>
            </div>
        </div>
        
        <div class="right">
            <div class="panel">
                <h2>Today's Economic Calendar</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Currency</th>
                            <th>Event</th>
                            <th>Impact</th>
                            <th>Previous</th>
                            <th>Forecast</th>
                            <th>Actual</th>
                        </tr>
                    </thead>
                    <tbody>
"""
    
    for event in events[:30]:  # Limit to 30 events
        impact_class = f"impact-{event.get('impact', 'low')}"
        html += f"""
                        <tr>
                            <td>{event.get('time', '--')}</td>
                            <td>{event.get('currency', '--')}</td>
                            <td>{event.get('event', '--')}</td>
                            <td class="{impact_class}">
                                <span class="impact-dot {event.get('impact', 'low')}"></span>
                                {event.get('impact', 'low').upper()}
                            </td>
                            <td class="previous">{event.get('previous', '--')}</td>
                            <td class="forecast">{event.get('forecast', '--')}</td>
                            <td class="actual">{event.get('actual', '--')}</td>
                        </tr>
"""
    
    html += """
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""
    
    return html

def generate_markdown(events, next_high=None):
    """Generate Markdown for Obsidian"""
    now = get_central_time()
    
    md = f"""# Trading Dashboard

**Last Updated:** {now.strftime('%A, %B %d, %Y %I:%M %p CT')}

---

## Sessions

| Session | Status |
|---------|--------|
| Asian | {'ACTIVE' if 17 <= now.hour < 24 or now.hour < 0 else 'CLOSED'} |
| London | {'ACTIVE' if 2 <= now.hour < 8 else 'CLOSED'} |
| New York | {'ACTIVE' if 7 <= now.hour < 17 else 'CLOSED'} |

---

## Next High Impact Event

"""
    
    if next_high:
        md += f"""**{next_high.get('date', '')} at {next_high.get('time', '')} CT**

- **Event:** {next_high.get('event', '')}
- **Currency:** {next_high.get('currency', '')}
- **Impact:** 🔴 HIGH
- **Previous:** {next_high.get('previous', '--')}
- **Forecast:** {next_high.get('forecast', '--')}
- **Actual:** {next_high.get('actual', '--')}

---
"""
    else:
        md += "No high impact events today.\n\n---\n"
    
    md += """## Today's Economic Calendar

| Time | Currency | Event | Impact | Previous | Forecast | Actual |
|------|----------|-------|--------|---------|---------|--------|
"""
    
    for event in events[:30]:
        impact_icon = "🔴" if event.get('impact') == 'high' else ("🟡" if event.get('impact') == 'medium' else "🟢")
        md += f"| {event.get('time', '--')} | {event.get('currency', '--')} | {event.get('event', '--')} | {impact_icon} | {event.get('previous', '--')} | {event.get('forecast', '--')} | {event.get('actual', '--')} |\n"
    
    md += """

---

## Trading Rules

- ⏱️ Avoid trading 30 minutes before/after high impact events
- ✅ Wait for confirmation after events
- 👀 Watch for fake outs around major events
- 📊 Check actual vs forecast for directional bias

*Dashboard auto-generated by Athena*
"""
    
    return md

def main():
    """Main function"""
    print("Fetching economic calendar...")
    
    # Fetch data
    data = fetch_forex_factory_calendar()
    
    if "error" in data:
        print(f"Error: {data['error']}")
        # Generate error output
        error_html = f"""<!DOCTYPE html>
<html><body style="background:#0a0a0f;color:#fff;padding:40px;font-family:sans-serif;">
<h1 style="color:#ff4444;">Error Loading Calendar</h1>
<p>{data['error']}</p>
<p>Last attempted: {datetime.now(CENTRAL_TZ)}</p>
</body></html>"""
        
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(HTML_OUTPUT, 'w') as f:
            f.write(error_html)
        return
    
    events = data.get("events", [])
    next_high = get_next_high_impact(events)
    
    # Generate outputs
    html = generate_html(events, next_high)
    md = generate_markdown(events, next_high)
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    with open(HTML_OUTPUT, 'w') as f:
        f.write(html)
    
    with open(MD_OUTPUT, 'w') as f:
        f.write(md)
    
    print(f"✅ Dashboard updated")
    print(f"   HTML: {HTML_OUTPUT}")
    print(f"   MD: {MD_OUTPUT}")
    print(f"   Events: {len(events)}")
    if next_high:
        print(f"   Next High Impact: {next_high.get('event')} at {next_high.get('time')}")

if __name__ == "__main__":
    main()
