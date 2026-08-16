"""
Taiwan Market Dashboard — 資料抓取 + 指標計算
──────────────────────────────────────────────
用法：
  python fetch_and_calc.py          # 每日更新（抓最近 200 日）
  python fetch_and_calc.py --full   # 首次建立（抓 5 年歷史）
"""

import json, sys, time
from pathlib import Path
from datetime import datetime, date
import pandas as pd
import numpy as np
import yfinance as yf

BASE   = Path(__file__).parent.parent
CONFIG = BASE / "config" / "industries.json"
OUTPUT = BASE / "data" / "indicators.json"

PERIOD_FULL  = "5y"
PERIOD_DAILY = "200d"   # 夠算 MA120 + CMF20

# ── 工具 ──────────────────────────────────────────────────────────────────────

def resolve_ticker(code: str) -> str | None:
    """嘗試 .TW / .TWO，回傳有資料的那個"""
    for suffix in [".TW", ".TWO"]:
        ticker = f"{code}{suffix}"
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if len(hist) > 0:
                return ticker
        except Exception:
            pass
        time.sleep(0.2)
    return None

def fetch_ohlcv(ticker: str, period: str) -> pd.DataFrame:
    """抓 OHLCV，回傳 DataFrame（index=date，cols=Open/High/Low/Close/Volume）"""
    try:
        hist = yf.Ticker(ticker).history(period=period)
        if hist.empty:
            return pd.DataFrame()
        hist.index = hist.index.tz_localize(None).normalize()
        return hist[["Open", "High", "Low", "Close", "Volume"]]
    except Exception as e:
        print(f"  ⚠ {ticker} 抓取失敗: {e}")
        return pd.DataFrame()

# ── 指標計算 ──────────────────────────────────────────────────────────────────

def calc_cmf(df: pd.DataFrame, n: int = 20) -> float:
    """Chaikin Money Flow"""
    if len(df) < n:
        return float("nan")
    d = df.tail(n).copy()
    hl = d["High"] - d["Low"]
    hl = hl.replace(0, np.nan)
    mfm = ((2 * d["Close"] - d["High"] - d["Low"]) / hl).fillna(0)
    mfv = mfm * d["Volume"]
    vol_sum = d["Volume"].sum()
    return float(mfv.sum() / vol_sum) if vol_sum > 0 else float("nan")

def calc_stock_indicators(df: pd.DataFrame) -> dict:
    """計算單支股票的指標"""
    if len(df) < 20:
        return None
    close = df["Close"]
    ma20  = close.rolling(20).mean().iloc[-1]
    ma120 = close.rolling(120).mean().iloc[-1] if len(df) >= 120 else float("nan")
    high_1y = close.tail(252).max()
    latest  = close.iloc[-1]
    drawdown = (high_1y - latest) / high_1y if high_1y > 0 else float("nan")

    # 牛熊狀態
    above_ma120 = bool(latest > ma120) if not np.isnan(ma120) else None
    if above_ma120 is None:
        bull_bear = "unknown"
    elif above_ma120 and drawdown < 0.10:
        bull_bear = "bull_stable"      # 多頭穩定 🟢
    elif above_ma120 and drawdown < 0.20:
        bull_bear = "bull_volatile"    # 多頭動盪 🟡
    elif above_ma120:
        bull_bear = "bull_weak"        # 多頭但距高點已遠 🟠
    else:
        bull_bear = "bear"             # 空頭 🔴

    return {
        "close":       round(float(latest), 2),
        "ma20":        round(float(ma20), 2),
        "ma120":       round(float(ma120), 2) if not np.isnan(ma120) else None,
        "high_1y":     round(float(high_1y), 2),
        "drawdown":    round(float(drawdown), 4) if not np.isnan(drawdown) else None,
        "cmf_20":      round(calc_cmf(df, 20), 4),
        "above_ma20":  bool(latest > ma20),
        "above_ma120": above_ma120,
        "bull_bear":   bull_bear,
    }

