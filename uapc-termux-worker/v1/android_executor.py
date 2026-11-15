"""Opt-in local Android build runner. No remote shell commands."""
import os,json,re,hashlib,subprocess,shutil,stat,urllib.request,urllib.error,zipfile,base64
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
UUID=re.compile(r"^[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")
SAFE=re.compile(r"^[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*$")
APK_TYPE = "application/vnd.android.package-archive"

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def runner_token():
    token = os.getenv("UAPC_RUNNER_TOKEN", "")
    if token:
        return token
    path = Path.home() / ".config/uapc/runner-token"
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("insecure_runner_token_file")
        token = stream.read(1025).decode("ascii").strip()
    if not re.fullmatch(r"[!-~]{32,1023}", token):
        raise ValueError("invalid_runner_token_file")
    return token


def transport_error(error, operation):
    if isinstance(error, urllib.error.HTTPError):
        if error.code in (401, 403):
            return {"status": "blocked", "detail": "runner_access_denied", "http_status": error.code}
        if error.code == 404:
            return {"status": "blocked", "detail": "runner_route_unavailable", "http_status": error.code}
        if error.code not in (408, 429) and error.code < 500:
            return {"status": "blocked", "detail": operation + "_rejected", "http_status": error.code}
    return {"status": "retry", "detail": operation + "_unavailable"}

def source(root,name):
    if not isinstance(name,str) or not SAFE.fullmatch(name): raise ValueError("invalid_source")
    root=Path(root).expanduser().resolve()
    path=(root/name).resolve()
    if not path.is_relative_to(root) or not path.is_dir(): raise ValueError("source_outside_root")
    settings=[path/"settings.gradle",path/"settings.gradle.kts"]
    if not any(f.is_file() and not f.is_symlink() for f in settings): raise ValueError("gradle_settings_missing")
    approval=path/".uapc-approved"
    if approval.is_symlink() or not approval.is_file(): raise ValueError("local_source_approval_missing")
    return path
def inspect_apk(apk):
    """Local APK structure/signature check; backend still owns final verification."""
    if not apk.is_file() or apk.is_symlink():
        return False
    try:
        with zipfile.ZipFile(apk) as archive:
            with archive.open("AndroidManifest.xml") as manifest:
                if manifest.read(4) != bytes((3,0,8,0)):
                    return False
            dex_files = [name for name in archive.namelist()
                         if re.fullmatch(r"classes(?:[2-9][0-9]*)?[.]dex", name)]
            if not dex_files:
                return False
            with archive.open(dex_files[0]) as dex:
                if dex.read(4) != bytes((100,101,120,10)):
                    return False
        signer = shutil.which("apksigner")
        signer_command = [signer] if signer else []
        if not signer_command:
            sdk = os.getenv("ANDROID_HOME") or os.getenv("ANDROID_SDK_ROOT")
            candidate = Path(sdk) / "build-tools/35.0.0/lib/apksigner.jar" if sdk else None
            if candidate and candidate.is_file() and shutil.which("java"):
                signer_command = ["java", "-jar", str(candidate)]
        if not signer_command:
            return False
        checked = subprocess.run([*signer_command, "verify", str(apk)],
                                 capture_output=True, timeout=30)
        return checked.returncode == 0
    except (OSError, ValueError, KeyError, zipfile.BadZipFile,
            subprocess.TimeoutExpired, RuntimeError):
        return False

def build_generated_source(root, job, launcher, upload):
    from source_generator import materialize_bundle
    from source_pipeline import validate_android_source

    job_id = job["id"]
    if job.get("source_dir") != f"uapc-{job_id}":
        raise ValueError("invalid_generated_source_directory")
    bundle = validate_android_source({"files": job.get("source_bundle")})
    if any(item["path"].startswith(("app/build/", ".gradle/")) for item in bundle["files"]):
        raise ValueError("generated_build_outputs_forbidden")
    if bundle["sha256"] != job.get("source_sha256"):
        raise ValueError("generated_source_sha256_mismatch")
    # Each attempt gets a fresh tree. The trusted launcher exposes only this
    # tree and the Android toolchain to the isolated Gradle process.
    with tempfile.TemporaryDirectory(prefix=".uapc-build-", dir=root) as temporary:
        project = Path(temporary) / "project"
        materialize_bundle(bundle, project)
        return build(project, upload=upload, launcher=launcher)


def classify_gradle_failure(stdout, stderr):
    log = stdout + "\n" + stderr
    if "Android resource linking failed" in log or "Android resource compilation failed" in log:
        return "android_resource_linking_failed"
    if "Compilation failed; see the compiler" in log or "Compilation error. See log" in log:
        return "android_source_compilation_failed"
    if "A problem evaluating" in log or "Could not compile build file" in log:
        return "android_gradle_configuration_failed"
    return "gradle_build_failed"


