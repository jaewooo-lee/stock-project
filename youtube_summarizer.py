import os
import re
import sys
import json
import argparse
from datetime import datetime
import requests
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi

# Load environment variables
load_dotenv()

PLAYLIST_URL = "https://www.youtube.com/playlist?list=PL-kIFxHMwyFAqrAm34SbOfDgThMbH6lCL"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def find_key(data, target_key):
    """
    Recursively search for a key in a nested dictionary/list structure.
    Useful for handling changes in YouTube's inner JSON structure.
    """
    if isinstance(data, dict):
        for k, v in data.items():
            if k == target_key:
                return v
            result = find_key(v, target_key)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = find_key(item, target_key)
            if result is not None:
                return result
    return None

def fetch_playlist_videos(url=PLAYLIST_URL):
    """
    Fetch the YouTube playlist page and parse video IDs and titles.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"[-] 유튜브 플레이리스트 페이지를 가져오지 못했습니다. 상태 코드: {response.status_code}")
            return []
            
        html = response.text
        match = re.search(r"var ytInitialData\s*=\s*({.*?});", html)
        if not match:
            # Fallback regex parsing directly on the HTML
            print("[*] ytInitialData를 찾지 못해 정규식 fallback으로 비디오 ID를 추출합니다.")
            v_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
            seen = set()
            video_list = []
            for vid in v_ids:
                if vid not in seen:
                    seen.add(vid)
                    video_list.append({"id": vid, "title": "알 수 없음 (제목 추출 실패)"})
            return video_list

        data = json.loads(match.group(1))
        
        # Traverse structural layers recursively or with known paths
        try:
            content = data['contents']['twoColumnBrowseResultsRenderer']['tabs'][0]['tabRenderer']['content']
            item_contents = content['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents']
        except KeyError:
            # Fallback if structure changes
            item_contents = find_key(data, "itemSectionRenderer")
            if isinstance(item_contents, dict):
                item_contents = item_contents.get("contents", [])
            else:
                item_contents = []

        video_list = []
        if not item_contents:
            # Revert to regex on JSON text as fallback
            v_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', match.group(1))
            seen = set()
            for vid in v_ids:
                if vid not in seen:
                    seen.add(vid)
                    video_list.append({"id": vid, "title": "알 수 없음 (제목 추출 실패)"})
            return video_list

        for item in item_contents:
            lockup = item.get("lockupViewModel")
            if not lockup:
                # If there are other renderers, check them
                lockup = find_key(item, "lockupViewModel")
                if not lockup:
                    continue
            
            v_id = find_key(lockup, "videoId")
            
            title = None
            try:
                title = lockup['metadata']['lockupMetadataViewModel']['title']['content']
            except KeyError:
                title = find_key(lockup, "content")
                if not title or not isinstance(title, str):
                    title = "알 수 없음"
            
            if v_id:
                video_list.append({
                    "id": v_id,
                    "title": title
                })
        
        return video_list

    except Exception as e:
        print(f"[-] 플레이리스트 파싱 오류: {str(e)}")
        return []

def get_transcript(video_id):
    """
    Retrieve the Korean transcript for the given video ID.
    """
    try:
        api = YouTubeTranscriptApi()
        srt = api.fetch(video_id, languages=['ko'])
        full_text = " ".join([item.text for item in srt])
        return full_text
    except Exception as e:
        print(f"[-] 자막을 가져오는 데 실패했습니다 (ID: {video_id}). 오류: {str(e)}")
        return None

def extract_date_from_title(title):
    """
    Extract YYYY-MM-DD or YYYY/MM/DD date string from the video title.
    """
    match = re.search(r'(\d{4})[/-](\d{2})[/-](\d{2})', title)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return None

def summarize_transcript(transcript_text, title):
    """
    Summarize the transcript using the Gemini API.
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        print("[!] GEMINI_API_KEY가 설정되지 않았거나 예시 값입니다. 데모용 요약본을 제공합니다.")
        return (
            "📈 **주요 지수 및 시장 전반 동향**\n"
            "- S&P 500 지수는 0.14% 하락 마감하였고, 나스닥과 다우 지수 역시 주요 빅테크 기업들의 실적 발표를 앞두고 혼조세를 나타냈습니다.\n"
            "- 필라델피아 반도체 지수는 0.44% 상승하며 3거래일 연속 랠리를 이어갔습니다.\n\n"
            "💻 **빅테크 및 반도체/AI 동향**\n"
            "- 장 마감 후 실적을 발표한 알파벳(구글)은 클라우드 매출 부문에서 높은 성장세를 보였으나, 자본 지출(CAPEX) 확대 소식에 시간외 거래에서 하락세를 기록 중입니다.\n"
            "- 테슬라는 차량 인도량 둔화와 실적 우려로 장외 거래에서 매도세가 출현하였습니다.\n\n"
            "📊 **주요 매크로 경제 지표 및 이슈**\n"
            "- 유가 변동성으로 인한 물가 압력이 지속되면서 연준의 기준금리 결정 경로에 대한 시장 우려가 일부 반영되었습니다.\n"
            "- 채권 금리는 좁은 범위에서 횡보하는 움직임을 보였습니다.\n\n"
            "🔍 **특징적인 개별 종목 실적 및 이슈**\n"
            "- 구글(알파벳)과 테슬라의 실적 발표가 향후 AI 및 자율주행 섹터의 향방을 가를 주요 지표로 해석되고 있습니다."
        )
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = (
        f"동영상 제목: {title}\n\n"
        "아래는 해당 동영상의 자막 스크립트 내용입니다. 이 스크립트는 미국 증시의 하루 요약 요점입니다. "
        "이를 바탕으로 당일 미국 시장 흐름을 핵심 내용 위주로 정리해 주세요.\n\n"
        "요구 조건:\n"
        "1. 한국어로 작성해 주세요.\n"
        "2. 전문적이고 깔끔한 신문 기사 요약 톤(~입니다, ~했습니다)을 사용해 주세요.\n"
        "3. 다음 네 가지 영역을 구분하여 보기 좋게(글머리 기호 사용) 정리해 주세요:\n"
        "   - 📈 주요 지수 및 시장 전반 동향 (S&P500, 나스닥, 다우 등 등락률 및 요인)\n"
        "   - 💻 빅테크 및 반도체/AI 동향 (주요 기술주 및 AI 반도체 움직임 핵심 요약)\n"
        "   - 📊 주요 매크로 경제 지표 및 이슈 (연준 금리 전망, 채권 금리, 유가, 물가 등)\n"
        "   - 🔍 특징적인 개별 종목 실적 및 이슈 (구글, 테슬라 등 당일 이슈 기업 핵심 요약)\n"
        "4. 너무 길지 않고 가독성 있게 요약해 주세요.\n\n"
        f"스크립트 본문:\n{transcript_text}"
    )
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=20)
        if response.status_code == 200:
            res_data = response.json()
            summary = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
            return summary
        else:
            print(f"[-] Gemini API 호출 실패. 상태 코드: {response.status_code}, 메시지: {response.text}")
    except Exception as e:
        print(f"[-] Gemini 요약 처리 실패: {str(e)}")
        
    return None

