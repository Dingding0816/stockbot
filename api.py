from agent import router as agent_router
from fastapi import FastAPI
from config.loader import load_stock_config

# 依照你的專案結構，這裡放你的模型
# 如果你的模型檔案名稱不同，告訴我，我會幫你調整
from models.memory_model import MemoryModel
from models.tech_model import TechModel

app = FastAPI()

app.include_router(agent_router)

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


from fastapi.templating import Jinja2Templates
from fastapi import Request

templates = Jinja2Templates(directory="templates")
# 暴力解決 Render 環境下 Jinja2 導致 unhashable type: 'dict' 的快取 Bug
templates.env.cache = None

@app.get("/dashboard/{symbol}")
def dashboard_page(request: Request, symbol: str):
    if symbol not in MODEL_REGISTRY:
        return {"error": f"Symbol {symbol} not supported"}

    # 使用明確的關鍵字指定參數，防止 FastAPI 版本不同導致傳參對調崩潰
    return templates.TemplateResponse(
        name="dashboard.html",
        context={"request": request, "symbol": symbol}
    )

@app.get("/api/predict/{symbol}")
def api_predict(symbol: str):
    if symbol not in MODEL_REGISTRY:
        return {"error": f"Symbol {symbol} not supported"}

    model = MODEL_REGISTRY[symbol]
    return model.get_prediction()

from fastapi.responses import HTMLResponse

@app.get("/category/memory")
def category_memory():
    html = """
    <html>
    <head>
        <title>Memory Stocks</title>
        <style>
            body { font-family: Arial; background-color: #111; color: #eee; text-align: center; }
            .btn {
                display: inline-block;
                padding: 12px 20px;
                margin: 10px;
                background-color: #444;
                color: white;
                text-decoration: none;
                border-radius: 6px;
                font-size: 18px;
            }
            .btn:hover { background-color: #666; }
        </style>
    </head>
    <body>
        <h1>記憶體存儲 Memory</h1>
        <p>分類：記憶體・DRAM・NAND</p>
    """
    # 自動讀取 stocks.yaml 裡的所有股票
    for symbol in STOCK_CONFIG.keys():
        html += f'<a href="/dashboard/{symbol}" class="btn">{symbol} Dashboard</a><br>'

    html += """
        <br><a href="/" class="btn">回主頁</a>
    </body>
    </html>
    """

    return HTMLResponse(html)
