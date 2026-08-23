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
            user_msg = event.message.text
            reply = f"你說：{user_msg}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

    return "OK"
