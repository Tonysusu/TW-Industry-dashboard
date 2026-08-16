"""
把 data/indicators.json 嵌入 index.html，讓本機直接開檔案也能預覽。
GitHub Pages 部署後用 fetch() 讀，不依賴這個。
"""
import json, re
from pathlib import Path

BASE   = Path(__file__).parent.parent
DATA   = BASE / "data" / "indicators.json"
HTML   = BASE / "index.html"

data = json.loads(DATA.read_text(encoding="utf-8"))
data.pop("ticker_cache", None)
inline = json.dumps(data, ensure_ascii=False)

html = HTML.read_text(encoding="utf-8")

# 移除舊的 INLINE_DATA（若有）
html = re.sub(r'\n<script>const INLINE_DATA = .*?</script>\n', '', html, flags=re.DOTALL)

# 注入在主 <script> 之前，確保 init() 執行前已定義
tag = f'<script>const INLINE_DATA = {inline};</script>\n'
html = html.replace('</main>\n<script>', f'</main>\n{tag}<script>', 1)

HTML.write_text(html, encoding="utf-8")
print("✅ 資料已嵌入 index.html")
