#!/usr/bin/env python3
"""
Economic Calendar Dashboard
Static template with manual event entry + Telegram delivery
For automated live data, use the forex_factory scraper with proper headers
"""

import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

CENTRAL_TZ = ZoneInfo("America/Chicago")
OUTPUT_DIR = os.path.expanduser("~/.hermes/cron/output")
EVENTS_FILE = os.path.expanduser("~/.hermes/cron/data/economic_events.json")
HTML_OUTPUT = f"{OUTPUT_DIR}/economic_dashboard.html"
MD_OUTPUT = f"{OUTPUT_DIR}/economic_dashboard.md"

def get_central_time():
    return datetime.now(CENTRAL_TZ)

def get_us_sessions():
    """Determine active trading sessions"""
    now = get_central_time()
    hour = now.hour
    
    sessions = {
        "asian": {"active": False, "status": "CLOSED"},
        "london": {"active": False, "status": "CLOSED"}, 
        "ny": {"active": False, "status": "CLOSED"}
    }
    
    # Asian: 5pm CT - 2am CT
    if hour >= 17 or hour < 2:
        sessions["asian"]["active"] = True
        sessions["asian"]["status"] = "ACTIVE"
    
    # London: 2am CT - 11am CT  
    if hour >= 2 and hour < 11:
        sessions["london"]["active"] = True
        sessions["london"]["status"] = "ACTIVE"
    
    # NY: 7:30am CT - 4pm CT
    if hour >= 7 and hour < 16:
        sessions["ny"]["active"] = True
        sessions["ny"]["status"] = "ACTIVE"
    
    return sessions

def load_events():
    """Load events from JSON file"""
    if os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE, 'r') as f:
            return json.load(f).get("events", [])
    return []

def save_events(events):
    """Save events to JSON file"""
    os.makedirs(os.path.dirname(EVENTS_FILE), exist_ok=True)
    with open(EVENTS_FILE, 'w') as f:
        json.dump({"events": events}, f, indent=2)

def get_default_events():
    """Return common recurring events for the week"""
    now = get_central_time()
    events = []
    
    # Common high impact events (user should verify actual times)
    common_events = [
        {"day": "monday", "time": "08:30", "currency": "USD", "event": "NY Empire State Manufacturing Index", "impact": "medium"},
        {"day": "tuesday", "time": "08:30", "currency": "USD", "event": "Retail Sales", "impact": "high"},
        {"day": "wednesday", "time": "07:00", "currency": "USD", "event": "MBA Mortgage Applications", "impact": "low"},
        {"day": "wednesday", "time": "08:30", "currency": "USD", "event": "CPI", "impact": "high"},
        {"day": "wednesday", "time": "10:00", "currency": "USD", "event": "Fed Chair Powell Speaks", "impact": "high"},
        {"day": "thursday", "time": "08:30", "currency": "USD", "event": "Philly Fed Manufacturing Index", "impact": "medium"},
        {"day": "thursday", "time": "08:30", "currency": "USD", "event": "Jobless Claims", "impact": "medium"},
        {"day": "friday", "time": "08:30", "currency": "USD", "event": "Non-Farm Payrolls (NFP)", "impact": "high"},
        {"day": "friday", "time": "08:30", "currency": "USD", "event": "Unemployment Rate", "impact": "high"},
    ]
    
    # Filter to current day and add actual/forecast
    current_day = now.strftime("%A").lower()
    
    for ev in common_events:
        if ev["day"] == current_day:
            events.append({
                "date": now.strftime("%b %d"),
                "time": ev["time"],
                "currency": ev["currency"],
                "event": ev["event"],
                "impact": ev["impact"],
                "previous": "--",
                "forecast": "--",
                "actual": "--"
            })
    
    return events

def add_event(time, currency, event, impact, previous="--", forecast="--", actual="--"):
    """Add a new event"""
    events = load_events()
    now = get_central_time()
    
    events.append({
        "date": now.strftime("%b %d"),
        "time": time,
        "currency": currency,
        "event": event,
        "impact": impact,
        "previous": previous,
        "forecast": forecast,
        "actual": actual
    })
    
    save_events(events)
    return events

