FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends git libjpeg62-turbo-dev zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# output.css is pre-built and committed — no Tailwind build step needed here
RUN python manage.py collectstatic --noinput

CMD ["sh", "-c", "python manage.py migrate && python manage.py loaddata content/fixtures/initial_content.json && python manage.py setup_roles && python manage.py setup_deployment_monitoring && python manage.py setup_event_archival && python manage.py warmup && gunicorn mmtuk_cms.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers=4 --timeout=300 --access-logfile -"]
