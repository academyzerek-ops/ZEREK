# ZEREK API — Dockerfile с WeasyPrint-системными библиотеками.
# Nixpacks не смог надёжно установить libpango/libcairo/libgobject
# в dlopen-видимые пути на Railway → переключились на Docker.

FROM python:3.12-slim

# Системные библиотеки для WeasyPrint (Pango / Cairo / GObject)
# + шрифты + общие утилиты. --no-install-recommends уменьшает образ.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libfontconfig1 \
    libcairo2 \
    libjpeg62-turbo \
    libgdk-pixbuf-2.0-0 \
    libglib2.0-0 \
    shared-mime-info \
    fonts-liberation \
    fonts-dejavu-core \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Сначала deps — кеш слоя сохраняется между изменениями кода.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код.
COPY . .

# Railway подставит $PORT; для локального запуска дефолт 8000.
ENV PORT=8000
EXPOSE 8000

# Явный sh -c, чтобы ${PORT} раскрывался. В exec-form переменные
# не раскрываются; просто shell-form тоже ломалась на Railway.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
