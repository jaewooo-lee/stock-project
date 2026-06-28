import requests
from bs4 import BeautifulSoup
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import os
import shutil
import json
import google.generativeai as genai
from jinja2 import Template
from app import database, config

# Initialize Gemini API if key is available
if config.GEMINI_API_KEY:
    genai.configure(api_key=config.GEMINI_API_KEY)

def fetch_kr_stock(ticker: str):
    """
    Fetch South Korea stock information from Naver Realtime API.
    """
    url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{ticker}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("resultCode") == "success":
                areas = data.get("result", {}).get("areas", [])
                if areas and areas[0].get("datas"):
                    item = areas[0]["datas"][0]
                    price = item.get("nv")
                    change = item.get("cv")
                    change_rate = item.get("cr")
                    rf = item.get("rf") # '1' upper limit, '2' rise, '3' flat, '4' lower limit, '5' fall
                    prev_close = item.get("pcv")
                    
                    sign = ""
                    if rf in ["1", "2"]:
                        sign = "+"
                    elif rf in ["4", "5"]:
                        sign = "-"

                    return {
                        "ticker": ticker,
                        "name": item.get("nm", "Unknown"),
                        "price": f"{price:,}" if price is not None else "N/A",
                        "change": f"{sign}{change:,}" if change is not None and change != 0 else "0",
                        "change_rate": f"{sign}{change_rate}%" if change_rate is not None else "0.0%",
                        "prev_close": f"{prev_close:,}" if prev_close is not None else "N/A",
                        "raw_change_rate": float(change_rate) if change_rate is not None else 0.0,
                        "status": "rise" if rf in ["1", "2"] else "fall" if rf in ["4", "5"] else "flat"
                    }
    except Exception as e:
        print(f"Error fetching KR stock {ticker}: {e}")
    return None

def fetch_us_stock(ticker: str):
    """
    Fetch US stock information from yfinance.
    """
    try:
        stock = yf.Ticker(ticker)
        # Fetch 1 day history for reliability
        hist = stock.history(period="2d")
        if not hist.empty and len(hist) >= 1:
            info = stock.info
            name = info.get("longName", ticker)
            
            # Extract close prices
            if len(hist) >= 2:
                prev_close = hist['Close'].iloc[-2]
                current_price = hist['Close'].iloc[-1]
            else:
                prev_close = info.get("previousClose", hist['Close'].iloc[0])
                current_price = hist['Close'].iloc[-1]

            change = current_price - prev_close
            change_rate = (change / prev_close) * 100 if prev_close else 0.0
            
            sign = "+" if change > 0 else "-" if change < 0 else ""
            status = "rise" if change > 0 else "fall" if change < 0 else "flat"
            
            return {
                "ticker": ticker,
                "name": name,
                "price": f"{current_price:,.2f}",
                "change": f"{sign}{abs(change):,.2f}",
                "change_rate": f"{sign}{abs(change_rate):.2f}%",
                "prev_close": f"{prev_close:,.2f}",
                "raw_change_rate": change_rate,
                "status": status
            }
    except Exception as e:
        print(f"Error fetching US stock {ticker}: {e}")
    return None

def fetch_market_indices():
    """
    Fetch South Korea and Global Market Indices, and USD/KRW Exchange Rate.
    """
    indices = {}
    
    # 1. KOSPI & KOSDAQ from Naver API
    url = "https://polling.finance.naver.com/api/realtime?query=SERVICE_INDEX:KOSPI,KOSDAQ"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("resultCode") == "success":
                areas = data.get("result", {}).get("areas", [])
                if areas and areas[0].get("datas"):
                    for item in areas[0]["datas"]:
                        name = item.get("nm")
                        price = item.get("nv")
                        change = item.get("cv")
                        change_rate = item.get("cr")
                        rf = item.get("rf")
                        sign = "+" if rf in ["1", "2"] else "-" if rf in ["4", "5"] else ""
                        indices[name] = {
                            "price": f"{price:,.2f}" if price is not None else "N/A",
                            "change": f"{sign}{change:,.2f}" if change is not None else "0",
                            "change_rate": f"{sign}{change_rate}%" if change_rate is not None else "0.0%",
                            "status": "rise" if rf in ["1", "2"] else "fall" if rf in ["4", "5"] else "flat"
                        }
    except Exception as e:
        print(f"Error fetching KR indices: {e}")

    # Fallbacks or defaults if index fetch fails
    for k in ["코스피", "코스닥"]:
        if k not in indices:
            indices[k] = {"price": "N/A", "change": "0", "change_rate": "0.0%", "status": "flat"}

    # 2. S&P 500, NASDAQ, USD/KRW from yfinance
    yf_targets = {
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "환율 (USD/KRW)": "USDKRW=X"
    }
    
    for name, sym in yf_targets.items():
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="2d")
            if not hist.empty:
                if len(hist) >= 2:
                    prev_val = hist['Close'].iloc[-2]
                    curr_val = hist['Close'].iloc[-1]
                else:
                    curr_val = hist['Close'].iloc[-1]
                    prev_val = curr_val # default
                
                change = curr_val - prev_val
                change_rate = (change / prev_val) * 100 if prev_val else 0.0
                sign = "+" if change > 0 else "-" if change < 0 else ""
                status = "rise" if change > 0 else "fall" if change < 0 else "flat"
                
                indices[name] = {
                    "price": f"{curr_val:,.2f}" if name != "환율 (USD/KRW)" else f"{curr_val:,.1f}",
                    "change": f"{sign}{abs(change):,.2f}" if name != "환율 (USD/KRW)" else f"{sign}{abs(change):,.1f}",
                    "change_rate": f"{sign}{abs(change_rate):.2f}%",
                    "status": status
                }
        except Exception as e:
            print(f"Error fetching {name} Index: {e}")
            indices[name] = {"price": "N/A", "change": "0", "change_rate": "0.0%", "status": "flat"}
            
    return indices

