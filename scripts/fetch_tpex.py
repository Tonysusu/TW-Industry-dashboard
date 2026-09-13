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
    # 上櫃股票除權除息預告表（官方 OpenAPI，找到於 2026-09-13，取代原本查無資料的舊嘗試）
    save("tpex_exright.json", fetch("https://www.tpex.org.tw/openapi/v1/tpex_exright_prepost"))
    print("TPEx data update complete.")
