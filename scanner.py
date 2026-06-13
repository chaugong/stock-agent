import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def screen_500_ma_breakout(tickers, period_type='W'):
    """
    篩選突破 500日/週線的股票
    :param tickers: 股票代號列表 (例如 ['AAPL', 'MSFT', '700.HK'])
    :param period_type: 'D' 代表日線, 'W' 代表週線
    """
    breakout_list = []
    interval = '1d' if period_type == 'D' else '1wk'
    
    # 500個週期需要足夠的歷史數據
    start_date = (datetime.now() - timedelta(days=500 * 8)).strftime('%Y-%m-%d')
    
    for ticker in tickers:
        try:
            # 下載數據
            df = yf.download(ticker, start=start_date, interval=interval, progress=False)
            if len(df) < 500:
                continue
                
            # 計算 500 均線
            df['MA_500'] = df['Close'].rolling(window=500).mean()
            
            # 獲取最近兩期的數據 (當期與前期)
            current_close = df['Close'].iloc[-1]
            current_ma = df['MA_500'].iloc[-1]
            prev_close = df['Close'].iloc[-2]
            prev_ma = df['MA_500'].iloc[-2]
            current_volume = df['Volume'].iloc[-1]
            avg_volume = df['Volume'].iloc[-20:].mean() # 20期平均量
            
            # 判斷突破條件：前一期在線下，最新一期收在線上
            if prev_close <= prev_ma and current_close > current_ma:
                # 計算量比 (大戶思維：爆量突破更可靠)
                volume_ratio = current_volume / avg_volume
                
                breakout_list.append({
                    'Ticker': ticker,
                    'Close': round(current_close, 2),
                    'MA500': round(current_ma, 2),
                    'Volume_Ratio': round(volume_ratio, 2)
                })
        except Exception as e:
            print(f"無法處理 {ticker}: {e}")
            
    return pd.DataFrame(breakout_list)

# 測試範例
if __name__ == "__main__":
    # 這裡可以替換成你的股票池，例如標普500成分股或港股通名單
    test_pool = ['AAPL', 'AMD', 'NVDA', 'BABA', '0700.HK', '3690.HK'] 
    
    print("正在篩選每週突破 500週線 的股票...")
    results = screen_500_ma_breakout(test_pool, period_type='W')
    
    if not results.empty:
        print("\n🔥 成功突破 500週線 的股票清單：")
        print(results.to_string(index=False))
    else:
        print("\n本週暫時沒有股票突破 500週線。")
