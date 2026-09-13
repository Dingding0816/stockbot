import os
import requests
import matplotlib
matplotlib.use('Agg')  # 強制指定 Linux 伺服器專用無介面繪圖模式，解決 savefig 崩潰
import matplotlib.pyplot as plt
import matplotlib.patheffects as patheffects
from datetime import datetime, timedelta
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from run_daily_new_17 import run_prediction

# 全自動讀取 Render 後台寫入的頂級付費金鑰，徹底防止字串拼接裁切錯誤
import os
FINNHUB_API_KEY = os.getenv("FINNHUB_TOKEN", "d9l0mr1r01qoc1b3psp0d9l0mr1r01qoc1b3pspg")

app = FastAPI(
    title="Stock Prediction API",
    description="MU / SNDK / MXL / STX / META 多股票 AI 預估系統",
    version="2.1.0"
)

# 允許跨網域存取 (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# 多股票 預測 API 端點
# -----------------------------
@app.get("/predict/{symbol}")
def predict_symbol(symbol: str):
    return run_prediction(symbol=symbol.upper(), return_dict=True)

# -----------------------------
# 動態成交量與收盤價圖表產生器
# -----------------------------
@app.get("/volume_chart/{symbol}")
def volume_chart(symbol: str):
    symbol = symbol.upper()
    img_filename = f"/tmp/volume_chart_{symbol}.png"
    
    # 智慧快取機制：6 小時內有圖直接回傳，極致節省付費額度
    if os.path.exists(img_filename):
        file_age = time.time() - os.path.getmtime(img_filename)
        if file_age < 21600:
            return FileResponse(img_filename, media_type="image/png")

    has_data = False
    dates, volumes, closes = [], [], []

    # ======= ⚡ 【時區與休市終極對齊】精準計算上一個有效的美股開盤日 =======
    base_url = "https://finnhub.io"
    
    # 1. 取得目前的 UTC 時間 (美股主要對齊 UTC)
    now_utc = datetime.utcnow()
    
    # 2. 如果今天是週末 (週六或週日)，或者今天還沒到美股收盤時間
    # 我們將結束時間「強行固定在上週五美股收盤時間 (UTC 約晚上 21:00)」
    if now_utc.weekday() == 5:    # 週六
        last_trade_date = now_utc - timedelta(days=1)
    elif now_utc.weekday() == 6:  # 週日
        last_trade_date = now_utc - timedelta(days=2)
    else:
        # 平日如果還沒開盤或正在盤中，保險起見也往前推 1 天抓完整的前一日歷史數據
        last_trade_date = now_utc - timedelta(days=1)
        
    # 將計算好的標準開盤日轉成 Finnhub 規定接收的 UNIX 時間戳記
    to_time = int(datetime(last_trade_date.year, last_trade_date.month, last_trade_date.day, 21, 0, 0).timestamp())
    from_time = to_time - (35 * 24 * 60 * 60)  # 往前推 35 天，確保一定有足夠的 15 筆交易日資料

    # 自動優先讀取您在 Render 後台設定的頂級付費金鑰 (FINNHUB_TOKEN)
    token = os.getenv("FINNHUB_TOKEN", "d9l0mr1r01qoc1b3psp0d9l0mr1r01qoc1b3pspg")

    query_params = {
        "symbol": symbol,
        "resolution": "D",
        "from": from_time,
        "to": to_time,
        "token": token
    }
    
    try:
        r = requests.get(base_url, params=query_params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data.get("s") == "ok" and "t" in data and data["t"] and len(data["t"]) > 0:
                ts = data["t"][-15:]
                volumes = data["v"][-15:]
                closes = data["c"][-15:]
                dates = [datetime.fromtimestamp(t).strftime("%m-%d") for t in ts]
                if len(dates) > 0:
                    has_data = True
    except Exception:
        pass

    # ---------------------------------------------------------
    # 🎨 Matplotlib 繪圖邏輯（100% 呈現真實市場歷史走勢）
    # ---------------------------------------------------------
    plt.clf()
    plt.close('all')
    fig = plt.figure(figsize=(12, 5))
    ax1 = fig.gca()
    
    if has_data:
        # ======= 狀況 A：歷史資料完全釋放，點亮最精美的趨勢圖 =======
        ax1.set_facecolor("#f3f4f6")
        plt.rcParams['axes.edgecolor'] = "#111827"
        plt.rcParams['axes.linewidth'] = 1.2

        bars = ax1.bar(dates, volumes, color="#4ade80", alpha=0.45, width=0.55, zorder=2, label="Volume")

        import matplotlib.ticker as ticker
        ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f"{x/1_000_000:.1f}M"))
        ax1.tick_params(axis="y", colors="#111827", labelsize=11)
        ax1.tick_params(axis="x", colors="#111827", rotation=45, labelsize=11)

        ax2 = ax1.twinx()
        line = ax2.plot(dates, closes, color="#7c3aed", linewidth=2.8, marker="o", markersize=7,
                        markerfacecolor="#c4b5fd", markeredgecolor="#111827", zorder=3, label="Close Price")
        ax2.tick_params(axis="y", colors="#111827", labelsize=11)

        for i, v in enumerate(volumes):
            ax1.text(i, v, f"{v/1_000_000:.1f}M", ha="center", va="bottom", fontsize=9, color="#065f46")
        for i, c in enumerate(closes):
            ax2.text(i, c, f"{c:.1f}", ha="center", va="bottom", fontsize=9, color="#4c1d95")

        for spine in ax1.spines.values():
            spine.set_path_effects([patheffects.withSimplePatchShadow(offset=(2, -2), alpha=0.4)])

        plt.title(f"{symbol} Volume & Close Price", color="#111827", fontsize=16, pad=12)
        plt.legend(handles=[bars, line], loc="lower center", bbox_to_anchor=(0.5, -0.25), ncol=2, frameon=False, fontsize=12)
        plt.grid(alpha=0.25, color="#d1d5db")
        
    else:
        # ======= 狀況 B：防禦安全提示面板 =======
        ax1.set_facecolor("#111827")
        ax1.get_xaxis().set_visible(False)
        ax1.get_yaxis().set_visible(False)
        for spine in ax1.spines.values():
            spine.set_visible(False)
        
        plt.text(0.5, 0.6, f"{symbol} Historical Chart", ha="center", va="center", fontsize=18, color="#ffffff", fontweight="bold")
        plt.text(0.5, 0.4, "Finnhub API responding empty. Please try refresh.", ha="center", va="center", fontsize=12, color="#9ca3af")
        plt.title(f"{symbol} - Dashboard Status", color="#ffffff", fontsize=14, pad=12)

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

