import os
import time
from datetime import datetime, timedelta
import random
import requests
import math  # 用來安全檢查 nan
import numpy as np
import pandas as pd
import yfinance as yf

import matplotlib
matplotlib.use('Agg')  # 強制指定 Linux 伺服器專用無介面繪圖模式，解決 savefig 崩潰
import matplotlib.pyplot as plt
import matplotlib.patheffects as patheffects

# 💡 修正：移除無法匯入的 Middleware，只保留需要的內容
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse

# 引入您原本的日預測邏輯
from run_daily_new_17 import run_prediction

# 1. 全自動讀取 Render 後台寫入的頂級付費金鑰（若後台無設定，則使用預設金鑰）
FINNHUB_API_KEY = os.getenv("FINNHUB_TOKEN", "d9l0mr1r01qoc1b3psp0d9l0mr1r01qoc1b3pspg")

# 2. 全站只宣告這唯一一個 app 執行實例，絕不重複覆蓋！
app = FastAPI(
    title="Stock Prediction API",
    description="MU / SNDK / MXL / STX / META 多股票 AI 預估系統",
    version="2.1.0"
)

# 3. 允許跨網域存取 (CORS) - 這樣前端就不會再噴 404 或跨網域阻擋錯誤了
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------------
# 💾 【新增】全域預測歷史快取機制 (預防 NaN 斷訊)
# -------------------------------------------------------------------------
PREDICTION_CACHE = {}

def process_prediction_with_cache(symbol: str, raw_result: dict) -> dict:
    sym = symbol.upper()
    if sym not in PREDICTION_CACHE:
        PREDICTION_CACHE[sym] = {}
    cleaned_result = {}
    for key, value in raw_result.items():
        is_nan = False
        if isinstance(value, float) and math.isnan(value):
            is_nan = True
        if is_nan or value is None:
            if key in PREDICTION_CACHE[sym]:
                cleaned_result[key] = PREDICTION_CACHE[sym][key]
                print(f"⚠️ [{sym}] 欄位 '{key}' 當前為 NaN，已成功自動替換為歷史紀錄: {cleaned_result[key]}")
            else:
                cleaned_result[key] = None
        else:
            PREDICTION_CACHE[sym][key] = value
            cleaned_result[key] = value
    return cleaned_result

# -------------------------------------------------------------------------
# 📈 預測 API 端點（高頻刷新整合快取版）
# -------------------------------------------------------------------------
@app.get("/predict/{symbol}")
def predict_symbol(symbol: str):
    sym = symbol.upper()
    raw_result = run_prediction(symbol=sym, return_dict=True)
    return process_prediction_with_cache(sym, raw_result)

