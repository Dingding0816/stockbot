import re

# 1. 讀取你目前壞掉的 api.py
with open("api.py", "r", encoding="utf-8") as f:
    code = f.read()

# 2. 暴力清洗：直接移除可能殘留、錯位的舊局部變數，確保結構純淨
code = code.replace("is_live_trading_up = True", "")

# 3. 智慧修復：精準比對大漲大跌的條件區塊，強迫它回歸完美縮排與引號閉合
pattern = r"elif is_live_trading and dir_30m > 0\.45:.*?(is_down_triggered = False)"
replacement = "elif is_live_trading and dir_30m > 0.45:\n        is_up_triggered = True\n\n    # 🚨 智慧分流大跌條件\n    \\1"

cleaned_code = re.sub(pattern, replacement, code, flags=re.DOTALL)

# 4. 將校正完畢、100% 語法正確的內容重新寫回 api.py
with open("api.py", "w", encoding="utf-8") as f:
    f.write(cleaned_code)

print("✨ [語法修復成功]！api.py 的隱形縮排與結構錯位已完全洗淨！")
