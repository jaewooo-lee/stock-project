import requests
import json
import os
from app import config

TOKEN_CACHE_FILE = os.path.join(os.path.dirname(config.DATABASE_FILE) or ".", ".kakao_tokens.json")

def _load_cached_tokens():
    if os.path.exists(TOKEN_CACHE_FILE):
        try:
            with open(TOKEN_CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_cached_tokens(tokens):
    try:
        with open(TOKEN_CACHE_FILE, "w") as f:
            json.dump(tokens, f)
    except Exception as e:
        print(f"Error saving Kakao token cache: {e}")

def refresh_access_token():
    """
    Refresh Kakao access token using refresh token.
    Updates the token cache.
    """
    cached = _load_cached_tokens()
    # Prefer cached refresh token if exists, otherwise fallback to env config
    refresh_token = cached.get("refresh_token") or config.KAKAO_REFRESH_TOKEN

    if not refresh_token:
        print("Warning: Kakao refresh token is not configured.")
        return None

    url = "https://kauth.kakao.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": config.KAKAO_REST_API_KEY,
        "refresh_token": refresh_token
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    try:
        response = requests.post(url, data=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            access_token = data.get("access_token")
            # If a new refresh_token is returned, update it. Otherwise keep the old one.
            new_refresh_token = data.get("refresh_token", refresh_token)
            
            _save_cached_tokens({
                "access_token": access_token,
                "refresh_token": new_refresh_token
            })
            print("Kakao access token successfully refreshed.")
            return access_token
        else:
            print(f"Failed to refresh Kakao token. Status: {response.status_code}, Response: {response.text}")
            return None
    except Exception as e:
        print(f"Error calling Kakao token refresh: {e}")
        return None

def get_access_token():
    cached = _load_cached_tokens()
    access_token = cached.get("access_token")
    if not access_token:
        access_token = refresh_access_token()
    return access_token

def send_kakao_message(text_content: str, link_url: str):
    """
    Send KakaoTalk 'Send to Me' message.
    Automatically handles 401 Unauthorized by refreshing token once.
    """
    access_token = get_access_token()
    if not access_token:
        print("Error: Access token unavailable. Cannot send Kakao notification.")
        return False

    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    
    # Template Object for KakaoTalk default text message
    template_object = {
        "object_type": "text",
        "text": text_content,
        "link": {
            "web_url": link_url,
            "mobile_web_url": link_url
        },
        "button_title": "보고서 상세보기"
    }
    
    payload = {
        "template_object": json.dumps(template_object, ensure_ascii=False)
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    try:
        response = requests.post(url, data=payload, headers=headers)
        if response.status_code == 200:
            print("KakaoTalk notification sent successfully.")
            return True
        elif response.status_code == 401:
            print("KakaoTalk access token expired (401). Retrying with a refreshed token...")
            # Try to refresh token and call again
            new_token = refresh_access_token()
            if new_token:
                headers["Authorization"] = f"Bearer {new_token}"
                response = requests.post(url, data=payload, headers=headers)
                if response.status_code == 200:
                    print("KakaoTalk notification sent successfully after token refresh.")
                    return True
            print(f"Retry failed. Status: {response.status_code}, Response: {response.text}")
            return False
        else:
            print(f"Failed to send Kakao message. Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        print(f"Error calling Kakao send message API: {e}")
        return False
