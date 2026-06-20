# Deploy — Google Cloud Run (IAM-gated, no public URL)

The Streamlit UI runs as a single Cloud Run service in **your own GCP project**,
**EU region**, **scale-to-zero**. Access is locked to named Google accounts via IAM:
there is **no public URL** — each user reaches it through `gcloud run services proxy`
on `localhost`. PII never enters the image (`data/` is excluded by `.dockerignore`;
classroom defaults come from `src/timetabling/defaults.py`).

## 0. One-time prerequisites

Run these in **Cloud Shell** (gcloud is preinstalled) or on a machine with the
[gcloud CLI](https://cloud.google.com/sdk/docs/install) installed.

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

Pick the EU region closest to you — `europe-west1` (Belgium) or `europe-west3`
(Frankfurt, closest to TR):

```bash
gcloud config set run/region europe-west3
```

## 1. Deploy (build happens server-side via Cloud Build)

From the repo root (the directory with `Dockerfile` and `app.py`):

```bash
gcloud run deploy timetabling \
  --source . \
  --no-allow-unauthenticated \
  --memory 4Gi --cpu 4 --cpu-boost \
  --timeout 3600 \
  --min-instances 0 --max-instances 2
```

- `--no-allow-unauthenticated` → no public access; IAM required.
- `--timeout 3600` → keeps the Streamlit websocket alive (a solve can run up to the
  600s slider limit; the websocket is one long request).
- `--min-instances 0` → scales to zero, so there is no idle cost (first hit cold-starts
  ~10–30 s while the OR-Tools image boots).
- `--source .` → Cloud Build reads the `Dockerfile`; `.dockerignore` keeps `data/` out.

## 2. Grant access to the 1–2 users

```bash
gcloud run services add-iam-policy-binding timetabling \
  --member="user:alice@gmail.com" --role="roles/run.invoker"
gcloud run services add-iam-policy-binding timetabling \
  --member="user:bob@gmail.com"   --role="roles/run.invoker"
```

## 3. Open the app (each user, on their own machine)

The user needs gcloud installed and must be one of the granted accounts:

```bash
gcloud auth login                       # once, as the granted account
gcloud run services proxy timetabling --region europe-west3 --port 8080
```

Then open **http://localhost:8080**. The proxy injects the user's Google identity
token, so Cloud Run authorizes the request. Closing the proxy closes access.

## Updating

Re-run the **Step 1** deploy command; Cloud Run rolls out a new revision with zero
downtime. IAM bindings persist across deploys.

## Notes

- **Region / KVKK:** keep the service in an EU region; enable Cloud Audit Logs.
- **Cost:** scale-to-zero + 1–2 users ≈ a few cents per active hour, $0 when idle.
- **Bumping the solve time limit > 600 s:** also raise the Solve-page slider max and
  keep `--timeout` ≥ that value.
