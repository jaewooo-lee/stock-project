# Stock Tracker System (v3)

모바일 웹 인터페이스를 통해 국내/해외 관심 종목을 검색 및 관리하고, 사용자 맞춤 다중 알림 스케줄에 맞춰 최신 주식 정보와 주요 금융 뉴스(AI 요약)를 담은 모바일 리포트 및 카카오톡 알림을 제공하는 시스템입니다.

---

## 🛠 주요 기능
1. **관심 종목 관리**: 모바일 웹에서 KOSPI/KOSDAQ 및 NYSE/NASDAQ 주식을 검색하여 등록 및 삭제 가능.
2. **다중 알림 스케줄링**: 하루 여러 시간대의 알림(HH:MM)을 등록하면 스케줄러가 재시작 없이 실시간으로 작동.
3. **주식 정보 수집 & AI 뉴스 요약**: 스케줄에 맞춰 네이버 금융/yfinance를 통해 주식 및 지수 정보를 가져오고, 네이버 주요 경제 뉴스 5개를 스크랩한 뒤 **Google Gemini API**를 활용해 요약하여 보고서를 자동 생성.
4. **아코디언 UI 모바일 리포트**: `<details>` 태그를 사용한 Native 모바일 웹 리포트 및 과거 리포트 아카이브 지원.
5. **카카오톡 알림 전송**: 보고서 요약 및 링크를 카카오톡 '나에게 보내기' API로 전송하며, 리프레시 토큰을 이용한 자동 토큰 갱신 기능 제공.
6. **Docker Compose 배포**: Nginx와 FastAPI가 격리된 멀티 컨테이너로 연동되어 원클릭 배포 가능.

---

## 🏗 시스템 아키텍처

- **Frontend**: HTML5, Vanilla JS, Tailwind CSS 기반의 Single Page Application.
- **Backend API**: Python 3.11 / FastAPI 및 APScheduler 기반 동적 스케줄링.
- **Database**: SQLite (관심종목, 알림 스케줄, 리포트 생성 기록 보관).
- **Web Server**: Nginx (프론트엔드 static 서빙, 보고서 html 정적 서빙 및 API 프록시 처리).

---

## 🚀 실행 및 배포 방법

### 1. 사전 요구사항
- **Docker** 및 **Docker Compose** 설치
- **Google Gemini API Key** 발급 ([Google AI Studio](https://aistudio.google.com/))
- **카카오 디벨로퍼스 앱** 생성 ([Kakao Developers](https://developers.kakao.com/))
  - 내 애플리케이션 생성 후 **REST API 키** 확보.
  - [제품 설정] -> [카카오 로그인] 활성화.
  - Redirect URI 등록: `http://localhost:8000/api/kakao/callback` (로컬 기본 설정)
  - [제품 설정] -> [카카오 로그인] -> [동의항목]에서 **'카카오톡 메시지 전송' (나에게 보내기)** 필수 동의 설정.

### 2. 환경변수 설정
프로젝트 루트 폴더에 `.env` 파일을 생성하고 설정값을 입력합니다.
```bash
cp .env.example .env
```
`.env` 파일 내용:
```env
GEMINI_API_KEY=발급받은_Gemini_API_Key
KAKAO_REST_API_KEY=발급받은_카카오_REST_API_키
KAKAO_REDIRECT_URI=http://localhost:8000/api/kakao/callback
BASE_URL=http://localhost
```

### 3. 컨테이너 빌드 및 실행
```bash
docker-compose up --build -d
```
실행이 완료되면 브라우저에서 `http://localhost`로 접속하여 대시보드를 확인할 수 있습니다.

### 4. 카카오톡 연동 및 리프레시 토큰 발급
최초 1회 카카오톡 메시지 전송 권한을 얻기 위한 인증 토큰 등록 단계입니다.
1. `http://localhost` 대시보드에 접속합니다.
2. 우측 상단의 **[카카오 연동]** 버튼을 클릭하고 **[카카오 인증 시작]**을 클릭합니다.
3. 카카오 로그인 및 동의를 진행하면 브라우저 화면에 **Refresh Token** 문자열이 출력됩니다.
4. 해당 토큰을 복사하여 `.env` 파일의 `KAKAO_REFRESH_TOKEN` 항목에 입력합니다.
   ```env
   KAKAO_REFRESH_TOKEN=출력된_리프레시_토큰_값
   ```
5. 백엔드 컨테이너를 재시작하여 갱신된 환경변수를 적용합니다.
   ```bash
   docker-compose restart backend-api
   ```
   *(이후 2개월 동안은 백엔드에서 자동으로 만료 시간 전에 액세스 토큰을 갱신합니다.)*

---

## 📂 파일 구조
```
stock-project/
├── backend/
│   ├── app/
│   │   ├── main.py            # API 엔드포인트 및 앱 제어
│   │   ├── database.py        # SQLite 스키마 및 CRUD 헬퍼
│   │   ├── collector.py       # 데이터 수집, Gemini 뉴스 요약, HTML 리포트 생성
│   │   ├── scheduler.py       # APScheduler 동적 스케줄링
│   │   └── notifier.py        # 카카오 API 연동 및 토큰 자동 갱신
│   ├── requirements.txt       # 파이썬 의존 라이브러리
│   └── Dockerfile             # 백엔드 빌드 Dockerfile
├── frontend/
│   ├── index.html             # 모바일 대시보드 UI
│   └── assets/
│       └── app.js             # 종목/스케줄 CRUD 및 AJAX 리포트 서빙 스크립트
├── nginx/
│   └── default.conf           # Nginx 프록시 설정
├── docker-compose.yml         # 멀티 컨테이너 정의서
└── README.md                  # 본 가이드 문서
```
