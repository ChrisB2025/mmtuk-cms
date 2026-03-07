FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends git libjpeg62-turbo-dev zlib1g-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Install Tailwind CSS standalone CLI
RUN curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64 \
    && chmod +x tailwindcss-linux-x64 \
    && mv tailwindcss-linux-x64 /usr/local/bin/tailwindcss

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Build Tailwind CSS
RUN tailwindcss -i content/static/content/css/input.css -o content/static/content/css/output.css --minify

RUN python manage.py collectstatic --noinput

CMD ["sh", "-c", "python manage.py migrate && python manage.py setup_roles && python manage.py setup_deployment_monitoring && python manage.py setup_event_archival && python manage.py warmup && gunicorn mmtuk_cms.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers=4 --timeout=300 --access-logfile -"]
