#!/usr/bin/env bash
# One-shot: build the benchmark image, (re)create a Cloud Run Job, execute it,
# and print the resulting metrics from Cloud Logging.
#
#   bench/run_job.sh                 # both periods, 3 runs, 3000s budget
#
# Resources match prod (kairos service): 4 vCPU / 8Gi. Cloud Run Jobs allocate
# CPU for the whole task (no request-throttling), so timing is more stable than
# the request-driven UI service — but still note: it is Cloud Run burst CPU, not
# a dedicated VM, so report the machine line printed by the job.
set -euo pipefail

PROJECT="$(gcloud config get-value project 2>/dev/null)"
REGION="${REGION:-europe-west1}"
REPO="${REPO:-kairos}"                       # Artifact Registry repo (reuse the prod one)
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/kairos-bench:latest"
JOB="${JOB:-kairos-bench}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# 1. Stage the (untracked, possibly-PII) sample CSVs into a gitignored context
#    dir that .dockerignore's `data/` rule does not match.
echo "[1/4] staging sample CSVs into bench/_ctx/ ..."
rm -rf bench/_ctx && mkdir -p bench/_ctx
cp data/sample_courses_2025_001.csv data/sample_courses_2025_002.csv bench/_ctx/

# 2. Build + push the image (ensure the Artifact Registry repo exists first).
if ! gcloud artifacts repositories describe "$REPO" \
        --location "$REGION" >/dev/null 2>&1; then
  echo "[2/4] creating Artifact Registry repo $REPO ..."
  gcloud artifacts repositories create "$REPO" \
      --repository-format docker --location "$REGION"
fi
echo "[2/4] building image $IMAGE ..."
gcloud builds submit --config bench/cloudbuild.bench.yaml \
    --substitutions "_IMAGE=${IMAGE}" .

# 3. Create or update the Job (idempotent).
echo "[3/4] (re)creating Cloud Run Job $JOB ..."
if gcloud run jobs describe "$JOB" --region "$REGION" >/dev/null 2>&1; then
  gcloud run jobs update "$JOB" --region "$REGION" --image "$IMAGE" \
      --cpu 4 --memory 8Gi --task-timeout 3600 --max-retries 0
else
  gcloud run jobs create "$JOB" --region "$REGION" --image "$IMAGE" \
      --cpu 4 --memory 8Gi --task-timeout 3600 --max-retries 0
fi

# 4. Execute and wait, then dump the captured metrics JSON from the logs.
echo "[4/4] executing (this runs the full solve; can take many minutes) ..."
gcloud run jobs execute "$JOB" --region "$REGION" --wait

echo
echo "===== job log tail (metrics) ====="
gcloud logging read \
    "resource.type=cloud_run_job AND resource.labels.job_name=${JOB}" \
    --project "$PROJECT" --limit 200 --freshness 2h \
    --format 'value(textPayload)' | tac
echo
echo "Tip: the full machine-readable result is between the"
echo "     BENCHMARK_JSON_BEGIN / BENCHMARK_JSON_END markers above."

rm -rf bench/_ctx
