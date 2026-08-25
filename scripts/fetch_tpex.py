"""
每日抓取 TPEx 上櫃資料，存成靜態 JSON 供 checklist/index.html 直接讀取
"""
import requests
import json
import os

headers = {"User-Agent": "Mozilla/5.0"}
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "checklist")

def fetch(url):
    r = requests.get(url, headers=headers, timeout=20)
    return r.json()

def save(filename, data):
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"Saved {path}")

if __name__ == "__main__":
    save("tpex_disposal.json", fetch("https://www.tpex.org.tw/www/zh-tw/bulletin/disposal"))
    save("tpex_notice.json",   fetch("https://www.tpex.org.tw/www/zh-tw/bulletin/attention"))
    save("tpex_margin.json",   fetch("https://www.tpex.org.tw/www/zh-tw/margin/balance"))
    print("TPEx data update complete.")
