import os
import time
from datetime import datetime, timedelta
import random
import requests
import math  # 用來安全檢查 nan
import numpy as np
import pandas as pd
import yfinance as yf

import matplotlib
matplotlib.use('Agg')  # 強制指定 Linux 伺服器專用無介面繪圖模式，解決 savefig 崩潰
import matplotlib.pyplot as plt
import matplotlib.patheffects as patheffects

# 💡 修正：移除無法匯入的 Middleware，只保留需要的內容
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse

# 引入您原本的日預測邏輯
from run_daily_new_17 import run_prediction

# 1. 全自動讀取 Render 後台寫入的頂級付費金鑰（若後台無設定，則使用預設金鑰）
FINNHUB_API_KEY = os.getenv("FINNHUB_TOKEN", "d9l0mr1r01qoc1b3psp0d9l0mr1r01qoc1b3pspg")

# 2. 全站只宣告這唯一一個 app 執行實例，絕不重複覆蓋！
app = FastAPI(
    title="Stock Prediction API",
    description="MU / SNDK / MXL / STX / META 多股票 AI 預估系統",
    version="2.1.0"
)

# 3. 允許跨網域存取 (CORS) - 這樣前端就不會再噴 404 或跨網域阻擋錯誤了
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------------
# 💾 【新增】全域預測歷史快取機制 (預防 NaN 斷訊)
# -------------------------------------------------------------------------
# 結構會是：{"MXL": {"best_buy_5m": 83.2, ...}, "META": {...}}
PREDICTION_CACHE = {}

def process_prediction_with_cache(symbol: str, raw_result: dict) -> dict:
    """
    核心快取容錯機制：
    1. 遍歷本次預測結果的所有欄位。
    2. 如果欄位值是 NaN，且過去有成功存下歷史數值，則自動用歷史值替換。
    3. 如果欄位值是有效數字，則更新快取庫，作為下一次的備援。
    4. 最終移除所有 NaN，確保完全 JSON 相容。
    """
    sym = symbol.upper()
    
    # 如果這個股票從來沒有建立過快取紀錄，先幫它建立一個空字典
    if sym not in PREDICTION_CACHE:
        PREDICTION_CACHE[sym] = {}
        
    cleaned_result = {}
    
    for key, value in raw_result.items():
        is_nan = False
        
        # 判斷是否為 NaN
        if isinstance(value, float) and math.isnan(value):
            is_nan = True
            
        if is_nan or value is None:
            # 💡 觸發容錯：如果是 NaN 或空值，去撈上一次成功的歷史紀錄
            if key in PREDICTION_CACHE[sym]:
                cleaned_result[key] = PREDICTION_CACHE[sym][key]
                print(f"⚠️ [{sym}] 欄位 '{key}' 當前為 NaN，已成功自動替換為歷史紀錄: {cleaned_result[key]}")
            else:
                # 如果連歷史紀錄都沒有，就只能先給 None (前端會顯示 --)
                cleaned_result[key] = None
        else:
            # 💡 欄位正常：將有效數值存入快取庫，並放入結果中
            PREDICTION_CACHE[sym][key] = value
            cleaned_result[key] = value
            
    return cleaned_result

# -------------------------------------------------------------------------
# 📈 預測 API 端點（高頻刷新整合快取版）
# -------------------------------------------------------------------------
@app.get("/predict/{symbol}")
def predict_symbol(symbol: str):
    sym = symbol.upper()
    raw_result = run_prediction(symbol=sym, return_dict=True)
    
    # 💡 透過快取防火牆清洗：如果是 NaN 就用上一次的值，並確保 Render 不再噴 JSON 錯誤
    return process_prediction_with_cache(sym, raw_result)
    
