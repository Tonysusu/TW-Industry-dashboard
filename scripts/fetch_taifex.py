"""
每日抓取 TAIFEX（期交所）股票期貨清單與公告，存成靜態 JSON 供 checklist/index.html 直接讀取。

原本這兩項是瀏覽器端即時透過 corsproxy.io 代理抓取，代理不穩定常常查詢失敗。
CORS 是瀏覽器才有的限制，伺服器對伺服器（這支腳本跑在 GitHub Actions）不受影響，
所以改成這裡直接抓、存成靜態 JSON，不再需要 corsproxy.io。
"""
import requests
import re
import json
import os
from html.parser import HTMLParser

headers = {"User-Agent": "Mozilla/5.0"}
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "checklist")


def save(filename, data):
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"Saved {path}")


def fetch_futures_codes():
    r = requests.get("https://www.taifex.com.tw/cht/2/stockLists", headers=headers, timeout=20)
    return sorted(set(re.findall(r"\b([0-9]{4,5})\b", r.text)))


class TableExtractor(HTMLParser):
    """簡單的 comment-safe 表格抽取器（stdlib，不需額外裝 bs4）"""
    def __init__(self):
        super().__init__()
        self.tables = []
        self.cur_table = None
        self.cur_row = None
        self.cur_cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.cur_table = []
            self.tables.append(self.cur_table)
        elif tag == "tr" and self.cur_table is not None:
            self.cur_row = []
            self.cur_table.append(self.cur_row)
        elif tag == "td" and self.cur_row is not None:
            self.cur_cell = []
            self.cur_row.append(self.cur_cell)

    def handle_data(self, data):
        if self.cur_cell is not None and self.cur_row and self.cur_cell is self.cur_row[-1]:
            self.cur_cell.append(data)

    def handle_endtag(self, tag):
        if tag == "td":
            self.cur_cell = None
        elif tag == "tr":
            self.cur_row = None
        elif tag == "table":
            self.cur_table = None


def fetch_announcements():
    r = requests.get("https://www.taifex.com.tw/cht/11/announcement", headers=headers, timeout=20)
    parser = TableExtractor()
    parser.feed(r.text)
    if not parser.tables:
        return []
    # 公告表是頁面裡列數最多的那張表（其餘是查詢用的小表格）
    main_table = max(parser.tables, key=len)
    rows = []
    for tr in main_table:
        if len(tr) < 2:
            continue
        date = "".join(tr[0]).strip()
        title = "".join(tr[1]).strip()
        if date and title:
            rows.append({"date": date, "title": title})
    return rows


if __name__ == "__main__":
    save("taifex_futures_codes.json", fetch_futures_codes())
    save("taifex_announcements.json", fetch_announcements())
    print("TAIFEX data update complete.")