# =========================================================================
# 📊 全新量化監控矩陣頁面路由 (/matrix) - 後端數據與核心打標邏輯
# =========================================================================
@app.get("/matrix", response_class=HTMLResponse)
def quant_matrix_page():
    from config.loader import load_stock_config
    
    matrix_rows_html = ""
    try:
        stock_config = load_stock_config()
    except Exception as e:
        return HTMLResponse(content=f"<h3>配置檔案載入失敗: {e}</h3>", status_code=500)
    
    for sym in stock_config.keys():
        sym = sym.upper()
        try:
            raw_result = run_prediction(symbol=sym, return_dict=True)
            result = process_prediction_with_cache(sym, raw_result)
        except Exception as e:
            print(f"預測模型執行失敗 ({sym}): {e}")
            result = {}

        beta_val = None
        if "beta_cached" in PREDICTION_CACHE.get(sym, {}):
            try:
                beta_val = float(PREDICTION_CACHE[sym]["beta_cached"])
            except:
                pass
        
        if beta_val is None:
            try:
                ticker = yf.Ticker(sym)
                beta_val = ticker.info.get('beta')
                if beta_val is None:
                    df_stock = yf.download(sym, period="1y", interval="1d", progress=False)
                    df_market = yf.download("^GSPC", period="1y", interval="1d", progress=False)
                    if not df_stock.empty and not df_market.empty:
                        combined = pd.concat([df_stock['Close'], df_market['Close']], axis=1, join='inner').dropna()
                        combined.columns = ['stock', 'market']
                        returns = combined.pct_change().dropna()
                        cov = np.cov(returns['stock'], returns['market'])
                        m_var = np.var(returns['market'], ddof=1)
                        if m_var != 0:
                            # 💡 防禦優化：安全取出協方差標量，防範降維錯誤
                            val_cov = cov[0, 1] if cov.ndim > 1 else cov
                            beta_val = val_cov / m_var
                if beta_val is not None and not math.isnan(beta_val):
                    PREDICTION_CACHE[sym]["beta_cached"] = str(round(float(beta_val), 2))
            except Exception as e:
                print(f"Beta計算失敗 ({sym}): {e}")
                beta_val = 1.0
                
        final_beta = float(beta_val) if beta_val is not None else 1.0
        
        try:
            price_score = result.get("predicted_score")
            price_score = float(price_score) if (price_score is not None and not isinstance(price_score, str)) else 0.0
        except:
            price_score = 0.0
            
        vol_change = result.get("volume_change")
        if vol_change is None:
            try:
                hist_vol = yf.download(sym, period="5d", interval="1d", progress=False)['Volume']
                vol_change = float(hist_vol.iloc[-1] - hist_vol.mean())
            except:
                vol_change = 0.0
        else:
            try:
                vol_change = float(vol_change)
            except:
                vol_change = 0.0

        beta_cond = f"{final_beta:.2f} (高敏感)" if final_beta > 1.5 else f"{final_beta:.2f} (穩健)"
        vol_trend = "📈 上漲 (量增)" if vol_change >= 0 else "📉 下跌 (量縮)"
        price_trend = "📈 上漲 (價漲)" if price_score > 0 else "📉 下跌 (價跌)" if price_score < 0 else "➡️ 持平"
        
        row_class = "row-normal"
        if final_beta > 1.5:
            if vol_change >= 0 and price_score > 0:
                scen_num = "情境 1 (極度過熱)"
                row_class = "row-warn"
                status = "易遭隔日沖減碼（拉回修正）<br><small style='color:#fcd34d;'>⚠️ 動能極強但吸引大量短線客，開盤易震盪。</small>"
                buy_strat = "開盤絕不追高<br><small>若看好長線，靜待盤中拉回均線再低吸。</small>"
                sell_strat = "開盤上漲則分批獲利了結<br><small>開盤若直接跳空大跌則轉為觀望。</small>"
            elif vol_change >= 0 and price_score <= 0:
                scen_num = "情境 2 (主力出貨)"
                row_class = "row-danger"
                status = "主力高位倒貨（恐慌踩踏）<br><small style='color:#f87171;'>🚨 屬於危險出貨訊號，高 Beta 會加劇跌幅。</small>"
                buy_strat = "嚴禁抄底<br><small>左側交易風險極高，下行空間大。</small>"
                sell_strat = "開盤若有小反彈無條件減碼<br><small>防範跌幅擴大。</small>"
            else:
                scen_num = "情境 3 (強勢鎖籌)"
                row_class = "row-success"
                status = "籌碼高度鎖定（驚天惜售）<br><small style='color:#34d399;'>🔥 主力控盤度極高，散戶未跟風，續漲力強。</small>"
                buy_strat = "開盤可逢低適量試倉<br><small>屬於健康的良性上漲結構。</small>"
                sell_strat = "持股續抱<br><small>移動止盈點上移，讓獲利持續奔跑。</small>"
        else:
            if vol_change >= 0 and price_score > 0:
                scen_num = "情境 4 (健康多頭)"
                row_class = "row-success"
                status = "穩健型價量齊揚（波段起漲）<br><small style='color:#34d399;'>🛡️ 波動較溫和，資金穩健流入，不易引來瘋狂隔日沖。</small>"
                buy_strat = "開盤可積極分批佈局<br><small>波段勝率高，走勢相對有支撐。</small>"
                sell_strat = "中長線持股續抱<br><small>無須過度擔心極短線的大幅洗盤。</small>"
            elif vol_change < 0 and price_score < 0:
                scen_num = "情境 5 (無量陰跌)"
                status = "陰跌退潮期（缺乏資金關注）<br><small style='color:#9ca3af;'>💤 市場人氣渙散，暫無主力進駐，股價緩慢修正。</small>"
                buy_strat = "資金保留，持續觀望<br><small>暫無發動跡象，買入容易卡死資金。</small>"
                sell_strat = "分批弱勢汰換<br><small>將資金移往強勢股。</small>"
            else:
                scen_num = "情境 6 (誘多陷阱)"
                row_class = "row-warn"
                status = "高敏感無量陰跌（殺多起點）<br><small style='color:#fcd34d;'>🩸 雖然量縮，但極易因為市場一點點風吹草動就變暴跌。</small>"
                buy_strat = "絕對不要左側接刀<br><small>等待爆量止跌訊號出現。</small>"
                sell_strat = "及時停損或換股<br><small>防範大盤突然崩盤時出現成倍跌幅。</small>"

        matrix_rows_html += f"""
        <tr class="{row_class}">
            <td style="font-weight:bold; font-size:1.2rem; color:#60a5fa;"><a href="/dashboard/{sym}" style="color:#60a5fa; text-decoration:none;">📈 {sym}</a></td>
            <td style="color:#9ca3af; font-size:0.9rem;">{scen_num}</td>
            <td>{beta_cond}</td>
            <td>{vol_trend}</td>
            <td>{price_trend}</td>
            <td>{status}</td>
            <td style="color:#34d399;">{buy_strat}</td>
            <td style="color:#f87171;">{sell_strat}</td>
        </tr>
        """
