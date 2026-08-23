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