def try_send_kakao(message):
    """
    Send the summary message to KakaoTalk using send_daily_stocks module if available.
    """
    try:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from send_daily_stocks import send_talk_message
        
        # Kakao text template limit is around 1000 characters. Let's truncate if too long.
        if len(message) > 950:
            truncated_message = message[:920] + "\n\n... (이하 생략 - 전체 내용은 리포트 참조)"
        else:
            truncated_message = message
            
        print("[*] 카카오톡 발송을 시도합니다...")
        success = send_talk_message(truncated_message)
        if success:
            print("[+] 카카오톡 메시지가 성공적으로 발송되었습니다.")
        else:
            print("[-] 카카오톡 메시지 발송에 실패했습니다. (콘솔 로그 확인)")
    except ImportError:
        print("[-] send_daily_stocks 모듈을 찾을 수 없어 카카오톡 발송을 수행할 수 없습니다.")
    except Exception as e:
        print(f"[-] 카카오톡 발송 중 에러가 발생했습니다: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="오선의 미국 증시 오늘의 요약 유튜브 자막 요약 프로그램")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--latest", action="store_true", help="가장 최신 요약 영상을 요약합니다. (기본값)")
    group.add_argument("--list", action="store_true", help="최근 동영상 목록 10개를 표시하고 선택합니다.")
    group.add_argument("--date", type=str, help="특정 날짜(YYYY-MM-DD 또는 YYYY/MM/DD)에 해당하는 영상을 요약합니다.")
    
    parser.add_argument("--save", action="store_true", help="요약 결과를 reports 폴더에 마크다운 파일로 저장합니다.")
    parser.add_argument("--send-kakao", action="store_true", help="요약 결과를 카카오톡으로 발송합니다.")
    
    args = parser.parse_args()
    
