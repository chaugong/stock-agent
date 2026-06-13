import os
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
import concurrent.futures

def send_telegram_message(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def check_single_stock(ticker, exclude_industries):
    """檢查單隻股票是否符合市值與行業條件"""
    try:
        t_obj = yf.Ticker(ticker)
        info = t_obj.info
        
        # 條件 1: 市值大於 10 億美元
        market_cap = info.get('marketCap', 0)
        if market_cap < 1000000000:
            return None
            
        # 條件 2: 排除特定行業
        industry = info.get('industry', '')
        
        for blacklist in exclude_industries:
            if blacklist.lower() in industry.lower():
                return None
        
        if 'biotech' in industry.lower() or 'biotechnology' in industry.lower():
            return None
            
        return ticker
    except Exception:
        # 如果獲取失敗，安全起見保留，交給 K 線階段處理
        return ticker

def get_filtered_us_pool():
    """從 SEC 獲取完整美股名單，並進行全量過濾"""
    print("正在從美國證監會 (SEC) 官方獲取【完整】美股名單...")
    tickers = set()
    
    headers = {
        "User-Agent": "MyStockAgent/1.0 (contact: tester@example.com)"
    }
    
    try:
        sec_url = "https://www.sec.gov/files/company_tickers.json"
        response = requests.get(sec_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            sec_data = response.json()
            for item in sec_data.values():
                symbol = item['ticker']
                if symbol.isalpha():  # 只保留普通股
                    tickers.add(symbol)
            print(f"成功從 SEC 獲取 {len(tickers)} 隻全美股原始名單。")
        else:
            raise Exception(f"SEC 錯誤碼: {response.status_code}")
    except Exception as e:
        print(f"SEC 名單獲取失敗: {e}")
        return ['AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'TSLA']

    raw_tickers = list(tickers)
    exclude_industries = ['Biotechnology', 'Airlines', 'Tobacco', 'Gambling', 'Casinos', 'Beverages—Wineries & Distilleries']
    
    print("正在對【全量美股】進行多線程行業與市值篩選，請稍候...")
    final_pool = []
    
    # 💡 為了應付數千隻股票的處理，這裡引入了「多線程技術 (Multi-threading)」
    # 讓雲端伺服器同時檢查多隻股票，大幅提升全量掃描速度，防止超時
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(check_single_stock, t, exclude_industries): t for t in raw_tickers}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                final_pool.append(res)
                
    print(f"全量過濾完畢！最終進入 500 日線篩選的優質股票共: {len(final_pool)} 隻")
    return final_pool

def screen_500_day_ma_breakout(tickers):
    breakout_list = []
    start_date = (datetime.now() - timedelta(days=1000)).strftime('%Y-%m-%d')
    
    print(f"正在下載 {len(tickers)} 隻精選股的 K 線數據並計算 500 日線...")
    try:
        data = yf.download(tickers, start=start_date, interval='1d', group_by='ticker', progress=False)
    except Exception as e:
        print(f"批量下載 K 線失敗: {e}")
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
            
            # 突破 500日線 條件
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
    # 1. 獲取滿足條件的【完整】美股池
    filtered_pool = get_filtered_us_pool()
    
    # 2. 執行 500 日線突破篩選
    results = screen_500_day_ma_breakout(filtered_pool)
    
    # 3. 發送報告
    message_title = f"🎯 *【Agent 全量美股篩選報告】*\n日期: {datetime.now().strftime('%Y-%m-%d')}\n篩選範圍: SEC 全量美股普通股\n過濾條件: 市值>10億 | 剔除生技/航空/煙/酒/賭\n指標條件: *突破 500日均線*\n掃描總數: {len(filtered_pool)} 隻優質美股\n\n"
    
    if results:
        message_body = "🔥 *成功突破 500日線 的標的 (按大戶量比排序)：*\n"
        results = sorted(results, key=lambda x: x['Volume_Ratio'], reverse=True)
        for stock in results[:15]:
            message_body += f" 📈 *{stock['Ticker']}*\n  └ 現價: ${stock['Close']}\n  └ 大戶成交量比: {stock['Volume_Ratio']}x\n\n"
    else:
        message_body = "😴 *全量股票池中，本日暫時沒有股票突破 500日線。*"
        
    send_telegram_message(message_title + message_body)
    print("全量 500日線篩選任務完成！")