def generate_html(events=None, next_high=None):
    """Generate HTML dashboard"""
    if events is None:
        events = get_default_events()
    
    now = get_central_time()
    sessions = get_us_sessions()
    
    # Find next high impact
    if next_high is None:
        for ev in events:
            if ev.get("impact") == "high":
                next_high = ev
                break
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Economic Calendar Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 25px;
            padding-bottom: 15px;
            border-bottom: 1px solid #333;
        }}
        .header h1 {{
            color: #00d4ff;
            font-size: 24px;
            letter-spacing: 1px;
        }}
        .header .time {{
            color: #888;
            font-size: 14px;
            text-align: right;
        }}
        .header .time span {{
            display: block;
            color: #00ff88;
            font-size: 18px;
            font-weight: bold;
        }}
        .sessions {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-bottom: 25px;
        }}
        .session {{
            background: #12121a;
            border: 1px solid #222;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            transition: all 0.3s ease;
        }}
        .session.active {{
            border-color: #00ff88;
            box-shadow: 0 0 20px rgba(0, 255, 136, 0.1);
        }}
        .session.closed {{
            opacity: 0.5;
        }}
        .session h3 {{
            color: #666;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 8px;
        }}
        .session .status {{
            font-size: 16px;
            font-weight: bold;
        }}
        .session.active .status {{
            color: #00ff88;
        }}
        .session.closed .status {{
            color: #ff4444;
        }}
        .session .hours {{
            color: #555;
            font-size: 11px;
            margin-top: 5px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 20px;
        }}
        .panel {{
            background: #12121a;
            border: 1px solid #222;
            border-radius: 10px;
            padding: 20px;
        }}
        .panel h2 {{
            color: #00d4ff;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #222;
        }}
        .next-event {{
            background: linear-gradient(135deg, #1a0a0a 0%, #2a1515 100%);
            border-left: 4px solid #ff4444;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 15px;
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
            font-weight: bold;
        }}
        .next-event .event-meta {{
            display: flex;
            gap: 20px;
            margin-top: 10px;
        }}
        .next-event .event-meta div {{
            color: #888;
            font-size: 12px;
        }}
        .next-event .event-meta span {{
            color: #00d4ff;
            font-weight: bold;
        }}
        .no-events {{
            color: #888;
            text-align: center;
            padding: 40px;
            font-style: italic;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th {{
            text-align: left;
            padding: 12px 8px;
            color: #666;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
            border-bottom: 1px solid #222;
        }}
        td {{
            padding: 14px 8px;
            border-bottom: 1px solid #1a1a25;
            font-size: 13px;
        }}
        tr:hover {{
            background: #1a1a25;
        }}
        .impact-high {{ color: #ff4444; font-weight: bold; }}
        .impact-medium {{ color: #ffaa00; }}
        .impact-low {{ color: #44bb44; }}
        .impact-dot {{
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 6px;
        }}
        .impact-dot.high {{ background: #ff4444; }}
        .impact-dot.medium {{ background: #ffaa00; }}
        .impact-dot.low {{ background: #44bb44; }}
        .currency {{
            color: #00d4ff;
            font-weight: bold;
        }}
        .actual-released {{
            color: #00ff88;
            font-weight: bold;
        }}
        .rules {{
            margin-top: 20px;
        }}
        .rules li {{
            color: #888;
            font-size: 12px;
            line-height: 2;
            padding-left: 5px;
        }}
        .rules li::marker {{
            color: #00d4ff;
        }}
        .add-form {{
            background: #1a1a25;
            border-radius: 8px;
            padding: 15px;
            margin-top: 15px;
        }}
        .add-form h3 {{
            color: #888;
            font-size: 11px;
            text-transform: uppercase;
            margin-bottom: 10px;
        }}
        .add-form input, .add-form select {{
            width: 100%;
            padding: 8px;
            margin-bottom: 8px;
            background: #0a0a0f;
            border: 1px solid #333;
            border-radius: 4px;
            color: #fff;
            font-size: 12px;
        }}
        .add-form button {{
            width: 100%;
            padding: 10px;
            background: #00d4ff;
            border: none;
            border-radius: 4px;
            color: #000;
            font-weight: bold;
            cursor: pointer;
        }}
        .add-form button:hover {{
            background: #00ff88;
        }}
        @media (max-width: 900px) {{
            .grid {{ grid-template-columns: 1fr; }}
            .sessions {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Economic Calendar</h1>
        <div class="time">
            {now.strftime('%A, %B %d, %Y')}
            <span>{now.strftime('%I:%M %p')} CT</span>
        </div>
    </div>
    
    <div class="sessions">
        <div class="session {'active' if sessions['asian']['active'] else 'closed'}">
            <h3>Asian</h3>
            <div class="status">{sessions['asian']['status']}</div>
            <div class="hours">5:00 PM - 2:00 AM CT</div>
        </div>
        <div class="session {'active' if sessions['london']['active'] else 'closed'}">
            <h3>London</h3>
            <div class="status">{sessions['london']['status']}</div>
            <div class="hours">2:00 AM - 11:00 AM CT</div>
        </div>
        <div class="session {'active' if sessions['ny']['active'] else 'closed'}">
            <h3>New York</h3>
            <div class="status">{sessions['ny']['status']}</div>
            <div class="hours">7:30 AM - 4:00 PM CT</div>
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
                    <div class="event-meta">
                        <div>Time: <span>{next_high.get('time', '--')}</span></div>
                        <div>Currency: <span>{next_high.get('currency', '--')}</span></div>
                    </div>
                    <div class="event-meta">
                        <div>Previous: <span>{next_high.get('previous', '--')}</span></div>
                        <div>Forecast: <span>{next_high.get('forecast', '--')}</span></div>
                    </div>
                </div>
"""
    else:
        html += """
                <div class="no-events">No high impact events today</div>
"""
    
    html += """
                <h2 style="margin-top: 20px;">Trading Rules</h2>
                <ul class="rules">
                    <li>Avoid trading 15min before/after 🔴 HIGH impact events</li>
                    <li>Wait for confirmation after events</li>
                    <li>Watch for fake outs around major events</li>
                    <li>Check actual vs forecast for directional bias</li>
                    <li>Reduce position size during volatile periods</li>
                </ul>
                
                <div class="add-form">
                    <h3>Add Event</h3>
                    <form action="/add-event" method="post">
                        <input type="text" name="time" placeholder="Time (HH:MM)" value="08:30">
                        <select name="currency">
                            <option value="USD">USD</option>
                            <option value="EUR">EUR</option>
                            <option value="GBP">GBP</option>
                            <option value="JPY">JPY</option>
                            <option value="AUD">AUD</option>
                            <option value="CAD">CAD</option>
                            <option value="CHF">CHF</option>
                        </select>
                        <input type="text" name="event" placeholder="Event Name">
                        <select name="impact">
                            <option value="high">🔴 High</option>
                            <option value="medium">🟡 Medium</option>
                            <option value="low">🟢 Low</option>
                        </select>
                        <input type="text" name="previous" placeholder="Previous">
                        <input type="text" name="forecast" placeholder="Forecast">
                        <button type="submit">Add Event</button>
                    </form>
                </div>
            </div>
        </div>
        
        <div class="right">
            <div class="panel">
                <h2>Today's Events</h2>
"""
    
    if events:
        html += """<table>
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
        for ev in events:
            impact_class = f"impact-{ev.get('impact', 'low')}"
            actual_class = "actual-released" if ev.get('actual') and ev.get('actual') != "--" else ""
            html += f"""<tr>
                            <td>{ev.get('time', '--')}</td>
                            <td class="currency">{ev.get('currency', '--')}</td>
                            <td>{ev.get('event', '--')}</td>
                            <td class="{impact_class}">
                                <span class="impact-dot {ev.get('impact', 'low')}"></span>
                                {ev.get('impact', 'low').upper()}
                            </td>
                            <td>{ev.get('previous', '--')}</td>
                            <td>{ev.get('forecast', '--')}</td>
                            <td class="{actual_class}">{ev.get('actual', '--')}</td>
                        </tr>
"""
        html += "</tbody></table>"
    else:
        html += '<div class="no-events">No events for today.<br>Add events using the form.</div>'
    
    html += """
            </div>
        </div>
    </div>
</body>
</html>
"""
    
    return html

def generate_markdown(events=None, next_high=None):
    """Generate Markdown for Obsidian"""
    if events is None:
        events = get_default_events()
    
    now = get_central_time()
    sessions = get_us_sessions()
    
    if next_high is None:
        for ev in events:
            if ev.get("impact") == "high":
                next_high = ev
                break
    
    md = f"""# Economic Calendar Dashboard

**Updated:** {now.strftime('%A, %B %d, %Y %I:%M %p CT')}

---

## Trading Sessions

| Session | Status | Hours |
|---------|--------|-------|
| Asian | {'🟢 ACTIVE' if sessions['asian']['active'] else '🔴 CLOSED'} | 5:00 PM - 2:00 AM CT |
| London | {'🟢 ACTIVE' if sessions['london']['active'] else '🔴 CLOSED'} | 2:00 AM - 11:00 AM CT |
| New York | {'🟢 ACTIVE' if sessions['ny']['active'] else '🔴 CLOSED'} | 7:30 AM - 4:00 PM CT |

---

## Next High Impact Event
"""
    
    if next_high:
        md += f"""
**{next_high.get('event', '')}**

- **Date:** {next_high.get('date', '')}
- **Time:** {next_high.get('time', '')} CT
- **Currency:** {next_high.get('currency', '')}
- **Impact:** 🔴 HIGH
- **Previous:** {next_high.get('previous', '--')}
- **Forecast:** {next_high.get('forecast', '--')}
- **Actual:** {next_high.get('actual', '--')}

"""
    else:
        md += "\nNo high impact events today.\n\n"
    
    md += """---

## Today's Economic Calendar

| Time | Currency | Event | Impact | Previous | Forecast | Actual |
|------|----------|-------|--------|---------|---------|--------|
"""
    
    for ev in events:
        impact_icon = "🔴" if ev.get('impact') == 'high' else ("🟡" if ev.get('impact') == 'medium' else "🟢")
        md += f"| {ev.get('time', '--')} | {ev.get('currency', '--')} | {ev.get('event', '--')} | {impact_icon} | {ev.get('previous', '--')} | {ev.get('forecast', '--')} | {ev.get('actual', '--')} |\n"
    
    md += """

---

## Trading Rules

- ⏱️ Avoid trading 15 minutes before/after HIGH impact events
- ✅ Wait for candle confirmation after events
- 👀 Watch for fake outs around NFP, FOMC, CPI
- 📊 Actual > Forecast = currency strengthens
- 📊 Actual < Forecast = currency weakens

---

*Dashboard auto-generated by Athena*
"""
    
    return md

def main():
    """Main function"""
    events = load_events()
    
    # If no events loaded, use defaults
    if not events:
        events = get_default_events()
    
    # Find next high impact
    next_high = None
    for ev in events:
        if ev.get("impact") == "high":
            next_high = ev
            break
    
    # Generate outputs
    html = generate_html(events, next_high)
    md = generate_markdown(events, next_high)
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    with open(HTML_OUTPUT, 'w') as f:
        f.write(html)
    
    with open(MD_OUTPUT, 'w') as f:
        f.write(md)
    
    print(f"✅ Dashboard generated")
    print(f"   Events: {len(events)}")
    if next_high:
        print(f"   Next High: {next_high.get('event')} at {next_high.get('time')}")

if __name__ == "__main__":
    main()
