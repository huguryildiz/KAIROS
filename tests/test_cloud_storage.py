from pathlib import Path

from timetabling import cloud_storage


def test_upload_outputs_if_configured_skips_without_bucket(tmp_path, monkeypatch):
    p = tmp_path / "schedule.json"
    p.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("KAIROS_GCS_BUCKET", "ambient-bucket")

    uploaded = cloud_storage.upload_outputs_if_configured(
        {"json": p},
        env={},
        token_provider=lambda: "unused",
        uploader=lambda **kwargs: "unused",
    )

    assert uploaded == {}


def test_upload_outputs_if_configured_uploads_with_prefix(tmp_path):
    p = tmp_path / "schedule.json"
    p.write_text("{}", encoding="utf-8")
    calls = []

    def fake_uploader(**kwargs):
        calls.append(kwargs)
        return f"gs://{kwargs['bucket']}/{kwargs['object_name']}"

    uploaded = cloud_storage.upload_outputs_if_configured(
        {"json": p},
        env={"KAIROS_GCS_BUCKET": "kairos-results", "KAIROS_GCS_PREFIX": "runs/"},
        token_provider=lambda: "token",
        uploader=fake_uploader,
    )

    assert uploaded == {"json": "gs://kairos-results/runs/schedule.json"}
    assert calls == [{
        "bucket": "kairos-results",
        "object_name": "runs/schedule.json",
        "path": p,
        "token": "token",
    }]


def test_list_outputs_if_configured_skips_without_bucket(monkeypatch):
    monkeypatch.setenv("KAIROS_GCS_BUCKET", "ambient-bucket")

    rows = cloud_storage.list_outputs_if_configured(
        env={},
        token_provider=lambda: "unused",
        lister=lambda **kwargs: [{"name": "unused"}],
    )

    assert rows == []


def test_list_outputs_if_configured_returns_newest_first():
    calls = []

    def fake_lister(**kwargs):
        calls.append(kwargs)
        return [
            {"name": "runs/schedule_001_20260628_140509.json", "size": "128", "updated": "2026-06-28T11:05:09Z"},
            {"name": "runs/schedule_001_20260628_140509.csv", "size": "256", "updated": "2026-06-28T11:05:10Z"},
            {"name": "runs/schedule_001_20260627_090000.json", "size": "64", "updated": "2026-06-27T06:00:00Z"},
        ]

    rows = cloud_storage.list_outputs_if_configured(
        env={"KAIROS_GCS_BUCKET": "kairos-results", "KAIROS_GCS_PREFIX": "runs"},
        token_provider=lambda: "token",
        lister=fake_lister,
    )

    assert [r["file"] for r in rows] == [
        "schedule_001_20260628_140509.csv",
        "schedule_001_20260628_140509.json",
        "schedule_001_20260627_090000.json",
    ]
    assert rows[0]["size_bytes"] == 256
    assert "runs%2Fschedule_001_20260628_140509.csv" in rows[0]["download_url"]
    assert "access_token=token" in rows[0]["download_url"]
    assert rows[0]["download_url"].startswith("https://storage.googleapis.com/")
    assert calls == [{"bucket": "kairos-results", "prefix": "runs", "token": "token"}]