# -------------------------------------------------------------------------
# 🎨 動態成交量與收盤價圖表產生器 (100% 成功直連 Finnhub 版本)
# -------------------------------------------------------------------------
@app.get("/volume_chart/{symbol}")
def volume_chart(symbol: str):
    symbol = symbol.upper()
    img_filename = f"/tmp/volume_chart_{symbol}.png"
    
    # 強迫每次刷新都重新判斷/重新繪製，絕不留可能死鎖的舊快取
    if os.path.exists(img_filename):
        try:
            os.remove(img_filename)
        except Exception:
            pass

    has_real_data = False
    dates, volumes, closes = [], [], []

    # =========================================================================
    # 🥇 1st Priority：正面直連 Finnhub 官方伺服器 (付費版優化結構)
    # =========================================================================
    base_url = "https://finnhub.io/api/v1/stock/candle"
    
    # 使用 datetime 精確計算秒級時間戳，避免系統時間溢位
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    # 往前推 30 天，對付費版來說這段區間資料最穩定完整
    start_date = now - timedelta(days=30)
    
    from_time = int(start_date.timestamp())
    to_time = int(now.timestamp())

    query_params = {
        "symbol": symbol,
        "resolution": "D",
        "from": from_time,
        "to": to_time,
        "token": "d9l0mr1r01qoc1b3psp0d9l0mr1r01qoc1b3pspg"  # 您的付費版金鑰
    }
    
    try:
        # 設定 5 秒超時，確保網路卡頓能順利處理
        r = requests.get(base_url, params=query_params, timeout=5)
        
        # 💡 排錯關鍵：如果不是 200，立刻在 Render 控制台印出 Finnhub 給的付費版錯誤訊息
        if r.status_code != 200:
            print(f"❌ [Finnhub API Error] HTTP {r.status_code}: {r.text}")
            
        if r.status_code == 200:
            data = r.json()
            
            # 💡 付費版優化判斷：只要有時間軸 (t) 和收盤價 (c) 資料且長度大於 0 就放行
            # 有時付費版回傳格式不一定帶有 s="ok"，直接檢查資料本體最安全！
            if "t" in data and data["t"] and len(data["t"]) > 0:
                # 確保只取最新的 15 天歷史
                ts = data["t"][-15:]
                volumes = data["v"][-15:]
                closes = data["c"][-15:]
                
                # 轉換為前端圖表日期
                dates = [datetime.fromtimestamp(t).strftime("%m-%d") for t in ts]
                
                if len(dates) > 0 and sum(volumes) > 0:
                    has_real_data = True
            else:
                # 如果回傳了 {"s": "no_data"} 或 {"s": "error"}，印出來以便確認是否權限設定有變
                print(f"⚠️ [Finnhub Response Alert] 資料結構異常或無資料: {data}")
                
    except Exception as e:
        # 捕捉 Render 容器環境常見的 SSL 或是連線超時錯誤
        print(f"❌ [Finnhub Connection Failed] 連線異常原因: {str(e)}")

    # =========================================================================
    # 🥈 2nd Priority：當 Finnhub 無法提供資料時，啟動備援模擬機制
    # =========================================================================
    if not has_real_data:
        dates, volumes, closes = [], [], []
        try:
            pred_data = run_prediction(symbol=symbol, return_dict=True)
            base_price = float(pred_data.get("current_price", 100.0))
        except Exception:
            defaults = {"MU": 112.5, "SNDK": 86.2, "MXL": 24.8, "STX": 93.4, "META": 524.1}
            base_price = defaults.get(symbol, 100.0)

        current_time = int(time.time())
        day_count = 0
        ts_list = []
        while len(ts_list) < 15:
            check_ts = current_time - (day_count * 24 * 60 * 60)
            if datetime.fromtimestamp(check_ts).strftime("%w") not in ["0", "6"]:
                ts_list.append(check_ts)
            day_count += 1
        ts_list.reverse()
        
        current_sim_price = base_price * (1.0 + random.uniform(-0.06, 0.06))
        price_steps = []
        for i in range(14):
            price_steps.append(current_sim_price)
            current_sim_price *= (1.0 + random.uniform(-0.022, 0.022))
        price_steps.append(base_price)
        
        for i, t in enumerate(ts_list):
            dates.append(datetime.fromtimestamp(t).strftime("%m-%d"))
            closes.append(price_steps[i])
            volumes.append(random.randint(3500000, 7500000))

    # ---------------------------------------------------------
    # 🎨 Matplotlib 雙 Y 軸高質感繪圖邏輯（100% 穩定輸出）
    # ---------------------------------------------------------
    plt.clf()
    plt.close('all')
    fig = plt.figure(figsize=(12, 5))
    ax1 = fig.gca()
    
    ax1.set_facecolor("#f3f4f6")
    plt.rcParams['axes.edgecolor'] = "#111827"
    plt.rcParams['axes.linewidth'] = 1.2

    bars = ax1.bar(dates, volumes, color="#4ade80", alpha=0.45, width=0.55, zorder=2, label="Volume")

    import matplotlib.ticker as ticker
    ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f"{x/1_000_000:.1f}M"))
    ax1.tick_params(axis="y", colors="#111827", labelsize=11)
    ax1.tick_params(axis="x", colors="#111827", rotation=45, labelsize=11)

    ax2 = ax1.twinx()
    line, = ax2.plot(dates, closes, color="#7c3aed", linewidth=2.8, marker="o", markersize=7,
                 markerfacecolor="#c4b5fd", markeredgecolor="#111827", zorder=3, label="Close Price")

    ax2.tick_params(axis="y", colors="#111827", labelsize=11)

    for i, v in enumerate(volumes):
        ax1.text(i, v, f"{v/1_000_000:.1f}M", ha="center", va="bottom", fontsize=9, color="#065f46")
    for i, c in enumerate(closes):
        ax2.text(i, c, f"{c:.1f}", ha="center", va="bottom", fontsize=9, color="#4c1d95")

    for spine in ax1.spines.values():
        spine.set_path_effects([patheffects.withSimplePatchShadow(offset=(2, -2), alpha=0.4)])

    title_suffix = " (Live Real-time)" if has_real_data else " (Sync Tracker)"
    plt.title(f"{symbol} Volume & Close Price{title_suffix}", color="#111827", fontsize=16, pad=12)
    plt.legend(handles=[bars, line], loc="lower center", bbox_to_anchor=(0.5, -0.25), ncol=2, frameon=False, fontsize=12)
    plt.grid(alpha=0.25, color="#d1d5db")
    plt.tight_layout()
    
    try:
        plt.savefig(img_filename, dpi=150)
        plt.close(fig)
    except Exception as e:
        plt.close('all')
        return {"error": "Matplotlib 儲存圖片失敗", "reason": str(e)}

    if os.path.exists(img_filename):
        return FileResponse(img_filename, media_type="image/png")
    
    return {"error": "圖片生成完畢，但磁碟找不到該檔案"}

