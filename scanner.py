import os
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta

def send_telegram_message(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def get_filtered_us_pool():
    """獲取全美股名單，並過濾市值、行業"""
    print("正在獲取並篩選全美股標的物...")
    tickers = set()
    
    # 💡 加入瀏覽器標頭，防止 Wikipedia 阻擋爬蟲 (403 Forbidden)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        # 1. 抓取 S&P 500 名單
        sp500_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        res_sp = requests.get(sp500_url, headers=headers, timeout=15)
        sp500_table = pd.read_html(res_sp.text)[0]
        tickers.update(sp500_table['Symbol'].tolist())
        
        # 2. 抓取 Nasdaq 100 名單
        ndx_url = "https://en.wikipedia.org/wiki/Nasdaq-100"
        res_ndx = requests.get(ndx_url, headers=headers, timeout=15)
        ndx_table = pd.read_html(res_ndx.text)[4]
        col = 'Ticker' if 'Ticker' in ndx_table.columns else 'Symbol'
        tickers.update(ndx_table[col].tolist())
    except Exception as e:
        print(f"網頁抓取失敗，啟動核心備用名單機制: {e}")
        return ['AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'META', 'TSLA', 'AMD', 'INTC', 'NFLX', 'QCOM', 'AVGO']

    raw_tickers = [str(t).replace('.', '-') for t in tickers if isinstance(t, str)]
    final_pool = []
    
    exclude_industries = ['Biotechnology', 'Airlines', 'Tobacco', 'Gambling', 'Casinos', 'Beverages—Wineries & Distilleries']
    
    print(f"成功下載名單，開始過濾 {len(raw_tickers)} 隻美股行業與市值...")
    for ticker in raw_tickers:
        try:
            t_obj = yf.Ticker(ticker)
            info = t_obj.info
            
            # 條件 1: 市值大於 10 億美元
            market_cap = info.get('marketCap', 0)
            if market_cap < 1000000000:
                continue
                
            # 條件 2: 排除特定行業
            industry = info.get('industry', '')
            is_blacklisted = False
            for blacklist in exclude_industries:
                if blacklist.lower() in industry.lower():
                    is_blacklisted = True
                    break
            
            if 'biotech' in industry.lower() or 'biotechnology' in industry.lower():
                is_blacklisted = True
                
            if is_blacklisted:
                continue
                
            final_pool.append(ticker)
        except Exception:
            # 如果個別股票 info 獲取超時，安全起見保留在池中
            final_pool.append(ticker)
            
    print(f"過濾完畢！最終進入 500 日線篩選的優質股票共: {len(final_pool)} 隻")
    return final_pool

def screen_500_day_ma_breakout(tickers):
    breakout_list = []
    start_date = (datetime.now() - timedelta(days=1000)).strftime('%Y-%m-%d')
    
    try:
        data = yf.download(tickers, start=start_date, interval='1d', group_by='ticker', progress=False)
    except Exception as e:
        print(f"批量下載日 K 線數據失敗: {e}")
        return []

    for ticker in tickers:
        try:
            if ticker not in data.columns.levels[0]:
                continue
            df = data[ticker].dropna(subset=['Close'])
            
            if len(df) < 500:
                continue
                
            df['MA_500'] = df['Close'].rolling(window=500).mean()
            
            current_close = df['Close'].iloc[-1]
            current_ma = df['MA_500'].iloc[-1]
            prev_close = df['Close'].iloc[-2]
            prev_ma = df['MA_500'].iloc[-2]
            current_volume = df['Volume'].iloc[-1]
            avg_volume = df['Volume'].iloc[-20:].mean()
            
            # 突破條件
            if prev_close <= prev_ma and current_close > current_ma:
                volume_ratio = current_volume / avg_volume
                breakout_list.append({
                    'Ticker': ticker,
                    'Close': round(current_close, 2),
                    'Volume_Ratio': round(volume_ratio, 2)
                })
        except Exception:
            continue
            
    return breakout_list

if __name__ == "__main__":
    filtered_pool = get_filtered_us_pool()
    results = screen_500_day_ma_breakout(filtered_pool)
    
    message_title = f"🎯 *【Agent 定製化美股篩選報告】*\n日期: {datetime.now().strftime('%Y-%m-%d')}\n過濾條件: 市值>10億 | 剔除生技/航空/煙/酒/賭\n指標條件: *突破 500日均線*\n掃描總數: {len(filtered_pool)} 隻優質美股\n\n"
    
    if results:
        message_body = "🔥 *本日/本週成功突破 500日線 的標的：*\n"
        results = sorted(results, key=lambda x: x['Volume_Ratio'], reverse=True)
        for stock in results[:15]:
            message_body += f" 📈 *{stock['Ticker']}*\n  └ 現價: ${stock['Close']}\n  └ 大戶成交量比: {stock['Volume_Ratio']}x\n\n"
    else:
        message_body = "😴 *精選股票池中，暫時沒有股票突破 500日線。*"
        
    send_telegram_message(message_title + message_body)
    print("500日線篩選任務完成！")