def build(path, upload=None, launcher=None):
    wrapper=path/"gradlew"
    if launcher:
        cmd = [launcher, str(path)]
    elif wrapper.is_file() and not wrapper.is_symlink(): cmd=["sh",str(wrapper),"--no-daemon","assembleDebug"]
    elif shutil.which("gradle"): cmd=["gradle","--no-daemon","assembleDebug"]
    else: return {"status":"blocked","detail":"gradle_missing"}
    # Remove previous outputs: never report an APK left by an older build.
    output_dir=path/"app/build/outputs/apk/debug"
    if output_dir.is_symlink(): return {"status":"blocked","detail":"output_symlink_rejected"}
    if output_dir.exists():
        for old in output_dir.glob("*.apk"):
            if old.is_symlink(): return {"status":"blocked","detail":"artifact_symlink_rejected"}
            old.unlink()
    try:
        if launcher:
            toolchain_environment = ("PATH", "LANG", "JAVA_HOME", "ANDROID_HOME", "ANDROID_SDK_ROOT")
            build_env = {key: os.environ[key] for key in toolchain_environment if key in os.environ}
        else:
            build_env = os.environ.copy()
            for credential in ("UAPC_RUNNER_TOKEN", "UAPC_VERCEL_BYPASS"):
                build_env.pop(credential, None)
        result=subprocess.run(cmd,cwd=path,timeout=1200,capture_output=True,text=True,env=build_env)
    except subprocess.TimeoutExpired: return {"status":"failed","detail":"gradle_timeout"}
    if result.returncode:
        return {"status": "failed", "detail": classify_gradle_failure(result.stdout, result.stderr)}
    if launcher and output_dir.resolve() != output_dir:
        return {"status": "failed", "detail": "output_symlink_rejected"}
    apks=list(output_dir.glob("*.apk"))[:10]
    evidence=[]
    for apk in apks:
        if inspect_apk(apk):
            with apk.open("rb") as stream:
                evidence.append({"name": apk.name, "sha256": hashlib.file_digest(stream, "sha256").hexdigest(),
                                 "size_bytes": os.fstat(stream.fileno()).st_size})
    if not evidence:
        return {"status":"failed","detail":"apk_invalid_or_unsigned"}
    report={"status":"built_unverified","detail":"independent_verification_required","artifacts":evidence}
    if len(evidence) == 1:
        artifact = output_dir / evidence[0]["name"]
        if evidence[0]["size_bytes"] <= 1024 * 1024:
            report["apk_base64"]=base64.b64encode(artifact.read_bytes()).decode("ascii")
        elif upload is not None:
            upload(artifact, evidence[0]["size_bytes"])
            report["apk_uploaded"] = True
        else:
            report["detail"] = "artifact_storage_required_for_download"
    else:
        report["detail"]="artifact_storage_required_for_download"
    return report
