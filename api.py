from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from run_daily_new_17 import run_prediction

from linebot import LineBotApi, WebhookParser
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = FastAPI(
    title="MU Prediction API",
    description="Micron (MU) AI 預估系統 API",
    version="1.0.0"
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
# MU Prediction API
# -----------------------------
@app.get("/mu/predict")
def mu_predict():
    return run_prediction(return_dict=True)

@app.get("/", response_class=HTMLResponse)
def home():
    result = run_prediction(return_dict=True)

    def r(x):
        return round(x, 1) if isinstance(x, (int, float)) else x

    # 取修正後的值（true_xxx）
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

    # 方向文字與顏色
    direction_text = "持平"
    direction_color = "#cccccc"
    if score > 0:
        direction_text = "上漲 📈"
        direction_color = "#4caf50"
    elif score < 0:
        direction_text = "下跌 📉"
        direction_color = "#f44336"

    # ⭐⭐⭐ CSS 需要的計算值（提前算好）
    trend_percent = max(min(score * 100 + 50, 100), 0)
    heat_alpha = min(abs(actual) * 5, 0.8)

    html = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>MU Prediction Dashboard</title>

    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #0b1120;
            color: #e5e7eb;
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

        /* 趨勢條 */
        .trend-bar {{
            height: 8px;
            border-radius: 4px;
            margin-top: 10px;
            background: linear-gradient(90deg,
                #f44336 {trend_percent}%,
                #4caf50 {trend_percent}%
            );
        }}

        /* 波動熱度 */
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

        @media (max-width: 600px) {{
            .title {{
                font-size: 1.6rem;
            }}
            .card-value {{
                font-size: 1.4rem;
            }}
        }}
    </style>
</head>

<body>
    <div class="container">
        <div class="title">MU Prediction Dashboard</div>
        <div class="subtitle">深色金融風 · 儀表板 · 手機優化 · 高級版</div>

        <div class="grid">

            <!-- 組 1 -->
            <div class="card card-group-1">
                <div class="card-title">目前價格</div>
                <div class="card-value">{current_price}</div>
                <div class="trend-bar"></div>
            </div>

            <div class="card card-group-1">
                <div class="card-title">預估方向</div>
                <div class="card-value direction">{direction_text}</div>
                <div style="
                    width: 80px;
                    height: 80px;
                    border-radius: 50%;
                    border: 6px solid #1f2937;
                    border-top-color: {direction_color};
                    margin: 12px auto 0 auto;
                    transform: rotate({score * 180}deg);
                    transition: transform 0.6s ease;
                "></div>
            </div>

            <!-- 組 2 -->
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

            <!-- 組 3 -->
            <div class="card card-group-3">
                <div class="card-title">15 分鐘最高價</div>
                <div class="card-value">{est_high15}</div>
            </div>

            <div class="card card-group-3">
                <div class="card-title">15 分鐘最低價</div>
                <div class="card-value">{est_low15}</div>
            </div>

            <!-- 組 4 -->
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

# -----------------------------
# LINE Webhook
# -----------------------------
line_bot_api = LineBotApi("YOUR_LINE_TOKEN")
parser = WebhookParser("YOUR_LINE_SECRET")

@app.post("/callback")
async def callback(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Line-Signature")

    try:
        events = parser.parse(body.decode("utf-8"), signature)
    except Exception as e:
        print("Signature error:", e)
        return "OK"

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessage):
            text = event.message.text.strip().lower()

            if text == "run":
                try:
                    result = run_prediction(return_dict=True)

                    def r(x):
                        return round(x, 1) if isinstance(x, (int, float)) else x

                    score = result.get("predicted_score", 0)
                    if score > 0:
                        direction = "上漲 📈"
                    elif score < 0:
                        direction = "下跌 📉"
                    else:
                        direction = "持平"

                    msg = (
                        f"📊 MU 預估結果\n"
                        f"方向：{direction}\n"
                        f"5 分鐘最佳買入價：{r(result.get('best_buy_5m'))}\n"
                        f"5 分鐘最佳賣出價：{r(result.get('best_sell_5m'))}\n"
                        f"15 分鐘最高價：{r(result.get('true_high15'))}\n"
                        f"15 分鐘最低價：{r(result.get('true_low15'))}\n"
                        f"全日預估最高價：{r(result.get('true_high_full'))}\n"
                        f"全日預估最低價：{r(result.get('true_low_full'))}\n"
                        f"預估分數：{r(score)}\n"
                        f"實際結果：{r(result.get('actual_result'))}\n"
                        f"時間：{result.get('timestamp')}"
                    )

                except Exception as e:
                    msg = f"❌ 執行 run 時發生錯誤：{e}"

                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
                continue

            reply = f"你說：{text}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

    return "OK"
