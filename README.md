# 📈 Stock Tracker & AI YouTube Market Summarizer

국내외 주요 주식 시황 및 경제 뉴스를 자동 수집하고, **YouTube 증시 브리핑 영상(삼프로TV 등)의 자막을 Google Gemini AI로 요약**하여 **카카오톡 '나에게 보내기'**로 자동 발송하는 스마트 주식 트래커 시스템입니다.

웹 대시보드를 통해 알림 이력 확인, 즉시 발송 테스트, 정기 발송 스케줄(APScheduler) 관리 및 카카오 OAuth 연동을 간편하게 제어할 수 있습니다.

---

## 📑 목차
1. [주요 기능](#-주요-기능)
2. [시스템 아키텍처 및 기술 스택](#-시스템-아키텍처-및-기술-스택)
3. [프로젝트 구조](#-프로젝트-구조)
4. [사전 준비 및 환경 설정](#-사전-준비-및-환경-설정)
5. [서버 구동 방법](#-서버-구동-방법)
   - [방법 1: 로컬 파이썬 가상환경에서 실행](#방법-1-로컬-파이썬-가상환경에서-실행)
   - [방법 2: Docker 컨테이너로 실행 (추천)](#방법-2-docker-컨테이너로-실행-추천)
   - [방법 3: Docker Compose로 실행](#방법-3-docker-compose로-실행)
6. [카카오톡 연동 가이드](#-카카오톡-연동-가이드)
7. [Dockerfile 빌드 및 푸시 가이드](#-dockerfile-빌드-및-푸시-가이드)
   - [기본 Docker 이미지 빌드 및 로컬 테스트](#1-기본-docker-이미지-빌드-및-로컬-테스트)
   - [Docker Hub 로그인 및 푸시](#2-docker-hub-로그인-및-푸시)
   - [멀티 아키텍처(Multi-Arch) 빌드 및 푸시](#3-멀티-아키텍처multi-arch-빌드-및-푸시)
8. [GitHub Actions를 통한 Docker Build & Push 자동화](#-github-actions를-통한-docker-build--push-자동화)
   - [GitHub Secrets 설정](#1-github-secrets-설정)
   - [자동 배포 워크플로우 동작 방식](#2-자동-배포-워크플로우-동작-방식)

---

## ✨ 주요 기능

* 📊 **국내/글로벌 주식 및 시장 지표 자동 브리핑**
  - 주요 지수(KOSPI, KOSDAQ, S&P 500, NASDAQ, 환율 등) 및 관심 종목의 최신 주가/등락률 자동 집계
  - 네이버 금융 및 주요 언론사 핵심 뉴스 스크랩
* 🤖 **AI 기반 YouTube 증시 시황 요약**
  - 삼프로TV 등 증시 전문 유튜브 채널의 최신 영상 자동 감지 및 자막(Transcript) 추출
  - **Google Gemini API**를 활용한 핵심 시장 포인트 및 투자 인사이트 요약
* 💬 **카카오톡 나에게 보내기 자동 발송**
  - 리포트 요약본을 카카오톡 메시지로 매일 정해진 시각에 자동 전송
  - OAuth 토큰 자동 갱신(Refresh Token) 지원으로 영구적인 무중단 발송 보장
* ⏰ **다중 스케줄러 & 웹 대시보드 (Port: 5001)**
  - 모바일 친화적인 반응형 웹 UI 제공
  - 원하는 발송 시간대(예: 아침 08:30 장전 브리핑, 15:40 장마감 브리핑 등) 자유로운 추가/수정/삭제/활성화 토글
  - 카카오 로그인 원클릭 인증 및 발송 이력 실시간 모니터링
* 🐳 **컨테이너 기반 배포 최적화**
  - 경량화된 Dockerfile 제공 (Python 3.11-slim)
  - Synology NAS, 라즈베리파이, 클라우드 VPS(x86/ARM64) 어디서나 손쉽게 구동 가능
  - GitHub Actions를 통한 CI/CD 이미지 자동 빌드 및 Docker Hub 푸시 파이프라인 탑재

---

## 🛠 시스템 아키텍처 및 기술 스택

| 영역 | 기술 스택 | 설명 |
| :--- | :--- | :--- |
| **Backend & Web Server** | Python 3.11, Flask | 웹 대시보드, API 엔드포인트, 발송 오케스트레이션 |
| **Scheduler** | APScheduler (BackgroundScheduler) | 크론 기반 실시간 동적 스케줄링 관리 |
| **Financial Data** | yfinance, requests, BeautifulSoup4 | 국내외 주식 시세, 시장 지표 및 금융 뉴스 크롤링 |
| **AI Summarizer** | Google Gemini API (google-generativeai) | YouTube 자막 및 뉴스 텍스트 자동 요약 |
| **Video Processing** | youtube-transcript-api | YouTube 재생목록 영상 자막 추출 |
| **Notification** | Kakao Open API (OAuth 2.0) | 카카오톡 나에게 보내기 메시지 API 연동 |
| **Container & CI/CD** | Docker, Docker Compose, GitHub Actions | 컨테이너 가상화, 멀티 아키텍처 빌드 및 자동 배포 |

---

## 📂 프로젝트 구조

```text
stock-project/
├── .github/
│   └── workflows/
│       └── docker-build-push.yml # GitHub Actions Docker 빌드 & 푸시 워크플로우
├── data/                         # 토큰 및 스케줄/이력 데이터 저장소 (Git 제외)
│   ├── kakao_token.json          # 카카오 OAuth 인증 토큰
│   ├── kakao_schedule.json       # 등록된 알림 스케줄
│   └── kakao_history.json        # 전송 결과 히스토리
├── templates/
│   └── index.html                # 모바일/데스크톱 반응형 대시보드 템플릿
├── app.py                        # Flask 메인 애플리케이션 & 스케줄러 서버 (포트 5001)
├── send_daily_stocks.py          # 일일 주식 지표 및 뉴스 수집/발송 엔진
├── youtube_summarizer.py         # YouTube 자막 추출 및 Gemini AI 요약 엔진
├── kakao_auth.py                 # 카카오 OAuth 인증 헬퍼 모듈
├── Dockerfile                    # 서비스 경량 Docker 빌드 설정
├── .dockerignore                 # Docker 빌드 제외 목록
├── docker-compose.yml            # Docker Compose 설정
├── requirements.txt              # 파이썬 의존성 패키지 목록
├── .env.example                  # 환경 변수 설정 템플릿
└── README.md                     # 본 문서
```

---

## ⚙️ 사전 준비 및 환경 설정

### 1. API 키 발급
1. **Google Gemini API Key**: [Google AI Studio](https://aistudio.google.com/)에서 API 키를 발급받습니다.
2. **카카오 REST API 키**:
   - [Kakao Developers](https://developers.kakao.com/) 접속 후 애플리케이션 생성.
   - [앱 키] 메뉴에서 **REST API 키** 복사.
   - [제품 설정] -> [카카오 로그인] 활성화.
   - [Redirect URI] 등록:
     - 로컬/Docker 기본 웹 대시보드 사용 시: `http://localhost:5001/oauth`
     - 외부 도메인/IP 사용 시: `http://<서버IP또는도메인>:5001/oauth`
   - [제품 설정] -> [카카오 로그인] -> [동의항목]에서 **'카카오톡 메시지 전송' (나에게 보내기)** 필수 동의 설정.

### 2. 환경변수 파일 (`.env`) 생성
프로젝트 루트 경로에서 `.env.example`을 복사하여 `.env` 파일을 생성합니다.

```bash
cp .env.example .env
```

`.env` 파일에 발급받은 정보를 입력합니다:
```env
# Google Gemini API
GEMINI_API_KEY=AIzaSy...당신의_Gemini_API_Key

# 카카오 REST API
KAKAO_REST_API_KEY=당신의_카카오_REST_API_키
KAKAO_CLIENT_SECRET=보안설정시_클라이언트_시크릿(선택)
KAKAO_REDIRECT_URI_LOCAL=http://localhost:5001/oauth

# 애플리케이션 보안키 (선택)
APP_API_KEY=
```

---

## 🚀 서버 구동 방법

### 방법 1: 로컬 파이썬 가상환경에서 실행

```bash
# 1. 가상환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. 필수 라이브러리 설치
pip install --upgrade pip
pip install -r requirements.txt

# 3. 대시보드 & 스케줄러 서버 구동
python app.py
```
* 서버가 실행되면 브라우저에서 `http://localhost:5001`에 접속합니다.

---

### 방법 2: Docker 컨테이너로 실행 (추천)

데이터 유실 방지를 위해 호스트의 `./data` 디렉토리를 컨테이너 내부 `/app/data`로 바인드 마운트합니다.

```bash
# 1. 이미지 빌드
docker build -t stock-tracker:latest .

# 2. 컨테이너 실행
docker run -d \
  --name stock-tracker \
  --restart unless-stopped \
  -p 5001:5001 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  stock-tracker:latest

# 3. 로그 확인
docker logs -f stock-tracker
```
* 브라우저에서 `http://localhost:5001`에 접속하여 관리 화면을 확인합니다.

---

### 방법 3: Docker Compose로 실행

```bash
docker-compose up -d
```
* 컨테이너 중지: `docker-compose down`
* 로그 모니터링: `docker-compose logs -f`

---

## 🔑 카카오톡 연동 가이드

1. 서버 구동 후 브라우저로 대시보드(`http://localhost:5001`)에 접속합니다.
2. 상단 카카오 계정 상태 카드에서 **[카카오 로그인 및 인증]** 버튼을 클릭합니다.
3. 카카오 계정으로 로그인 후 메시지 전송 권한 동의를 완료합니다.
4. 연동이 완료되면 `data/kakao_token.json` 파일에 Access Token 및 Refresh Token이 안전하게 저장됩니다.
5. 대시보드의 **[주식 브리핑 즉시 전송]** 또는 **[유튜브 요약 즉시 전송]** 버튼을 눌러 카카오톡으로 메시지가 정상 수신되는지 테스트합니다.
6. *(토큰 자동 갱신 엔진이 내장되어 있어 매 전송 시 자동으로 만료 여부를 체크하고 리프레시합니다.)*

---

## 🐳 Dockerfile 빌드 및 푸시 가이드

### 1. 기본 Docker 이미지 빌드 및 로컬 테스트

`<dockerhub-username>` 부분을 본인의 Docker Hub 사용자명(ID)으로 변경하여 실행합니다.

```bash
# 이미지 빌드
docker build -t <dockerhub-username>/stock-tracker:latest .

# 로컬에서 이미지 실행 테스트
docker run -d \
  --name stock-test \
  -p 5001:5001 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  <dockerhub-username>/stock-tracker:latest

# 실행 확인
docker ps
docker logs stock-test

# 테스트 완료 후 삭제
docker stop stock-test && docker rm stock-test
```

### 2. Docker Hub 로그인 및 푸시

```bash
# 1. Docker Hub 로그인 (터미널에서 ID/PW 또는 Access Token 입력)
docker login

# 2. 이미지 태그 지정 (필요 시 버전 태그 추가)
docker tag <dockerhub-username>/stock-tracker:latest <dockerhub-username>/stock-tracker:v1.0.0

# 3. Docker Hub로 푸시
docker push <dockerhub-username>/stock-tracker:latest
docker push <dockerhub-username>/stock-tracker:v1.0.0
```

### 3. 멀티 아키텍처(Multi-Arch) 빌드 및 푸시
Synology NAS, 라즈베리파이(ARM64), 클라우드 VPS(AMD64) 등 다양한 기기에서 호환되도록 Docker Buildx를 이용해 멀티 플랫폼 이미지를 빌드하고 동시에 푸시할 수 있습니다.

```bash
# 1. Buildx 빌더 생성 및 활성화
docker buildx create --name multi-builder --use
docker buildx inspect --bootstrap

# 2. 멀티 아키텍처(AMD64 + ARM64) 빌드 & 푸시 실행
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t <dockerhub-username>/stock-tracker:latest \
  -t <dockerhub-username>/stock-tracker:v1.0.0 \
  --push .
```

---

## 🚀 GitHub Actions를 통한 Docker Build & Push 자동화

본 저장소에는 코드를 `main` 브랜치에 push하거나 릴리스 태그(`v*`)를 생성할 때 자동으로 Docker 이미지를 빌드하여 Docker Hub에 푸시하는 GitHub Actions 워크플로우가 구성되어 있습니다. (`.github/workflows/docker-build-push.yml`)

### 1. GitHub Secrets 설정

GitHub 리포지토리의 저장소 비밀(Secrets)을 설정해야 워크플로우가 Docker Hub에 로그인할 수 있습니다.

1. 본인의 GitHub 리포지토리로 이동합니다.
2. **Settings** -> 좌측 메뉴의 **Secrets and variables** -> **Actions** 선택.
3. **New repository secret** 버튼을 클릭하여 아래 2가지 값을 등록합니다:
   - `DOCKERHUB_USERNAME`: 본인의 Docker Hub 계정 아이디
   - `DOCKERHUB_TOKEN`: Docker Hub Personal Access Token (또는 계정 비밀번호)
     > 💡 **Docker Hub Token 발급 방법**:
     > Docker Hub 로그인 -> 우측 상단 프로필 -> **Account Settings** -> **Security** -> **New Access Token** 클릭 후 발급.

### 2. 자동 배포 워크플로우 동작 방식

* **워크플로우 파일 경로**: `.github/workflows/docker-build-push.yml`
* **트리거 시점**:
  - `main` 브랜치로 `git push`가 발생했을 때
  - 버전 태그(예: `git tag v1.0.0 && git push origin v1.0.0`)를 푸시했을 때
  - GitHub Actions 탭에서 **Run workflow** 버튼으로 수동 실행(`workflow_dispatch`)했을 때
  - Pull Request 시에는 로그인 및 푸시 없이 **빌드 무결성 테스트**만 수행
* **주요 프로세스**:
  1. 저장소 소스코드 체크아웃
  2. QEMU 및 Docker Buildx 환경 구축 (`linux/amd64`, `linux/arm64` 멀티 아키텍처 지원)
  3. GitHub Secrets를 통해 Docker Hub 안전 로그인
  4. Docker 메타데이터 자동 추출 (`latest`, 브랜치명, 버전 태그, 커밋 SHA 등)
  5. GitHub Actions 캐시(GHA)를 활용한 초고속 빌드 및 Docker Hub 자동 Push

<details>
<summary><b>📄 워크플로우 전체 코드 (.github/workflows/docker-build-push.yml) 펼쳐보기</b></summary>

```yaml
name: Build and Push Docker Image

on:
  push:
    branches:
      - main
    tags:
      - 'v*.*.*'
      - 'v*'
  pull_request:
    branches:
      - main
  workflow_dispatch:

jobs:
  build-and-push:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up QEMU (Multi-platform support)
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Docker Hub
        if: github.event_name != 'pull_request'
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Extract Docker metadata (tags, labels)
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ secrets.DOCKERHUB_USERNAME }}/stock-tracker
          tags: |
            type=raw,value=latest,enable={{is_default_branch}}
            type=ref,event=branch
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha,format=short

      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile
          platforms: linux/amd64,linux/arm64
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```
</details>

> 💡 **참고: GitHub Personal Access Token (PAT) 권한 안내**
> 로컬 터미널에서 `.github/workflows/` 폴더를 푸시할 때 `refusing to allow a Personal Access Token to create or update workflow without 'workflow' scope` 에러가 발생하는 경우:
> 1. GitHub -> **Settings** -> **Developer Settings** -> **Personal Access Tokens** -> 사용 중인 토큰 선택
> 2. `workflow` 항목(Update GitHub Action workflows)에 체크 후 저장
> 3. 또는 GitHub 웹 저장소 화면에서 **Actions** 탭 또는 **Add file** -> **Create new file**로 `.github/workflows/docker-build-push.yml`을 직접 생성할 수도 있습니다.


---

## 📝 라이선스 및 주의사항

* 본 프로젝트에서 제공하는 주가 정보 및 AI 요약 내용은 투자 참고용이며, 투자 결과에 대한 법적 책임을 지지 않습니다.
* 카카오톡 나에게 보내기 API는 개발자 본인 계정으로 전송되는 개인화 서비스입니다.
* 보안을 위해 `.env` 파일과 `data/kakao_token.json` 파일은 절대로 공용 저장소에 노출되지 않도록 주의하십시오.