def scrape_naver_news():
    """
    Scrape 5 major financial news articles from Naver Finance main news.
    """
    url = "https://finance.naver.com/news/mainnews.naver"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    news_list = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        # Parse euc-kr encoding
        response.encoding = 'euc-kr'
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Naver finance main news selectors: dl.newsList dd.articleSubject a
        articles = soup.select("dl.newsList")
        for article in articles[:5]:
            subject_tag = article.select_one("dd.articleSubject a")
            summary_tag = article.select_one("dd.articleSummary")
            
            if subject_tag:
                title = subject_tag.get_text().strip()
                link = "https://finance.naver.com" + subject_tag["href"]
                summary = ""
                if summary_tag:
                    # Clean up summary text (remove photos/author tags if any)
                    summary = summary_tag.get_text().strip()
                    # Clean whitespaces
                    summary = " ".join(summary.split())
                
                news_list.append({
                    "title": title,
                    "url": link,
                    "summary": summary
                })
    except Exception as e:
        print(f"Error scraping Naver Finance news: {e}")
        
    return news_list

def summarize_news_with_gemini(news_list):
    """
    Summarize scraped news list using Google Gemini API.
    If API Key is missing or error occurs, fall back to scraped summary.
    """
    if not config.GEMINI_API_KEY or not news_list:
        print("Gemini API not configured or news list is empty. Using fallback summaries.")
        return news_list
        
    prompt = (
        "아래는 오늘 스크랩된 주요 금융 뉴스 목록입니다. "
        "각 뉴스 기사에 대해, 모바일 웹 앱의 아코디언 UI에 들어갈 핵심을 2~3줄로 매우 쉽고 명료한 한글로 요약해주세요.\n\n"
        "반드시 기사 내용을 요약해야 하며, 출력 형식은 아래 JSON 구조를 엄격히 준수해 리스트 형태로 제공해주세요. "
        "별도의 마크다운 설명이나 텍스트 없이 오직 JSON 블록만 반환하세요.\n"
        "[\n"
        "  {\n"
        "    \"title\": \"(기사 원본 제목 그대로)\",\n"
        "    \"url\": \"(제공된 원본 URL 그대로)\",\n"
        "    \"summary\": \"(여기에 2~3줄로 요약된 내용)\"\n"
        "  }\n"
        "]\n\n"
        "뉴스 목록:\n"
    )
    
    for idx, item in enumerate(news_list):
        prompt += f"뉴스 {idx+1}:\n제목: {item['title']}\n원문 URL: {item['url']}\n스니펫: {item['summary']}\n\n"
        
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean JSON markdown blocks if Gemini returns them
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        summaries = json.loads(text)
        # Merge URL/Title fallback just in case
        for i, s in enumerate(summaries):
            if i < len(news_list):
                news_list[i]["summary"] = s.get("summary", news_list[i]["summary"])
                news_list[i]["title"] = s.get("title", news_list[i]["title"])
        print("Successfully summarized news with Gemini API.")
    except Exception as e:
        print(f"Error during Gemini news summarization: {e}. Falling back to default summaries.")
        
    return news_list

def cleanup_old_reports(reports_dir: str, days_threshold: int):
    """
    Deletes report HTML files in reports_dir that are older than days_threshold.
    """
    now = datetime.now()
    threshold_time = now - timedelta(days=days_threshold)
    
    print(f"Starting old reports cleanup (threshold: {days_threshold} days)...")
    if not os.path.exists(reports_dir):
        return
        
    count = 0
    for filename in os.listdir(reports_dir):
        if filename.startswith("report_") and filename.endswith(".html"):
            file_path = os.path.join(reports_dir, filename)
            try:
                # Check modification time
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                if file_time < threshold_time:
                    os.remove(file_path)
                    print(f"Deleted old report file: {filename}")
                    count += 1
            except Exception as e:
                print(f"Error deleting file {filename}: {e}")
                
    print(f"Cleanup complete. Deleted {count} files.")

