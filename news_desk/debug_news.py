#!/usr/bin/env python3
import requests
import xml.etree.ElementTree as ET
import os
import json
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/generate"
WATCHLIST_DIR = "/tmp/trading-desk/data/watchlists"
NEWS_DIR = "/tmp/trading-desk/news_desk"

FEEDS = {
    "ForexLive": "https://www.forexlive.com/feed/news",
    "Investing.com": "https://www.investing.com/rss/news.rss", 
    "MarketWatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
}

def parse_rss(url, timeout=15):
    try:
        response = requests.get(url, timeout=timeout, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            items = []
            for item in root.findall('.//item')[:10]:
                title = item.findtext('title', '')
                link = item.findtext('link', '')
                pub_date = item.findtext('pubDate', '')
                desc = item.findtext('description', '')
                items.append({
                    'title': title,
                    'link': link,
                    'pubDate': pub_date,
                    'description': desc[:200] if desc else ''
                })
            return items
    except Exception as e:
        print(f"DEBUG parse_rss error: {e}", file=__import__('sys').stderr)
    return []

# Load instruments
instruments = set()
for session in ['asian', 'london', 'ny']:
    path = f"{WATCHLIST_DIR}/{session}_session.txt"
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    instruments.add(line.split()[0])

print(f"DEBUG instruments: {instruments}", file=__import__('sys').stderr)

# Fetch all news
all_articles = []
seen = set()

for source, url in FEEDS.items():
    print(f"DEBUG fetching {source}...", file=__import__('sys').stderr)
    articles = parse_rss(url)
    print(f"DEBUG got {len(articles)} from {source}", file=__import__('sys').stderr)
    for article in articles:
        if article['title'] not in seen:
            seen.add(article['title'])
            article['source'] = source
            all_articles.append(article)

print(f"DEBUG total articles: {len(all_articles)}", file=__import__('sys').stderr)

# Print first 3
for a in all_articles[:3]:
    print(f"DEBUG article: {a['title'][:60]}", file=__import__('sys').stderr)