def run_summarizer_job(save=False, send_kakao=False, video=None, target_date=None):
    """
    유튜브 증시 요약 작업을 수행합니다.
    """
    if not video:
        print("[*] 유튜브 '오선의 미국 증시 오늘의 요약' 플레이리스트 정보 로딩 중...")
        videos = fetch_playlist_videos()
        if not videos:
            print("[-] 플레이리스트에서 동영상 정보를 가져오지 못했습니다.")
            return False
            
        # Filter out videos that are not related to daily summary
        summary_videos = [v for v in videos if "오늘의 요약" in v["title"]]
        if not summary_videos:
            summary_videos = videos
            
        if target_date:
            input_date = target_date.replace('/', '-')
            print(f"[*] 입력한 날짜 {input_date}에 해당하는 영상을 검색 중...")
            matched_video = None
            for v in summary_videos:
                v_date = extract_date_from_title(v["title"])
                if v_date and v_date.replace('/', '-') == input_date:
                    matched_video = v
                    break
            
            if not matched_video:
                # Fallback search for substring in title
                for v in summary_videos:
                    if input_date in v["title"] or target_date in v["title"]:
                        matched_video = v
                        break
            
            if not matched_video:
                print(f"[-] {target_date} 날짜 혹은 제목에 매칭되는 요약 영상을 찾지 못했습니다.")
                return False
            video = matched_video
        else:
            video = summary_videos[0]

    v_id = video["id"]
    v_title = video["title"]
    v_date = extract_date_from_title(v_title) or datetime.now().strftime("%Y-%m-%d")

    print(f"\n[*] 비디오 ID: {v_id}")
    print(f"[*] 비디오 제목: {v_title}")
    print("[*] 유튜브 자막(스크립트) 수집 중...")
    
    transcript = get_transcript(v_id)
    if not transcript:
        return False
        
    print("[+] 자막 수집 완료. Gemini AI 요약 요청 중...")
    summary = summarize_transcript(transcript, v_title)
    
    if not summary:
        print("[-] 요약 생성에 실패했습니다.")
        return False

    print("\n================== GEMINI AI 요약 결과 ==================")
    print(summary)
    print("=======================================================")

    # Handle Save option
    if save:
        reports_dir = "reports"
        os.makedirs(reports_dir, exist_ok=True)
        file_path = os.path.join(reports_dir, f"youtube_summary_{v_date}.md")
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# {v_title}\n\n")
                f.write(f"- **동영상 링크**: https://www.youtube.com/watch?v={v_id}\n")
                f.write(f"- **날짜**: {v_date}\n")
                f.write(f"- **요약 생성 시각**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("## 📝 미국 증시 핵심 요약\n\n")
                f.write(summary)
            print(f"[+] 요약 결과가 마크다운 파일로 저장되었습니다: {file_path}")
        except Exception as e:
            print(f"[-] 파일 저장 오류: {str(e)}")

    # Handle KakaoTalk option
    if send_kakao:
        kakao_msg = (
            f"📢 [유튜브 미증시 요약 - {v_date}]\n"
            f"🎥 {v_title}\n\n"
            f"{summary}\n\n"
            f"🔗 동영상 보기: https://youtu.be/{v_id}"
        )
        try_send_kakao(kakao_msg)
        
    return True

def main():
    parser = argparse.ArgumentParser(description="오선의 미국 증시 오늘의 요약 유튜브 자막 요약 프로그램")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--latest", action="store_true", help="가장 최신 요약 영상을 요약합니다. (기본값)")
    group.add_argument("--list", action="store_true", help="최근 동영상 목록 10개를 표시하고 선택합니다.")
    group.add_argument("--date", type=str, help="특정 날짜(YYYY-MM-DD 또는 YYYY/MM/DD)에 해당하는 영상을 요약합니다.")
    
    parser.add_argument("--save", action="store_true", help="요약 결과를 reports 폴더에 마크다운 파일로 저장합니다.")
    parser.add_argument("--send-kakao", action="store_true", help="요약 결과를 카카오톡으로 발송합니다.")
    
    args = parser.parse_args()
    
    # Default behavior is --latest if no source is specified
    if not (args.list or args.date):
        args.latest = True

    if args.list or args.date:
        print("[*] 유튜브 '오선의 미국 증시 오늘의 요약' 플레이리스트 정보 로딩 중...")
        videos = fetch_playlist_videos()
        
        if not videos:
            print("[-] 플레이리스트에서 동영상 정보를 가져오지 못했습니다.")
            return

        summary_videos = [v for v in videos if "오늘의 요약" in v["title"]]
        if not summary_videos:
            summary_videos = videos

        selected_video = None

        if args.list:
            print("\n=== 최근 오늘의 요약 동영상 목록 ===")
            display_limit = min(10, len(summary_videos))
            for i in range(display_limit):
                v = summary_videos[i]
                v_date = extract_date_from_title(v["title"]) or "날짜 파악 불가"
                print(f"[{i+1}] {v['title']} (날짜: {v_date})")
                
            print("====================================")
            try:
                choice = input(f"요약할 영상 번호를 선택해 주세요 (1-{display_limit}): ").strip()
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < display_limit:
                    selected_video = summary_videos[choice_idx]
                else:
                    print("[-] 잘못된 번호입니다. 프로그램을 종료합니다.")
                    return
            except ValueError:
                print("[-] 올바른 숫자를 입력해야 합니다. 프로그램을 종료합니다.")
                return
            except KeyboardInterrupt:
                print("\n[*] 사용자에 의해 취소되었습니다.")
                return

        elif args.date:
            # Standardize date format to YYYY-MM-DD
            input_date = args.date.replace('/', '-')
            print(f"[*] 입력한 날짜 {input_date}에 해당하는 영상을 검색 중...")
            for v in summary_videos:
                v_date = extract_date_from_title(v["title"])
                if v_date and v_date.replace('/', '-') == input_date:
                    selected_video = v
                    break
            
            if not selected_video:
                # Fallback search for substring in title
                for v in summary_videos:
                    if input_date in v["title"] or args.date in v["title"]:
                        selected_video = v
                        break
                        
            if not selected_video:
                print(f"[-] {args.date} 날짜 혹은 제목에 매칭되는 요약 영상을 찾지 못했습니다.")
                return
                
        run_summarizer_job(save=args.save, send_kakao=args.send_kakao, video=selected_video)
    else:  # args.latest
        run_summarizer_job(save=args.save, send_kakao=args.send_kakao)

if __name__ == "__main__":
    main()
