import urllib.request
import json
import sys

def fetch_stock_info():
    url = "https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:005930,000660"
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            raw_data = response.read()
            # Naver's API might return UTF-8, but let's check decoding
            try:
                decoded_data = raw_data.decode('utf-8')
            except UnicodeDecodeError:
                decoded_data = raw_data.decode('euc-kr', errors='replace')
                
            data = json.loads(decoded_data)
            return data
    except Exception as e:
        print(f"Error fetching stock data: {e}", file=sys.stderr)
        return None

def print_stock_data(data):
    if not data or data.get("resultCode") != "success":
        print("Failed to retrieve valid data from Naver Finance.", file=sys.stderr)
        return

    datas = data.get("result", {}).get("areas", [{}])[0].get("datas", [])
    
    # Mapping stock code to clean names since API names might have encoding issues
    name_map = {
        "005930": "삼성전자 (Samsung Electronics)",
        "000660": "SK하이닉스 (SK Hynix)"
    }
    
    print("=" * 60)
    print(f"{'Stock Name':<30} | {'Price (KRW)':<12} | {'Change':<8} | {'Chg %':<8}")
    print("-" * 60)
    
    for item in datas:
        code = item.get("cd")
        name = name_map.get(code, item.get("nm", "Unknown"))
        price = item.get("nv")
        change = item.get("cv")
        change_rate = item.get("cr")
        rf = item.get("rf") # fluctuation code: '1'-upper limit, '2'-rise, '3'-flat, '4'-lower limit, '5'-fall
        
        # Determine change prefix (up / down)
        sign = ""
        if rf in ["1", "2"]:
            sign = "+"
        elif rf in ["4", "5"]:
            sign = "-"
            
        formatted_price = f"{price:,}" if price is not None else "N/A"
        formatted_change = f"{sign}{change:,}" if change is not None and change != 0 else "0"
        formatted_rate = f"{sign}{change_rate}%" if change_rate is not None else "0.0%"
        
        print(f"{name:<30} | {formatted_price:>12} | {formatted_change:>8} | {formatted_rate:>8}")
        
        # Detail information
        open_val = item.get("ov")
        high_val = item.get("hv")
        low_val = item.get("lv")
        prev_close = item.get("pcv")
        volume = item.get("aq")
        
        print(f"  [Details] Prev Close: {prev_close:,} | Open: {open_val:,} | High: {high_val:,} | Low: {low_val:,} | Volume: {volume:,}")
        print("-" * 60)
    print("=" * 60)

if __name__ == "__main__":
    stock_data = fetch_stock_info()
    if stock_data:
        print_stock_data(stock_data)
