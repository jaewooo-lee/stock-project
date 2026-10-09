import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
import requests
import yfinance as yf
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 상수 및 파일명 정의
TOKEN_FILE = "data/kakao_token.json"
HISTORY_FILE = "data/kakao_history.json"

# 데이터 폴더 자동 생성
os.makedirs("data", exist_ok=True)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def load_history():
    """
    이력 파일을 읽어옵니다.
    """
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_history(history):
    """
    이력을 파일에 씁니다.
    """
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        return False

def add_history_entry(message, status, error=None):
    """
    이력을 추가하고 최대 100건으로 유지합니다.
    """
    history = load_history()
    new_entry = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "message": message,
        "status": status,
        "error": error
    }
    history.insert(0, new_entry)
    if len(history) > 100:
        history = history[:100]
    save_history(history)
    return new_entry

def load_access_token():
    """
    로컬 JSON 토큰 파일에서 access_token을 로드합니다.
    """
    if not os.path.exists(TOKEN_FILE):
        return None
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            token_info = json.load(f)
            return token_info.get("access_token")
    except Exception:
        return None

def refresh_kakao_token():
    """
    Refresh Token을 사용해 카카오에 신규 Access Token을 요청하고 갱신합니다.
    """
    if not os.path.exists(TOKEN_FILE):
        raise FileNotFoundError("토큰 파일이 존재하지 않습니다. 먼저 대시보드에서 연동해 주세요.")
        
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        token_info = json.load(f)
        
    refresh_token = token_info.get("refresh_token")
    if not refresh_token:
        raise ValueError("토큰 파일에 refresh_token이 존재하지 않습니다.")
        
    load_dotenv()
    rest_api_key = os.getenv("KAKAO_REST_API_KEY")
    client_secret = os.getenv("KAKAO_CLIENT_SECRET")
    
    token_url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "refresh_token": refresh_token
    }
    if client_secret:
        data["client_secret"] = client_secret
        
    response = requests.post(token_url, data=data)
    refreshed_info = response.json()
    
    if "access_token" not in refreshed_info:
        raise Exception(f"토큰 갱신 실패: {refreshed_info.get('error_description', '알 수 없는 오류')}")
        
    token_info["access_token"] = refreshed_info["access_token"]
    if "refresh_token" in refreshed_info:
        token_info["refresh_token"] = refreshed_info["refresh_token"]
        
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(token_info, f, ensure_ascii=False, indent=4)
        
    return token_info["access_token"]

def send_talk_message(message_text):
    """
    카카오 공식 API를 통해 직접 나에게 보내기 전송을 수행합니다.
    401 만료 시 자동 토큰 갱신을 시도합니다.
    """
    access_token = load_access_token()
    if not access_token:
        err_msg = "저장된 토큰이 없습니다. 대시보드(http://localhost:5001)에 먼저 연동을 진행해 주세요."
        print("[-] " + err_msg)
        add_history_entry(message_text, "Failed (Cron)", err_msg)
        return False
        
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    template_object = {
        "object_type": "text",
        "text": message_text,
        "link": {
            "web_url": "https://developers.kakao.com",
            "mobile_web_url": "https://developers.kakao.com"
        },
        "button_title": "카카오 디벨로퍼스"
    }
    
    payload = {
        "template_object": json.dumps(template_object, ensure_ascii=False)
    }
    
    response = requests.post(url, headers=headers, data=payload)
    
    # 401 만료 시 자동 갱신 후 전송 재시도
    if response.status_code == 401:
        print("[*] 엑세스 토큰 만료 감지. 토큰 자동 리프레시 시도 중...")
        try:
            new_access_token = refresh_kakao_token()
            headers["Authorization"] = f"Bearer {new_access_token}"
            response = requests.post(url, headers=headers, data=payload)
        except Exception as e:
            err_msg = f"토큰 만료로 인한 갱신 시도 실패: {str(e)}"
            print("[-] " + err_msg)
            add_history_entry(message_text, "Failed (Cron)", err_msg)
            return False
            
    if response.status_code == 200:
        result = response.json()
        if result.get("result_code") == 0:
            print("[+] 카카오톡 메시지가 성공적으로 발송되었습니다.")
            add_history_entry(message_text, "Success (Cron)")
            return True
        else:
            err_msg = f"카카오 API 오류 (코드: {result.get('result_code')})"
            print("[-] " + err_msg)
            add_history_entry(message_text, "Failed (Cron)", err_msg)
            return False
    else:
        err_msg = f"API HTTP 에러 (상태 코드: {response.status_code})"
        print("[-] " + err_msg)
        add_history_entry(message_text, "Failed (Cron)", err_msg)
        return False

