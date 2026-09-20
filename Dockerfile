# 공개 배포용 이미지. 백엔드 하나가 API와 화면을 같이 서빙한다.
# 화면이 상대경로(/api/...)를 쓰기 때문에 주소 설정이 따로 없다.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app/backend

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/
COPY dashboard/ /app/dashboard/

EXPOSE 8000

# PORT는 호스팅이 준다. 없으면 8000.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
