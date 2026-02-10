FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends git libjpeg62-turbo-dev zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

CMD ["sh", "-c", "python manage.py migrate && python manage.py setup_roles && gunicorn mmtuk_cms.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 2 --timeout 120"]
