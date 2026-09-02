# Build trang web truoc trong stage rieng: image cuoi khong can Node lan node_modules.
FROM node:24-slim AS web
WORKDIR /web
# Copy manifest truoc de sua code React khong lam mat cache layer npm ci.
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build


FROM python:3.14-slim

# Pin dung version uv dang dung o local, de build lai luon cho ket qua giong nhau.
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /uvx /usr/local/bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

# tzdata: bot ghi gio tung van nen container bat buoc phai biet mui gio thuc,
# khong co thi cot "Gio" tren sheet se lech ve UTC.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cai dependency truoc, copy source sau: sua code khong lam mat cache layer nay.
# --frozen: dung dung uv.lock, khong tu resolve lai -> deploy dung y het local.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY README.md main.py ./
COPY ghibai/ ./ghibai/
RUN uv sync --frozen --no-dev

# Ban build cua trang web; WEB_DIST trong docker-compose tro toi day.
COPY --from=web /web/dist ./web/dist

# SQLite ghi vao /app/data nen thu muc phai thuoc ve user chay bot, khong chay bang root.
RUN useradd --create-home --uid 10001 ghibai \
    && mkdir -p /app/data /app/secrets \
    && chown -R ghibai:ghibai /app
USER ghibai

# Khong co HEALTHCHECK: bot dung long polling nen khong co endpoint nao de kiem tra that.
# Khi polling chet, python-telegram-bot thoat han -> restart policy cua compose lo phan do.
CMD ["ghibai"]
