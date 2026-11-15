"""UAPC universal source-preparation stage.

Invoked by a trusted worker after a project objective is received. Generates
source and stages it for review. Never runs untrusted generated build scripts.
"""
import argparse
import hashlib
import json
from pathlib import Path
from source_generator import generate_bundle, materialize_bundle, validate_bundle


def package_generated_activity(bundle, objective):
    """Add build metadata for the explicitly selected single-activity Java profile."""
    java_path = "app/src/main/java/uapc/generated/MainActivity.java"
    if [item["path"] for item in bundle["files"]] != ["activity-body.java"]:
        raise ValueError("android_java_profile_requires_single_activity")
    body = bundle["files"][0]["content"].strip()
    if not body or "setContentView(" not in body:
        raise ValueError("android_java_profile_requires_activity_body")
    project_id = hashlib.sha256(objective.encode()).hexdigest()[:16]
    metadata = {
        java_path: (
            "package uapc.generated;\n\n"
            "import android.os.Bundle;\n"
            "import android.view.*;\n"
            "import android.widget.*;\n\n"
            "public class MainActivity extends android.app.Activity {\n"
            "    @Override protected void onCreate(Bundle state) {\n"
            "        super.onCreate(state);\n"
            + "\n".join("        " + line for line in body.splitlines())
            + "\n    }\n}\n"
        ),
        "settings.gradle": (
            "pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }\n"
            "include ':app'\n"
        ),
        "app/build.gradle": (
            "plugins { id 'com.android.application' version '8.7.3' }\n"
            "android {\n"
            "    namespace 'uapc.generated'\n"
            "    compileSdk 35\n"
            "    defaultConfig {\n"
            f"        applicationId 'uapc.generated.app{project_id}'\n"
            "        minSdk 24\n"
            "        targetSdk 35\n"
            "    }\n"
            "}\n"
        ),
        "app/src/main/AndroidManifest.xml": (
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n'
            '    <application android:label="UAPC Generated App">\n'
            '        <activity android:name="uapc.generated.MainActivity" android:exported="true">\n'
            '            <intent-filter>\n'
            '                <action android:name="android.intent.action.MAIN"/>\n'
            '                <category android:name="android.intent.category.LAUNCHER"/>\n'
            '            </intent-filter>\n'
            '        </activity>\n'
            '    </application>\n'
            '</manifest>\n'
        ),
    }
    return validate_bundle({"files": [
        {"path": path, "content": content} for path, content in metadata.items()
    ]})

def generate_android_source(objective, generator=generate_bundle):
    if not isinstance(objective, str) or not 1 <= len(objective.strip()) <= 10000:
        raise ValueError("invalid_objective")
    android_objective = (
        "Generate a buildable Android Gradle application project, not a plan or "
        "placeholder. Include settings.gradle or settings.gradle.kts, the app "
        "module build.gradle or build.gradle.kts, an AndroidManifest.xml and "
        "actual application source code. The application requirements are: "
        + objective
    )
    return validate_android_source(generator(android_objective))


def validate_generated_gradle(bundle):
    files = {item["path"]: item["content"] for item in bundle["files"]}
    gradle = "\n".join(content for path, content in files.items()
                       if path in ("build.gradle", "build.gradle.kts", "settings.gradle",
                                   "settings.gradle.kts", "app/build.gradle", "app/build.gradle.kts"))
    if "com.android.application" not in gradle or "8.7.3" not in gradle:
        raise ValueError("android_gradle_plugin_version_missing")
    module = files.get("app/build.gradle", files.get("app/build.gradle.kts", ""))
    if "namespace" not in module:
        raise ValueError("android_namespace_missing")
    return bundle


def supply_missing_gradle_root(bundle):
    """Supply standard plugin wiring if the generated app omits its root build file."""
    import re
    from xml.etree import ElementTree

    files = {item["path"]: item["content"] for item in bundle["files"]}
    settings_path = "settings.gradle" if "settings.gradle" in files else "settings.gradle.kts"
    module_path = "app/build.gradle" if "app/build.gradle" in files else "app/build.gradle.kts"
    module = files[module_path]
    if not re.search(r"""\binclude\s*\(?\s*['"]:app['"]""", files[settings_path]):
        raise ValueError("android_settings_app_include_missing")
    if (not {"build.gradle", "build.gradle.kts"} & files.keys()
            and "com.android.application" in module
            and "version" not in module.split("}", 1)[0]
            and "com.android.application" not in files[settings_path]):
        files["build.gradle"] = "plugins { id 'com.android.application' version '8.7.3' apply false }\n"
    if "pluginManagement" not in files[settings_path]:
        files[settings_path] = (
            "pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }\n"
            + files[settings_path]
        )
    if ("dependencyResolutionManagement" not in files[settings_path]
            and not any("repositories" in files.get(path, "")
                        for path in (module_path, "build.gradle", "build.gradle.kts"))):
        files[settings_path] += (
            "\ndependencyResolutionManagement { repositories { google(); mavenCentral() } }\n"
        )
    if not re.search(r"(?m)^\s*namespace\b", module):
        try:
            package = ElementTree.fromstring(files["app/src/main/AndroidManifest.xml"]).get("package", "")
        except ElementTree.ParseError:
            raise ValueError("invalid_android_manifest") from None
        if re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+", package, re.ASCII):
            files[module_path] = re.sub(r"\bandroid\s*\{",
                                        lambda match: match[0] + f'\n    namespace = "{package}"\n',
                                        module, count=1)
    return validate_generated_gradle(validate_android_source(
        {"files": [{"path": path, "content": content} for path, content in files.items()]}))


def validate_android_source(files):
    bundle = validate_bundle(files)
    paths = {item["path"] for item in bundle["files"]}
    if any(path.split("/")[0] in ("gradlew", "gradlew.bat") for path in paths):
        raise ValueError("generated_gradle_wrapper_forbidden")
    if not ({"settings.gradle", "settings.gradle.kts"} & paths):
        raise ValueError("android_settings_gradle_missing")
    if not ({"app/build.gradle", "app/build.gradle.kts"} & paths):
        raise ValueError("android_app_gradle_missing")
    if "app/src/main/AndroidManifest.xml" not in paths:
        raise ValueError("android_manifest_missing")
    if not any(path.startswith("app/src/main/") and
               path.endswith((".kt", ".java")) for path in paths):
        raise ValueError("android_app_source_missing")
    return bundle


def prepare(objective, source_root, task_id, generator=generate_bundle):
    import uuid
    try:
        normalized = str(uuid.UUID(str(task_id)))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("invalid_task_id") from None
    root = Path(source_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("source_root_not_directory")
    bundle = generate_android_source(objective, generator)
    dest = root / ("uapc-" + normalized)
    result = materialize_bundle(bundle, dest)
    return {"task_id": normalized, "source_dir": dest.name,
            "source_sha256": result["sha256"], "file_count": result["file_count"],
            "approved": False, "next_step": "review_source_then_approve"}

def main():
    parser = argparse.ArgumentParser(description="UAPC generic source staging (no build or auto-approval)")
    parser.add_argument("--objective", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--bundle-file", help="Local JSON source bundle; no paid AI API required")
    args = parser.parse_args()
    if args.bundle_file:
        bundle_path = Path(args.bundle_file).resolve(strict=True)
        if not bundle_path.is_file() or bundle_path.stat().st_size > 300000:
            raise ValueError("source_bundle_file_invalid_or_oversized")
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        generator = lambda _objective: bundle
    else:
        generator = generate_bundle
    result = prepare(args.objective, args.source_root, args.task_id, generator=generator)
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()
