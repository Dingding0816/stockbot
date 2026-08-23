from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from run_daily_new_17 import run_prediction   # ← 改成你的主程式檔名

app = FastAPI(
    title="MU Prediction API",
    description="Micron (MU) AI 預估系統 API",
    version="1.0.0"
)

# 允許所有前端（Web App）連線
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 你之後可以改成你的網域
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------
# 1️⃣ 主要 API：取得最新 MU 預估結果
# -----------------------------------------
@app.get("/mu/predict")
def mu_predict():
    """
    回傳最新 MU 預估結果（不推播、不寫 CSV）
    """
    return run_prediction(return_dict=True)


# -----------------------------------------
# 2️⃣ 健康檢查（給部署平台用）
# -----------------------------------------
@app.get("/health")
def health_check():
    return {"status": "ok"}

from fastapi import Request
from linebot import LineBotApi, WebhookParser
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# 你的 LINE Channel Access Token & Secret
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
            user_msg = event.message.text
            reply = f"你說：{user_msg}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

    return "OK"
