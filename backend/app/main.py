from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import requests
import yfinance as yf
from contextlib import asynccontextmanager
from app import database, scheduler, collector, config

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database and Start Scheduler
    database.init_db()
    scheduler.start_scheduler()
    yield
    # Shutdown: Shutdown Scheduler
    scheduler.shutdown_scheduler()

app = FastAPI(
    title="Stock Tracker Backend API",
    version="3.0",
    lifespan=lifespan
)

# Enable CORS for local development frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request bodies
class WatchlistItem(BaseModel):
    ticker: str
    name: str
    market: str

class ScheduleItem(BaseModel):
    time_str: str

# 1. Watchlist Endpoints
@app.get("/api/watchlist")
def read_watchlist():
    return database.get_watchlist()

@app.post("/api/watchlist")
def create_watchlist_item(item: WatchlistItem):
    success = database.add_to_watchlist(item.ticker, item.name, item.market)
    if not success:
        raise HTTPException(status_code=400, detail="Stock already exists in watchlist or invalid format.")
    return {"message": f"Successfully added {item.name} to watchlist."}

@app.delete("/api/watchlist/{item_id}")
def delete_watchlist_item(item_id: int):
    success = database.delete_from_watchlist(item_id)
    if not success:
        raise HTTPException(status_code=404, detail="Watchlist item not found.")
    return {"message": "Successfully deleted item from watchlist."}

# 2. Schedule Endpoints
@app.get("/api/schedules")
def read_schedules():
    return database.get_schedules()

@app.post("/api/schedules")
def create_schedule(item: ScheduleItem):
    success = database.add_schedule(item.time_str)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add schedule. Duplicate or invalid time format (HH:MM).")
    scheduler.reload_jobs()
    return {"message": f"Successfully registered schedule for {item.time_str}."}

@app.put("/api/schedules/{schedule_id}/toggle")
def toggle_schedule_status(schedule_id: int, is_active: bool):
    success = database.toggle_schedule(schedule_id, is_active)
    if not success:
        raise HTTPException(status_code=404, detail="Schedule not found.")
    scheduler.reload_jobs()
    return {"message": f"Schedule state updated to {'active' if is_active else 'inactive'}."}

@app.delete("/api/schedules/{schedule_id}")
def delete_schedule_item(schedule_id: int):
    success = database.delete_schedule(schedule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Schedule not found.")
    scheduler.reload_jobs()
    return {"message": "Successfully deleted schedule."}

# 3. Report History Endpoints
@app.get("/api/reports")
def read_reports():
    return database.get_report_history()

# 4. Manual Trigger
@app.post("/api/trigger")
def trigger_collection(background_tasks: BackgroundTasks):
    """
    Triggers the report generation and notification job instantly in the background.
    """
    background_tasks.add_task(collector.generate_report_job)
    return {"message": "Stock report collection and notification job triggered in background."}

# 5. Stock Search API (KR & US)
@app.get("/api/search")
def search_stock(q: str = Query(..., min_length=1)):
    """
    Search endpoint supporting:
    - KR Stocks: Naver Auto-complete API
    - US Stocks: Direct ticker check via yfinance
    """
    results = []
    
    # 1. KR Stock search using Naver Auto-Complete API
    naver_search_url = f"https://ac.finance.naver.com/ac?q={q}&q_enc=utf-8&st=1&r_lt=1&r_enc=utf-8&r_format=json"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        res = requests.get(naver_search_url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            # Parse Naver auto-complete items
            # Format: [["삼성전자", "005930", "samsung", "KOSPI", "삼성전자"]]
            items_list = data.get("items", [])
            if items_list and len(items_list[0]) > 0:
                for item in items_list[0]:
                    results.append({
                        "ticker": item[1],
                        "name": item[0],
                        "market": "KR",
                        "display_market": item[3]
                    })
    except Exception as e:
        print(f"Error during Naver stock search: {e}")
        
    # 2. US Stock search (If the query looks like a US Ticker, e.g. letters only)
    if q.isalpha():
        ticker_str = q.upper()
        try:
            stock = yf.Ticker(ticker_str)
            info = stock.info
            # Validate if it has a price or currency to ensure it exists
            if "currentPrice" in info or "regularMarketPrice" in info or "bid" in info:
                results.append({
                    "ticker": ticker_str,
                    "name": info.get("longName", info.get("shortName", ticker_str)),
                    "market": "US",
                    "display_market": info.get("exchange", "US Exchange")
                })
        except Exception:
            pass # Ticker doesn't exist or error in lookup
            
    return results

# 6. KakaoTalk OAuth URL
@app.get("/api/kakao/auth-url")
def get_kakao_auth_url():
    if not config.KAKAO_REST_API_KEY:
        return {"url": None}
    url = f"https://kauth.kakao.com/oauth/authorize?client_id={config.KAKAO_REST_API_KEY}&redirect_uri={config.KAKAO_REDIRECT_URI}&response_type=code"
    return {"url": url}

# 7. KakaoTalk OAuth Helper Callback
@app.get("/api/kakao/callback", response_class=HTMLResponse)
def kakao_callback(code: str = None, error: str = None):
    """
    Helper endpoint for retrieving Kakao API Refresh Token.
    Instructs the developer with instructions on how to use it in .env.
    """
    if error:
        return f"""
        <html>
            <body style="font-family: sans-serif; text-align: center; padding-top: 50px; background-color: #0b0f19; color: #f3f4f6;">
                <h1 style="color: #f43f5e;">카카오 로그인 에러</h1>
                <p>{error}</p>
            </body>
        </html>
        """
        
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code missing")
        
    # Request Token exchange
    url = "https://kauth.kakao.com/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": config.KAKAO_REST_API_KEY,
        "redirect_uri": config.KAKAO_REDIRECT_URI,
        "code": code
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        response = requests.post(url, data=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            refresh_token = data.get("refresh_token")
            access_token = data.get("access_token")
            
            return f"""
            <html>
                <body style="font-family: sans-serif; padding: 40px; background-color: #0b0f19; color: #f3f4f6; line-height: 1.6;">
                    <div style="max-w: 600px; margin: 0 auto; background: rgba(17, 25, 40, 0.75); border: 1px solid rgba(255, 255, 255, 0.08); padding: 30px; border-radius: 20px;">
                        <h1 style="color: #4ade80; margin-top: 0;">🎉 카카오 인증 성공!</h1>
                        <p>아래 발급된 <strong>Refresh Token</strong>을 복사하여 프로젝트 루트 폴더의 <code>.env</code> 파일에 입력해 주세요.</p>
                        
                        <div style="background-color: #1e293b; padding: 15px; border-radius: 10px; word-break: break-all; font-family: monospace; font-size: 14px; border: 1px solid #334155; margin: 20px 0; color: #38bdf8;">
                            {refresh_token}
                        </div>
                        
                        <p style="font-size: 13px; color: #94a3b8;">
                            * 이 리프레시 토큰은 약 2개월간 유효하며, 서버 백엔드에서 자동으로 만료 전에 갱신하여 엑세스 토큰을 받아오는 데 사용됩니다.
                        </p>
                    </div>
                </body>
            </html>
            """
        else:
            return f"""
            <html>
                <body style="font-family: sans-serif; text-align: center; padding-top: 50px; background-color: #0b0f19; color: #f3f4f6;">
                    <h1 style="color: #f43f5e;">토큰 발급 실패</h1>
                    <p>상태 코드: {response.status_code}</p>
                    <p>{response.text}</p>
                </body>
            </html>
            """
    except Exception as e:
        return f"인증 처리 도중 에러가 발생했습니다: {str(e)}"
