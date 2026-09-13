from fastapi import FastAPI
from config.loader import load_stock_config

# 依照你的專案結構，這裡放你的模型
# 如果你的模型檔案名稱不同，告訴我，我會幫你調整
from models.memory_model import MemoryModel
from models.tech_model import TechModel

app = FastAPI()

# 讀取 stocks.yaml
STOCK_CONFIG = load_stock_config()

# 建立模型註冊表
MODEL_REGISTRY = {}

for symbol, cfg in STOCK_CONFIG.items():
    model_type = cfg.get("model_type")

    if model_type == "memory":
        MODEL_REGISTRY[symbol] = MemoryModel(symbol)
    elif model_type == "tech":
        MODEL_REGISTRY[symbol] = TechModel(symbol)
    else:
        raise ValueError(f"Unknown model type: {model_type}")


@app.get("/dashboard/{symbol}")
def dashboard(symbol: str):
    if symbol not in MODEL_REGISTRY:
        return {"error": f"Symbol {symbol} not supported"}

    model = MODEL_REGISTRY[symbol]
    return model.get_prediction()