# -----------------------------
# 整合型：深色金融風預測儀表板（安全字串替換版）
# -----------------------------
@app.get("/dashboard/{symbol}", response_class=HTMLResponse)
def dashboard(symbol: str):
    symbol = symbol.upper()
    result = run_prediction(symbol=symbol, return_dict=True)

    def r(x):
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

    direction_text = "持平"
    if score is not None:
        if score > 0:
            direction_text = "上漲 📈"
        elif score < 0:
            direction_text = "下跌 📉"

    trend_percent = max(min((score if score is not None else 0) * 100 + 50, 100), 0)
    heat_alpha = min(abs(actual if actual is not None else 0) * 5, 0.8)

    # 頂部導覽列：動態讀取 stocks.yaml 自動產生切換標籤
    from config.loader import load_stock_config
    stock_config = load_stock_config()
    links_html = ""
    for sym in stock_config.keys():
        links_html += f'<a href="/dashboard/{sym}" style="margin-right:12px;color:#93c5fd;text-decoration:none;font-weight:bold;font-size:1.1rem;">{sym}</a>\n'

    # 使用標準 HTML 原始碼，不使用容易出錯的 f-string 大括號
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
        <!-- 橫跨整張網頁的精美歷史圖表，完美安置在最上方 -->
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
                <div class="card-title">Direction (預估方向)</div>
                <div class="card-value">__DIRECTION_TEXT__</div>
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
    # 用安全、精準的 .replace() 逐一塞入變數，徹底斷絕大括號錯位 Bug
    final_html = raw_html.replace("__SYMBOL__", str(symbol)) \
                         .replace("__TREND_PERCENT__", str(trend_percent)) \
                         .replace("__HEAT_ALPHA__", str(heat_alpha)) \
                         .replace("__LINKS_HTML__", str(links_html)) \
                         .replace("__CURRENT_PRICE__", str(current_price)) \
                         .replace("__DIRECTION_TEXT__", str(direction_text)) \
                         .replace("__BEST_BUY_5M__", str(best_buy_5m)) \
                         .replace("__BEST_SELL_5M__", str(best_sell_5m)) \
                         .replace("__EST_HIGH15__", str(est_high15)) \
                         .replace("__EST_LOW15__", str(est_low15)) \
                         .replace("__EST_HIGH_FULL_DAY__", str(est_high_full_day)) \
                         .replace("__EST_LOW_FULL_DAY__", str(est_low_full_day)) \
                         .replace("__TS__", str(ts))

    return HTMLResponse(content=final_html)

# -----------------------------
# 主頁：股票選單 (動態讀取所有分類)
# -----------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    from config.loader import load_stock_config
    stock_config = load_stock_config()
    
    categories_set = set()
    for cfg in stock_config.values():
        if "category" in cfg:
            categories_set.add(cfg["category"])
            
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
        h3 {{ font-size: 1.1rem; color: #9ca3af; margin-bottom: 40px; }}
        .category-btn {{ display: block; padding: 20px 40px; margin: 14px auto; font-size: 1.4rem; border-radius: 14px; text-decoration: none; background: rgba(31, 41, 55, 0.8); color: #e5e7eb; box-shadow: 0 10px 25px rgba(0,0,0,0.45); border: 1px solid #374151; transition: 0.25s; max-width: 420px; backdrop-filter: blur(6px); }}
        .category-btn:hover {{ background: rgba(55, 65, 81, 0.9); transform: scale(1.05); }}
    </style>
</head>
<body>
    <div class="bg-grid"></div>
    <div class="wrap">
        <h1>⚡ Silicon Sector Matrix</h1>
        <h3>半導體 · 記憶體 · AI · 多股票智能中樞</h3>
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