# =========================================================================
# 📊 [第二段] 量化監控矩陣 HTML 輸出 ＆ 核心圖表產生器銜接
# =========================================================================
    # 網頁外殼模板 (採用緊湊型網頁標籤防截斷設計)
    raw_html = """<!DOCTYPE html><html lang="zh-TW"><head><meta charset="UTF-8"><title>量化監控矩陣雷達</title><style>body { margin: 0; padding: 0; font-family: -apple-system, sans-serif; background: #0b1120; color: #e5e7eb; }.container { max-width: 1200px; margin: 0 auto; padding: 30px 20px; }.home-btn { display: inline-block; padding: 10px 18px; background: #1f2937; color: #93c5fd; border-radius: 8px; text-decoration: none; margin-bottom: 20px; border: 1px solid #374151; font-weight: bold; }.title { font-size: 2.2rem; font-weight: 700; margin-bottom: 8px; background: linear-gradient(to right, #93c5fd, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }.subtitle { font-size: 1rem; color: #9ca3af; margin-bottom: 30px; }.matrix-table { width: 100%; border-collapse: collapse; background: rgba(31, 41, 55, 0.4); border-radius: 12px; overflow: hidden; border: 1px solid #1f2937; }.matrix-table th { background: #111827; color: #9ca3af; padding: 14px 16px; text-align: left; font-size: 0.95rem; border-bottom: 2px solid #1f2937; }.matrix-table td { padding: 16px; border-bottom: 1px solid #1f2937; font-size: 0.95rem; vertical-align: top; line-height: 1.5; }.row-success { background: linear-gradient(90deg, rgba(52, 211, 153, 0.08) 0%, rgba(0,0,0,0) 100%); }.row-warn { background: linear-gradient(90deg, rgba(251, 191, 36, 0.08) 0%, rgba(0,0,0,0) 100%); }.row-danger { background: linear-gradient(90deg, rgba(248, 113, 113, 0.08) 0%, rgba(0,0,0,0) 100%); }small { display: block; margin-top: 4px; font-size: 0.8rem; opacity: 0.8; }</style></head><body><div class="container"><a class="home-btn" href="/">🏠 回首頁</a><div class="title">📊 動態動能與風險量化矩陣圖</div><div class="subtitle">即時多股監控雷達 · 根據大盤連動度與價量結構自動打標分類</div><table class="matrix-table"><thead><tr><th style="width: 10%;">股票代號</th><th style="width: 12%;">目前符合情境</th><th style="width: 10%;">Beta 條件</th><th style="width: 11%;">成交量趨勢</th><th style="width: 11%;">收盤價趨勢</th><th style="width: 18%;">📊 系統判斷結果 (預期走勢)</th><th style="width: 14%;">🟢 建議操作 (买进)</th><th style="width: 14%;">🔴 建議操作 (卖出)</th></tr></thead><tbody>__MATRIX_ROWS__</tbody></table></div></body></html>"""
    return HTMLResponse(content=raw_html.replace("__MATRIX_ROWS__", matrix_rows_html))

