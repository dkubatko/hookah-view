# Hookah Shop: one small Python image; data lives in /data (mount a volume).
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data PORT=8440
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY static ./static
ARG GIT_COMMIT=dev
ENV GIT_COMMIT=$GIT_COMMIT
RUN mkdir -p /data && chown 99:100 /data
USER 99:100
EXPOSE 8440
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8440/api/health',timeout=4)"
CMD ["python", "-m", "app.main"]
