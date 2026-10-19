FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --create-home --uid 1000 prumo
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Estáticos com hash e comprimidos, servidos pelo WhiteNoise. Esta chave só existe durante o build.
RUN DJANGO_DEBUG=false DJANGO_SECRET_KEY=somente-para-collectstatic python manage.py collectstatic --noinput
USER prumo
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers \"${GUNICORN_WORKERS:-2}\" --access-logfile -"]