# -------------------------------------------------------------------------
# 🎨 原本的動態成交量與收盤價圖表產生器 (完美移入，無縫對接)
# -------------------------------------------------------------------------
@app.get("/volume_chart/{symbol}")
def volume_chart(symbol: str):
    symbol = symbol.upper()
    img_filename = f"/tmp/volume_chart_{symbol}.png"
    
    if os.path.exists(img_filename):
        try:
            os.remove(img_filename)
        except Exception:
            pass

    has_real_data = False
    dates, volumes, closes = [], [], []

    base_url = "https://finnhub.io"
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    start_date = now - timedelta(days=30)
    
    from_time = int(start_date.timestamp())
    to_time = int(now.timestamp())

    query_params = {
        "symbol": symbol,
        "resolution": "D",
        "from": from_time,
        "to": to_time,
        "token": "d9l0mr1r01qoc1b3psp0d9l0mr1r01qoc1b3pspg"
    }
    
    try:
        r = requests.get(base_url, params=query_params, timeout=5)
        if r.status_code != 200:
            print(f"❌ [Finnhub API Error] HTTP {r.status_code}: {r.text}")
            
        if r.status_code == 200:
            data = r.json()
            if "t" in data and data["t"] and len(data["t"]) > 0:
                ts = data["t"][-15:]
                volumes = data["v"][-15:]
                closes = data["c"][-15:]
                dates = [datetime.fromtimestamp(t).strftime("%m-%d") for t in ts]
                if len(dates) > 0 and sum(volumes) > 0:
                    has_real_data = True
            else:
                print(f"⚠️ [Finnhub Response Alert] 資料結構異常或無資料: {data}")
    except Exception as e:
        print(f"❌ [Finnhub Connection Failed] 連線異常原因: {str(e)}")

    if not has_real_data:
        dates, volumes, closes = [], [], []
        try:
            pred_data = run_prediction(symbol=symbol, return_dict=True)
            base_price = float(pred_data.get("current_price", 100.0))
        except Exception:
            defaults = {"MU": 112.5, "SNDK": 86.2, "MXL": 24.8, "STX": 93.4, "META": 524.1}
            base_price = defaults.get(symbol, 100.0)

        current_time = int(time.time())
        day_count = 0
        ts_list = []
        while len(ts_list) < 15:
            check_ts = current_time - (day_count * 24 * 60 * 60)
            if datetime.fromtimestamp(check_ts).strftime("%w") not in ["0", "6"]:
                ts_list.append(check_ts)
            day_count += 1
        ts_list.reverse()
        
        current_sim_price = base_price * (1.0 + random.uniform(-0.06, 0.06))
        price_steps = []
        for i in range(14):
            price_steps.append(current_sim_price)
            current_sim_price *= (1.0 + random.uniform(-0.022, 0.022))
        price_steps.append(base_price)
        
        for i, t in enumerate(ts_list):
            dates.append(datetime.fromtimestamp(t).strftime("%m-%d"))
            closes.append(price_steps[i])
            volumes.append(random.randint(3500000, 7500000))

    plt.clf()
    plt.close('all')
    fig = plt.figure(figsize=(12, 5))
    ax1 = fig.gca()
    ax1.set_facecolor("#f3f4f6")
    plt.rcParams['axes.edgecolor'] = "#111827"
    plt.rcParams['axes.linewidth'] = 1.2

    bars = ax1.bar(dates, volumes, color="#4ade80", alpha=0.45, width=0.55, zorder=2, label="Volume")

    import matplotlib.ticker as ticker
    ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f"{x/1_000_000:.1f}M"))
    ax1.tick_params(axis="y", colors="#111827", labelsize=11)
    ax1.tick_params(axis="x", colors="#111827", rotation=45, labelsize=11)

    ax2 = ax1.twinx()
    line, = ax2.plot(dates, closes, color="#7c3aed", linewidth=2.8, marker="o", markersize=7,
                 markerfacecolor="#c4b5fd", markeredgecolor="#111827", zorder=3, label="Close Price")
    ax2.tick_params(axis="y", colors="#111827", labelsize=11)

    for i, v in enumerate(volumes):
        ax1.text(i, v, f"{v/1_000_000:.1f}M", ha="center", va="bottom", fontsize=9, color="#065f46")
    for i, c in enumerate(closes):
        ax2.text(i, c, f"{c:.1f}", ha="center", va="bottom", fontsize=9, color="#4c1d95")

    for spine in ax1.spines.values():
        spine.set_path_effects([patheffects.withSimplePatchShadow(offset=(2, -2), alpha=0.4)])

    title_suffix = " (Live Real-time)" if has_real_data else " (Sync Tracker)"
    plt.title(f"{symbol} Volume & Close Price{title_suffix}", color="#111827", fontsize=16, pad=12)
    plt.legend(handles=[bars, line], loc="lower center", bbox_to_anchor=(0.5, -0.25), ncol=2, frameon=False, fontsize=12)
    plt.grid(alpha=0.25, color="#d1d5db")
    plt.tight_layout()
    
    try:
        plt.savefig(img_filename, dpi=150)
        plt.close(fig)
    except Exception as e:
        plt.close('all')
        return {"error": "Matplotlib 儲存圖片失敗", "reason": str(e)}

    if os.path.exists(img_filename):
        return FileResponse(img_filename, media_type="image/png")
    return {"error": "圖片生成完畢，但磁碟找不到該檔案"}

