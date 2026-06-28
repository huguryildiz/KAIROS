# Headless benchmark image for the KAIROS solver, run as a Cloud Run Job.
# Built from the repo root so it can see src/ and bench/:
#     gcloud builds submit --config bench/cloudbuild.bench.yaml .
# The sample CSVs are staged into bench/_ctx/ (gitignored, NOT under data/, so
# they dodge .dockerignore's data/ rule) by bench/run_job.sh before the build.
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY bench/benchmark.py ./bench/benchmark.py
COPY bench/soft_oat.py ./bench/soft_oat.py
COPY bench/_ctx/ ./data/

# Defaults can be overridden by the Job's container args. Both periods, 3 runs,
# prod-matching 3000s budget. Classroom inventory comes from defaults.py.
ENTRYPOINT ["python3"]
CMD ["bench/benchmark.py", \
     "--case", "data/sample_courses_2025_001.csv:001", \
     "--case", "data/sample_courses_2025_002.csv:002", \
     "--runs", "3", "--time-limit", "3000", "--out", "/tmp/benchmark.json"]
