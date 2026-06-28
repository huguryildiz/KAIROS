from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
from typing import Callable, Mapping
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

TOKEN_URL = (
    "http://metadata.google.internal/computeMetadata/v1/instance/"
    "service-accounts/default/token"
)


def metadata_access_token(timeout: float = 5.0) -> str:
    req = Request(TOKEN_URL, headers={"Metadata-Flavor": "Google"})
    with urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    token = data.get("access_token")
    if not token:
        raise RuntimeError("metadata server did not return an access token")
    return token


def upload_file(
    *,
    bucket: str,
    object_name: str,
    path: Path,
    token: str,
) -> str:
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    url = (
        f"https://storage.googleapis.com/upload/storage/v1/b/{quote(bucket, safe='')}/o"
        f"?uploadType=media&name={quote(object_name, safe='')}"
    )
    req = Request(
        url,
        data=path.read_bytes(),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": content_type,
        },
    )
    with urlopen(req, timeout=30) as resp:
        resp.read()
    return f"gs://{bucket}/{object_name}"


def list_objects(
    *,
    bucket: str,
    prefix: str,
    token: str,
) -> list[dict]:
    items: list[dict] = []
    page_token = None
    while True:
        query = {
            "prefix": prefix.strip("/"),
            "fields": "items(name,size,updated,contentType),nextPageToken",
        }
        if page_token:
            query["pageToken"] = page_token
        url = (
            f"https://storage.googleapis.com/storage/v1/b/{quote(bucket, safe='')}/o?"
            f"{urlencode(query)}"
        )
        req = Request(url, headers={"Authorization": f"Bearer {token}"})
        with urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        items.extend(payload.get("items", []))
        page_token = payload.get("nextPageToken")
        if not page_token:
            return items


def _object_name(prefix: str, path: Path) -> str:
    clean = prefix.strip("/")
    if not clean:
        return path.name
    return f"{clean}/{path.name}"


def upload_outputs_if_configured(
    paths: Mapping[str, Path],
    *,
    env: Mapping[str, str] | None = None,
    token_provider: Callable[[], str] = metadata_access_token,
    uploader: Callable[..., str] = upload_file,
) -> dict[str, str]:
    cfg = os.environ if env is None else env
    bucket = (cfg.get("KAIROS_GCS_BUCKET") or "").strip()
    if not bucket:
        return {}

    prefix = cfg.get("KAIROS_GCS_PREFIX", "schedule-outputs")
    token = token_provider()
    uploaded: dict[str, str] = {}
    for kind, path in paths.items():
        uploaded[kind] = uploader(
            bucket=bucket,
            object_name=_object_name(prefix, Path(path)),
            path=Path(path),
            token=token,
        )
    return uploaded


def list_outputs_if_configured(
    *,
    env: Mapping[str, str] | None = None,
    token_provider: Callable[[], str] = metadata_access_token,
    lister: Callable[..., list[dict]] = list_objects,
) -> list[dict]:
    cfg = os.environ if env is None else env
    bucket = (cfg.get("KAIROS_GCS_BUCKET") or "").strip()
    if not bucket:
        return []

    prefix = cfg.get("KAIROS_GCS_PREFIX", "schedule-outputs").strip("/")
    token = token_provider()
    rows = []
    for item in lister(bucket=bucket, prefix=prefix, token=token):
        name = str(item.get("name", ""))
        if not name:
            continue
        download_url = (
            f"https://storage.googleapis.com/download/storage/v1/b/"
            f"{quote(bucket, safe='')}/o/{quote(name, safe='')}?alt=media&access_token={token}"
        )
        rows.append({
            "updated": item.get("updated", ""),
            "file": Path(name).name,
            "size_bytes": int(item.get("size") or 0),
            "download_url": download_url,
        })
    return sorted(rows, key=lambda r: (r["updated"], r["file"]), reverse=True)
