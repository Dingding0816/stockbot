import requests
import matplotlib.pyplot as plt
from datetime import datetime
from fastapi.responses import FileResponse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from run_daily_new_17 import run_prediction
FINNHUB_API_KEY = "d9l0mr1r01qoc1b3psp0d9l0mr1r01qoc1b3pspg"


app = FastAPI(
    title="Stock Prediction API",
    description="MU / SNDK 多股票 AI 預估系統",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# 多股票 API
# -----------------------------
@app.get("/predict/{symbol}")
def predict_symbol(symbol: str):
    return run_prediction(symbol=symbol.upper(), return_dict=True)

@app.get("/volume_chart/{symbol}")
def volume_chart(symbol: str):
    symbol = symbol.upper()
    url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=D&count=30&token={FINNHUB_API_KEY}"
    r = requests.get(url)
    data = r.json()

    ts = data["t"][-15:]
    volumes = data["v"][-15:]
    closes = data["c"][-15:]   # 收盤價
    dates = [datetime.fromtimestamp(t).strftime("%m-%d") for t in ts]

    plt.figure(figsize=(12,5))

    # -----------------------------
    # 金屬風背景（深色漸層）
    # -----------------------------
    ax = plt.gca()
    ax.set_facecolor("#1a1a1a")  # 深金屬底色
    plt.rcParams['axes.edgecolor'] = "#888888"
    plt.rcParams['axes.linewidth'] = 1.2

    # -----------------------------
    # 折線圖（成交量）
    # -----------------------------
    plt.plot(
        dates,
        volumes,
        color="#00eaff",
        linewidth=3,
        marker="o",
        markersize=6,
        markerfacecolor="#00eaff",
        markeredgecolor="#ffffff"
    )

    # -----------------------------
    # Bar 圖（每日收盤價）
    # -----------------------------
    plt.bar(
        dates,
        closes,
        color="#ffaa33",
        alpha=0.35,
        width=0.5,
        label="收盤價"
    )

    # -----------------------------
    # Y 軸格式化（去掉 1e7）
    # -----------------------------
    import matplotlib.ticker as ticker
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f"{x/1_000_000:.1f}M"))

    # -----------------------------
    # 標題 + 美化
    # -----------------------------
    plt.title(f"{symbol} Volume & Close Price", color="#e5e7eb", fontsize=14)
    plt.xticks(rotation=45, color="#e5e7eb")
    plt.yticks(color="#e5e7eb")
    plt.grid(alpha=0.2)

    plt.tight_layout()
    plt.savefig("volume_chart.png", dpi=150)
    plt.close()

    return FileResponse("volume_chart.png")



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

        <!-- 未來分類（你可以自由新增） -->
        <!--
        <a class="category-btn" href="/category/cpu">CPU</a>
        <a class="category-btn" href="/category/gpu">GPU</a>
        <a class="category-btn" href="/category/ai">AI 加速器</a>
        -->
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
            background:#0b1120;
            color:#e5e7eb;
            font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            text-align:center;
        }
        .wrap {
            max-width: 960px;
            margin: 0 auto;
            padding: 60px 20px;
        }
        h1 {
            font-size:2rem;
            margin-bottom:10px;
        }
        h3 {
            font-size:1rem;
            color:#9ca3af;
            margin-bottom:30px;
        }
        a.btn {
            display:inline-block;
            padding:18px 40px;
            margin:12px;
            font-size:1.4rem;
            border-radius:12px;
            text-decoration:none;
            background:#1f2937;
            color:#e5e7eb;
            box-shadow:0 10px 25px rgba(0,0,0,0.45);
            border:1px solid #374151;
            transition:0.2s;
        }
        a.btn:hover {
            background:#374151;
            transform:scale(1.05);
        }
        .back-btn {
            display:inline-block;
            margin-top:20px;
            color:#93c5fd;
            text-decoration:none;
        }
    </style>
</head>
<body>
    <div class="wrap">
        <h1>記憶體存儲 Memory</h1>
        <h3>分類：記憶體 · DRAM · NAND</h3>

        <a class="btn" href="/dashboard/MU">MU Dashboard</a>
        <a class="btn" href="/dashboard/SNDK">SNDK Dashboard</a>

        <br>
        <a class="back-btn" href="/">⬅ 回主頁</a>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html)