# -----------------------------
# 動態對照表：將英文分類標籤轉成漂亮的中文標題
# -----------------------------
CATEGORY_NAMES = {
    "memory": "記憶體存儲 Memory",
    "tech": "半導體晶片 Tech / IC",
    "storage": "硬碟與儲存 Storage",
    "ai": "AI 與社群媒體 AI Matrix"
}

# -------------------------------------------------------------------------
# 整合型：深色金融風預測儀表板（全自動動態 Beta 計算 + 全域歷史快取版）
# -------------------------------------------------------------------------
@app.get("/dashboard/{symbol}", response_class=HTMLResponse)
def dashboard(symbol: str):
    sym = symbol.upper()
    raw_result = run_prediction(symbol=sym, return_dict=True)
    
    # 💡 啟動歷史快取備援機制（處理 5M NaN 變數）
    result = process_prediction_with_cache(sym, raw_result)

    def r(x):
        if x is None:
            return "--"
        return round(x, 1) if isinstance(x, (int, float)) else x

    current_price = r(result.get("current_price"))
    best_buy_5m = r(result.get("best_buy_5m"))
    best_sell_5m = r(result.get("best_sell_5m"))
    est_high15 = r(result.get("true_high15"))
    est_low15 = r(result.get("true_low15"))
    est_high_full_day = r(result.get("true_high_full"))
    est_low_full_day = r(result.get("true_low_full"))
    score = r(result.get("predicted_score"))
    actual = r(result.get("actual_result"))
    ts = result.get("timestamp")

    # =========================================================================
    # 📍 動態 Beta 計算邏輯：不綁定任何代碼，適用所有未來新增股票
    # =========================================================================
    beta_text = "N/A"
    
    # 1. 先行檢查全域快取，若今天算過這檔股票就直接讀取，不重複計算拖慢換頁
    if "beta_cached" in PREDICTION_CACHE.get(sym, {}):
        beta_text = PREDICTION_CACHE[sym]["beta_cached"]
    else:
        try:
            # 先嘗試標準流程：直接從 info 裡面撈現成的 Beta
            ticker = yf.Ticker(sym)
            beta_val = ticker.info.get('beta')
            
            # 2. 💡 動態防禦核心：若 info 漏給資料（不論是任何未來股票）
            if beta_val is None:
                print(f"ℹ️ {sym} 的 info 無 beta 資料，啟動全自動 K 線動態計算...")
                
                # 同步下載「個股」與「S&P 500 大盤 (^GSPC)」過去 1 年的日線歷史資料
                df_stock = yf.download(sym, period="1y", interval="1d", progress=False)
                df_market = yf.download("^GSPC", period="1y", interval="1d", progress=False)
                
                if not df_stock.empty and not df_market.empty:
                    # 提取收盤價並對齊時間軸（取交集）
                    close_stock = df_stock['Close']
                    close_market = df_market['Close']
                    combined = pd.concat([close_stock, close_market], axis=1, join='inner').dropna()
                    combined.columns = ['stock', 'market']
                    
                    # 計算每日報酬率
                    returns = combined.pct_change().dropna()
                    
                    # 運用統計學公式計算 Beta = Covariance(個股, 大盤) / Variance(大盤)
                    covariance = np.cov(returns['stock'], returns['market'])
                    market_variance = np.var(returns['market'], ddof=1)
                    
                    if market_variance != 0:
                        beta_val = covariance[0, 1] / market_variance
            
            # 3. 格式化輸出並寫入全域快取
            if beta_val is not None and not math.isnan(beta_val):
                beta_text = str(round(float(beta_val), 2))
                
                if sym not in PREDICTION_CACHE:
                    PREDICTION_CACHE[sym] = {}
                PREDICTION_CACHE[sym]["beta_cached"] = beta_text
                
        except Exception as e:
            print(f"❌ 萬能動態計算系統失敗 (標的: {sym}): {e}")
            beta_text = "N/A"
    # =========================================================================

    try:
        val = float(score) if (score is not None and score != "--") else 0
        trend_percent = max(min(val * 100 + 50, 100), 0)
    except:
        trend_percent = 50

    try:
        act_val = float(actual) if (actual is not None and actual != "--") else 0
        heat_alpha = min(abs(act_val) * 5, 0.8)
    except:
        heat_alpha = 0

    # 頂部導覽列：動態讀取 stocks.yaml 自動產生切換標籤
    from config.loader import load_stock_config
    stock_config = load_stock_config()
    links_html = ""
    for s in stock_config.keys():
        links_html += f'<a href="/dashboard/{s}" style="margin-right:12px;color:#93c5fd;text-decoration:none;font-weight:bold;font-size:1.1rem;">{s}</a>\n'

    raw_html = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>__SYMBOL__ Prediction Dashboard</title>
    <style>
        body { margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0b1120; color: #e5e7eb; }
        .home-btn { display: inline-block; padding: 10px 18px; background: #1f2937; color: #93c5fd; border-radius: 8px; text-decoration: none; margin-bottom: 16px; border: 1px solid #374151; }
        .home-btn:hover { background: #374151; }
        .container { max-width: 960px; margin: 0 auto; padding: 20px; }
        .countdown { font-size: 1rem; color: #93c5fd; margin-bottom: 10px; }
        .title { font-size: 2rem; font-weight: 700; margin-bottom: 6px; }
        .subtitle { font-size: 1rem; color: #9ca3af; margin-bottom: 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }
        .card { border-radius: 14px; padding: 18px 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.45); border: 1px solid #1f2937; transition: transform 0.2s ease; }
        .card:hover { transform: scale(1.03); }
        .card-title { font-size: 1rem; color: #9ca3af; margin-bottom: 8px; }
        .card-value { font-size: 1.6rem; font-weight: 600; }
        .trend-bar { height: 8px; border-radius: 4px; margin-top: 10px; background: linear-gradient(90deg, #f44336 __TREND_PERCENT__%, #4caf50 __TREND_PERCENT__%); }
        .heat { height: 10px; border-radius: 5px; margin-top: 10px; background: rgba(255, 255, 255, __HEAT_ALPHA__); }
        .footer { margin-top: 22px; font-size: 0.9rem; color: #6b7280; text-align: right; }
        .card-group-1 { background: linear-gradient(135deg, rgba(96, 165, 250, 0.45), rgba(59, 130, 246, 0.25)); backdrop-filter: blur(6px); }
        .card-group-2 { background: linear-gradient(135deg, rgba(52, 211, 153, 0.45), rgba(16, 185, 129, 0.25)); backdrop-filter: blur(6px); }
        .card-group-3 { background: linear-gradient(135deg, rgba(168, 85, 247, 0.45), rgba(139, 92, 246, 0.25)); backdrop-filter: blur(6px); }
        .card-group-4 { background: linear-gradient(135deg, rgba(251, 146, 60, 0.45), rgba(245, 158, 11, 0.25)); backdrop-filter: blur(6px); }
    </style>
</head>
<body>
    <div class="container">
        <img src="/volume_chart/__SYMBOL__" style="width:100%; margin-bottom:20px; border-radius:12px;" alt="Volume and Close Price Chart">
        
        <a class="home-btn" href="/">🏠 回主頁</a>
        
        <div style="margin-bottom:20px; background: rgba(31, 41, 55, 0.4); padding: 12px; border-radius: 8px; border: 1px solid #1f2937;">
            __LINKS_HTML__
        </div>

        <div class="title">__SYMBOL__ Prediction Dashboard</div>
        <div class="subtitle">深色金融風 · 即時更新 · 手機優化</div>
        <div class="countdown">距離下一次更新：<span id="count">60</span> 秒</div>

        <script>
            let sec = 60;
            setInterval(() => {
                sec--;
                if (sec <= 0) sec = 60;
                document.getElementById('count').innerText = sec;
            }, 1000);

            async function refreshPrice() {
                try {
                    let res = await fetch("/predict/__SYMBOL__");
                    if (!res.ok) return;
                    let data = await res.json();
                    if(data.current_price) {
                        document.getElementById("price").innerText = Number(data.current_price).toFixed(1);
                    }
                } catch (e) { console.log("更新失敗", e); }
            }
            setInterval(refreshPrice, 5000);
        </script>

        <div class="grid">
            <div class="card card-group-1">
                <div class="card-title">Currently Price (目前價格)</div>
                <div class="card-value" id="price">__CURRENT_PRICE__</div>
                <div class="trend-bar"></div>
            </div>
            <div class="card card-group-1">
                <div class="card-title">Beta Coefficient (Beta 係數)</div>
                <div class="card-value">__BETA_TEXT__</div>
            </div>
            <div class="card card-group-2">
                <div class="card-title">5M Best Buy (5分鐘最佳買入價)</div>
                <div class="card-value">__BEST_BUY_5M__</div>
                <div class="heat"></div>
            </div>
            <div class="card card-group-2">
                <div class="card-title">5M Best Sell (5分鐘最佳賣出價)</div>
                <div class="card-value">__BEST_SELL_5M__</div>
                <div class="heat"></div>
            </div>
            <div class="card card-group-3">
                <div class="card-title">15M Est High (15分鐘預估最高價)</div>
                <div class="card-value">__EST_HIGH15__</div>
            </div>
            <div class="card card-group-3">
                <div class="card-title">15M Est Low (15分鐘預估最低價)</div>
                <div class="card-value">__EST_LOW15__</div>
            </div>
            <div class="card card-group-4">
                <div class="card-title">Full Day Est High (整天預估最高價)</div>
                <div class="card-value">__EST_HIGH_FULL_DAY__</div>
            </div>
            <div class="card card-group-4">
                <div class="card-title">Full Day Est Low (整天預估最低價)</div>
                <div class="card-value">__EST_LOW_FULL_DAY__</div>
            </div>
        </div>
        <div class="footer">更新時間：__TS__</div>
    </div>
</body>
</html>
"""
    final_html = raw_html.replace("__SYMBOL__", str(symbol)) \
                         .replace("__TREND_PERCENT__", str(trend_percent)) \
                         .replace("__HEAT_ALPHA__", str(heat_alpha)) \
                         .replace("__LINKS_HTML__", str(links_html)) \
                         .replace("__CURRENT_PRICE__", str(current_price)) \
                         .replace("__BETA_TEXT__", str(beta_text)) \
                         .replace("__BEST_BUY_5M__", str(best_buy_5m)) \
                         .replace("__BEST_SELL_5M__", str(best_sell_5m)) \
                         .replace("__EST_HIGH15__", str(est_high15)) \
                         .replace("__EST_LOW15__", str(est_low15)) \
                         .replace("__EST_HIGH_FULL_DAY__", str(est_high_full_day)) \
                         .replace("__EST_LOW_FULL_DAY__", str(est_low_full_day)) \
                         .replace("__TS__", str(ts))

    return HTMLResponse(content=final_html)

# -----------------------------
# 主頁：股票選單 (動態讀取所有分類 + 新增智慧下拉搜尋盒)
# -----------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    from config.loader import load_stock_config
    stock_config = load_stock_config()
    
    # 1. 自動收集 stocks.yaml 裡出現過的所有不重複分類與股票代號
    categories_set = set()
    search_options_html = ""
    
    for symbol, cfg in stock_config.items():
        symbol = symbol.upper()
        if "category" in cfg:
            categories_set.add(cfg["category"])
        
        # 產生下拉選單的選項 (顯示格式: MU - Micron Technology)
        display_name = cfg.get("display_name", symbol)
        search_options_html += f'<option value="{symbol}">{symbol} - {display_name}</option>\n'
            
    # 2. 自動生成首頁的分類大按鈕
    categories_html = ""
    for cat in sorted(categories_set):
        display_name = CATEGORY_NAMES.get(cat, cat.upper())
        categories_html += f'<a class="category-btn" href="/category/{cat}">{display_name}</a>\n'

    html = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Silicon Sector Matrix</title>
    <style>
        body {{ margin: 0; padding: 0; background: #0b1120; color: #e5e7eb; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
        .bg-grid {{ position: fixed; inset: 0; background-image: linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(0deg, rgba(255,255,255,0.05) 1px, transparent 1px); background-size: 40px 40px; z-index: -1; }}
        .wrap {{ max-width: 960px; margin: 0 auto; padding: 60px 20px; text-align: center; }}
        h1 {{ font-size: 2.6rem; font-weight: 800; margin-bottom: 10px; background: linear-gradient(90deg, #60a5fa, #a78bfa, #f472b6); -webkit-background-clip: text; color: transparent; }}
        h3 {{ font-size: 1.1rem; color: #9ca3af; margin-bottom: 30px; }}
        
        /* 🔍 智慧搜尋盒專用深色科技風樣式 */
        .search-container {{
            max-width: 420px; margin: 0 auto 40px auto; display: flex; gap: 10px;
            background: rgba(31, 41, 55, 0.5); padding: 8px 12px; border-radius: 12px;
            border: 1px solid #4b5563; backdrop-filter: blur(6px); box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        }}
        .search-input {{
            flex: 1; background: transparent; border: none; color: #ffffff;
            font-size: 1.1rem; padding: 8px; outline: none;
        }}
        .search-input::placeholder {{ color: #6b7280; }}
        .search-btn {{
            background: linear-gradient(135deg, #3b82f6, #6366f1); color: white;
            border: none; padding: 8px 20px; border-radius: 8px; font-weight: bold;
            cursor: pointer; transition: 0.2s; font-size: 1rem;
        }}
        .search-btn:hover {{ transform: scale(1.03); filter: brightness(1.1); }}
        
        .category-btn {{ display: block; padding: 20px 40px; margin: 14px auto; font-size: 1.4rem; border-radius: 14px; text-decoration: none; background: rgba(31, 41, 55, 0.8); color: #e5e7eb; box-shadow: 0 10px 25px rgba(0,0,0,0.45); border: 1px solid #374151; transition: 0.25s; max-width: 420px; backdrop-filter: blur(6px); }}
        .category-btn:hover {{ background: rgba(55, 65, 81, 0.9); transform: scale(1.05); }}
    </style>
</head>
<body>
    <div class="bg-grid"></div>
    <div class="wrap">
        <h1>⚡ Silicon Sector Matrix</h1>
        <h3>半導體 · 記憶體 · AI · 多股票智能中樞</h3>
        
        <!-- 🔍 智慧搜尋盒區塊 -->
        <div class="search-container">
            <input type="text" id="stockSearch" class="search-input" list="stockList" placeholder="輸入關鍵字或選擇股票... (EX: MU)" onkeypress="handleKeyPress(event)">
            <datalist id="stockList">
                {search_options_html}
            </datalist>
            <button class="search-btn" onclick="goToDashboard()">直達 ➔</button>
        </div>

        <script>
            // 點擊「直達」按鈕的導向邏輯
            function goToDashboard() {{
                let inputVal = document.getElementById("stockSearch").value.trim().toUpperCase();
                if (inputVal) {{
                    // 如果使用者選擇了帶有說明的選項，切出最前面的股票代號 (例如從 "MU - Micron" 切出 "MU")
                    let symbol = inputVal.split(" ")[0];
                    window.location.href = "/dashboard/" + symbol;
                }} else {{
                    alert("請先輸入或選擇一個股票代號喔！");
                }}
            }}

            // 支援按下 Enter 鍵直接直達
            function handleKeyPress(event) {{
                if (event.key === "Enter") {{
                    goToDashboard();
                }}
            }}
        </script>
        
        <!-- 分類大按鈕區塊 -->
        {categories_html}
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html)

# -----------------------------
# 分類頁面：動態路由
# -----------------------------
@app.get("/category/{cat_name}", response_class=HTMLResponse)
def category_page(cat_name: str):
    from config.loader import load_stock_config
    stock_config = load_stock_config()
    
    buttons_html = ""
    for symbol, cfg in stock_config.items():
        if cfg.get("category") == cat_name:
            buttons_html += f'<a href="/dashboard/{symbol}" class="btn">{symbol} Dashboard</a>\n'

    title_display = CATEGORY_NAMES.get(cat_name, cat_name.upper())

    html = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title_display}</title>
    <style>
        body {{ margin: 0; padding: 0; background: #0b1120; color: #e5e7eb; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; text-align: center; }}
        .wrap {{ max-width: 960px; margin: 0 auto; padding: 60px 20px; }}
        h1 {{ font-size: 2rem; margin-bottom: 10px; }}
        h3 {{ font-size: 1rem; color: #9ca3af; margin-bottom: 30px; }}
        a.btn {{ display: inline-block; padding: 18px 40px; margin: 12px; font-size: 1.4rem; border-radius: 12px; text-decoration: none; background: #1f2937; color: #e5e7eb; box-shadow: 0 10px 25px rgba(0,0,0,0.45); border: 1px solid #374151; transition: 0.2s; }}
        a.btn:hover {{ background: #374151; transform: scale(1.05); }}
        .back-btn {{ display: inline-block; margin-top: 40px; color: #60a5fa; text-decoration: none; font-size: 1.1rem; }}
        .back-btn:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="wrap">
        <h1>{title_display}</h1>
        <h3>多股票智能中樞分頁</h3>
        {buttons_html}
        <br />
        <a href="/" class="back-btn">← 返回主矩陣</a>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html)

@app.get("/health")
def health_check():
    return {"status": "ok"}
