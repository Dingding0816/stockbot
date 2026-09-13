from fastapi import APIRouter
import yaml

router = APIRouter()

CONFIG_PATH = "config/stocks.yaml"

@router.post("/agent/add_stock")
def add_stock(symbol: str, model_type: str, data_source: str, display_name: str = None, refresh_interval: int = 60):
    # 讀取現有 YAML
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)

    # 如果股票已存在
    if symbol in config:
        return {"error": f"{symbol} already exists"}

    # 新增股票設定
    config[symbol] = {
        "model_type": model_type,
        "data_source": data_source,
        "refresh_interval": refresh_interval,
        "display_name": display_name or symbol
    }

    # 寫回 YAML
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f)

    return {"status": "success", "added": symbol}