def aggregate_sub(stocks_data: list) -> dict:
    """次產業加權彙整"""
    valid = [s for s in stocks_data if s.get("indicators")]
    if not valid:
        return {}
    n = len(valid)
    # CMF 以成交量加權（這裡先用等權，volume 資訊在 indicators 裡沒存，之後可優化）
    cmfs = [s["indicators"]["cmf_20"] for s in valid if s["indicators"].get("cmf_20") is not None]
    above_20  = sum(1 for s in valid if s["indicators"].get("above_ma20"))
    above_120 = sum(1 for s in valid if s["indicators"].get("above_ma120"))
    dd_vals   = [s["indicators"]["drawdown"] for s in valid if s["indicators"].get("drawdown") is not None]

    avg_cmf = round(float(np.mean(cmfs)), 4) if cmfs else None
    breadth_20  = round(above_20  / n, 4)
    breadth_120 = round(above_120 / n, 4)
    avg_dd      = round(float(np.mean(dd_vals)), 4) if dd_vals else None

    # 次產業牛熊：依站上 MA120 比例 + 平均回檔
    if breadth_120 >= 0.6 and (avg_dd is None or avg_dd < 0.15):
        bull_bear = "bull_stable"
    elif breadth_120 >= 0.6:
        bull_bear = "bull_volatile"
    elif breadth_120 >= 0.4:
        bull_bear = "neutral"
    else:
        bull_bear = "bear"

    return {
        "bull_bear":    bull_bear,
        "cmf_20":       avg_cmf,
        "breadth_20":   breadth_20,
        "breadth_120":  breadth_120,
        "avg_drawdown": avg_dd,
        "stock_count":  n,
    }

# ── 主流程 ─────────────────────────────────────────────────────────────────────

def run(full_history: bool = False):
    period = PERIOD_FULL if full_history else PERIOD_DAILY
    config = json.loads(CONFIG.read_text(encoding="utf-8"))

    # 讀舊資料（有的話），保留 ticker cache
    old_data = {}
    if OUTPUT.exists():
        old_data = json.loads(OUTPUT.read_text(encoding="utf-8"))
    ticker_cache = old_data.get("ticker_cache", {})

    result = {
        "last_updated": date.today().isoformat(),
        "ticker_cache": ticker_cache,
        "industries":   [],
    }

    for ind in config["industries"]:
        print(f"\n▶ 產業：{ind['name']}")
        ind_result = {
            "id":             ind["id"],
            "name":           ind["name"],
            "name_en":        ind["name_en"],
            "sub_industries": [],
        }
        all_stock_data = []

        for sub in ind["sub_industries"]:
            print(f"  次產業：{sub['name']}")
            sub_stocks = []

            for s in sub["stocks"]:
                code = s["code"]
                # 解析 ticker（有 cache 直接用）
                if code not in ticker_cache:
                    ticker = resolve_ticker(code)
                    if ticker:
                        ticker_cache[code] = ticker
                        print(f"    {code} {s['name']} → {ticker}")
                    else:
                        print(f"    {code} {s['name']} → ❌ 找不到")
                        ticker_cache[code] = None
                ticker = ticker_cache.get(code)

                indicators = None
                if ticker:
                    df = fetch_ohlcv(ticker, period)
                    if not df.empty:
                        indicators = calc_stock_indicators(df)
                    time.sleep(0.3)

                sub_stocks.append({
                    "code":       code,
                    "name":       s["name"],
                    "ticker":     ticker,
                    "indicators": indicators,
                })
                if indicators:
                    print(f"    {code} {s['name']}: {indicators['bull_bear']} | CMF={indicators['cmf_20']} | close={indicators['close']}")

            agg = aggregate_sub(sub_stocks)
            ind_result["sub_industries"].append({
                "id":         sub["id"],
                "name":       sub["name"],
                "summary":    agg,
                "stocks":     sub_stocks,
            })
            all_stock_data.extend(sub_stocks)

        # 產業層彙整
        ind_result["summary"] = aggregate_sub(all_stock_data)
        result["industries"].append(ind_result)

    result["ticker_cache"] = ticker_cache
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 完成，輸出至 {OUTPUT}")

if __name__ == "__main__":
    full = "--full" in sys.argv
    run(full_history=full)
