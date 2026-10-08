FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

FROM runtime AS review

COPY tests ./tests

# 월 1회 건물 · 땅 적재 도구(방식1). compose 는 마지막 단계(final)만 빌드한다 - 이 단계는 --target geo-loader 로만 만든다
FROM runtime AS geo-loader

COPY requirements-geo.txt ./
RUN pip install --no-cache-dir -r requirements-geo.txt

FROM runtime AS final
