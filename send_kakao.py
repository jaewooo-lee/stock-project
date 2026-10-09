import os
import json
import argparse
import requests
from dotenv import load_dotenv

# kakao_auth의 토큰 갱신 함수 가져오기
from kakao_auth import refresh_kakao_token, TOKEN_FILE

load_dotenv()

def load_access_token():
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

def send_talk_message(message_text):
    """
    카카오톡 '나에게 보내기' API를 통해 메시지를 전송합니다.
    401 에러 발생 시 토큰을 자동으로 재발급받아 재시도합니다.
    """
    access_token = load_access_token()
    if not access_token:
        print("[-] 오류: 저장된 토큰이 없습니다. 먼저 인증 서버를 실행해 로그인 해주세요.")
        print("    실행 명령: python kakao_auth.py")
        return False

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    # 기본 텍스트 템플릿 구성
    template_object = {
        "object_type": "text",
        "text": message_text,
        "link": {
            "web_url": "https://developers.kakao.com",
            "mobile_web_url": "https://developers.kakao.com"
        },
        "button_title": "카카오 디벨로퍼스"
    }

    data = {
        "template_object": json.dumps(template_object, ensure_ascii=False)
    }

    response = requests.post(url, headers=headers, data=data)
    
    # 401 Unauthorized 오류 시 토큰 자동 갱신 시도
    if response.status_code == 401:
        print("[*] 액세스 토큰이 만료되었습니다. 토큰 갱신을 시도합니다...")
        try:
            new_access_token = refresh_kakao_token()
            print("[+] 토큰 갱신 성공. 메시지 전송을 재시도합니다.")
            headers["Authorization"] = f"Bearer {new_access_token}"
            response = requests.post(url, headers=headers, data=data)
        except Exception as e:
            print(f"[-] 토큰 갱신 실패: {str(e)}")
            print("[-] 로그인이 만료되었을 수 있습니다. 다시 인증을 완료해 주세요.")
            print("    실행 명령: python kakao_auth.py")
            return False

    if response.status_code == 200:
        result = response.json()
        if result.get("result_code") == 0:
            print("[+] 카카오톡 메시지가 성공적으로 전송되었습니다.")
            return True
        else:
            print(f"[-] 전송 실패 (결과 코드: {result.get('result_code')})")
            return False
    else:
        print(f"[-] API 호출 실패 (HTTP Status: {response.status_code})")
        print(response.text)
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="카카오톡 '나에게 보내기' 메시지 전송 프로그램")
    parser.add_argument(
        "--message", 
        "-m", 
        type=str, 
        required=True, 
        help="전송할 카카오톡 메시지 본문"
    )
    
    args = parser.parse_args()
    send_talk_message(args.message)
