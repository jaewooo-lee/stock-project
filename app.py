import os
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify, redirect, render_template
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# .env 파일 로드
load_dotenv()

app = Flask(__name__)

# 환경 변수 및 파일명 정의
REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET")
APP_API_KEY = os.getenv("APP_API_KEY")
REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI_LOCAL", "http://localhost:5001/oauth")
TOKEN_FILE = "data/kakao_token.json"
HISTORY_FILE = "data/kakao_history.json"
SCHEDULE_FILE = "data/kakao_schedule.json"

# 데이터 폴더 자동 생성
os.makedirs("data", exist_ok=True)

# 전역 스케줄러 인스턴스 생성
from zoneinfo import ZoneInfo
scheduler = BackgroundScheduler(daemon=True, timezone=ZoneInfo("Asia/Seoul"))

def run_stock_job():
    """
    주식 브리핑 백그라운드 태스크 실행 헬퍼
    """
    try:
        print("[*] 백그라운드 스케줄러: 주식 브리핑 전송 작업을 시작합니다...")
        import send_daily_stocks
        # 스크립트의 main을 직접 호출 (직접 리프레시 및 전송을 내장하고 있음)
        send_daily_stocks.main()
    except Exception as e:
        print(f"[-] 백그라운드 스케줄러 주식 작업 에러: {str(e)}")

def run_youtube_job(date_offset=-1):
    """
    유튜브 증시 요약 백그라운드 태스크 실행 헬퍼
    """
    try:
        print(f"[*] 백그라운드 스케줄러: 유튜브 증시 요약 작업을 시작합니다... (offset: {date_offset})")
        from datetime import datetime, timedelta
        target_date = (datetime.now() + timedelta(days=date_offset)).strftime("%Y-%m-%d")
        print(f"[*] 스케줄러 유튜브 요약 대상 날짜: {target_date}")
        import youtube_summarizer
        youtube_summarizer.run_summarizer_job(save=True, send_kakao=True, target_date=target_date)
    except Exception as e:
        print(f"[-] 백그라운드 스케줄러 유튜브 작업 에러: {str(e)}")


DEFAULT_SCHEDULES = [
    {
        "id": "schedule_1200",
        "cron": "0 12 * * *",
        "description": "정오 12시 주가 및 주요 뉴스 브리핑"
    },
    {
        "id": "schedule_1600",
        "cron": "0 16 * * *",
        "description": "오후 4시 주가 및 주요 뉴스 브리핑"
    },
    {
        "id": "schedule_youtube_0830",
        "cron": "30 8 * * tue-sat",
        "description": "화~토 아침 8시 30분 유튜브 미국 증시 요약",
        "job_type": "youtube",
        "date_offset": -1
    }
]

def load_schedules():
    """
    스케줄 목록을 설정 파일에서 읽어옵니다. 없으면 기본 설정을 생성하고 저장합니다.
    중복된 ID가 있거나 누락된 경우 고유한 ID로 자동 복원(Self-healing)하여 저장합니다.
    """
    if not os.path.exists(SCHEDULE_FILE):
        save_schedules(DEFAULT_SCHEDULES)
        return DEFAULT_SCHEDULES
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                return DEFAULT_SCHEDULES
            
            # 중복 ID 감지 및 고유화 (Self-healing)
            seen_ids = set()
            has_duplicates = False
            import time
            for idx, sch in enumerate(data):
                sch_id = sch.get("id")
                if not sch_id or sch_id in seen_ids:
                    has_duplicates = True
                    # 고유한 ID 부여 (밀리초 타임스탬프 + 인덱스 조합)
                    sch["id"] = f"schedule_{int(time.time() * 1000)}_{idx}"
                seen_ids.add(sch["id"])
                
            if has_duplicates:
                print("[!] 중복되거나 누락된 스케줄 ID 감지: 고유 ID로 자동 복구하여 파일에 다시 저장합니다.")
                save_schedules(data)
                
            return data
    except Exception as e:
        print(f"[-] 스케줄 로드 에러: {str(e)}")
        return DEFAULT_SCHEDULES