def fetch_news_headlines(keyword):
    """
    Google News RSS를 파싱하여 특정 키워드에 대한 최신 뉴스 3개의 제목을 가져옵니다.
    """
    encoded_keyword = urllib.parse.quote(keyword)
    rss_url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=ko&gl=KR&ceid=KR:ko"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    req = urllib.request.Request(rss_url, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            
            headlines = []
            for item in root.findall('.//item')[:3]:
                title = item.find('title').text
                if " - " in title:
                    title = title.rsplit(" - ", 1)[0]
                headlines.append({"title": title})
                
            return headlines
    except Exception as e:
        print(f"[-] 뉴스 수집 오류 ({keyword}): {str(e)}")
        return []

def summarize_news_with_gemini(headlines, keyword):
    """
    Gemini 1.5 Flash API를 호출하여 수집된 뉴스 헤드라인들을 1~2줄로 요약합니다.
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        return None
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    titles_str = "\n".join([f"- {h['title']}" for h in headlines])
    prompt = (
        f"아래는 최근에 발행된 '{keyword}' 관련 뉴스 제목들입니다. "
        "이 헤드라인들을 종합하여 최근의 주요 동향이나 핵심 이슈를 한글 1~2줄로 짧게 요약해 주세요. "
        "~입니다, ~로 보입니다와 같이 정중한 어조의 요점만 간단하게 작성해 주세요.\n\n"
        f"뉴스 헤드라인 목록:\n{titles_str}"
    )
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            res_data = response.json()
            summary = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
            return summary
    except Exception as e:
        print(f"[-] Gemini AI 요약 오류: {str(e)}")
        
    return None

def get_stock_data(ticker_symbol, korean_name):
    """
    yfinance 주가 정보와 최신 뉴스 동향(AI 요약 또는 헤드라인 폴백)을 가공합니다.
    """
    ticker = yf.Ticker(ticker_symbol)
    hist = ticker.history(period="2d")
    
    if hist.empty or len(hist) < 1:
        return f"[-] {korean_name} ({ticker_symbol}) 데이터를 가져올 수 없습니다.\n"
        
    current_price = hist['Close'].iloc[-1]
    
    if len(hist) >= 2:
        prev_close = hist['Close'].iloc[-2]
        change = current_price - prev_close
        change_rate = (change / prev_close) * 100
    else:
        change = 0
        change_rate = 0.0
        
    high_val = hist['High'].iloc[-1]
    low_val = hist['Low'].iloc[-1]
    volume = hist['Volume'].iloc[-1]
    
    if change > 0:
        emoji = "📈"
        sign = "+"
    elif change < 0:
        emoji = "📉"
        sign = ""
    else:
        emoji = "➖"
        sign = ""
        
    stock_text = (
        f"🔹 {korean_name} ({ticker_symbol})\n"
        f"  • 현재가: {int(current_price):,}원\n"
        f"  • 전일대비: {emoji} {sign}{int(change):,}원 ({sign}{change_rate:.2f}%)\n"
        f"  • 금일고가: {int(high_val):,}원 | 금일저가: {int(low_val):,}원\n"
        f"  • 거래량: {int(volume):,}주\n"
    )
    
    headlines = fetch_news_headlines(korean_name)
    if headlines:
        summary = summarize_news_with_gemini(headlines, korean_name)
        if summary:
            stock_text += f"  • 📰 주요 동향 요약: {summary}\n"
        else:
            headlines_text = "\n".join([f"    - {h['title']}" for h in headlines])
            stock_text += f"  • 📰 최근 주요 뉴스:\n{headlines_text}\n"
    else:
        stock_text += "  • 📰 최근 뉴스 정보가 존재하지 않습니다.\n"
        
    return stock_text

def main():
    print("[*] 야후 파이낸스 주가 데이터 및 구글 뉴스 수집 중 (독립 구동 모드)...")
    
    try:
        samsung_info = get_stock_data("005930.KS", "삼성전자")
        hynix_info = get_stock_data("000660.KS", "SK하이닉스")
        
        message = (
            "📢 [데일리 주식 & 뉴스 브리핑]\n"
            "시장 요약 정보 및 주요 동향 분석입니다.\n\n"
            f"{samsung_info}\n"
            f"{hynix_info}"
        )
        
        print("[*] 수집된 메시지 본문:")
        print(message)
        print("=" * 40)
        
        # 카카오톡 다이렉트 전송 실행
        send_talk_message(message)
            
    except Exception as e:
        print(f"[-] 에러 발생: {str(e)}")

if __name__ == "__main__":
    main()
