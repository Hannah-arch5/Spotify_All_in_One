#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

WINDOWS = [
    {
        "name": "wednesday-20260527-1500-cst",
        "since": "2026-05-25T07:00:00+00:00",
        "until": "2026-05-27T07:00:00+00:00",
        "description": "episodes published before Wednesday 2026-05-27 15:00 Asia/Shanghai",
    },
    {
        "name": "friday-20260529-1500-cst",
        "since": "2026-05-27T07:00:00+00:00",
        "until": "2026-05-29T07:00:00+00:00",
        "description": "episodes published before Friday 2026-05-29 15:00 Asia/Shanghai",
    },
]


def _run(args: list[str]) -> str:
    completed = subprocess.run(
        [PYTHON, *args],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        raise RuntimeError(
            f"{' '.join(args)} failed with exit code {completed.returncode}\n"
            f"stdout:\n{completed.stdout.strip()}\n\nstderr:\n{completed.stderr.strip()}"
        )
    if completed.stderr.strip():
        print(completed.stderr.strip(), file=sys.stderr)
    return completed.stdout.strip()


def _last_line(output: str) -> str:
    lines = output.splitlines()
    return lines[-1] if lines else ""


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def backfill_window(window: dict[str, str], args: argparse.Namespace) -> dict[str, object]:
    result: dict[str, object] = {
        "window": window["name"],
        "description": window["description"],
        "since": window["since"],
        "until": window["until"],
    }
    manifest_path = Path(
        _last_line(
            _run(
                [
                    "scripts/check_new_episodes.py",
                    "--since",
                    window["since"],
                    "--until",
                    window["until"],
                ]
            )
        )
    )
    result["manifest"] = str(manifest_path)
    manifest = _read_json(manifest_path)
    result["new_episode_count"] = manifest["summary"]["new_episode_count"]
    result["feed_failures"] = manifest["summary"]["feed_failures"]
    result["episode_list"] = _last_line(_run(["scripts/render_episode_list.py", str(manifest_path)]))

    if manifest["summary"]["feed_failures"]:
        result["status"] = "blocked_feed_failures"
        return result
    if manifest["summary"]["new_episode_count"] == 0:
        result["status"] = "no_new_episodes"
        return result
    if args.check_only:
        result["status"] = "check_only_ready_for_pipeline"
        return result

    pipeline_args = [
        "scripts/run_report_pipeline.py",
        "--manifest",
        str(manifest_path),
        "--gemini-mode",
        args.gemini_mode,
        "--model",
        args.model,
        "--sleep-seconds",
        str(args.sleep_seconds),
        "--cleanup-transcripts-on-pass",
    ]
    if args.dry_run:
        pipeline_args.append("--dry-run")
    pipeline_output = _run(pipeline_args)
    result["pipeline"] = json.loads(pipeline_output)
    result["status"] = result["pipeline"].get("status", "pipeline_finished")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill the missed Spotify report windows for 2026-05-27 and 2026-05-29.")
    parser.add_argument("--window", choices=["all", "wednesday", "friday"], default="all")
    parser.add_argument("--check-only", action="store_true", help="Only create manifests and readable episode lists.")
    parser.add_argument("--dry-run", action="store_true", help="Build packages without calling Gemini.")
    parser.add_argument("--model", default="gemini-2.5-flash")
    parser.add_argument("--gemini-mode", choices=["chunked", "single"], default="chunked")
    parser.add_argument("--sleep-seconds", type=int, default=70)
    args = parser.parse_args()

    selected = WINDOWS
    if args.window == "wednesday":
        selected = [WINDOWS[0]]
    elif args.window == "friday":
        selected = [WINDOWS[1]]

    results = [backfill_window(window, args) for window in selected]
    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