def save_schedules(schedules):
    """
    스케줄 목록을 설정 파일에 저장합니다.
    """
    try:
        with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump(schedules, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        return False

def update_active_schedules():
    """
    저장된 스케줄 설정을 토대로 백그라운드 스케줄러 작업을 동적 갱신합니다.
    """
    scheduler.remove_all_jobs()
    schedules = load_schedules()
    
    for sch in schedules:
        cron_expr = sch["cron"].strip()
        fields = cron_expr.split()
        if len(fields) != 5:
            print(f"[-] 잘못된 크론식 제외: {cron_expr}")
            continue
            
        try:
            trigger = CronTrigger(
                minute=fields[0],
                hour=fields[1],
                day=fields[2],
                month=fields[3],
                day_of_week=fields[4],
                timezone=ZoneInfo("Asia/Seoul")
            )
            job_type = sch.get("job_type", "stock")
            if job_type == "youtube":
                date_offset = int(sch.get("date_offset", -1))
                scheduler.add_job(
                    run_youtube_job,
                    trigger=trigger,
                    id=sch["id"],
                    kwargs={"date_offset": date_offset},
                    replace_existing=True
                )
            else:
                scheduler.add_job(
                    run_stock_job,
                    trigger=trigger,
                    id=sch["id"],
                    replace_existing=True
                )

            print(f"[+] 백그라운드 스케줄러에 작업 등록 완료: ID={sch['id']}, Cron='{cron_expr}'")
        except Exception as e:
            print(f"[-] 크론 트리거 등록 에러 (ID={sch['id']}): {str(e)}")

def load_history():
    """
    전송 이력을 로컬 JSON 파일에서 읽어옵니다.
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
    전송 이력을 로컬 JSON 파일에 저장합니다.
    """
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        return False

def add_history_entry(message, status, error=None):
    """
    새로운 전송 이력을 목록 최상단에 추가합니다.
    최대 100건으로 이력을 제한합니다.
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
    
    # 이력 최대 100개 제한
    if len(history) > 100:
        history = history[:100]
        
    save_history(history)
    return new_entry


def get_access_token():
    """
    저장된 토큰 파일에서 access_token을 읽어옵니다.
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
    Refresh Token을 사용하여 Access Token을 갱신하고 파일에 업데이트합니다.
    """
    if not os.path.exists(TOKEN_FILE):
        raise FileNotFoundError("토큰 파일이 존재하지 않습니다. 먼저 연동을 완료해 주세요.")
        
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        token_info = json.load(f)
        
    refresh_token = token_info.get("refresh_token")
    if not refresh_token:
        raise ValueError("토큰 파일에 refresh_token이 존재하지 않습니다.")
        
    # 새로운 환경변수가 갱신되었을 수 있으므로 다시 읽음
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

@app.route("/")
def index():
    """
    대시보드 메인 페이지 렌더링
    """
    return render_template("index.html")

@app.route("/oauth-login")
def oauth_login():
    """
    카카오 인증 URL로 리다이렉트
    """
    if not REST_API_KEY or REST_API_KEY == "your_kakao_rest_api_key_here":
        return "오류: .env 파일에 KAKAO_REST_API_KEY를 설정해 주세요.", 400
        
    auth_url = (
        f"https://kauth.kakao.com/oauth/authorize"
        f"?client_id={REST_API_KEY}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=talk_message"
    )
    return redirect(auth_url)

@app.route("/oauth")
def oauth():
    """
    카카오 OAuth Callback 처리
    """
    code = request.args.get("code")
    if not code:
        return "인가 코드를 받지 못했습니다.", 400

    token_url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": REST_API_KEY,
        "redirect_uri": REDIRECT_URI,
        "code": code
    }
    if CLIENT_SECRET:
        data["client_secret"] = CLIENT_SECRET
        
    try:
        response = requests.post(token_url, data=data)
        token_info = response.json()
        
        if "access_token" not in token_info:
            error_desc = token_info.get("error_description", "알 수 없는 오류")
            return f"토큰 발급 실패: {error_desc}", 400
            
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(token_info, f, ensure_ascii=False, indent=4)
            
        # 로그인 성공 후 메인 페이지로 이동
        return redirect("/")
    except Exception as e:
        return f"서버 에러가 발생했습니다: {str(e)}", 500

@app.route("/api/status")
def api_status():
    """
    현재 인증 연동 상태 반환 API
    """
    access_token = get_access_token()
    return jsonify({
        "authenticated": access_token is not None
    })

@app.route("/api/logout", methods=["POST"])
def api_logout():
    """
    연동 해제 (토큰 파일 삭제) API
    """
    if os.path.exists(TOKEN_FILE):
        try:
            os.remove(TOKEN_FILE)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    return jsonify({"success": True})

@app.route("/api/history")
def api_history():
    """
    전송 이력 목록 반환 API
    """
    return jsonify(load_history())

@app.route("/api/history/clear", methods=["POST"])
def api_history_clear():
    """
    전송 이력 전체 삭제 API
    """
    if save_history([]):
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "이력 삭제에 실패했습니다."}), 500

@app.route("/api/schedule")
def api_schedule():
    """
    현재 설정된 크론 스케줄 목록 반환
    """
    return jsonify(load_schedules())

@app.route("/api/schedule/add", methods=["POST"])
def api_schedule_add():
    """
    신규 크론 스케줄 등록 및 스케줄러 동적 반영
    """
    data = request.get_json()
    if not data or "cron" not in data:
        return jsonify({"success": False, "error": "크론식(cron)이 누락되었습니다."}), 400
        
    cron_expr = data["cron"].strip()
    description = data.get("description", "주식/뉴스 브리핑").strip()
    job_type = data.get("job_type", "stock").strip()
    
    if job_type not in ["stock", "youtube"]:
        return jsonify({"success": False, "error": "잘못된 작업 유형입니다. 'stock' 또는 'youtube'만 가능합니다."}), 400
        
    # 크론 트리거 유효성 검증
    fields = cron_expr.split()
    if len(fields) != 5:
        return jsonify({"success": False, "error": "올바른 5개 필드 크론식을 입력해 주세요. (예: 0 12 * * *)"}), 400
        
    try:
        CronTrigger(
            minute=fields[0],
            hour=fields[1],
            day=fields[2],
            month=fields[3],
            day_of_week=fields[4],
            timezone=ZoneInfo("Asia/Seoul")
        )
    except Exception as e:
        return jsonify({"success": False, "error": f"잘못된 크론식 표현입니다: {str(e)}"}), 400
        
    date_offset = data.get("date_offset", -1)
    try:
        date_offset = int(date_offset)
    except (ValueError, TypeError):
        date_offset = -1

    schedules = load_schedules()
    new_id = f"schedule_{int(datetime.now().timestamp() * 1000)}"
    new_sch = {
        "id": new_id,
        "cron": cron_expr,
        "description": description,
        "job_type": job_type,
        "date_offset": date_offset
    }
    schedules.append(new_sch)
    
    if save_schedules(schedules):
        update_active_schedules()
        return jsonify({"success": True, "schedule": new_sch})
    return jsonify({"success": False, "error": "스케줄을 저장하지 못했습니다."}), 500

@app.route("/api/schedule/edit", methods=["POST"])
def api_schedule_edit():
    """
    기존 크론 스케줄 수정 및 스케줄러 동적 반영
    """
    data = request.get_json()
    if not data or "id" not in data or "cron" not in data:
        return jsonify({"success": False, "error": "스케줄 ID(id)와 크론식(cron)이 누락되었습니다."}), 400
        
    sch_id = data["id"]
    cron_expr = data["cron"].strip()
    description = data.get("description", "주식/뉴스 브리핑").strip()
    job_type = data.get("job_type", "stock").strip()
    date_offset = data.get("date_offset", -1)
    
    if job_type not in ["stock", "youtube"]:
        return jsonify({"success": False, "error": "잘못된 작업 유형입니다. 'stock' 또는 'youtube'만 가능합니다."}), 400
        
    try:
        date_offset = int(date_offset)
    except (ValueError, TypeError):
        date_offset = -1
        
    # 크론 트리거 유효성 검증
    fields = cron_expr.split()
    if len(fields) != 5:
        return jsonify({"success": False, "error": "올바른 5개 필드 크론식을 입력해 주세요. (예: 0 12 * * *)"}), 400
        
    try:
        CronTrigger(
            minute=fields[0],
            hour=fields[1],
            day=fields[2],
            month=fields[3],
            day_of_week=fields[4],
            timezone=ZoneInfo("Asia/Seoul")
        )
    except Exception as e:
        return jsonify({"success": False, "error": f"잘못된 크론식 표현입니다: {str(e)}"}), 400
        
    schedules = load_schedules()
    updated = False
    for sch in schedules:
        if sch["id"] == sch_id:
            sch["cron"] = cron_expr
            sch["description"] = description
            sch["job_type"] = job_type
            sch["date_offset"] = date_offset
            updated = True
            break
            
    if not updated:
        return jsonify({"success": False, "error": "해당 스케줄을 찾을 수 없습니다."}), 404
        
    if save_schedules(schedules):
        update_active_schedules()
        return jsonify({"success": True, "schedule": data})
    return jsonify({"success": False, "error": "스케줄을 수정하지 못했습니다."}), 500

@app.route("/api/schedule/delete", methods=["POST"])
def api_schedule_delete():
    """
    특정 스케줄 삭제 및 스케줄러 동적 반영
    """
    data = request.get_json()
    if not data or "id" not in data:
        return jsonify({"success": False, "error": "스케줄 ID(id)가 누락되었습니다."}), 400
        
    sch_id = data["id"]
    schedules = load_schedules()
    
    new_schedules = [sch for sch in schedules if sch["id"] != sch_id]
    
    if len(new_schedules) == len(schedules):
        return jsonify({"success": False, "error": "해당 스케줄을 찾을 수 없습니다."}), 404
        
    if save_schedules(new_schedules):
        update_active_schedules()
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "스케줄을 삭제하지 못했습니다."}), 500

@app.route("/api/schedule/run_now", methods=["POST"])
def api_schedule_run_now():
    """
    특정 스케줄 즉시 실행 (일회성 실행)
    """
    data = request.get_json()
    if not data or "id" not in data:
        return jsonify({"success": False, "error": "스케줄 ID(id)가 누락되었습니다."}), 400
        
    sch_id = data["id"]
    schedules = load_schedules()
    target_sch = None
    for sch in schedules:
        if sch["id"] == sch_id:
            target_sch = sch
            break
            
    if not target_sch:
        return jsonify({"success": False, "error": "해당 스케줄을 찾을 수 없습니다."}), 404
        
    job_type = target_sch.get("job_type", "stock")
    
    # Thread를 사용하여 비동기로 즉시 실행
    import threading
    if job_type == "stock":
        t = threading.Thread(target=run_stock_job)
    else:
        date_offset = int(target_sch.get("date_offset", -1))
        t = threading.Thread(target=run_youtube_job, kwargs={"date_offset": date_offset})
        
    t.daemon = True
    t.start()
    
    return jsonify({"success": True, "message": f"'{target_sch.get('description')}' 작업이 즉시 백그라운드에서 실행되었습니다."})


@app.route("/api/send", methods=["POST"])
def api_send():
    """
    메시지 전송 API (만료 시 자동 토큰 리프레시 수행 및 전송 이력 기록)
    """
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"success": False, "error": "메시지 본문이 누락되었습니다."}), 400
        
    message_text = data["message"]
    access_token = get_access_token()
    if not access_token:
        return jsonify({"success": False, "error": "로그인 연동이 해제되어 있습니다.", "reauth_required": True}), 401
        
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
    
    # 만료된 토큰일 경우 (HTTP 401) 자동 리프레시 시도
    if response.status_code == 401:
        try:
            new_access_token = refresh_kakao_token()
            headers["Authorization"] = f"Bearer {new_access_token}"
            response = requests.post(url, headers=headers, data=payload)
        except Exception as e:
            # 갱신도 완전히 실패한 경우
            err_msg = f"인증 만료로 인한 토큰 갱신 실패: {str(e)}"
            add_history_entry(message_text, "Failed", err_msg)
            return jsonify({
                "success": False, 
                "error": err_msg, 
                "reauth_required": True
            }), 401
            
    if response.status_code == 200:
        result = response.json()
        if result.get("result_code") == 0:
            add_history_entry(message_text, "Success")
            return jsonify({"success": True})
        else:
            err_msg = f"카카오 API 오류 (코드: {result.get('result_code')})"
            add_history_entry(message_text, "Failed", err_msg)
            return jsonify({"success": False, "error": err_msg}), 400
    else:
        err_msg = f"API HTTP 에러 (상태 코드: {response.status_code})"
        add_history_entry(message_text, "Failed", err_msg)
        return jsonify({"success": False, "error": err_msg}), response.status_code

def check_api_auth():
    """
    APP_API_KEY 보안 키가 설정되어 있는 경우, 헤더 인증을 체크합니다.
    """
    if not APP_API_KEY:
        # 보안 키가 비어있는 경우 무인증 통과
        return True
        
    auth_header = request.headers.get("Authorization")
    x_api_key = request.headers.get("X-API-Key")
    
    # Bearer 토큰 파싱
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        
    # 비교 검증
    if token == APP_API_KEY or x_api_key == APP_API_KEY:
        return True
        
    return False

@app.route("/api/v1/send", methods=["POST"])
def api_v1_send():
    """
    외부 REST API를 통한 카카오톡 전송 엔드포인트
    """
    if not check_api_auth():
        return jsonify({"success": False, "error": "인증에 실패했습니다. (Unauthorized)"}), 401
        
    # JSON 및 Form Data 둘 다 호환되도록 파싱
    message_text = None
    if request.is_json:
        data = request.get_json()
        message_text = data.get("message")
    else:
        message_text = request.form.get("message")
        
    if not message_text:
        return jsonify({"success": False, "error": "메시지 본문(message)이 누락되었습니다."}), 400
        
    # 전송 처리
    access_token = get_access_token()
    if not access_token:
        return jsonify({
            "success": False, 
            "error": "카카오 연동이 해제되어 있어 발송할 수 없습니다. 대시보드에 접속해 연동을 먼저 해주세요."
        }), 400
        
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
    
    # 만료된 토큰일 경우 (HTTP 401) 자동 리프레시 시도
    if response.status_code == 401:
        try:
            new_access_token = refresh_kakao_token()
            headers["Authorization"] = f"Bearer {new_access_token}"
            response = requests.post(url, headers=headers, data=payload)
        except Exception as e:
            # 갱신도 완전히 실패한 경우
            err_msg = f"인증 만료로 인한 토큰 갱신 실패: {str(e)}"
            add_history_entry(message_text, "Failed (API)", err_msg)
            return jsonify({"success": False, "error": err_msg}), 401
            
    if response.status_code == 200:
        result = response.json()
        if result.get("result_code") == 0:
            add_history_entry(message_text, "Success (API)")
            return jsonify({"success": True})
        else:
            err_msg = f"카카오 API 오류 (코드: {result.get('result_code')})"
            add_history_entry(message_text, "Failed (API)", err_msg)
            return jsonify({"success": False, "error": err_msg}), 400
    else:
        err_msg = f"API HTTP 에러 (상태 코드: {response.status_code})"
        add_history_entry(message_text, "Failed (API)", err_msg)
        return jsonify({"success": False, "error": err_msg}), response.status_code

if __name__ == "__main__":
    # 백그라운드 스케줄러 시작 및 작업 연동
    scheduler.start()
    update_active_schedules()
    
    print("==================================================")
    print("카카오톡 전송 웹 대시보드가 정상적으로 시작되었습니다.")
    print("브라우저에서 다음 주소로 접속해 주세요: http://localhost:5001")
    print("==================================================")
    app.run(host="0.0.0.0", port=5001, debug=True, use_reloader=False)
