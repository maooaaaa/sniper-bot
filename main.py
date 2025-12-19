import feedparser
import requests
import json
import os
import re
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
from time import mktime

# --- 設定エリア ---
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
DATA_FILE = "data.json"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# スナイパー用：濃い情報源リスト
RSS_URLS = [
    # はてなブックマーク（祭り検知用）
    "https://b.hatena.ne.jp/entrylist/it.rss",
    "https://b.hatena.ne.jp/entrylist/life.rss",
    # Apple・ガジェット
    "https://gori.me/feed",
    "https://iphone-mania.jp/feed/",
    # ゲーム無料・PC特価
    "https://automaton-media.com/feed/",
    "https://b2b.hack.ne.jp/feed",
]

# カテゴリ定義
CATEGORIES = [
    {
        "name": "🚨 緊急：価格設定ミス・バグ疑惑",
        "keywords": ["価格崩壊", "設定ミス", "表記ミス", "価格ミス", "0円設定", "桁間違い", "90%OFF", "99%OFF"],
        "color": 0xFF0000,
        "priority": True 
    },
    {
        "name": "🍎 Apple整備済・復活",
        "keywords": ["整備済", "MacBook", "iPad", "認定整備", "再入荷", "在庫復活"],
        "color": 0xFFFFFF,
        "priority": False
    },
    {
        "name": "🎮 ゲーム・ソフト 100%OFF",
        "keywords": ["無料配布", "期間限定無料", "100%OFF", "タダ", "プレゼント", "配布開始"],
        "color": 0x00FF00,
        "priority": False
    },
    {
        "name": "💰 その他 激アツ案件",
        "keywords": ["キャッシュバック", "全員", "神案件", "バラマキ", "利益"],
        "color": 0xFFA500,
        "priority": False
    }
]

def load_sent_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: return []
    return []

def save_sent_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data[-300:], f, ensure_ascii=False, indent=2)

def is_within_24h(entry):
    if not hasattr(entry, 'published_parsed'): return True
    published_time = datetime.fromtimestamp(mktime(entry.published_parsed))
    return (datetime.now() - published_time) < timedelta(hours=24)

def extract_code_simple(text):
    pattern = r'(?:コード|クーポン)[:：]\s*([a-zA-Z0-9\-_]{4,20})'
    match = re.search(pattern, text)
    if match:
        code = match.group(1)
        if not re.search(r'(202[0-9]|http)', code):
            return code
    return None

def send_discord(category, title, link, code, source_name):
    content_text = ""
    if category["priority"]:
        content_text = "@everyone 🚨 **緊急速報！価格ミスの可能性があります！**"

    description = f"**{title}**\n\n"
    if code: description += f"🎫 クーポンコード:\n```{code}```\n"
    else: description += "🔗 **コード不要またはリンク先で確認**\n"
    description += f"\n[👉 商品ページ・詳細を見る]({link})"

    embed = {
        "title": category["name"],
        "description": description,
        "url": link,
        "color": category["color"],
        "footer": {"text": f"Source: {source_name}"}
    }

    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"username": "Sniper Bot", "content": content_text, "embeds": [embed]})
        time.sleep(2)
    except Exception as e:
        print(f"Error: {e}")

def main():
    if not DISCORD_WEBHOOK_URL: return
    sent_urls = load_sent_data()
    new_sent_urls = sent_urls.copy()
    print("Sniping targets...")

    for rss_url in RSS_URLS:
        try:
            resp = requests.get(rss_url, headers=HEADERS, timeout=10)
            feed = feedparser.parse(resp.content)
            source_name = feed.feed.title if 'title' in feed.feed else "Web"

            for entry in feed.entries[:5]:
                link = entry.link
                title = entry.title
                if link in sent_urls: continue
                if not is_within_24h(entry): continue

                matched_category = None
                for cat in CATEGORIES:
                    text_to_check = title
                    if 'summary' in entry: text_to_check += entry.summary
                    if any(k in text_to_check for k in cat["keywords"]):
                        matched_category = cat
                        break 
                
                if matched_category:
                    print(f"🎯 HIT [{matched_category['name']}]: {title}")
                    description = entry.summary if 'summary' in entry else ""
                    code = extract_code_simple(BeautifulSoup(description, "html.parser").get_text())
                    send_discord(matched_category, title, link, code, source_name)
                    new_sent_urls.append(link)

        except Exception as e:
            print(f"Error checking {rss_url}: {e}")
            continue

    save_sent_data(new_sent_urls)
    print("Mission Complete.")

if __name__ == "__main__":
    main()
