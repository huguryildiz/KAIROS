#!/usr/bin/env bash
# Build the benchmark image, run the soft one-at-a-time benchmark as Cloud Run Jobs,
# and print the resulting log output.
#
# Defaults:
#   periods: 001 and 002
#   N:       9999 (all sample rows)
#   budget:  converge 600s, anneal 120s/profile
#   seeds:   0,1,2
#
# Examples:
#   bench/run_soft_oat_job.sh
#   PERIODS=001 SEEDS=0,1 N=9999 CONVERGE_S=900 ANNEAL_S=180 bench/run_soft_oat_job.sh
set -euo pipefail

PROJECT="$(gcloud config get-value project 2>/dev/null)"
REGION="${REGION:-europe-west1}"
REPO="${REPO:-kairos}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/kairos-bench:soft-oat"
JOB_PREFIX="${JOB_PREFIX:-kairos-soft-oat}"

PERIODS="${PERIODS:-001 002}"
N="${N:-9999}"
CONVERGE_S="${CONVERGE_S:-600}"
ANNEAL_S="${ANNEAL_S:-120}"
ACCEPTOR="${ACCEPTOR:-deluge}"
SEEDS="${SEEDS:-0,1,2}"
TASK_TIMEOUT="${TASK_TIMEOUT:-7200}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "[1/4] staging sample CSVs into bench/_ctx/ ..."
rm -rf bench/_ctx && mkdir -p bench/_ctx
cp data/sample_courses_2025_001.csv data/sample_courses_2025_002.csv data/classrooms.csv bench/_ctx/

if ! gcloud artifacts repositories describe "$REPO" \
        --location "$REGION" >/dev/null 2>&1; then
  echo "[2/4] creating Artifact Registry repo $REPO ..."
  gcloud artifacts repositories create "$REPO" \
      --repository-format docker --location "$REGION"
fi

echo "[2/4] building image $IMAGE ..."
gcloud builds submit --config bench/cloudbuild.bench.yaml \
    --substitutions "_IMAGE=${IMAGE}" .

for PERIOD in $PERIODS; do
  JOB="${JOB_PREFIX}-${PERIOD}"
  ARGS="bench/soft_oat.py,${PERIOD},${N},${CONVERGE_S},${ANNEAL_S},${ACCEPTOR},${SEEDS}"

  echo "[3/4] (re)creating Cloud Run Job $JOB ..."
  if gcloud run jobs describe "$JOB" --region "$REGION" >/dev/null 2>&1; then
    gcloud run jobs update "$JOB" --region "$REGION" --image "$IMAGE" \
        --cpu 4 --memory 8Gi --task-timeout "$TASK_TIMEOUT" --max-retries 0 \
        --args "$ARGS"
  else
    gcloud run jobs create "$JOB" --region "$REGION" --image "$IMAGE" \
        --cpu 4 --memory 8Gi --task-timeout "$TASK_TIMEOUT" --max-retries 0 \
        --args "$ARGS"
  fi

  echo "[4/4] executing $JOB ..."
  gcloud run jobs execute "$JOB" --region "$REGION" --wait

  echo
  echo "===== $JOB log output ====="
  gcloud logging read \
      "resource.type=cloud_run_job AND resource.labels.job_name=${JOB}" \
      --project "$PROJECT" --limit 500 --freshness 8h \
      --format 'value(textPayload)' | tac
  echo
done

rm -rf bench/_ctx
