# 1단계: 파이썬 베이스 이미지 지정 (slim 이미지로 가볍게 구성)
FROM python:3.11-slim

# 2단계: 환경 변수 설정
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_ROOT_USER_ACTION=ignore

# 3단계: 작업 디렉토리 생성 및 설정
WORKDIR /app

# 4단계: 타임존 설치 (스케줄러 시간 동기화를 위함)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && rm -rf /var/lib/apt/lists/*
ENV TZ=Asia/Seoul

# 5단계: 종속 패키지 복사 및 설치
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt


# 6단계: 소스 코드 복사
COPY . .
RUN chmod +x .

# 7단계: 데이터 볼륨 선언 (시놀로지 볼륨 매핑을 권장)
VOLUME ["/app/data"]

# 8단계: 포트 노출
EXPOSE 5001

# 9단계: 애플리케이션 시작
CMD ["python", "app.py"]
