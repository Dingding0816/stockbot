from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from run_daily_new_17 import run_prediction

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
    <title>Stock Prediction Dashboard</title>
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
            font-size:2.2rem;
            margin-bottom:10px;
        }
        h3 {
            font-size:1.1rem;
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
    </style>
</head>
<body>
    <div class="wrap">
        <h1>📈 多股票 AI 預估系統</h1>
        <h3>深色金融風 · 儀表板 · 手機優化 · 高級版</h3>

        <a class="btn" href="/dashboard/MU">MU Prediction Dashboard</a>
        <a class="btn" href="/dashboard/SNDK">SNDK Prediction Dashboard</a>
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
    direction_color = "#cccccc"
    if score > 0:
        direction_text = "上漲 📈"
        direction_color = "#4caf50"
    elif score < 0:
        direction_text = "下跌 📉"
        direction_color = "#f44336"

    trend_percent = max(min(score * 100 + 50, 100), 0)
    heat_alpha = min(abs(actual) * 5, 0.8)

    html = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />

    <!-- ⭐ 自動每分鐘更新 -->
    <meta http-equiv="refresh" content="60">

    <title>{symbol} Prediction Dashboard</title>

    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #0b1120;
            color: #e5e7eb;
        }}

        /* 回主頁按鈕 */
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

        /* 四組卡片底色 */
        .card-group-1 {{ 
            background: linear-gradient(135deg, rgba(96, 165, 250, 0.45), rgba(59, 130, 246, 0.25)) !important;
            backdrop-filter: blur(6px);
        }}
        .card-group-2 {{ 
            background: linear-gradient(135deg, rgba(52, 211, 153, 0.45), rgba(16, 185, 129, 0.25)) !important;
            backdrop-filter: blur(6px);
        }}
        .card-group-3 {{ 
            background: linear-gradient(135deg, rgba(168, 85, 247, 0.45), rgba(139, 92, 246, 0.25)) !important;
            backdrop-filter: blur(6px);
        }}
        .card-group-4 {{ 
            background: linear-gradient(135deg, rgba(251, 146, 60, 0.45), rgba(245, 158, 11, 0.25)) !important;
            backdrop-filter: blur(6px);
        }}

        .container {{
            max-width: 960px;
            margin: 0 auto;
            padding: 20px;
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
    </style>
</head>

<body>
    <div class="container">

        <!-- ⭐ 回主頁按鈕 -->
        <a class="home-btn" href="/">🏠 回主頁</a>

        <!-- 股票切換 -->
        <div style="margin-bottom:16px;">
            <a href="/dashboard/MU" style="margin-right:8px;color:#93c5fd;text-decoration:none;">MU</a>
            <a href="/dashboard/SNDK" style="color:#93c5fd;text-decoration:none;">SNDK</a>
        </div>

        <div class="title">{symbol} Prediction Dashboard</div>
        <div class="subtitle">深色金融風 · 儀表板 · 手機優化 · 高級版</div>

        <div class="grid">

            <div class="card card-group-1">
                <div class="card-title">目前價格</div>
                <div class="card-value">{current_price}</div>
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
