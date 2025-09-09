import os
import time
import datetime as dt
from typing import List, Dict, Tuple, Optional


API_KEY = os.getenv("BINANCE_API_KEY", "keykeykey")  #这里填写API_KEY ！！！！！！！！！！！！！！！！！！！！！！！
API_SECRET = os.getenv("BINANCE_API_SECRET", "secretsecretsecret")  #这里填写API_SECRET ！！！！！！！！！！！！！！！！！！！！！！！

# 触发阈值（0.5 = 50%）  这个是检测日内波动百分比的阈值，如果日内波动超过这个值就会被记录，想要修改百分比修改这个值就行
PCT_THRESHOLD = 0.5
LOOKBACK_DAYS = 7
TZ_UTC = getattr(dt, "UTC", dt.timezone.utc)
USING_PYTHON_BINANCE = False
USING_CONNECTOR = False
client = None
spot = None

try:
    from binance.client import Client as PBClient
    USING_PYTHON_BINANCE = True
except Exception:
    pass

if not USING_PYTHON_BINANCE:
    try:
        from binance.spot import Spot as ConnectorSpot
        USING_CONNECTOR = True
    except Exception:
        pass

if not (USING_PYTHON_BINANCE or USING_CONNECTOR):
    raise ImportError(
        "未找到可用的 Binance Python 库。请安装以下：\n"
        "  pip install python-binance\n"
    )

def init_clients():
    global client, spot
    if USING_PYTHON_BINANCE:
        client = PBClient(api_key=API_KEY, api_secret=API_SECRET)
    else:
        spot = ConnectorSpot(api_key=API_KEY, api_secret=API_SECRET)

init_clients()

def get_account_info_and_balances() -> Tuple[Dict, List[Dict]]:
    if USING_PYTHON_BINANCE:
        info = client.get_account()
        balances = info.get("balances", [])
    else:
        info = spot.account()
        balances = info.get("balances", [])
    non_zero = []
    for b in balances:
        free = float(b.get("free", 0) or 0)
        locked = float(b.get("locked", 0) or 0)
        if (free + locked) > 0:
            non_zero.append({"asset": b["asset"], "free": free, "locked": locked})
    non_zero.sort(key=lambda x: -(x["free"] + x["locked"]))
    return info, non_zero

def get_usdt_spot_symbols() -> List[str]:
    symbols = []
    if USING_PYTHON_BINANCE:
        ex = client.get_exchange_info()
    else:
        ex = spot.exchange_info()
    for s in ex.get("symbols", []):
        if (
            s.get("status") == "TRADING"
            and s.get("quoteAsset") == "USDT"
            and s.get("isSpotTradingAllowed", False)
        ):
            symbols.append(s["symbol"])
    return symbols

def fetch_daily_klines(symbol: str, limit: int = 14) -> List[list]:
    """获取日K，返回已收盘的最后 LOOKBACK_DAYS """
    try:
        if USING_PYTHON_BINANCE:
            klines = client.get_klines(symbol=symbol, interval="1d", limit=limit)
        else:
            klines = spot.klines(symbol, "1d", limit=limit)
        if not klines:
            return []
        now_ms = int(time.time() * 1000)
        closed = [k for k in klines if int(k[6]) < now_ms]  # k[6] 是 close_time
        if len(closed) > LOOKBACK_DAYS:
            closed = closed[-LOOKBACK_DAYS:]
        return closed
    except Exception:
        return []