def run():
    if os.getenv("UAPC_ANDROID_EXECUTOR_ENABLED")!="1": return {"status":"disabled"}
    base=os.getenv("UAPC_BACKEND_URL","https://uapc-android-development.vercel.app").rstrip("/")
    parsed=urlsplit(base)
    worker=os.getenv("UAPC_WORKER_ID","termux-android")
    if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or not re.fullmatch(r"(?:termux|cloud-apk)-[A-Za-z0-9_-]{1,60}",worker): return {"status":"blocked","detail":"invalid_transport"}
    try:
        token = runner_token()
    except FileNotFoundError:
        return {"status":"blocked","detail":"runner_token_missing"}
    except (OSError, ValueError):
        return {"status":"blocked","detail":"runner_token_file_unusable"}
    if len(token) < 32 or not token.isascii() or any(c.isspace() for c in token):
        return {"status":"blocked","detail":"runner_token_invalid"}
    sdk=os.getenv("ANDROID_HOME") or os.getenv("ANDROID_SDK_ROOT")
    if not sdk or not Path(sdk).is_dir(): return {"status":"blocked","detail":"android_sdk_missing"}
    sdk_root=Path(sdk)
    if not any((sdk_root/"platforms").glob("android-*/android.jar")): return {"status":"blocked","detail":"android_platform_missing"}
    # Installed SDK binaries may target x86_64 and fail on Termux aarch64.
    # A present file is not proof of an executable build tool.
    aapt2=shutil.which("aapt2")
    if not aapt2:
        return {"status":"blocked","detail":"compatible_aapt2_missing"}
    try:
        check=subprocess.run([aapt2,"version"],capture_output=True,timeout=15)
    except (OSError,subprocess.TimeoutExpired):
        return {"status":"blocked","detail":"compatible_aapt2_unusable"}
    if check.returncode:
        return {"status":"blocked","detail":"compatible_aapt2_unusable"}
    # Android Gradle Plugin may still select the incompatible SDK copy.
    # Require an explicit override on Termux rather than claiming build readiness.
    if "com.termux" in str(Path.home()) and not os.getenv("UAPC_AGP_AAPT2_OVERRIDE_CONFIRMED"):
        return {"status":"blocked","detail":"termux_agp_aapt2_override_unconfirmed"}
    if not shutil.which("java"): return {"status":"blocked","detail":"java_missing"}
    root=Path(os.getenv("UAPC_ANDROID_PROJECTS_ROOT","~/uapc-projects")).expanduser().resolve()
    if not root.is_dir(): return {"status":"blocked","detail":"projects_root_missing"}
    launcher = os.getenv("UAPC_ISOLATED_ANDROID_BUILD_LAUNCHER")
    if launcher:
        executable = Path(launcher)
        if not executable.is_absolute() or not executable.is_file() or not os.access(executable, os.X_OK):
            return {"status": "blocked", "detail": "isolated_build_launcher_unavailable"}
    if not launcher and not shutil.which("gradle") and not any(p.is_file() and not p.is_symlink() for p in root.glob("*/gradlew")):
        return {"status": "blocked", "detail": "gradle_missing"}
    headers={"Authorization":"Bearer "+token,"X-UAPC-Worker-ID":worker,"Content-Type":"application/json"}
    if launcher:
        headers["X-UAPC-Generated-Build"] = "1"
    scope = os.getenv("UAPC_TASK_SCOPE")
    if scope:
        if not UUID.fullmatch(scope):
            return {"status":"blocked","detail":"invalid_task_scope"}
        headers["X-UAPC-Task-Scope"] = scope
    bypass = os.getenv("UAPC_VERCEL_BYPASS")
    if bypass:
        headers["x-vercel-protection-bypass"] = bypass
    opener = urllib.request.build_opener(NoRedirect())
    def call(path,payload=None,timeout=30):
        req=urllib.request.Request(base+path,headers=headers,data=json.dumps(payload).encode() if payload is not None else None,method="POST" if payload is not None else "GET")
        with opener.open(req,timeout=timeout) as resp:
            return resp.status,json.loads(resp.read(1_600_001)) if resp.status!=204 else None
    def upload(apk, size):
        from apk_storage import trusted_url

        status, info = call(f"/api/runner/v1/jobs/{job['id']}/apk-upload", {"size_bytes": size})
        url = info.get("url", "") if isinstance(info, dict) else ""
        if status != 200 or not isinstance(url, str) or not trusted_url(url):
            raise ValueError("invalid_apk_upload_url")
        with apk.open("rb") as stream:
            req = urllib.request.Request(url, data=stream, method="PUT", headers={
                "Content-Type": APK_TYPE, "Content-Length": str(size),
            })
            with opener.open(req, timeout=90) as response:
                if response.status not in (200, 201, 204):
                    raise ValueError("apk_storage_rejected")
    checks = dict.fromkeys(("source_root", "java", "gradle", "android_sdk", "server_https",
                           "runner_token_configured", "worker_id_valid"), True)
    try:
        heartbeat_status, heartbeat = call("/api/runner/v1/heartbeat", {
            "checks": checks, "ready_for_reviewed_gradle_project": False,
        })
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        return transport_error(error, "heartbeat")
    if heartbeat_status != 200 or not isinstance(heartbeat, dict) or heartbeat.get("ok") is not True:
        return {"status":"blocked","detail":"invalid_heartbeat"}
    try: status,job=call("/api/runner/v1/jobs/next")
    except (urllib.error.URLError,TimeoutError,ValueError) as error: return transport_error(error, "poll")
    if status==204: return {"status":"idle"}
    if status!=200 or not isinstance(job,dict) or not isinstance(job.get("id"),str) or not UUID.fullmatch(job["id"]): return {"status":"blocked","detail":"invalid_job"}
    try:
        if job.get("type")!="android.gradle.build" or job.get("approved") is not True: result={"status":"blocked","detail":"unapproved_job"}
        elif "source_bundle" in job:
            if not launcher:
                raise ValueError("isolated_build_launcher_required")
            result = build_generated_source(root, job, launcher, upload)
        else:
            result = build(source(root,job.get("source_dir")), upload=upload)
    except (urllib.error.URLError, TimeoutError): result={"status":"failed","detail":"apk_storage_upload_failed"}
    except ValueError as exc: result={"status":"blocked","detail":str(exc)}
    except OSError: result={"status":"failed","detail":"build_environment_unavailable"}
    try: status,_=call("/api/runner/v1/jobs/"+job["id"]+"/result",result,timeout=120)
    except (urllib.error.URLError,TimeoutError,ValueError) as error: return transport_error(error, "result_upload")
    return {"status":"reported","http_status":status,"runner_status":result["status"],"job_id":job["id"]}
if __name__=="__main__":
    try: print(json.dumps(run(),sort_keys=True))
    except Exception: print(json.dumps({"status":"blocked","detail":"executor_error"}))
