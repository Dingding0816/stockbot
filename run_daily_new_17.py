import finnhub
import pandas as pd
import numpy as np
import requests
from datetime import datetime
import pytz
import os
import time
import json

# ============================================
# 0. 進階版自動學習（B）
# ============================================

def get_weights_file(symbol):
    return f"{symbol.lower()}_weights.json"

LEARNING_RATE = 0.05
SMOOTHING_ALPHA = 0.3

def load_weights(symbol):
    file = get_weights_file(symbol)
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        w = {
            "semi": 0.25,
            "futures": 0.25,
            "gap": 0.15,
            "atr": 0.15,
            "ret30": 0.10,
            "vol30": 0.05,
            "dir30": 0.05,
            "bias": 0.0
        }
        save_weights(symbol, w)
        return w

def save_weights(symbol, w):
    file = get_weights_file(symbol)
    with open(file, "w", encoding="utf-8") as f:
        json.dump(w, f, ensure_ascii=False, indent=2)

def predict(weights, features):
    return (
        weights["semi"]   * features["semi"] +
        weights["futures"]* features["futures"] +
        weights["gap"]    * features["gap"] +
        weights["atr"]    * features["atr"] +
        weights["ret30"]  * features["ret30"] +
        weights["vol30"]  * features["vol30"] +
        weights["dir30"]  * features["dir30"] +
        weights["bias"]
    )

def update_weights(weights, features, actual, predicted):
    error = actual - predicted
    new_w = {}

    for key in ["semi","futures","gap","atr","ret30","vol30","dir30"]:
        w_old = weights[key]
        x = features[key]
        w_update = w_old + LEARNING_RATE * error * x
        w_new = (1 - SMOOTHING_ALPHA) * w_old + SMOOTHING_ALPHA * w_update
        new_w[key] = w_new

    w_old = weights["bias"]
    w_update = w_old + LEARNING_RATE * error * 1.0
    w_new = (1 - SMOOTHING_ALPHA) * w_old + SMOOTHING_ALPHA * w_update
    new_w["bias"] = w_new

    return new_w

# ============================================
# 1. CSV 自動解鎖
# ============================================

def wait_for_csv(path, timeout=10):
    start = time.time()
    while True:
        try:
            f = open(path, "a", encoding="utf-8")
            f.close()
            return True
        except PermissionError:
            if time.time() - start > timeout:
                return False
            time.sleep(0.5)

# ============================================
# 2. 安全取值
# ============================================

def safe_value(v, default=0):
    try:
        if v is None:
            return default
        return float(v)
    except:
        return default

def safe_calc(v, fallback):
    try:
        if np.isnan(v):
            return fallback
        return float(v)
    except:
        return fallback

# ============================================
# 3. Finnhub
# ============================================

FINNHUB_API_KEY = "d9l0mr1r01qoc1b3psp0d9l0mr1r01qoc1b3pspg"
finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)

# ============================================
# 4. 主預測程式（多股票版）
# ============================================