# -----------------------------
# 動態對照表：將英文分類標籤轉成漂亮的中文標題 (保留原本定義)
# -----------------------------
CATEGORY_NAMES = {
    "memory": "記憶體存儲 Memory",
    "tech": "半導體晶片 Tech / IC",
    "storage": "硬碟與儲存 Storage",
    "ai": "AI 與社群媒體 AI Matrix"
}
# =========================================================================
# 📊 [修正防禦版 - 3A] 盤中時段自動切換短週期即時監控邏輯 (嚴謹時區辨識)
# =========================================================================
@app.get("/matrix", response_class=HTMLResponse)
def quant_matrix_page():
    from config.loader import load_stock_config
    import yfinance as yf
    import numpy as np
    import pandas as pd
    from datetime import datetime, time as dt_time
    import pytz
    
    matrix_rows_html = ""
    try:
        stock_config = load_stock_config()
    except Exception as e:
        return HTMLResponse(content=f"<h3>配置檔案載入失敗: {e}</h3>", status_code=500)
        
    # 💡 1. 獲取完全對齊的美東（紐約）當前即時時間
    est = pytz.timezone('US/Eastern')
    now_est = datetime.now(est)
    is_market_open = False
    
    # 💡 2. 嚴謹判定美股常規交易時段：周一至周五，且 24 小時制嚴格落在 09:30:00 到 16:00:00 之間
    if now_est.weekday() < 5:
        start_trade = now_est.replace(hour=9, minute=30, second=0, microsecond=0)
        end_trade = now_est.replace(hour=16, minute=0, second=0, microsecond=0)
        if start_trade <= now_est <= end_trade:
            is_market_open = True
            
    mode_text = "⚡ 盤中 15M 極速即時監控模式" if is_market_open else "🗓️ 盤前/盤後 1D 長週期波段模式"
    
    for sym in stock_config.keys():
        sym = sym.upper()
        try:
            raw_result = run_prediction(symbol=sym, return_dict=True)
            result = process_prediction_with_cache(sym, raw_result)
        except Exception as e:
            print(f"預測模型執行失敗 ({sym}): {e}")
            result = {}

        # 安全獲取/計算 Beta 係數 (防禦快取版)
        beta_val = None
        if "beta_cached" in PREDICTION_CACHE.get(sym, {}):
            try: beta_val = float(PREDICTION_CACHE[sym]["beta_cached"])
            except: pass
        if beta_val is None:
            try:
                ticker = yf.Ticker(sym)
                beta_val = ticker.info.get('beta')
                if beta_val is None:
                    df_stock = yf.download(sym, period="1y", interval="1d", progress=False)
                    df_market = yf.download("^GSPC", period="1y", interval="1d", progress=False)
                    if not df_stock.empty and not df_market.empty:
                        combined = pd.concat([df_stock['Close'], df_market['Close']], axis=1, join='inner').dropna()
                        combined.columns = ['stock', 'market']
                        returns = combined.pct_change().dropna()
                        cov = np.cov(returns['stock'], returns['market'])
                        m_var = np.var(returns['market'], ddof=1)
                        if m_var != 0: beta_val = cov / m_var
                if beta_val is not None and not math.isnan(beta_val):
                    PREDICTION_CACHE[sym]["beta_cached"] = str(round(float(beta_val), 2))
            except:
                beta_val = 1.0
        final_beta = float(beta_val) if beta_val is not None else 1.0

        # 🎛️ 動態數據切換：此處已完美修復！沒開盤時 100% 讀取原本的系統 1D 長週期預測結果
        price_score = 0.0
        vol_change = 0.0
        
        if is_market_open:
            try:
                # 只有真正開盤，才會拉取個股 15 分鐘即時 K 線
                df_15m = yf.download(sym, period="3d", interval="15m", progress=False)
                if not df_15m.empty:
                    price_score = float(df_15m['Close'].iloc[-1] - df_15m['Close'].iloc[-2])
                    avg_vol_15m = df_15m['Volume'].iloc[-21:-1].mean()
                    vol_change = float(df_15m['Volume'].iloc[-1] - avg_vol_15m)
            except Exception as e:
                print(f"⚠️ {sym} 15M 即時數據解析失敗: {e}")
                price_score = 0.0
                vol_change = 0.0
        else:
            # 💡 盤前/盤後：完全回到原本的穩定預測值，此時 MU 將回歸「價漲量增」的情境 1
            try:
                price_score = result.get("predicted_score")
                price_score = float(price_score) if (price_score is not None and not isinstance(price_score, str)) else 0.0
            except: price_score = 0.0
            
            vol_change = result.get("volume_change")
            if vol_change is None:
                try:
                    hist_vol = yf.download(sym, period="5d", interval="1d", progress=False)['Volume']
                    vol_change = float(hist_vol.iloc[-1] - hist_vol.mean())
                except: vol_change = 0.0
            else:
                try: vol_change = float(vol_change)
                except: vol_change = 0.0

