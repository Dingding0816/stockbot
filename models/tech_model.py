class TechModel:
    def __init__(self, symbol):
        self.symbol = symbol

    def get_prediction(self):
        # 你可以之後改成真正的模型邏輯
        return {
            "symbol": self.symbol,
            "status": "ok",
            "message": "TechModel placeholder response",
            "prediction": {
                "direction": "up",
                "confidence": 0.5
            }
        }