# HTML template matching mobile-first aesthetic with details (accordion)
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>주식 tracker 리포트</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Inter', sans-serif;
            background-color: #0b0f19;
            color: #f3f4f6;
        }
        .header-font {
            font-family: 'Outfit', sans-serif;
        }
        .glass {
            background: rgba(17, 25, 40, 0.75);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }
        .up-color { color: #f43f5e; }
        .down-color { color: #3b82f6; }
        .flat-color { color: #9ca3af; }
    </style>
</head>
<body class="min-h-screen pb-12">
    <div class="max-w-md mx-auto px-4 pt-6">
        
        <!-- Header -->
        <header class="flex justify-between items-center mb-6">
            <div>
                <h1 class="header-font text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400">STOCK TRACKER</h1>
                <p class="text-xs text-slate-400 font-medium mt-0.5">발행 시각: {{ generated_time }}</p>
            </div>
            <span class="px-2.5 py-1 text-xs font-semibold text-emerald-400 bg-emerald-950/50 border border-emerald-900/50 rounded-full">실시간 업데이트</span>
        </header>

        <!-- Market Index Section -->
        <section class="mb-6">
            <h2 class="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">주요 시장 지수</h2>
            <div class="grid grid-cols-2 gap-3">
                {% for name, info in indices.items() %}
                <div class="glass p-3.5 rounded-2xl">
                    <span class="text-xs font-medium text-slate-400">{{ name }}</span>
                    <div class="flex items-baseline justify-between mt-1">
                        <span class="text-lg font-bold">{{ info.price }}</span>
                        <span class="text-xs font-semibold {% if info.status == 'rise' %}up-color{% elif info.status == 'fall' %}down-color{% else %}flat-color{% endif %}">
                            {{ info.change_rate }}
                        </span>
                    </div>
                </div>
                {% endfor %}
            </div>
        </section>

        <!-- Watchlist Section -->
        <section class="mb-6">
            <h2 class="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">관심 종목 동향</h2>
            <div class="glass rounded-2xl overflow-hidden">
                {% if watchlist_data %}
                <div class="divide-y divide-slate-800">
                    {% for stock in watchlist_data %}
                    <div class="flex justify-between items-center p-4">
                        <div>
                            <p class="font-semibold text-slate-100">{{ stock.name }}</p>
                            <p class="text-[10px] text-slate-500 uppercase font-medium mt-0.5">{{ stock.market }} • {{ stock.ticker }}</p>
                        </div>
                        <div class="text-right">
                            <p class="font-bold text-slate-100">{{ stock.price }}</p>
                            <p class="text-xs font-semibold {% if stock.status == 'rise' %}up-color{% elif stock.status == 'fall' %}down-color{% else %}flat-color{% endif %} mt-0.5">
                                {{ stock.change }} ({{ stock.change_rate }})
                            </p>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                {% else %}
                <div class="p-6 text-center text-sm text-slate-500">
                    등록된 관심 종목이 없습니다.
                </div>
                {% endif %}
            </div>
        </section>

        <!-- AI News Section -->
        <section class="mb-6">
            <div class="flex items-center gap-2 mb-3">
                <h2 class="text-sm font-semibold text-slate-400 uppercase tracking-wider">주요 금융 뉴스 (AI 요약)</h2>
                <span class="text-[10px] bg-indigo-950/50 text-indigo-400 border border-indigo-900/50 px-2 py-0.5 rounded font-bold">Gemini 1.5</span>
            </div>
            
            <div class="space-y-3">
                {% if news_data %}
                {% for news in news_data %}
                <details class="group glass rounded-2xl overflow-hidden border border-slate-800 transition-all duration-300" {% if loop.index == 1 %}open{% endif %}>
                    <summary class="flex justify-between items-center p-4 cursor-pointer list-none select-none">
                        <span class="font-medium text-sm text-slate-200 pr-4 leading-snug group-open:text-indigo-300 group-open:font-semibold transition-colors duration-200">
                            {{ news.title }}
                        </span>
                        <div class="text-slate-500 group-open:rotate-180 transition-transform duration-300 flex-shrink-0">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                            </svg>
                        </div>
                    </summary>
                    <div class="px-4 pb-4 pt-1 text-xs text-slate-400 leading-relaxed border-t border-slate-800/40">
                        <p class="whitespace-pre-line">{{ news.summary }}</p>
                        <a href="{{ news.url }}" target="_blank" class="inline-flex items-center gap-1 text-indigo-400 hover:text-indigo-300 font-semibold mt-3 transition-colors duration-200">
                            원문 기사 읽기
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>
                        </a>
                    </div>
                </details>
                {% endfor %}
                {% else %}
                <div class="glass p-6 text-center text-sm text-slate-500 rounded-2xl">
                    수집된 금융 뉴스가 없습니다.
                </div>
                {% endif %}
            </div>
        </section>

    </div>
</body>
</html>
"""

def generate_report_job():
    """
    Main job sequence:
    1. Fetch stock data for watchlist
    2. Fetch market indices and exchange rates
    3. Scrape Naver news
    4. Summarize news via Gemini API
    5. Render HTML report (save latest to index.html and historical copy)
    6. Record history in DB
    7. Send KakaoTalk notification
    """
    print("=== Start Stock Data Collection Job ===")
    
    # 1. Get stocks list from DB
    watchlist = database.get_watchlist()
    watchlist_data = []
    
    for item in watchlist:
        ticker = item["ticker"]
        market = item["market"]
        
        if market == "KR":
            res = fetch_kr_stock(ticker)
        else:
            res = fetch_us_stock(ticker)
            
        if res:
            watchlist_data.append(res)
            
    # 2. Get market indices
    indices = fetch_market_indices()
    
    # 3. Scrape news
    news_raw = scrape_naver_news()
    
    # 4. Summarize news
    news_data = summarize_news_with_gemini(news_raw)
    
    # 5. Render HTML
    now = datetime.now()
    generated_time = now.strftime("%Y-%m-%d %H:%M:%S")
    time_stamp = now.strftime("%Y%m%d_%H%M")
    
    t = Template(HTML_TEMPLATE)
    html_content = t.render(
        generated_time=generated_time,
        indices=indices,
        watchlist_data=watchlist_data,
        news_data=news_data
    )
    
    # Save filenames
    latest_filename = "index.html"
    historical_filename = f"report_{time_stamp}.html"
    
    latest_path = os.path.join(config.REPORTS_DIR, latest_filename)
    historical_path = os.path.join(config.REPORTS_DIR, historical_filename)
    
    try:
        # Write to latest index.html
        with open(latest_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        # Write to historical file
        with open(historical_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        print(f"Successfully generated HTML reports: {latest_filename}, {historical_filename}")
    except Exception as e:
        print(f"Error saving HTML report files: {e}")
        return False
        
    # 6. Save to report_history DB
    report_title = f"{now.strftime('%Y-%m-%d %H:%M')} 리포트"
    database.add_report_history(report_title, historical_filename)
    
    # 7. Cleanup old reports (> 90 days)
    cleanup_old_reports(config.REPORTS_DIR, config.CLEANUP_DAYS)
    
    # 8. Send KakaoTalk Notification
    # Find highest rise and fall stock
    highest_stock = None
    lowest_stock = None
    if watchlist_data:
        # filter out stocks without valid rate
        valid_stocks = [s for s in watchlist_data if s["raw_change_rate"] is not None]
        if valid_stocks:
            highest_stock = max(valid_stocks, key=lambda x: x["raw_change_rate"])
            lowest_stock = min(valid_stocks, key=lambda x: x["raw_change_rate"])
            
    # Format message
    msg = f"[Stock Tracker 리포트 발송]\n"
    msg += f"발행시각: {now.strftime('%m/%d %H:%M')}\n\n"
    
    # Indices string
    index_parts = []
    for k in ["코스피", "S&P 500", "환율 (USD/KRW)"]:
        if k in indices and indices[k]["price"] != "N/A":
            index_parts.append(f"{k}: {indices[k]['price']}({indices[k]['change_rate']})")
    if index_parts:
        msg += "📈 주요 지수:\n" + "\n".join(index_parts) + "\n\n"
        
    # Stock info
    if highest_stock or lowest_stock:
        msg += "📊 종목 주요 변동:\n"
        if highest_stock:
            msg += f"🔥 최고상승: {highest_stock['name']} ({highest_stock['change_rate']})\n"
        if lowest_stock and lowest_stock != highest_stock:
            msg += f"❄️ 최고하락: {lowest_stock['name']} ({lowest_stock['change_rate']})\n"
        msg += "\n"
        
    # News Headline
    if news_data:
        msg += "📰 주요 금융 뉴스:\n"
        for i, news in enumerate(news_data[:3]): # Top 3 headlines
            msg += f"{i+1}. {news['title']}\n"
        msg += "\n"
        
    msg += f"🔗 보고서 모바일 링크:\n{config.BASE_URL}"
    
    from app import notifier
    # Send
    notifier.send_kakao_message(msg, config.BASE_URL)
    
    print("=== Stock Data Collection Job Completed ===")
    return True