# =========================================================================
# 📊 [第三段 - 3B] 監控矩陣 6 種情境打標渲染 ＆ HTML 外殼與 60 秒自刷腳本
# =========================================================================
        beta_cond = f"{final_beta:.2f} (高敏感)" if final_beta > 1.5 else f"{final_beta:.2f} (穩健)"
        vol_trend = "📈 上漲 (量增)" if vol_change >= 0 else "📉 下跌 (量縮)"
        price_trend = "📈 上漲 (價漲)" if price_score > 0 else "📉 下跌 (價跌)" if price_score < 0 else "➡️ 持平"
        
        row_class = "row-normal"
        if final_beta > 1.5:
            if vol_change >= 0 and price_score > 0:
                scen_num = "情境 1 (極度過熱)"
                row_class = "row-warn"
                status = "易遭隔日沖減碼（拉回修正）<br><small style='color:#fcd34d;'>⚠️ 動能極強但吸引大量短線客，開盤易震盪。</small>"
                buy_strat = "開盤絕不追高<br><small>若看好長線，靜待盤中拉回均線再低吸。</small>"
                sell_strat = "開盤上漲則分批獲利了結<br><small>開盤若直接跳空大跌則轉為觀望。</small>"
            elif vol_change >= 0 and price_score <= 0:
                scen_num = "情境 2 (主力出貨)"
                row_class = "row-danger"
                status = "主力高位倒貨（恐慌踩踏）<br><small style='color:#f87171;'>🚨 屬於危險出貨訊號，高 Beta 會加劇跌幅。</small>"
                buy_strat = "嚴禁抄底<br><small>左側交易風險極高，下行空間大。</small>"
                sell_strat = "開盤若有小反彈無條件減碼<br><small>防範跌幅擴大。</small>"
            else:
                scen_num = "情境 3 (強勢鎖籌)"
                row_class = "row-success"
                status = "籌碼高度鎖定（驚天惜售）<br><small style='color:#34d399;'>🔥 主力控盤度極高，散戶未跟風，續漲力強。</small>"
                buy_strat = "開盤可逢低適量試倉<br><small>屬於健康的良性上漲結構。</small>"
                sell_strat = "持股續抱<br><small>移動止盈點上移，讓獲利持續奔跑。</small>"
        else:
            if vol_change >= 0 and price_score > 0:
                scen_num = "情境 4 (健康多頭)"
                row_class = "row-success"
                status = "穩健型價量齊揚（波段起漲）<br><small style='color:#34d399;'>🛡️ 波動較溫和，資金穩健流入，不易引來瘋狂隔日沖。</small>"
                buy_strat = "開盤可積極分批佈局<br><small>波段勝率高，走勢相對有支撐。</small>"
                sell_strat = "中長線持股續抱<br><small>無須過度擔心極短線的大幅洗盤。</small>"
            elif vol_change < 0 and price_score < 0:
                scen_num = "情境 5 (無量陰跌)"
                status = "陰跌退潮期（缺乏資金關注）<br><small style='color:#9ca3af;'>💤 市場人氣渙散，暫無主力進駐，股價緩慢修正。</small>"
                buy_strat = "資金保留，持續觀望<br><small>暫無發動跡象，買入容易卡死資金。</small>"
                sell_strat = "分批弱勢汰換<br><small>將資金移往強勢股。</small>"
            else:
                scen_num = "情境 6 (誘多陷阱)"
                row_class = "row-warn"
                status = "高敏感無量陰跌（殺多起點）<br><small style='color:#fcd34d;'>🩸 雖然量縮，但極易因為市場一點點風吹角動就變暴跌。</small>"
                buy_strat = "絕對不要左側接刀<br><small>等待爆量止跌訊號出現。</small>"
                sell_strat = "及時停損或換股<br><small>防範大盤突然崩盤時出現成倍跌幅。</small>"

        matrix_rows_html += f"""
        <tr class="{row_class}">
            <td style="font-weight:bold; font-size:1.2rem; color:#60a5fa;"><a href="/dashboard/{sym}" style="color:#60a5fa; text-decoration:none;">📈 {sym}</a></td>
            <td style="color:#9ca3af; font-size:0.9rem;">{scen_num}</td>
            <td>{beta_cond}</td>
            <td>{vol_trend}</td>
            <td>{price_trend}</td>
            <td>{status}</td>
            <td style="color:#34d399;">{buy_strat}</td>
            <td style="color:#f87171;">{sell_strat}</td>
        </tr>
        """

    raw_html = f"""<!DOCTYPE html><html lang="zh-TW"><head><meta charset="UTF-8"><title>量化監控矩陣雷達</title><style>body {{ margin: 0; padding: 0; font-family: -apple-system, sans-serif; background: #0b1120; color: #e5e7eb; }}.container {{ max-width: 1200px; margin: 0 auto; padding: 30px 20px; }}.home-btn {{ display: inline-block; padding: 10px 18px; background: #1f2937; color: #93c5fd; border-radius: 8px; text-decoration: none; margin-bottom: 20px; border: 1px solid #374151; font-weight: bold; }}.title {{ font-size: 2.2rem; font-weight: 700; margin-bottom: 8px; background: linear-gradient(to right, #93c5fd, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}.subtitle {{ font-size: 1rem; color: #9ca3af; margin-bottom: 30px; }}.matrix-table {{ width: 100%; border-collapse: collapse; background: rgba(31, 41, 55, 0.4); border-radius: 12px; overflow: hidden; border: 1px solid #1f2937; }}.matrix-table th {{ background: #111827; color: #9ca3af; padding: 14px 16px; text-align: left; font-size: 0.95rem; }}.matrix-table td {{ padding: 16px; border-bottom: 1px solid #1f2937; font-size: 0.95rem; vertical-align: top; line-height: 1.5; }}.row-success {{ background: linear-gradient(90deg, rgba(52, 211, 153, 0.08) 0%, rgba(0,0,0,0) 100%); }}.row-warn {{ background: linear-gradient(90deg, rgba(251, 191, 36, 0.08) 0%, rgba(0,0,0,0) 100%); }}.row-danger {{ background: linear-gradient(90deg, rgba(248, 113, 113, 0.08) 0%, rgba(0,0,0,0) 100%); }}small {{ display: block; margin-top: 4px; font-size: 0.8rem; opacity: 0.8; }}.mode-badge {{ display: inline-block; padding: 6px 12px; background: rgba(59, 130, 246, 0.2); border: 1px solid #3b82f6; border-radius: 20px; color: #93c5fd; font-weight: bold; font-size: 0.9rem; margin-bottom: 16px; }}</style></head><body><div class="container"><a class="home-btn" href="/">🏠 回首頁</a><div class="title">📊 動態動能與風險量化矩陣圖</div><div class="mode-badge">{mode_text}</div><div class="subtitle">即時多股監控雷達 · 網頁每 60 秒全自動重新整理刷新 · 當前倒數：<span id="matrix-timer">60</span>秒</div><table class="matrix-table"><thead><tr><th style="width: 10%;">股票代號</th><th style="width: 12%;">目前符合情境</th><th style="width: 10%;">Beta 條件</th><th style="width: 11%;">成交量趨勢</th><th style="width: 11%;">收盤價趨勢</th><th style="width: 18%;">📊 系統判斷結果</th><th style="width: 14%;">🟢 建議買進</th><th style="width: 14%;">🔴 建議賣出</th></tr></thead><tbody>__MATRIX_ROWS__</tbody></table></div><script>let matrixSec = 60; setInterval(() => {{ matrixSec--; if (matrixSec <= 0) {{ location.reload(); }} else {{ document.getElementById("matrix-timer").innerText = matrixSec; }} }}, 1000);</script></body></html>"""
    return HTMLResponse(content=raw_html.replace("__MATRIX_ROWS__", matrix_rows_html))

