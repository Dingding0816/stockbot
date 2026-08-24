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

WEIGHTS_FILE = "mu_weights.json"
LEARNING_RATE = 0.05
SMOOTHING_ALPHA = 0.3

def load_weights():
    try:
        with open(WEIGHTS_FILE, "r", encoding="utf-8") as f:
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
        save_weights(w)
        return w

def save_weights(w):
    with open(WEIGHTS_FILE, "w", encoding="utf-8") as f:
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
# 1. 自動扣額度（每月）
# ============================================

PUSH_COUNT_FILE = "push_count.json"

def load_push_count():
    try:
        with open(PUSH_COUNT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        data = {"month": datetime.now().strftime("%Y-%m"), "count": 0}
        save_push_count(data)
        return data

def save_push_count(data):
    with open(PUSH_COUNT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_push_count():
    today_month = datetime.now().strftime("%Y-%m")
    data = load_push_count()

    if data["month"] != today_month:
        data["month"] = today_month
        data["count"] = 0

    data["count"] += 1
    save_push_count(data)

# ============================================
# 2. LINE 廣播推播
# ============================================

LINE_CHANNEL_ACCESS_TOKEN = "VK2OUm7lcUnjgIhnLElhzimTFuUOyWQ80XaaNVDpDPLOkbTtWxN9wjos8qcSQq9u64BNAY3ktCy4KvdoXZoMHPZUXAOeHLhkDMhOyw+kehYL4G7J7ALBeoi8DOsUL2seKahQttVSupNgeORM28AtXwdB04t89/1O/w1cDnyilFU="

def send_line_broadcast(message):
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    data = {
        "messages": [{"type": "text", "text": message}]
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=10)
        if r.status_code == 200:
            print("LINE 廣播成功")
            add_push_count()
            return True
        print("LINE 廣播失敗：", r.status_code, r.text)
        return False
    except Exception as e:
        print("LINE 廣播例外：", e)
        return False

# ============================================
# 3. Push 備援
# ============================================

LINE_USER_ID = "U7b17a87cd8efbd13bf4fa39a1164d586"

def send_line_push(user_id, message):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }

    data = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}]
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=10)
        if r.status_code == 200:
            print("Push 備援成功")
            add_push_count()
            return True

        print("Push 備援失敗：", r.status_code, r.text)
        return False

    except Exception as e:
        print("Push 備援例外：", e)
        return False

# ============================================
# 4. 偵測好友數量
# ============================================

def get_follower_count():
    url = "https://api.line.me/v2/bot/insight/followers"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json().get("followers", 1)
        return 1
    except:
        return 1

# ============================================
# 5. CSV 自動解鎖
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
# 6. 安全取值
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
# 7. Finnhub
# ============================================

FINNHUB_API_KEY = "d9l0mr1r01qoc1b3psp0d9l0mr1r01qoc1b3pspg"
finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)

# ============================================
# 8. 主推播程式（你的原始邏輯）
# ============================================

