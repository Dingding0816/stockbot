from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
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
    
@app.get("/")
def home():
    result = run_prediction(return_dict=True)

    # 四捨五入到小數點後一位
    def r(x):
        return round(x, 1) if isinstance(x, (int, float)) else x

    return {
        "message": "MU Prediction Dashboard",
        "current_price": r(result.get("current_price")),
        "未來5分鐘最佳買入價": r(result.get("best_buy_5m")),
        "未來5分鐘最佳賣出價格": r(result.get("best_sell_5m")),
        "未來15分鐘預估最高價": r(result.get("est_high15")),
        "未來15分鐘預估最低價": r(result.get("est_low15")),
        "全日預估最高價": r(result.get("est_high_full_day")),
        "全日預估最低價": r(result.get("est_low_full_day")),
        "預估分數(predicted_score)": r(result.get("predicted_score")),
        "實際結果(actual_result)": r(result.get("actual_result")),
        "timestamp": result.get("timestamp")
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}

# -----------------------------
# LINE Webhook
# -----------------------------
line_bot_api = LineBotApi("VK2OUm7lcUnjgIhnLElhzimTFuUOyWQ80XaaNVDpDPLOkbTtWxN9wjos8qcSQq9u64BNAY3ktCy4KvdoXZoMHPZUXAOeHLhkDMhOyw+kehYL4G7J7ALBeoi8DOsUL2seKahQttVSupNgeORM28AtXwdB04t89/1O/w1cDnyilFU=")
parser = WebhookParser("cdc8af606209cd1485a292ca8a9cc7f0")

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

            # ===== run 指令 =====
            if text == "run":
                try:
                    result = run_prediction(return_dict=True)

                    # 四捨五入到小數點後一位
                    def r(x):
                        return round(x, 1) if isinstance(x, (int, float)) else x

                    # 自動判斷方向（用 predicted_score）
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
                        f"15 分鐘最高價：{r(result.get('est_high15'))}\n"
                        f"15 分鐘最低價：{r(result.get('est_low15'))}\n"
                        f"全日預估最高價：{r(result.get('est_high_full_day'))}\n"
                        f"全日預估最低價：{r(result.get('est_low_full_day'))}\n"
                        f"預估分數：{r(score)}\n"
                        f"實際結果：{r(result.get('actual_result'))}\n"
                        f"時間：{result.get('timestamp')}"
                    )

                except Exception as e:
                    msg = f"❌ 執行 run 時發生錯誤：{e}"

                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
                continue

            # ===== 其他訊息 =====
            reply = f"你說：{text}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

    return "OK"
