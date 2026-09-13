import yaml
import os

def load_stock_config(path="config/stocks.yaml"):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r") as f:
        return yaml.safe_load(f)