# -----------------------------
# 多股票 Dashboard（深色金融風）
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
    if score > 0:
        direction_text = "上漲 📈"
    elif score < 0:
        direction_text = "下跌 📉"

    trend_percent = max(min(score * 100 + 50, 100), 0)
    heat_alpha = min(abs(actual) * 5, 0.8)

    html = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />

    <title>{symbol} Prediction Dashboard</title>

    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #0b1120;
            color: #e5e7eb;
        }}

        .home-btn {{
            display:inline-block;
            padding:10px 18px;
            background:#1f2937;
            color:#93c5fd;
            border-radius:8px;
            text-decoration:none;
            margin-bottom:16px;
            border:1px solid #374151;
        }}

        .home-btn:hover {{
            background:#374151;
        }}

        .container {{
            max-width: 960px;
            margin: 0 auto;
            padding: 20px;
        }}

        .countdown {{
            font-size: 1rem;
            color: #93c5fd;
            margin-bottom: 10px;
        }}

        .title {{
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 6px;
        }}

        .subtitle {{
            font-size: 1rem;
            color: #9ca3af;
            margin-bottom: 20px;
        }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 16px;
        }}

        .card {{
            border-radius: 14px;
            padding: 18px 20px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.45);
            border: 1px solid #1f2937;
            transition: transform 0.2s ease;
        }}

        .card:hover {{
            transform: scale(1.03);
        }}

        .card-title {{
            font-size: 1rem;
            color: #9ca3af;
            margin-bottom: 8px;
        }}

        .card-value {{
            font-size: 1.6rem;
            font-weight: 600;
        }}

        .trend-bar {{
            height: 8px;
            border-radius: 4px;
            margin-top: 10px;
            background: linear-gradient(90deg,
                #f44336 {trend_percent}%,
                #4caf50 {trend_percent}%
            );
        }}

        .heat {{
            height: 10px;
            border-radius: 5px;
            margin-top: 10px;
            background: rgba(255, 255, 255, {heat_alpha});
        }}

        .footer {{
            margin-top: 22px;
            font-size: 0.9rem;
            color: #6b7280;
            text-align: right;
        }}

        .card-group-1 {{
            background: linear-gradient(135deg, rgba(96, 165, 250, 0.45), rgba(59, 130, 246, 0.25));
            backdrop-filter: blur(6px);
        }}
        .card-group-2 {{
            background: linear-gradient(135deg, rgba(52, 211, 153, 0.45), rgba(16, 185, 129, 0.25));
            backdrop-filter: blur(6px);
        }}
        .card-group-3 {{
            background: linear-gradient(135deg, rgba(168, 85, 247, 0.45), rgba(139, 92, 246, 0.25));
            backdrop-filter: blur(6px);
        }}
        .card-group-4 {{
            background: linear-gradient(135deg, rgba(251, 146, 60, 0.45), rgba(245, 158, 11, 0.25));
            backdrop-filter: blur(6px);
        }}
    </style>
</head>

<body>
    <div class="container">
        <!-- 成交量圖（新增這一行） -->
        <img src="/volume_chart/{symbol}" style="width:100%; margin-bottom:20px; border-radius:12px;">
        
        <a class="home-btn" href="/">🏠 回主頁</a>

        <div style="margin-bottom:16px;">
            <a href="/dashboard/MU" style="margin-right:8px;color:#93c5fd;text-decoration:none;">MU</a>
            <a href="/dashboard/SNDK" style="color:#93c5fd;text-decoration:none;">SNDK</a>
        </div>

        <div class="title">{symbol} Prediction Dashboard</div>
        <div class="subtitle">深色金融風 · 即時更新 · 手機優化</div>

        <!-- 倒數計時 -->
        <div class="countdown">距離下一次更新：<span id="count">60</span> 秒</div>

        <script>
            // 倒數計時
            let sec = 60;
            setInterval(() => {{
                sec--;
                if (sec <= 0) sec = 60;
                document.getElementById('count').innerText = sec;
            }}, 1000);

            // 即時跳動價格（每 5 秒抓一次 API）
            async function refreshPrice() {{
                try {{
                    let res = await fetch("/predict/{symbol}");
                    let data = await res.json();

                    document.getElementById("price").innerText = data.current_price.toFixed(1);
                }} catch (e) {{
                    console.log("更新失敗", e);
                }}
            }}

            setInterval(refreshPrice, 5000);
        </script>

        <div class="grid">

            <div class="card card-group-1">
                <div class="card-title">目前價格</div>
                <div class="card-value" id="price">{current_price}</div>
                <div class="trend-bar"></div>
            </div>

            <div class="card card-group-1">
                <div class="card-title">預估方向</div>
                <div class="card-value">{direction_text}</div>
            </div>

            <div class="card card-group-2">
                <div class="card-title">5 分鐘最佳買入價</div>
                <div class="card-value">{best_buy_5m}</div>
                <div class="heat"></div>
            </div>

            <div class="card card-group-2">
                <div class="card-title">5 分鐘最佳賣出價</div>
                <div class="card-value">{best_sell_5m}</div>
                <div class="heat"></div>
            </div>

            <div class="card card-group-3">
                <div class="card-title">15 分鐘最高價</div>
                <div class="card-value">{est_high15}</div>
            </div>

            <div class="card card-group-3">
                <div class="card-title">15 分鐘最低價</div>
                <div class="card-value">{est_low15}</div>
            </div>

            <div class="card card-group-4">
                <div class="card-title">全日預估最高價</div>
                <div class="card-value">{est_high_full_day}</div>
            </div>

            <div class="card card-group-4">
                <div class="card-title">全日預估最低價</div>
                <div class="card-value">{est_low_full_day}</div>
            </div>

        </div>

        <div class="footer">
            更新時間：{ts}
        </div>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html)

@app.get("/health")
def health_check():
    return {"status": "ok"}