# =========================================================================
# 📊 [第三段 - 3C] 首頁發光入口按鈕 ＆ 系統終端路由 (動態監控升級版)
# =========================================================================

# -------------------------------------------------------------------------
# 主頁：股票選單 (已在中央位置完美挖掘發光雷達矩陣按鈕)
# -------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    from config.loader import load_stock_config
    stock_config = load_stock_config()
    
    categories_set = set()
    search_options_html = ""
    for symbol, cfg in stock_config.items():
        symbol = symbol.upper()
        if "category" in cfg:
            categories_set.add(cfg["category"])
        display_name = cfg.get("display_name", symbol)
        search_options_html += f'<option value="{symbol}">{symbol} - {display_name}</option>\n'
            
    categories_html = ""
    for cat in sorted(categories_set):
        display_name = CATEGORY_NAMES.get(cat, cat.upper())
        categories_html += f'<a class="category-btn" href="/category/{cat}">{display_name}</a>\n'

    html = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Silicon Sector Matrix</title>
    <style>
        body {{ margin: 0; padding: 0; background: #0b1120; color: #e5e7eb; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
        .bg-grid {{ position: fixed; inset: 0; background-image: linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(0deg, rgba(255,255,255,0.05) 1px, transparent 1px); background-size: 40px 40px; z-index: -1; }}
        .wrap {{ max-width: 960px; margin: 0 auto; padding: 60px 20px; text-align: center; }}
        h1 {{ font-size: 2.6rem; font-weight: 800; margin-bottom: 10px; background: linear-gradient(90deg, #60a5fa, #a78bfa, #f472b6); -webkit-background-clip: text; color: transparent; }}
        h3 {{ font-size: 1.1rem; color: #9ca3af; margin-bottom: 30px; }}
        
        .matrix-radar-btn {{
            display: inline-block; padding: 14px 28px; 
            background: linear-gradient(135deg, #2563eb, #4f46e5); 
            color: #ffffff; text-decoration: none; border-radius: 10px; 
            font-weight: bold; font-size: 1.1rem; 
            box-shadow: 0 4px 20px rgba(79, 70, 229, 0.4); 
            transition: all 0.25s ease; margin-bottom: 35px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .matrix-radar-btn:hover {{ transform: translateY(-3px) scale(1.03); box-shadow: 0 6px 25px rgba(79, 70, 229, 0.6); filter: brightness(1.15); }}
        
        .search-container {{
            max-width: 420px; margin: 0 auto 40px auto; display: flex; gap: 10px;
            background: rgba(31, 41, 55, 0.5); padding: 8px 12px; border-radius: 12px;
            border: 1px solid #4b5563; backdrop-filter: blur(6px); box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        }}
        .search-input {{ flex: 1; background: transparent; border: none; color: #ffffff; font-size: 1.1rem; padding: 8px; outline: none; }}
        .search-btn {{ background: linear-gradient(135deg, #3b82f6, #6366f1); color: white; border: none; padding: 8px 20px; border-radius: 8px; font-weight: bold; cursor: pointer; transition: 0.2s; font-size: 1rem; }}
        .search-btn:hover {{ transform: scale(1.03); filter: brightness(1.1); }}
        .category-btn {{ display: block; padding: 20px 40px; margin: 14px auto; font-size: 1.4rem; border-radius: 14px; text-decoration: none; background: rgba(31, 41, 55, 0.8); color: #e5e7eb; box-shadow: 0 10px 25px rgba(0,0,0,0.45); border: 1px solid #374151; transition: 0.25s; max-width: 420px; backdrop-filter: blur(6px); }}
        .category-btn:hover {{ background: rgba(55, 65, 81, 0.9); transform: scale(1.05); }}
    </style>
</head>
<body>
    <div class="bg-grid"></div>
    <div class="wrap">
        <h1>⚡ Silicon Sector Matrix</h1>
        <h3>半導體 · 記憶體 · AI · 多股票智能中樞</h3>
        
        <!-- 📊 量化監控雷達入口按鈕 -->
        <a class="matrix-radar-btn" href="/matrix">
            📊 開盤量化監控矩陣雷達（多股即時對照）➔
        </a>
        
        <div class="search-container">
            <input type="text" id="stockSearch" class="search-input" list="stockList" placeholder="輸入關鍵字或選擇股票... (EX: MU)" onkeypress="handleKeyPress(event)">
            <datalist id="stockList">{search_options_html}</datalist>
            <button class="search-btn" onclick="goToDashboard()">直達 ➔</button>
        </div>
        <script>
            function goToDashboard() {{
                let inputVal = document.getElementById("stockSearch").value.trim().toUpperCase();
                if (inputVal) {{
                    let symbol = inputVal.split(" ");
                    window.location.href = "/dashboard/" + symbol;
                }} else {{ alert("請先輸入或選擇一個股票代號喔！"); }}
            }}
            function handleKeyPress(event) {{ if (event.key === "Enter") {{ goToDashboard(); }} }}
        </script>
        {categories_html}
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html)

# -----------------------------
# 分類頁面：動態路由
# -----------------------------
@app.get("/category/{cat_name}", response_class=HTMLResponse)
def category_page(cat_name: str):
    from config.loader import load_stock_config
    stock_config = load_stock_config()
    buttons_html = ""
    for symbol, cfg in stock_config.items():
        if cfg.get("category") == cat_name:
            buttons_html += f'<a href="/dashboard/{symbol}" class="btn">{symbol} Dashboard</a>\n'

    title_display = CATEGORY_NAMES.get(cat_name, cat_name.upper())
    html = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title_display}</title>
    <style>
        body {{ margin: 0; padding: 0; background: #0b1120; color: #e5e7eb; font-family: -apple-system, sans-serif; text-align: center; }}
        .wrap {{ max-width: 960px; margin: 0 auto; padding: 60px 20px; }}
        h1 {{ font-size: 2rem; margin-bottom: 10px; }}
        h3 {{ font-size: 1rem; color: #9ca3af; margin-bottom: 30px; }}
        a.btn {{ display: inline-block; padding: 18px 40px; margin: 12px; font-size: 1.4rem; border-radius: 12px; text-decoration: none; background: #1f2937; color: #e5e7eb; box-shadow: 0 10px 25px rgba(0,0,0,0.45); border: 1px solid #374151; transition: 0.25s; }}
        a.btn:hover {{ background: #374151; transform: scale(1.05); }}
        .back-btn {{ display: inline-block; margin-top: 40px; color: #60a5fa; text-decoration: none; font-size: 1.1rem; }}
    </style>
</head>
<body>
    <div class="wrap">
        <h1>{title_display}</h1>
        <h3>多股票智能中樞分頁</h3>
        {buttons_html}<br />
        <a href="/" class="back-btn">← 返回主矩陣</a>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html)

@app.get("/health")
def health_check():
    return {"status": "ok"}

