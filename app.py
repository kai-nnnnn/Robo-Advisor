import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai

# ================= 1. 頁面與基本設定 =================
st.set_page_config(page_title="DAT.co 指標監控平台", layout="wide")
st.title("📊 DAT.co 財務指標監控平台: MSTR NAV 溢價分析")

st.markdown("""
本平台專注於分析數位資產儲備公司 (DAT.co) 的核心指標：**Premium to NAV (資產淨值溢價)**。
我們以 **MicroStrategy (MSTR)** 作為代表，觀察其市值相對於其持有的比特幣總價值的溢價變化。
""")

# 假設 MSTR 持有的比特幣數量 (可根據最新財報微調，此處以近期約 252,220 顆為例)
MSTR_BTC_HOLDINGS = 252220 

# ================= 2. 資料收集與處理 =================
@st.cache_data(ttl=3600) # 快取 1 小時

# ================= 2. 資料收集與處理 =================
@st.cache_data(ttl=3600) # 快取 1 小時
def load_data():
    try:
        # 1. 直接使用 yfinance，不設定自訂 session
        mstr = yf.Ticker("MSTR")
        btc = yf.Ticker("BTC-USD")
        
        # 2. 只抓取歷史價格 (history API 比較不容易被擋)
        df_mstr = mstr.history(period="1y")[['Close', 'Volume']].rename(columns={'Close': 'MSTR_Price', 'Volume': 'MSTR_Volume'})
        df_btc = btc.history(period="1y")[['Close']].rename(columns={'Close': 'BTC_Price'})
        
        # 3. 為了避免 429 Rate Limit，我們不再呼叫 mstr.info 抓取股數
        # 這裡直接寫入 MSTR 近期的流通股數 (Shares Outstanding) 約為 202,000,000 股
        shares_out = 202000000 
            
        # 合併資料 (移除時區以避免報錯)
        df_mstr.index = df_mstr.index.tz_localize(None)
        df_btc.index = df_btc.index.tz_localize(None)
        df = pd.merge(df_mstr, df_btc, left_index=True, right_index=True, how='inner')
        
        # 假設 MSTR 持有的比特幣數量
        MSTR_BTC_HOLDINGS = 252220 
        
        # 計算指標
        df['MSTR_Market_Cap'] = df['MSTR_Price'] * shares_out
        df['BTC_Holdings_Value'] = df['BTC_Price'] * MSTR_BTC_HOLDINGS
        
        # 計算 NAV Premium (%) 
        df['Premium_to_NAV'] = (df['MSTR_Market_Cap'] / df['BTC_Holdings_Value']) - 1
        df['Premium_to_NAV_Pct'] = df['Premium_to_NAV'] * 100
        
        return df
    except Exception as e:
        st.error(f"資料抓取失敗: {e}")
        return None

df = load_data()

# ================= 3. 資料視覺化 (Plotly) =================
if df is not None:
    st.subheader("📈 時間序列分析：MSTR 股價 vs 比特幣價格 vs NAV 溢價")
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.1, 
                        subplot_titles=('價格走勢 (USD)', 'Premium to NAV (溢價百分比 %)'),
                        row_heights=[0.6, 0.4])

    # 圖表 1: 價格走勢 (雙 Y 軸概念，這裡簡單畫在一起或看趨勢)
    fig.add_trace(go.Scatter(x=df.index, y=df['MSTR_Price'], name='MSTR 股價', line=dict(color='blue')), row=1, col=1)
    
    # 圖表 2: NAV 溢價
    colors = ['green' if val > 0 else 'red' for val in df['Premium_to_NAV_Pct']]
    fig.add_trace(go.Bar(x=df.index, y=df['Premium_to_NAV_Pct'], name='NAV 溢價 (%)', marker_color=colors), row=2, col=1)

    fig.update_layout(height=600, template="plotly_white", showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("查看原始數據表"):
        st.dataframe(df.tail(10).sort_index(ascending=False))

# ================= 4. AI 自動生成總結 (Bonus) =================
st.markdown("---")
st.subheader("🤖 AI 趨勢分析 (Bonus Requirement)")

# 移除讓使用者輸入 API Key 的欄位，改為直接提供按鈕
if st.button("生成分析報告"):
    if df is not None:
        try:
            # 從 Streamlit 系統後台讀取你設定的 API Key
            api_key = st.secrets["GEMINI_API_KEY"]
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # 準備給 AI 的近期數據摘要
            recent_data = df.tail(5)[['MSTR_Price', 'BTC_Price', 'Premium_to_NAV_Pct']].to_string()
            
            prompt = f"""
            你是一位專業的加密貨幣與傳統金融分析師。以下是 MicroStrategy (MSTR) 近5日的數據：
            {recent_data}
            
            請根據以上數據中的 'Premium_to_NAV_Pct' (資產淨值溢價百分比)，簡短分析：
            1. 目前 MSTR 相對於其持有的比特幣是處於溢價還是折價？趨勢如何？
            2. 這反映了市場對比特幣或 MSTR 的何種情緒？
            請用繁體中文回答，字數控制在 200 字以內。
            """
            
            with st.spinner("AI 正在分析數據中..."):
                response = model.generate_content(prompt)
                st.success("分析完成！")
                st.info(response.text)
                
        except KeyError:
            st.error("系統尚未設定 API Key，請開發者至 Streamlit 後台設定 `GEMINI_API_KEY`。")
        except Exception as e:
            st.error(f"AI API 呼叫失敗。錯誤訊息: {e}")
    else:
        st.warning("數據尚未載入，無法分析。")