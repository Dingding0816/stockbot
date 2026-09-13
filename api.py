import requests
import matplotlib.pyplot as plt
import matplotlib.patheffects as patheffects
from datetime import datetime
from fastapi.responses import FileResponse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from run_daily_new_17 import run_prediction

# Finnhub API Key 設定
FINNHUB_API_KEY = "d9l0mr1r01qoc1b3psp0d9l0mr1r01qoc1b3pspg"

app = FastAPI(
    title="Stock Prediction API",
    description="MU / SNDK 多股票 AI 預估系統",
    version="2.0.0"
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
@app.get("/volume_chart/{symbol}")
def volume_chart(symbol: str):
    symbol = symbol.upper()
    
    # 這是標準且正確的 Finnhub K線 API 網址
    url = f"https://finnhub.io{symbol}&resolution=D&count=30&token={FINNHUB_API_KEY}"
    
    r = requests.get(url)
    data = r.json()

    # 預防 Finnhub 沒有回傳資料導致後續陣列切片崩潰
    if "t" not in data:
        return {"error": f"No data returned from Finnhub for {symbol}", "api_response": data}

    ts = data["t"][-15:]
    volumes = data["v"][-15:]
    closes = data["c"][-15:]
    dates = [datetime.fromtimestamp(t).strftime("%m-%d") for t in ts]

    plt.figure(figsize=(12, 5))

    # -----------------------------
    # 左軸：成交量（Volume）
    # -----------------------------
    ax1 = plt.gca()
    ax1.set_facecolor("#f3f4f6")
    plt.rcParams['axes.edgecolor'] = "#111827"
    plt.rcParams['axes.linewidth'] = 1.2

    # 綠色 Bar：成交量
    bars = ax1.bar(
        dates,
        volumes,
        color="#4ade80",
        alpha=0.45,
        width=0.55,
        zorder=2,
        label="Volume (成交量)"
    )

    import matplotlib.ticker as ticker
    ax1.yaxis.set_major_formatter(
        ticker.FuncFormatter(lambda x, pos: f"{x/1_000_000:.1f}M")
    )

    ax1.tick_params(axis="y", colors="#111827", labelsize=11)
    ax1.tick_params(axis="x", colors="#111827", rotation=45, labelsize=11)

    # -----------------------------
    # 右軸：收盤價（Close Price）
    # -----------------------------
    ax2 = ax1.twinx()

    line = ax2.plot(
        dates,
        closes,
        color="#7c3aed",
        linewidth=2.8,
        marker="o",
        markersize=7,
        markerfacecolor="#c4b5fd",
        markeredgecolor="#111827",
        zorder=3,
        label="Close Price (收盤價)"
    )[0]

    ax2.tick_params(axis="y", colors="#111827", labelsize=11)

    # -----------------------------
    # 資料標籤（每個點標上成交量 & 收盤價）
    # -----------------------------
    # Bar 標籤（成交量）
    for i, v in enumerate(volumes):
        ax1.text(
            i,
            v,
            f"{v/1_000_000:.1f}M",
            ha="center",
            va="bottom",
            fontsize=9,
            color="#065f46"
        )

    # Line 標籤（收盤價）
    for i, c in enumerate(closes):
        ax2.text(
            i,
            c,
            f"{c:.1f}",
            ha="center",
            va="bottom",
            fontsize=9,
            color="#4c1d95"
        )

    # -----------------------------
    # 圖加陰影（左軸）
    # -----------------------------
    for spine in ax1.spines.values():
        spine.set_path_effects([
            patheffects.withSimplePatchShadow(offset=(2, -2), alpha=0.4)
        ])

    # -----------------------------
    # 標題
    # -----------------------------
    plt.title(
        f"{symbol} Volume & Close Price",
        color="#111827",
        fontsize=16,
        pad=12
    )

    # -----------------------------
    # 圖例（放到整張圖的最下方，左右並排）
    # -----------------------------
    plt.legend(
        handles=[bars, line],
        loc="lower center",
        bbox_to_anchor=(0.5, -0.25),
        ncol=2,
        frameon=False,
        fontsize=12
    )

    plt.grid(alpha=0.25, color="#d1d5db")
    plt.tight_layout()

    plt.savefig(f"volume_chart_{symbol}.png", dpi=150)
    plt.close()

    return FileResponse(f"volume_chart_{symbol}.png")

# -----------------------------
# 主頁：股票選單
# -----------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    html = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Silicon Sector Matrix</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            background: #0b1120;
            color: #e5e7eb;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }
        /* 背景：高級科技線條 */
        .bg-grid {
            position: fixed;
            inset: 0;
            background-image:
                linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px),
                linear-gradient(0deg, rgba(255,255,255,0.05) 1px, transparent 1px);
            background-size: 40px 40px;
            z-index: -1;
        }
        .wrap {
            max-width: 960px;
            margin: 0 auto;
            padding: 60px 20px;
            text-align: center;
        }
        h1 {
            font-size: 2.6rem;
            font-weight: 800;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #60a5fa, #a78bfa, #f472b6);
            -webkit-background-clip: text;
            color: transparent;
        }
        h3 {
            font-size: 1.1rem;
            color: #9ca3af;
            margin-bottom: 40px;
        }
        .category-btn {
            display: block;
            padding: 20px 40px;
            margin: 14px auto;
            font-size: 1.4rem;
            border-radius: 14px;
            text-decoration: none;
            background: rgba(31, 41, 55, 0.8);
            color: #e5e7eb;
            box-shadow: 0 10px 25px rgba(0,0,0,0.45);
            border: 1px solid #374151;
            transition: 0.25s;
            max-width: 420px;
            backdrop-filter: blur(6px);
        }
        .category-btn:hover {
            background: rgba(55, 65, 81, 0.9);
            transform: scale(1.05);
        }
    </style>
