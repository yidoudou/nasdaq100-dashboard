"""
自动抓取纳斯达克100指数数据，写入 data.json。
由 GitHub Actions 定时调用（服务端运行，不受浏览器CORS限制）。
抓取失败时保留上一次的成功值，不会用空值覆盖。
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

DATA_FILE = "data.json"


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def load_existing():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def fetch_index(existing, result):
    """从 Yahoo Finance 抓取纳指100点位和涨跌幅。"""
    try:
        raw = fetch(
            "https://query1.finance.yahoo.com/v8/finance/chart/%5ENDX"
            "?interval=1d&range=5d"
        )
        payload = json.loads(raw)
        meta = payload["chart"]["result"][0]["meta"]
        price = meta["regularMarketPrice"]
        prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
        change_pct = (price - prev_close) / prev_close * 100
        result["index"] = round(price, 2)
        result["changePct"] = round(change_pct, 2)

        # 自动追踪近期高点：只升不降（除非用户在页面里手动改）
        prev_high = existing.get("autoRecentHigh")
        result["autoRecentHigh"] = round(max(price, prev_high), 2) if prev_high else round(price, 2)
        return True
    except Exception as e:
        print("Yahoo Finance 抓取失败：", e, file=sys.stderr)
        # 抓取失败，保留已有值
        for key in ("index", "changePct", "autoRecentHigh"):
            if key in existing:
                result[key] = existing[key]
        return False


def fetch_pe(existing, result):
    """从 GuruFocus 抓取纳指100 PE-TTM。"""
    try:
        html = fetch(
            "https://www.gurufocus.com/economic_indicators/6778/nasdaq-100-pe-ratio"
        )
        m = re.search(
            r"Nasdaq 100 PE Ratio was ([\d.]+) as of (\d{4}-\d{2}-\d{2})", html
        )
        if not m:
            raise ValueError("未匹配到PE数值，页面结构可能变化")
        result["autoPeTTM"] = float(m.group(1))
        result["autoPeTTMDate"] = m.group(2)
        return True
    except Exception as e:
        print("GuruFocus 抓取失败：", e, file=sys.stderr)
        for key in ("autoPeTTM", "autoPeTTMDate"):
            if key in existing:
                result[key] = existing[key]
        return False


def main():
    existing = load_existing()
    result = {}

    ok1 = fetch_index(existing, result)
    ok2 = fetch_pe(existing, result)

    result["lastFetchTime"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    result["lastFetchOk"] = bool(ok1 or ok2)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
