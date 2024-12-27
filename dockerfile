FROM python:3.12.1-alpine

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 패키지 설치
RUN apk update && apk add --no-cache \
    gcc \
    musl-dev \
    linux-headers \
    python3-dev \
    postgresql-client \
    libc-dev \
    make \
    net-tools \
    py3-netifaces \
    && rm -rf /var/cache/apk/*

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on

# requirements.txt 파일 복사 및 netifaces 제거
COPY requirements.txt .
RUN grep -v "netifaces" requirements.txt > requirements_new.txt && \
    mv requirements_new.txt requirements.txt

# 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 나머지 프로젝트 파일들을 복사
COPY . .

# 비특권 사용자 생성 및 전환 추가
RUN adduser --disabled-password --no-create-home appuser && \
    chown -R appuser:appuser /app
USER appuser

# 소켓 통신을 위한 포트 노출
EXPOSE 8000

# 실행 명령어
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]  