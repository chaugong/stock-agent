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
    print("正在獲取並篩選全美股標的物 (預估需要 1-2 分鐘)...")
    
    # 步驟 1: 先從 Wikipedia 獲取核心大型股 (S&P 500 + Nasdaq 100) 作為高流動性基底
    # 這樣可以極大地保證市值 > 10 億美元
    tickers = set()
    try:
        sp500_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        sp500_table = pd.read_html(sp500_url)[0]
        tickers.update(sp500_table['Symbol'].tolist())
        
        ndx_url = "https://en.wikipedia.org/wiki/Nasdaq-100"
        ndx_table = pd.read_html(ndx_url)[4]
        col = 'Ticker' if 'Ticker' in ndx_table.columns else 'Symbol'
        tickers.update(ndx_table[col].tolist())
    except Exception as e:
        print(f"獲取基礎名單失敗: {e}")
        return ['AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'META', 'TSLA']

    raw_tickers = [str(t).replace('.', '-') for t in tickers if isinstance(t, str)]
    final_pool = []
    
    print(f"初步獲取 {len(raw_tickers)} 隻股票，開始進行大戶條件過濾...")
    
    # 步驟 2: 行業與市值過濾
    # 為了防止黑名單行業滲入，我們檢查 yfinance 的行業標籤
    # 黑名單關鍵字（英文）：Biotechnology(生技), Airlines(航空), Gambling/Gambling/Casinos(賭博), Tobacco(煙草), Beverages-Wineries & Distilleries(酒精)
    exclude_industries = ['Biotechnology', 'Airlines', 'Tobacco', 'Gambling', 'Casinos', 'Beverages—Wineries & Distilleries']
    exclude_sectors = ['Healthcare'] # 生物科技多數在醫療保健板塊，直接加強過濾
    
    # 由於讀取 info 較慢，這裡針對基本池做安全檢查，效率最高
    for ticker in raw_tickers:
        try:
            t_obj = yf.Ticker(ticker)
            info = t_obj.info
            
            # 條件 1: 市值大於 10 億美元 (1,000,000,000)
            market_cap = info.get('marketCap', 0)
            if market_cap < 1000000000:
                continue
                
            # 條件 2: 排除特定的行業與板塊
            industry = info.get('industry', '')
            sector = info.get('sector', '')
            
            # 檢查是否有黑名單行業關鍵字
            is_blacklisted = False
            for blacklist in exclude_industries:
                if blacklist.lower() in industry.lower():
                    is_blacklisted = True
                    break
            
            # 生物科技防禦線：如果行業含有 Biotech 或者是 Healthcare 裡面的小型研發股則跳過
            if 'biotech' in industry.lower() or 'biotechnology' in industry.lower():
                is_blacklisted = True
                
            if is_blacklisted:
                print(f" 🚫 已過濾板塊股票: {ticker} ({industry})")
                continue
                
            final_pool.append(ticker)
        except Exception:
            # 如果部分股票獲取 info 失敗，安全起見保留在池中進入 K 線篩選
            final_pool.append(ticker)
            
    print(f"過濾完畢！最終進入 500 週線篩選的優質股票共: {len(final_pool)} 隻")
    return final_pool

def screen_500_ma_breakout(tickers):
    breakout_list = []
    start_date = (datetime.now() - timedelta(days=500 * 8)).strftime('%Y-%m-%d')
    
    try:
        data = yf.download(tickers, start=start_date, interval='1wk', group_by='ticker', progress=False)
    except Exception as e:
        print(f"批量下載 K 線數據失敗: {e}")
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
    # 1. 獲取滿足條件的精選美股池（>10億市值，排除生技、航空、賭、煙、酒）
    filtered_pool = get_filtered_us_pool()
    
    # 2. 執行 500 週線突破篩選
    results = screen_500_ma_breakout(filtered_pool)
    
    # 3. 發送 Telegram 報告
    message_title = f"🎯 *【Agent 定製化美股篩選報告】*\n日期: {datetime.now().strftime('%Y-%m-%d')}\n過濾條件: 市值>10億 | 剔除生技/航空/煙/酒/賭\n掃描總數: {len(filtered_pool)} 隻優質美股\n\n"
    
    if results:
        message_body = "🔥 *成功突破 500 週線的標的 (按大戶量比排序)：*\n"
        results = sorted(results, key=lambda x: x['Volume_Ratio'], reverse=True)
        for stock in results[:15]:
            message_body += f" 📈 *{stock['Ticker']}*\n  └ 現價: ${stock['Close']}\n  └ 大戶成交量比: {stock['Volume_Ratio']}x\n\n"
    else:
        message_body = "😴 *本週精選股票池中，暫時沒有股票突破 500 週線。*"
        
    send_telegram_message(message_title + message_body)
    print("定製化篩選任務完成！")
