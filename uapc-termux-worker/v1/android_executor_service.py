"""Poll for Android source and build jobs independently."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
import time

import android_executor


def poll(component, run, interval):
    while True:
        try:
            outcome = run()
        except Exception as exc:
            outcome = {"status": "blocked", "detail": type(exc).__name__}
        print(json.dumps({"component": component, **outcome}, sort_keys=True), flush=True)
        time.sleep(interval)


def main():
    interval = max(15, min(300, int(os.getenv("UAPC_POLL_SECONDS", "30"))))
    workers = {}
    if os.getenv("UAPC_SOURCE_WORKER_ENABLED") == "1":
        import android_source_worker

        workers["source"] = android_source_worker.run
    if os.getenv("UAPC_ANDROID_EXECUTOR_ENABLED") == "1":
        workers["build"] = android_executor.run
    if not workers:
        print(json.dumps({"status": "disabled", "detail": "no_workers_enabled"}), flush=True)
        return 2
    # Poll in separate threads so Gradle and model inference can progress independently.
    with ThreadPoolExecutor(max_workers=len(workers)) as pool:
        futures = [pool.submit(poll, component, run, interval) for component, run in workers.items()]
        for future in futures:
            future.result()


if __name__ == "__main__":
    raise SystemExit(main())