def run_prediction(return_dict=False):
    tz_tw = pytz.timezone("Asia/Taipei")
    now_tw = datetime.now(tz_tw)
    version_time = now_tw.strftime("%H:%M:%S")
    version_time_csv = now_tw.strftime("%H:%M:%S")
    today = now_tw.strftime("%Y-%m-%d")

    # ============================================
    # 9. MU 日 K 線
    # ============================================

    ohlc_csv_path = "mu_daily_ohlc.csv"
    forecast_csv_path = "mu_full_day_history.csv"

    def update_daily_ohlc():
        url = f"https://finnhub.io/api/v1/stock/candle?symbol=MU&resolution=D&count=60&token={FINNHUB_API_KEY}"
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
            print("mu_daily_ohlc.csv 被鎖住，無法寫入")
            return df

        df.to_csv(ohlc_csv_path, index=False, encoding="utf-8")
        return df

    ohlc_df = update_daily_ohlc()
    if ohlc_df is not None and not ohlc_df.empty:
        latest_row = ohlc_df.iloc[-1]
        atr_mu = safe_value(latest_row["atr"], 0)
        prev_close = safe_value(latest_row["close"], 0)
    else:
        atr_mu = 0
        prev_close = safe_value(finnhub_client.quote("MU").get("pc"), 0)

    atr_factor = atr_mu / prev_close if prev_close > 0 else 0

    # ============================================
    # 14. 1 分鐘 K 線
    # ============================================

    def get_1m_klines():
        url = f"https://finnhub.io/api/v1/stock/candle?symbol=MU&resolution=1&count=60&token={FINNHUB_API_KEY}"
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

    k_df = get_1m_klines()
    def compute_short_features(df):
        df = df.copy()

        # 1m return
        df["ret_1m"] = df["c"].pct_change()

        # 3m return
        df["ret_3m"] = df["c"].pct_change(3)

        # 5m return
        df["ret_5m"] = df["c"].pct_change(5)

        # 1m ATR
        df["atr_1m"] = df["h"] - df["l"]

        # 5m ATR
        df["atr_5m"] = df["atr_1m"].rolling(5).mean()

        # 1m volume
        df["vol_1m"] = df["v"]

        # 5m volume
        df["vol_5m"] = df["v"].rolling(5).sum()

        return df

      # ============================================
    # 10. MU 即時成交價（盤中 / 盤後 / 盤前）
    # ============================================

    def get_realtime_price():
        try:
            r = requests.get(f"https://finnhub.io/api/v1/stock/trades?symbol=MU&token={FINNHUB_API_KEY}")
            trades = r.json().get("data", [])
            if trades:
                return safe_value(trades[-1]["p"], None)
        except:
            pass
        # 盤中 1 分鐘 K 線
        try:
            df_1m = get_1m_klines()
            if df_1m is not None and not df_1m.empty:
                return safe_value(df_1m["c"].iloc[-1], None)
        except:
            pass
        # quote 備援
        try:
            quote_mu = finnhub_client.quote("MU")
            return safe_value(quote_mu.get("c"), None)
        except:
            pass
        return prev_close
    current_price = get_realtime_price()

    # ============================================
    # 11. SOXX
    # ============================================

    try:
        quote_soxx = finnhub_client.quote("SOXX")
        semi_return = safe_value(quote_soxx.get("dp"), 0) / 100
    except:
        semi_return = 0

    # ============================================
    # 12. NASDAQ Futures
    # ============================================

    try:
        r = requests.get(f"https://finnhub.io/api/v1/quote?symbol=NQ=F&token={FINNHUB_API_KEY}")
        futures_return = safe_value(r.json().get("dp"), 0) / 100
    except:
        futures_return = 0

    # ============================================
    # 13. Gap
    # ============================================

    gap_pre = (current_price - prev_close) / prev_close if prev_close > 0 else 0

    # ============================================
    # 14.5  五分鐘最佳買入 / 賣出價格
    # ============================================

    def compute_5m_signals(
        current_price,
        ret_1m, ret_3m, ret_5m,
        atr_1m, atr_5m,
        vol_1m, vol_5m,
        semi_return, futures_return
    ):

        # 1. 短週期方向（最重要）
        short_direction = (
            ret_1m * 0.50 +
            ret_3m * 0.30 +
            ret_5m * 0.20
        )

        # 2. 短週期波動（ATR）
        short_volatility = (
            atr_1m * 0.6 +
            atr_5m * 0.4
        )

        # 3. 短週期成交量（量能強弱）
        volume_factor = (
            vol_1m * 0.4 +
            vol_5m * 0.6
        )

        # 4. 市場方向（半導體 + 期貨）
        market_bias = (
            semi_return * 0.4 +
            futures_return * 0.4
        )

        # 5. 綜合短週期預估（核心公式）
        price_change_est = (
            short_direction * 0.6 +
            short_volatility * 0.2 +
            volume_factor * 0.1 +
            market_bias * 0.1
        )

        # 6. 五分鐘高低點預估
        est_high_5m = current_price * (1 + price_change_est)
        est_low_5m  = current_price * (1 - price_change_est)

        # 7. 永不反轉
        true_low = min(est_low_5m, est_high_5m)
        true_high = max(est_low_5m, est_high_5m)

        # 8. 建議價位
        best_buy_5m  = true_low * 1.002   # 上調 0.2%
        best_sell_5m = true_high * 0.998  # 下調 0.2%

        return best_buy_5m, best_sell_5m

    # ============================================
    # 14.4 短週期特徵（1m / 3m / 5m）
    # ============================================

    df_1m = get_1m_klines()
    if df_1m is not None and not df_1m.empty:
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
    # 15. 30 分鐘三因子
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

    # 14.6 計算五分鐘最佳買入 / 賣出價格
    best_buy_5m, best_sell_5m = compute_5m_signals(
        current_price,
        ret_1m, ret_3m, ret_5m,
        atr_1m, atr_5m,
        vol_1m, vol_5m,
        semi_return, futures_return
    )

    # ============================
    # A. 計算價差比例
    # ============================
    spread_5m = best_sell_5m - best_buy_5m
    spread_ratio_5m = spread_5m / current_price

    # baseline（正常情況下的價差）
    baseline_spread_ratio = 0.002   # 0.2%

    # 多拉開多少
    extra_spread_ratio = spread_ratio_5m - baseline_spread_ratio
    extra_spread_ratio = max(extra_spread_ratio, 0)   # ← 建議補這行
    extra_spread_pct = extra_spread_ratio * 100

    # ============================
    # B. 將多拉開整合進價格本身
    # ============================
    best_buy_5m_adjusted  = best_buy_5m  * (1 - extra_spread_ratio)
    best_sell_5m_adjusted = best_sell_5m * (1 + extra_spread_ratio)

    # ============================================
    # 16. 整合成模型特徵
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
    # 17. 讀取權重 + 預測
    # ============================================

    weights = load_weights()
    predicted_score = predict(weights, features)

    # ============================================
    # 18. 原始預估模型
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
            - vol_30m_factor * -0.10
            - direction_30m * -0.05
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

    # ============================================
    # 19. 實際結果
    # ============================================

    actual_result = (current_price - prev_close) / prev_close if prev_close > 0 else 0

    # ============================================
    # 20. 更新權重
    # ============================================

    new_weights = update_weights(weights, features, actual_result, predicted_score)
    save_weights(new_weights)

    # ============================================
    # 21. 自動扣額度（每月）
    # ============================================

    push_data = load_push_count()
    used = push_data["count"]
    limit = 6000
    remaining = limit - used

    # ============================================
    # 22. 推播訊息
    # ============================================

    msg = (
        f"【MU 預估系統】\n"
        f"版本時間：{version_time}\n\n"
        f"整天預估最高價：{round(est_high_full_day,2)}\n"
        f"整天預估最低價：{round(est_low_full_day,2)}\n\n"
        f"未來15分鐘預估最高價：{round(est_high15,2)}\n"
        f"未來15分鐘預估最低價：{round(est_low15,2)}\n\n"
        f"--- 五分鐘建議價位 ---\n"
        f"未來5分鐘最佳買入價格：{round(best_buy_5m_adjusted, 2)}（已調整 +{extra_spread_pct:.2f}%）\n"
        f"未來5分鐘最佳賣出價格：{round(best_sell_5m_adjusted, 2)}（已調整 +{extra_spread_pct:.2f}%）\n"        
        f"--- 自動學習（B 進階版）---\n"
        f"預測分數：{predicted_score:.4f}\n"
        f"實際結果：{actual_result:.4f}\n\n"
        f"最新權重：\n"
        f"半導體：{new_weights['semi']:.4f}\n"
        f"期貨：{new_weights['futures']:.4f}\n"
        f"GAP：{new_weights['gap']:.4f}\n"
        f"ATR：{new_weights['atr']:.4f}\n"
        f"30m 報酬：{new_weights['ret30']:.4f}\n"
        f"30m 波動：{new_weights['vol30']:.4f}\n"
        f"30m 方向：{new_weights['dir30']:.4f}\n"
        f"Bias：{new_weights['bias']:.4f}\n\n"
        f"--- 推播額度資訊（自動計算） ---\n"
        f"本月推播額度：{limit} 則\n"
        f"已使用：{used} 則\n"
        f"剩餘：{remaining} 則\n"
    )
    # 如果是 API 呼叫 → 回傳 dict，不推播
    if return_dict:
        return {
            "current_price": current_price,
            "est_high_full_day": est_high_full_day,
            "est_low_full_day": est_low_full_day,
            "est_high15": est_high15,
            "est_low15": est_low15,
            "best_buy_5m": best_buy_5m_adjusted,
            "best_sell_5m": best_sell_5m_adjusted,
            "extra_spread_pct": extra_spread_pct,
            "predicted_score": predicted_score,
            "actual_result": actual_result,
            "weights": new_weights,
            "timestamp": version_time
        }

    print(msg)

    # ============================================
    # 24. 寫入 CSV
    # ============================================

    header = [
        "日期",
        "版本時間",
        "整天預估最高價",
        "整天預估最低價",
        "未來15分鐘預估最高價",
        "未來15分鐘預估最低價"
    ]

    row = [
        today,
        version_time_csv,
        round(est_high_full_day, 2),
        round(est_low_full_day, 2),
        round(est_high15, 2),
        round(est_low15, 2)
    ]

    file_exists = os.path.isfile(forecast_csv_path)
    if not wait_for_csv(forecast_csv_path):
        print("預估 CSV 檔案被鎖住，無法寫入")
    else:
        with open(forecast_csv_path, "a", encoding="utf-8") as f:
            if not file_exists:
                f.write(",".join(header) + "\n")
            f.write(",".join(map(str, row)) + "\n")

    print("✔ 本次預估完成")


    if __name__ == "__main__":
        pass