def run_prediction(symbol="MU", return_dict=False):

    symbol = symbol.upper()

    tz_tw = pytz.timezone("Asia/Taipei")
    now_tw = datetime.now(tz_tw)
    version_time = now_tw.strftime("%H:%M:%S")
    version_time_csv = now_tw.strftime("%H:%M:%S")
    today = now_tw.strftime("%Y-%m-%d")

    # ============================================
    # 5. 日 K 線（多股票版）
    # ============================================

    ohlc_csv_path = f"{symbol.lower()}_daily_ohlc.csv"
    forecast_csv_path = f"{symbol.lower()}_full_day_history.csv"

    def update_daily_ohlc():
        url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=D&count=60&token={FINNHUB_API_KEY}"
        r = requests.get(url)
        data = r.json()
        if data.get("s") != "ok":
            return None

        ts = data.get("t", [])
        opens = data.get("o", [])
        highs = data.get("h", [])
        lows = data.get("l", [])
        closes = data.get("c", [])

        df = pd.DataFrame({
            "date": [datetime.fromtimestamp(t).strftime("%Y-%m-%d") for t in ts],
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes
        })

        df = df.sort_values("date").reset_index(drop=True)
        df["prev_close"] = df["close"].shift(1)

        def calc_tr(row):
            if pd.isna(row["prev_close"]):
                return row["high"] - row["low"]
            return max(
                row["high"] - row["low"],
                abs(row["high"] - row["prev_close"]),
                abs(row["low"] - row["prev_close"])
            )

        df["tr"] = df.apply(calc_tr, axis=1)
        df["atr"] = df["tr"].rolling(window=14).mean()

        file_exists = os.path.isfile(ohlc_csv_path)
        if not wait_for_csv(ohlc_csv_path):
            print(f"{ohlc_csv_path} 被鎖住，無法寫入")
            return df

        df.to_csv(ohlc_csv_path, index=False, encoding="utf-8")
        return df

    ohlc_df = update_daily_ohlc()
    if ohlc_df is not None and not ohlc_df.empty:
        latest_row = ohlc_df.iloc[-1]
        atr_symbol = safe_value(latest_row["atr"], 0)
        prev_close = safe_value(latest_row["close"], 0)
    else:
        atr_symbol = 0
        prev_close = safe_value(finnhub_client.quote(symbol).get("pc"), 0)

    atr_factor = atr_symbol / prev_close if prev_close > 0 else 0

    # ============================================
    # 6. 1 分鐘 K 線（多股票版）
    # ============================================

    def get_1m_klines():
        url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=1&count=60&token={FINNHUB_API_KEY}"
        r = requests.get(url)
        data = r.json()
        if data.get("s") != "ok":
            return None

        df = pd.DataFrame({
            "t": data["t"],
            "o": data["o"],
            "h": data["h"],
            "l": data["l"],
            "c": data["c"]
        })

        df["datetime"] = df["t"].apply(lambda x: datetime.fromtimestamp(x))
        df = df.sort_values("datetime").reset_index(drop=True)
        return df

    # ============================================
    # 7. K 線合理性檢查
    # ============================================

    def is_valid_kline(df):
        if df is None or df.empty:
            return False

        h = df["h"].iloc[-1]
        l = df["l"].iloc[-1]
        c = df["c"].iloc[-1]
        o = df["o"].iloc[-1]

        if c <= 0 or h <= 0 or l <= 0 or o <= 0:
            return False

        if h > c * 1.02 or l < c * 0.98:
            return False

        if (h - l) > c * 0.02:
            return False

        ret_1m = df["c"].pct_change().iloc[-1]
        if abs(ret_1m) > 0.02:
            return False

        if abs(o - c) > c * 0.02:
            return False

        return True

    k_df = get_1m_klines()

    # ============================================
    # 8. 短週期特徵
    # ============================================

    def compute_short_features(df):
        df = df.copy()

        df["ret_1m"] = df["c"].pct_change().clip(-0.05, 0.05)
        df["ret_3m"] = df["c"].pct_change(3).clip(-0.10, 0.10)
        df["ret_5m"] = df["c"].pct_change(5).clip(-0.15, 0.15)

        raw_atr = df["h"] - df["l"]
        df["atr_1m"] = raw_atr.where(raw_atr < df["c"] * 0.05, df["c"] * 0.02)
        df["atr_5m"] = df["atr_1m"].rolling(5).mean()

        df["vol_1m"] = 0
        df["vol_5m"] = 0

        return df

    df_1m = get_1m_klines()

    if is_valid_kline(df_1m):
        df_1m = compute_short_features(df_1m)
        last = df_1m.iloc[-1]

        ret_1m = safe_value(last["ret_1m"], 0)
        ret_3m = safe_value(last["ret_3m"], 0)
        ret_5m = safe_value(last["ret_5m"], 0)

        atr_1m = safe_value(last["atr_1m"], 0)
        atr_5m = safe_value(last["atr_5m"], 0)

        vol_1m = safe_value(last["vol_1m"], 0)
        vol_5m = safe_value(last["vol_5m"], 0)

    else:
        ret_1m = ret_3m = ret_5m = 0
        atr_1m = atr_5m = 0
        vol_1m = vol_5m = 0

    # ============================================
    # 9. 即時成交價（多股票版）
    # ============================================

    def get_realtime_price():
        try:
            r = requests.get(f"https://finnhub.io/api/v1/stock/trades?symbol={symbol}&token={FINNHUB_API_KEY}")
            trades = r.json().get("data", [])
            if trades:
                return safe_value(trades[-1]["p"], None)
        except:
            pass

        try:
            df_1m = get_1m_klines()
            if df_1m is not None and not df_1m.empty:
                return safe_value(df_1m["c"].iloc[-1], None)
        except:
            pass

        try:
            quote_symbol = finnhub_client.quote(symbol)
            return safe_value(quote_symbol.get("c"), None)
        except:
            pass

        return prev_close

    current_price = get_realtime_price()

    # ============================================
    # 10. SOXX
    # ============================================

    try:
        quote_soxx = finnhub_client.quote("SOXX")
        semi_return = safe_value(quote_soxx.get("dp"), 0) / 100
    except:
        semi_return = 0

    # ============================================
    # 11. NASDAQ Futures
    # ============================================

    try:
        r = requests.get(f"https://finnhub.io/api/v1/quote?symbol=NQ=F&token={FINNHUB_API_KEY}")
        futures_return = safe_value(r.json().get("dp"), 0) / 100
    except:
        futures_return = 0

    # ============================================
    # 12. Gap
    # ============================================

    gap_pre = (current_price - prev_close) / prev_close if prev_close > 0 else 0

    # ============================================
    # 13. 五分鐘預估（含永不反轉）
    # ============================================

    def compute_5m_signals(
        current_price,
        ret_1m, ret_3m, ret_5m,
        atr_1m, atr_5m,
        vol_1m, vol_5m,
        semi_return, futures_return
    ):
        short_direction = (
            ret_1m * 0.50 +
            ret_3m * 0.30 +
            ret_5m * 0.20
        )

        price_change_est = short_direction * 0.1
        price_change_est = max(min(price_change_est, 0.003), -0.003)

        est_high_5m = current_price * (1 + price_change_est)
        est_low_5m  = current_price * (1 - price_change_est)

        best_buy_5m  = est_low_5m  * 1.001
        best_sell_5m = est_high_5m * 0.999

        # 永不反轉
        true_low = min(best_buy_5m, best_sell_5m)
        true_high = max(best_buy_5m, best_sell_5m)

        best_buy_5m = true_low
        best_sell_5m = true_high

        return best_buy_5m, best_sell_5m

    # ============================================
    # 14. 30 分鐘三因子
    # ============================================

    if k_df is not None and len(k_df) >= 30:
        last30 = k_df.iloc[-30:]
        price_30m_ago = safe_value(last30.iloc[0]["c"], current_price)
        return_30m = (current_price - price_30m_ago) / price_30m_ago
        high_30m = safe_value(last30["h"].max(), current_price)
        low_30m = safe_value(last30["l"].min(), current_price)
        vol_30m = high_30m - low_30m
        vol_30m_factor = vol_30m / current_price if current_price > 0 else 0
        up_count = (last30["c"] > last30["o"]).sum()
        down_count = (last30["c"] < last30["o"]).sum()
        direction_30m = (up_count - down_count) / 30
    else:
        return_30m = 0
        vol_30m_factor = 0
        direction_30m = 0

    # ============================================
    # 15. 五分鐘最佳買入 / 賣出價格
    # ============================================

    best_buy_5m, best_sell_5m = compute_5m_signals(
        current_price,
        ret_1m, ret_3m, ret_5m,
        atr_1m, atr_5m,
        vol_1m, vol_5m,
        semi_return, futures_return
    )

    # ============================================
    # 16. 價差調整
    # ============================================

    spread_5m = best_sell_5m - best_buy_5m
    spread_ratio_5m = spread_5m / current_price

    baseline_spread_ratio = 0.002
    extra_spread_ratio = spread_ratio_5m - baseline_spread_ratio
    extra_spread_ratio = max(extra_spread_ratio, 0)
    extra_spread_pct = extra_spread_ratio * 100

    best_buy_5m_adjusted  = best_buy_5m  * (1 - extra_spread_ratio)
    best_sell_5m_adjusted = best_sell_5m * (1 + extra_spread_ratio)

    # ============================================
    # 17. 整合特徵
    # ============================================

    features = {
        "semi": semi_return,
        "futures": futures_return,
        "gap": gap_pre,
        "atr": atr_factor,
        "ret30": return_30m,
        "vol30": vol_30m_factor,
        "dir30": direction_30m
    }

    # ============================================
    # 18. 讀取權重 + 預測
    # ============================================

    weights = load_weights(symbol)
    predicted_score = predict(weights, features)

    # ============================================
    # 19. 原始預估模型
    # ============================================

    est_high_full_day = safe_calc(
        current_price * (
            1
            + semi_return * 0.25
            + futures_return * 0.20
            + gap_pre * 0.05
            + atr_factor * 0.10
            + return_30m * 0.25
            + vol_30m_factor * 0.10
            + direction_30m * 0.05
        ),
        current_price
    )

    est_low_full_day = safe_calc(
        current_price * (
            1
            + semi_return * -0.20
            + futures_return * -0.15
            + gap_pre * -0.05
            - atr_factor * 0.10
            + return_30m * -0.20
            - vol_30m_factor * 0.10
            - direction_30m * 0.05
        ),
        current_price
    )

    est_high15 = safe_calc(
        current_price * (
            1
            + semi_return * 0.15
            + futures_return * 0.12
            + gap_pre * 0.03
            + atr_factor * 0.05
            + return_30m * 0.20
            + vol_30m_factor * 0.08
            + direction_30m * 0.05
        ),
        current_price
    )

    est_low15 = safe_calc(
        current_price * (
            1
            + semi_return * -0.12
            + futures_return * -0.10
            + gap_pre * -0.03
            - atr_factor * 0.05
            + return_30m * -0.15
            - vol_30m_factor * 0.08
            - direction_30m * 0.05
        ),
        current_price
    )

    # 永不反轉
    true_low_full  = min(est_low_full_day, est_high_full_day)
    true_high_full = max(est_low_full_day, est_high_full_day)

    true_low15  = min(est_low15, est_high15)
    true_high15 = max(est_low15, est_high15)

    # ============================================
    # 20. 實際結果
    # ============================================

    actual_result = (current_price - prev_close) / prev_close if prev_close > 0 else 0

    # ============================================
    # 21. 更新權重
    # ============================================

    new_weights = update_weights(weights, features, actual_result, predicted_score)
    save_weights(symbol, new_weights)

    # ============================================
    # 22. 回傳結果（給 API 用）
    # ============================================

    if return_dict:
        return {
            "symbol": symbol,
            "current_price": float(current_price),

            "best_buy_5m": float(best_buy_5m_adjusted),
            "best_sell_5m": float(best_sell_5m_adjusted),

            "true_high15": float(true_high15),
            "true_low15": float(true_low15),

            "true_high_full": float(true_high_full),
            "true_low_full": float(true_low_full),

            "est_high15": float(est_high15),
            "est_low15": float(est_low15),
            "est_high_full_day": float(est_high_full_day),
            "est_low_full_day": float(est_low_full_day),

            "extra_spread_pct": float(extra_spread_pct),
            "predicted_score": float(predicted_score),
            "actual_result": float(actual_result),

            "weights": {k: float(v) for k, v in new_weights.items()},
            "timestamp": version_time,
        }

    # ============================================
    # 23. 寫入 CSV（各股票獨立檔）
    # ============================================

    header = [
        "symbol",
        "日期",
        "版本時間",
        "整天預估最高價",
        "整天預估最低價",
        "未來15分鐘預估最高價",
        "未來15分鐘預估最低價"
    ]

    row = [
        symbol,
        today,
        version_time_csv,
        round(true_high_full, 2),
        round(true_low_full, 2),
        round(true_high15, 2),
        round(true_low15, 2)
    ]

    file_exists = os.path.isfile(forecast_csv_path)
    if not wait_for_csv(forecast_csv_path):
        print(f"{forecast_csv_path} 被鎖住，無法寫入")
    else:
        with open(forecast_csv_path, "a", encoding="utf-8") as f:
            if not file_exists:
                f.write(",".join(header) + "\n")
            f.write(",".join(map(str, row)) + "\n")

    print(f"✔ 本次預估完成：{symbol} {version_time}")


if __name__ == "__main__":
    # 測試用：直接跑一次 MU
    run_prediction(symbol="MU", return_dict=False)
