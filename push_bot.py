from run_daily_new_17 import run_prediction
import time
import pytz
from datetime import datetime

tz_tw = pytz.timezone("Asia/Taipei")
last_push_time = None

while True:
    now_tw = datetime.now(tz_tw)
    current_time_str = now_tw.strftime("%H:%M")
    hour = now_tw.hour
    minute = now_tw.minute

    # 早上區間：05:00 - 16:00（每 30 分鐘）
    if 5 <= hour <= 16:
        if minute in [0, 30]:
            if last_push_time != current_time_str:
                print(f"⏰ 推播：{current_time_str}")
                run_prediction()
                last_push_time = current_time_str

    # 晚上區間：19:30 - 01:00（每 15 分鐘）
    if (hour == 19 and minute >= 30) or (20 <= hour <= 23) or (hour == 0) or (hour == 1):
        if minute in [0, 15, 30, 45]:
            if last_push_time != current_time_str:
                print(f"⏰ 推播：{current_time_str}")
                run_prediction()
                last_push_time = current_time_str

    time.sleep(10)
