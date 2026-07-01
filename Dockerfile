# Streamlit timetabling UI for Google Cloud Run.
# Build:  gcloud run deploy --source .   (Cloud Build uses this Dockerfile)
# No data/ (PII) is copied in — the UI is fed by uploaded input; classroom
# defaults come from src/timetabling/defaults.py.
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY patch_ga_snippet.py ./patch_ga_snippet.py
RUN python patch_ga_snippet.py

COPY src/ ./src/
COPY views/ ./views/
COPY assets/ ./assets/
COPY .streamlit/ ./.streamlit/
COPY app.py ./

# Cloud Run provides $PORT (defaults to 8080). Streamlit must bind it on 0.0.0.0.
EXPOSE 8080
CMD streamlit run app.py \
    --server.port=${PORT:-8080} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --browser.gatherUsageStats=false
