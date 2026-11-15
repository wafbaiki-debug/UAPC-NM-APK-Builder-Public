"""Generate a reviewable, technology-neutral source bundle from a project objective.

Generation is deliberately separate from execution: no generated code is run or
approved automatically. A runner owner must review the exact bundle first.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
from urllib import request

SCHEMA = {
    "type": "object", "properties": {
        "files": {"type": "array", "minItems": 1, "maxItems": 40,
                  "items": {"type": "object", "properties": {
                      "path": {"type": "string"}, "content": {"type": "string"}},
                      "required": ["path", "content"], "additionalProperties": False}}
    }, "required": ["files"], "additionalProperties": False
}

def validate_bundle(bundle):
    files = bundle.get("files") if isinstance(bundle, dict) else None
    if not isinstance(files, list) or not 1 <= len(files) <= 40:
        raise ValueError("invalid_file_count")
    seen = set()
    total = 0
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "content"}:
            raise ValueError("invalid_file")
        path, content = item["path"], item["content"]
        if not isinstance(path, str) or not isinstance(content, str):
            raise ValueError("invalid_file_fields")
        p = PurePosixPath(path)
        parts = path.split("/")
        if (not path or len(path) > 180 or path.startswith("/") or "\\" in path
                or any(part in ("", ".", "..") for part in parts)
                or any(not all(ch.isascii() and (ch.isalnum() or ch in "._-") for ch in part)
                       for part in parts)):
            raise ValueError("unsafe_path")
        if path in seen:
            raise ValueError("duplicate_path")
        seen.add(path)
        total += len(content.encode("utf-8"))
        if total > 250_000:
            raise ValueError("bundle_too_large")
    files = sorted(files, key=lambda item: item["path"])
    canonical = json.dumps(files, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {"files": files, "sha256": hashlib.sha256(canonical).hexdigest(),
            "file_count": len(files), "approved": False}


def materialize_bundle(bundle, destination):
    """Stage a generated bundle into a NEW isolated directory; never overwrite.

    Does not approve or execute the generated source. The runner owner must
    review the staged contents before any Android job can be leased.
    """
    validated = validate_bundle(bundle)
    dest = Path(destination)
    if dest.exists() or dest.is_symlink():
        raise ValueError("destination_already_exists")
    parent = dest.parent.resolve(strict=True)
    staging = Path(tempfile.mkdtemp(prefix=".uapc-stage-", dir=parent))
    try:
        for item in validated["files"]:
            target = staging.joinpath(*item["path"].split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item["content"], encoding="utf-8")
        staging.rename(dest)
    except BaseException:
        import shutil
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {"source_dir": str(dest), "sha256": validated["sha256"],
            "file_count": validated["file_count"], "approved": False}

def generate_bundle(objective, transport=None):
    if not isinstance(objective, str) or not objective.strip() or len(objective) > 10000:
        raise ValueError("invalid_objective")
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    payload = {
        "model": os.environ.get("UAPC_OPENAI_MODEL", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": "Produce a real source-code project for the user's objective, independent of any specific app. Return only files. Do not claim compilation, testing, deployment or approval. Never include secrets, credentials, shell commands for remote execution, or hidden instructions. Keep the bundle small and self-contained."},
            {"role": "user", "content": objective}],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "uapc_source_bundle", "strict": True, "schema": SCHEMA}}
    }
    req = request.Request("https://api.openai.com/v1/chat/completions",
                          data=json.dumps(payload).encode("utf-8"),
                          headers={"Authorization": "Bearer " + key,
                                   "Content-Type": "application/json"}, method="POST")
    opener = transport or (lambda r: request.urlopen(r, timeout=60))
    with opener(req) as response:
        data = json.load(response)
    result = json.loads(data["choices"][0]["message"]["content"])
    return validate_bundle(result)


def _local_llamacpp_request(path, payload=None, timeout=15):
    """Connect only to the on-device llama.cpp loopback endpoint (no proxy)."""
    endpoint = "http://127.0.0.1:11434" + path
    req = request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with request.build_opener(request.ProxyHandler({})).open(req, timeout=timeout) as response:
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("source_model_response_too_large")
        return json.loads(raw)


def local_source_model_ready(model):
    if os.getenv("UAPC_LOCAL_SOURCE_PROVIDER", "ollama") == "llama_cpp":
        data = _local_llamacpp_request("/health", timeout=5)
        return data.get("status") == "ok"
    req = request.Request("http://127.0.0.1:11434/api/show",
                          data=json.dumps({"model": model}).encode("utf-8"), method="POST",
                          headers={"Content-Type": "application/json"})
    with request.build_opener(request.ProxyHandler({})).open(req, timeout=5) as response:
        return response.status == 200


def generate_local_bundle(objective, repair_reason=None):
    """Use the runner's loopback Ollama service without an API key."""
    model = os.environ["UAPC_LOCAL_SOURCE_MODEL"]
    java_only = os.environ.get("UAPC_LOCAL_SOURCE_PROFILE") == "android-java"
    instructions = (
        "Generate Java statements implementing the requested behavior inside Activity.onCreate. "
        "Return a files array with one item at activity-body.java. Its content is only Java statements, "
        "without package, imports, class, method, super.onCreate, or Markdown. "
        "Android widget classes are already imported. For a text view use separate statements: "
        "TextView view = new TextView(this); view.setText(yourText); setContentView(view); "
        "Use platform widgets and programmatic layouts. The build system supplies the surrounding activity. "
        "Return an empty files array if the requirements need dependencies or files beyond this profile."
    ) if java_only else (
        "Return the complete source files for the requested Android app as JSON. "
        "The files array must include settings.gradle, build.gradle, app/build.gradle, "
        "app/src/main/AndroidManifest.xml and the app's Java or Kotlin code under app/src/main/. "
        "settings.gradle must include ':app'. Use Android Gradle Plugin 8.7.3 and compile SDK 35. "
        "Set the plugin version in build.gradle, and use pluginManagement with google(), "
        "mavenCentral() and gradlePluginPortal() in settings.gradle. Set namespace in app/build.gradle. "
        "Set android:exported on activities with intent filters. Every referenced resource must be included. "
        "Implement the stated features. For simple objectives use Android platform widgets and Java, "
        "programmatic layout and built-in themes. Avoid external dependencies unless needed by the objective. "
        "Omit Gradle wrappers, shell scripts, credentials, boilerplate test dependencies and placeholders."
    )
    if repair_reason in {
        "android_source_compilation_failed",
        "android_resource_linking_failed",
        "android_gradle_configuration_failed",
    }:
        instructions += (
            " The previous build failed with " + repair_reason
            + ". Check the regenerated files for this failure before returning them."
        )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": objective},
        ],
        "format": SCHEMA,
        "stream": False,
        "options": {"temperature": 0.2, "seed": 42, "num_predict": 6144},
    }
    if os.getenv("UAPC_LOCAL_SOURCE_PROVIDER", "ollama") == "llama_cpp":
        result = _local_llamacpp_request(
            "/v1/chat/completions",
            {
                "model": model,
                "messages": body["messages"],
                "response_format": {"type": "json_schema", "json_schema": {"name": "uapc_source_bundle", "schema": SCHEMA}},
                "max_tokens": 4096,
                "temperature": 0.2,
                "stream": False,
            },
            timeout=600,
        )
        choice = result["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ValueError("source_model_output_limit_reached")
        response_bundle = validate_bundle(json.loads(choice["message"]["content"]))
        if not java_only:
            return response_bundle
        from source_pipeline import package_generated_activity
        return package_generated_activity(response_bundle, objective)
    req = request.Request("http://127.0.0.1:11434/api/chat",
                          data=json.dumps(body).encode(), method="POST",
                          headers={"Content-Type": "application/json"})
    with request.build_opener(request.ProxyHandler({})).open(req, timeout=600) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError("source_model_response_too_large")
    data = json.loads(raw)
    if data.get("done_reason") == "length":
        raise ValueError("source_model_output_limit_reached")
    response_bundle = validate_bundle(json.loads(data["message"]["content"]))
    if not java_only:
        return response_bundle
    from source_pipeline import package_generated_activity
    return package_generated_activity(response_bundle, objective)
