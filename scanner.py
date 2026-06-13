import os
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta

def send_telegram_message(message):
    """將訊息發送到使用者的 Telegram"""
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("錯誤：找不到 Telegram Token 或 Chat ID，請檢查 GitHub Secrets 設定。")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("Telegram 訊息發送成功！")
        else:
            print(f"Telegram 發送失敗，錯誤碼: {response.status_code}, 回應: {response.text}")
    except Exception as e:
        print(f"發送 Telegram 時發生異常: {e}")

def screen_500_ma_breakout(tickers, period_type='W'):
    """篩選突破 500日/週線的股票"""
    breakout_list = []
    interval = '1d' if period_type == 'D' else '1wk'
    start_date = (datetime.now() - timedelta(days=500 * 8)).strftime('%Y-%m-%d')
    
    for ticker in tickers:
        try:
            df = yf.download(ticker, start=start_date, interval=interval, progress=False)
            if len(df) < 500:
                continue
                
            df['MA_500'] = df['Close'].rolling(window=500).mean()
            
            current_close = df['Close'].iloc[-1]
            current_ma = df['MA_500'].iloc[-1]
            prev_close = df['Close'].iloc[-2]
            prev_ma = df['MA_500'].iloc[-2]
            current_volume = df['Volume'].iloc[-1]
            avg_volume = df['Volume'].iloc[-20:].mean()
            
            # 判斷突破：前一期在線下，最新一期在線上
            if prev_close <= prev_ma and current_close > current_ma:
                volume_ratio = current_volume / avg_volume
                breakout_list.append({
                    'Ticker': ticker,
                    'Close': round(current_close, 2),
                    'Volume_Ratio': round(volume_ratio, 2)
                })
        except Exception as e:
            print(f"無法處理 {ticker}: {e}")
            
    return breakout_list

if __name__ == "__main__":
    # 這裡放你想監控的股票池（可以自行修改代碼增加股票）
    # 提示：有些剛上市或不夠 500 週歷史的股票會自動被忽略
    test_pool = ['AAPL', 'AMD', 'NVDA', 'BABA', '0700.HK', '3690.HK', 'TSLA', 'MSFT', 'INTC'] 
    
    print("正在執行每週 500 週線突破篩選...")
    results = screen_500_ma_breakout(test_pool, period_type='W')
    
    # 建立發送訊息內容
    message_title = f"🔔 *【Agent 每週選股報告】*\n檢查時間: {datetime.now().strftime('%Y-%m-%d')}\n篩選條件: 突破 500 週均線\n\n"
    
    if results:
        message_body = "🔥 *成功突破的股票清現：*\n"
        for stock in results:
            message_body += f"📈 *{stock['Ticker']}*\n └ 收市價: ${stock['Close']}\n └ 量比: {stock['Volume_Ratio']}x\n\n"
    else:
        message_body = "😴 *本週測試股票池中，暫時沒有股票突破 500 週線。*"
        
    full_message = message_title + message_body
    
    # 執行發送
    send_telegram_message(full_message)
