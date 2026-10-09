import os
import json
import requests
from flask import Flask, request, redirect, render_template_string
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

app = Flask(__name__)

# 환경 변수 로드
REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET")
REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI_LOCAL", "http://localhost:5001/oauth")
TOKEN_FILE = "kakao_token.json"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>카카오 로그인 인증</title>
    <style>
        body {
            font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
            background-color: #f9f9fb;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .container {
            background-color: #fff;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            text-align: center;
            max-width: 400px;
            width: 100%;
        }
        h1 {
            color: #333;
            font-size: 24px;
            margin-bottom: 20px;
        }
        p {
            color: #666;
            font-size: 14px;
            line-height: 1.6;
            margin-bottom: 30px;
        }
        .btn {
            display: inline-block;
            background-color: #FEE500;
            color: #191919;
            text-decoration: none;
            padding: 14px 24px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 16px;
            transition: background-color 0.2s;
            border: none;
            cursor: pointer;
            width: 100%;
            box-sizing: border-box;
        }
        .btn:hover {
            background-color: #FADA0A;
        }
        .status-success {
            color: #2e7d32;
            font-weight: bold;
        }
        .status-error {
            color: #c62828;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        {% if step == 'init' %}
            <h1>카카오톡 메시지 인증</h1>
            <p>카카오톡 메시지를 보내기 위해 최초 1회 로그인이 필요합니다.<br>아래 버튼을 눌러 로그인을 완료해주세요.</p>
            <a href="{{ auth_url }}" class="btn">카카오 로그인</a>
        {% elif step == 'success' %}
            <h1 class="status-success">인증 완료!</h1>
            <p>카카오 토큰이 <code>{{ token_file }}</code> 파일에 성공적으로 저장되었습니다.<br>이제 이 창을 닫으셔도 됩니다.<br><br>터미널로 돌아가 스크립트를 계속 진행해주세요.</p>
        {% else %}
            <h1 class="status-error">오류 발생</h1>
            <p>{{ error_msg }}</p>
            <a href="/" class="btn">처음으로</a>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    if not REST_API_KEY or REST_API_KEY == "your_kakao_rest_api_key_here":
        return render_template_string(
            HTML_TEMPLATE,
            step="error",
            error_msg=".env 파일에 KAKAO_REST_API_KEY를 올바르게 입력해주세요."
        )
    
    # 카카오 로그인 URL 생성 (talk_message 권한 포함 필수 요청)
    auth_url = (
        f"https://kauth.kakao.com/oauth/authorize"
        f"?client_id={REST_API_KEY}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=talk_message"
    )
    return render_template_string(HTML_TEMPLATE, step="init", auth_url=auth_url)

@app.route("/oauth")
def oauth():
    code = request.args.get("code")
    if not code:
        return render_template_string(
            HTML_TEMPLATE,
            step="error",
            error_msg="인가 코드를 받지 못했습니다. 인증을 다시 진행해 주세요."
        )

    # 토큰 요청
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
            return render_template_string(
                HTML_TEMPLATE,
                step="error",
                error_msg=f"토큰 발급 실패: {error_desc}"
            )
            
        # 토큰을 JSON 파일에 저장
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(token_info, f, ensure_ascii=False, indent=4)
            
        return render_template_string(
            HTML_TEMPLATE,
            step="success",
            token_file=TOKEN_FILE
        )
    except Exception as e:
        return render_template_string(
            HTML_TEMPLATE,
            step="error",
            error_msg=f"서버 에러가 발생했습니다: {str(e)}"
        )

def refresh_kakao_token(token_file_path=TOKEN_FILE):
    """
    Refresh Token을 사용하여 Access Token을 갱신하고 파일에 업데이트합니다.
    """
    if not os.path.exists(token_file_path):
        raise FileNotFoundError(f"토큰 파일이 존재하지 않습니다. 먼저 로그인을 완료해 주세요: {token_file_path}")
        
    with open(token_file_path, "r", encoding="utf-8") as f:
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
        
    # 기존 정보에 새로운 정보 덮어쓰기 (refresh_token은 갱신 시 안올 수도 있으므로 기존 것 유지)
    token_info["access_token"] = refreshed_info["access_token"]
    if "refresh_token" in refreshed_info:
        token_info["refresh_token"] = refreshed_info["refresh_token"]
    
    with open(token_file_path, "w", encoding="utf-8") as f:
        json.dump(token_info, f, ensure_ascii=False, indent=4)
        
    return token_info["access_token"]

if __name__ == "__main__":
    print(f"인증 서버를 시작합니다. 브라우저에서 {REDIRECT_URI.replace('/oauth', '')} 에 접속해 주세요.")
    app.run(host="0.0.0.0", port=5001)