def check_symbol_spike(symbol: str, threshold: float = PCT_THRESHOLD) -> List[dict]:
    """
    返回过去 LOOKBACK_DAYS 天内触发 ≥threshold 的记录：
    - intraday_up: (high/open - 1)
    - intraday_down: (1 - low/open)
    - close_to_close: abs(close/prev_close - 1)
    """
    ks = fetch_daily_klines(symbol, limit=LOOKBACK_DAYS + 7)
    if len(ks) < 2:
        return []

    triggers = []
    prev_close = None
    for k in ks:
        o = float(k[1]); h = float(k[2]); l = float(k[3]); c = float(k[4])
        open_time_ms = int(k[0])
        date_utc = dt.datetime.fromtimestamp(open_time_ms / 1000, TZ_UTC).strftime("%Y-%m-%d")

        intraday_name = None
        intraday_pct = 0.0
        if o > 0:
            up = h / o - 1.0
            down = 1.0 - l / o
            if up >= threshold or down >= threshold:
                if up >= down:
                    intraday_name, intraday_pct = "intraday_up", up
                else:
                    intraday_name, intraday_pct = "intraday_down", down

        cc_name = None
        cc_pct = 0.0
        if prev_close and prev_close > 0:
            cc = c / prev_close - 1.0
            if abs(cc) >= threshold:
                cc_name, cc_pct = "close_to_close", cc

        prev_close = c

        best = None
        # 任一达到阈值即记录；若都达到，取绝对值更大的那一个
        if intraday_name and cc_name:
            best = (intraday_name, intraday_pct) if abs(intraday_pct) >= abs(cc_pct) else (cc_name, cc_pct)
        elif intraday_name:
            best = (intraday_name, intraday_pct)
        elif cc_name:
            best = (cc_name, cc_pct)

        if best:
            triggers.append({
                "date": date_utc,
                "type": best[0],
                "pct": best[1],
                "open": o, "high": h, "low": l, "close": c,
            })

    return triggers

def main():
    if not API_KEY or not API_SECRET:
        print("提示：未检测到环境变量 BINANCE_API_KEY / BINANCE_API_SECRET（仍可拉公共行情并输出，无需余额权限）。")

    info, non_zero = get_account_info_and_balances()
    print("\n=== 账户信息 (部分) ===")
    print(f"canTrade: {info.get('canTrade', 'N/A')}  updateTime: {info.get('updateTime', 'N/A')}")

    print("\n=== 非零余额（降序） ===")
    if not non_zero:
        print("(无余额或均为 0)")
    else:
        for b in non_zero:
            total = b["free"] + b["locked"]
            print(f"{b['asset']:<8}  free:{b['free']:>16.8f}  locked:{b['locked']:>16.8f}  total:{total:>16.8f}")

    print(f"\n=== 过去 {LOOKBACK_DAYS} 天内任意一天涨跌 ≥ {PCT_THRESHOLD*100:.0f}% 的 USDT 现货交易对 ===")
    symbols = get_usdt_spot_symbols()
    results = []  # [(symbol, [trigger...], max_abs_pct)]
    for i, sym in enumerate(symbols, 1):
        ts = check_symbol_spike(sym, PCT_THRESHOLD)
        if ts:
            max_abs = max(abs(x["pct"]) for x in ts)
            results.append((sym, ts, max_abs))
        if i % 25 == 0:
            time.sleep(0.2)  # 轻微限频

    if not results:
        print("未发现满足条件的交易对。")
    else:
        results.sort(key=lambda x: x[2], reverse=True)
        for sym, ts, _ in results:
            print(f"\n{sym}:")
            for x in ts:
                sign = "+" if x["pct"] >= 0 else "-"
                print(f"  {x['date']}  {x['type']:<14}  {sign}{abs(x['pct'])*100:>6.2f}%"
                      f"  O:{x['open']:.8g} H:{x['high']:.8g} L:{x['low']:.8g} C:{x['close']:.8g}")

    print("\n数据时间：", dt.datetime.now(TZ_UTC).isoformat())


PERIOD = 300 # 5分钟自动执行一次
if __name__ == "__main__":
    try:
        while True:
            t0 = time.monotonic()
            main()
            elapsed = time.monotonic() - t0
            time.sleep(max(0, PERIOD - elapsed))
    except KeyboardInterrupt:
        print("stopped")