</head>
<body>
    <div class="bg-grid"></div>
    <div class="wrap">
        <h1>⚡ Silicon Sector Matrix</h1>
        <h3>半導體 · 記憶體 · AI · 多股票智能中樞</h3>
        <!-- 記憶體存儲分類 -->
        <a class="category-btn" href="/category/memory">記憶體存儲 Memory</a>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html)

@app.get("/category/memory", response_class=HTMLResponse)
def category_memory():
    html = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Memory Stocks</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            background: #0b1120;
            color: #e5e7eb;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            text-align: center;
        }
        .wrap {
            max-width: 960px;
            margin: 0 auto;
            padding: 60px 20px;
        }
        h1 {
            font-size: 2rem;
            margin-bottom: 10px;
        }
        h3 {
            font-size: 1rem;
            color: #9ca3af;
            margin-bottom: 30px;
        }
        a.btn {
            display: inline-block;
            padding: 18px 40px;
            margin: 12px;
            font-size: 1.4rem;
            border-radius: 12px;
            text-decoration: none;
            background: #1f2937;
            color: #e5e7eb;
            box-shadow: 0 10px 25px rgba(0,0,0,0.45);
            border: 1px solid #374151;
            transition: 0.2s;
        }
        a.btn:hover {
            background: #374151;
            transform: scale(1.05);
        }
        .back-btn {
            display: inline-block;
            margin-top: 40px;
            color: #60a5fa;
            text-decoration: none;
            font-size: 1.1rem;
        }
        .back-btn:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="wrap">
        <h1>記憶體存儲 Memory</h1>
        <h3>分類：記憶體 · DRAM · NAND</h3>
        
        <a href="/volume_chart/MU" class="btn">MU Dashboard</a>
        <a href="/volume_chart/SNDK" class="btn">SNDK Dashboard</a>
        <a href="/volume_chart/MXL" class="btn">MXL Dashboard</a>
        
        <br />
        <a href="/" class="back-btn">← 返回主矩陣</a>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html)
