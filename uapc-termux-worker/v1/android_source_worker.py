"""Opt-in UAPC source-generation worker, independent of Android build worker.

Requires a locally running Ollama model. Never leases a task unless explicitly
enabled; backend records generated source as WAITING_APPROVAL, not COMPLETED.
"""
import json
import os
import re
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from android_executor import NoRedirect, runner_token, transport_error, UUID
from source_generator import generate_local_bundle, local_source_model_ready
from source_pipeline import validate_android_source


def run():
    if os.getenv("UAPC_SOURCE_WORKER_ENABLED") != "1":
        return {"status": "disabled"}
    base = os.getenv("UAPC_BACKEND_URL", "").rstrip("/")
    parsed = urlsplit(base)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.path or parsed.query or parsed.fragment):
        return {"status": "blocked", "detail": "invalid_transport"}
    worker = os.getenv("UAPC_WORKER_ID", "termux-android")
    if not re.fullmatch(r"(?:termux|cloud-apk)-[A-Za-z0-9_-]{1,60}", worker):
        return {"status": "blocked", "detail": "invalid_worker"}
    model = os.getenv("UAPC_LOCAL_SOURCE_MODEL")
    if not model:
        return {"status": "blocked", "detail": "local_source_model_missing"}
    if not re.fullmatch(r"[A-Za-z0-9_./:-]{1,120}", model):
        return {"status": "blocked", "detail": "invalid_source_model"}
    try:
        token = runner_token()
    except (OSError, ValueError):
        return {"status": "blocked", "detail": "runner_token_unavailable"}
    if len(token) < 32 or not token.isascii() or any(ch.isspace() for ch in token):
        return {"status": "blocked", "detail": "runner_token_invalid"}
    headers = {
        "Authorization": "Bearer " + token,
        "X-UAPC-Worker-ID": worker,
        "X-UAPC-Source-Generator": "ollama",
        "Content-Type": "application/json",
    }
    scope = os.getenv("UAPC_TASK_SCOPE")
    if scope:
        if not UUID.fullmatch(scope):
            return {"status": "blocked", "detail": "invalid_task_scope"}
        headers["X-UAPC-Task-Scope"] = scope
    bypass = os.getenv("UAPC_VERCEL_BYPASS")
    if bypass:
        headers["x-vercel-protection-bypass"] = bypass
    opener = urllib.request.build_opener(NoRedirect())
    def call(path, payload=None, timeout=30):
        req = urllib.request.Request(
            base + path, headers=headers,
            data=json.dumps(payload).encode() if payload is not None else None,
            method="POST" if payload is not None else "GET")
        with opener.open(req, timeout=timeout) as response:
            raw = response.read(1_500_000)
            return response.status, json.loads(raw) if raw else None
    try:
        ready = local_source_model_ready(model)
    except (urllib.error.URLError, TimeoutError, OSError):
        ready = False
    if not ready:
        return {"status": "blocked", "detail": "local_source_model_unavailable"}
    try:
        code, job = call("/api/runner/v1/jobs/next")
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return transport_error(exc, "poll")
    if code == 204:
        return {"status": "idle"}
    if (code != 200 or not isinstance(job, dict)
            or not UUID.fullmatch(str(job.get("id", "")))):
        return {"status": "blocked", "detail": "invalid_job"}
    if job.get("type") != "android.source.generate":
        return {"status": "blocked", "detail": "unexpected_job_type", "job_id": job["id"]}
    try:
        bundle = generate_local_bundle(job["objective"], repair_reason=job.get("repair_reason"))
        bundle = validate_android_source(bundle)
        result = {"status": "source_generated", "files": bundle["files"],
                  "model": model}
    except Exception as exc:
        result = {"status": "failed", "detail": "source_generation_" + type(exc).__name__}
    try:
        code, response = call("/api/runner/v1/jobs/" + job["id"] + "/result", result, timeout=120)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return transport_error(exc, "result_upload")
    return {"status": "reported", "job_id": job["id"],
            "http_status": code, "runner_status": result["status"],
            "backend_status": response.get("status") if isinstance(response, dict) else None}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
