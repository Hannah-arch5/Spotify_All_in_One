#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
LOCK_PATH = ROOT / "data" / "service_logs" / "scheduled-report.lock"
PROGRESS_LOG = ROOT / "data" / "service_logs" / "scheduled-report.progress.log"

sys.path.insert(0, str(ROOT))
from scripts.env_utils import load_project_env


class ServiceError(RuntimeError):
    pass


def progress(message: str) -> None:
    PROGRESS_LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().astimezone().isoformat()} {message}\n"
    with PROGRESS_LOG.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_command(args: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None, timeout: int | None = None) -> str:
    progress(f"START command={shlex.join(args)} cwd={cwd} timeout={timeout}")
    completed = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    if completed.returncode:
        progress(f"FAIL command={shlex.join(args)} returncode={completed.returncode}")
        raise ServiceError(
            json.dumps(
                {
                    "command": args,
                    "returncode": completed.returncode,
                    "stdout": completed.stdout.strip()[-2000:],
                    "stderr": completed.stderr.strip()[-2000:],
                },
                ensure_ascii=False,
            )
        )
    progress(f"DONE command={shlex.join(args)} stdout_bytes={len(completed.stdout)} stderr_bytes={len(completed.stderr)}")
    return completed.stdout.strip()


def parse_last_json(stdout: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(stdout):
        if char != "{":
            continue
        try:
            value, end = decoder.raw_decode(stdout[index:])
        except json.JSONDecodeError:
            continue
        if stdout[index + end :].strip():
            continue
        if isinstance(value, dict):
            return value
    raise ServiceError(f"Could not parse JSON output: {stdout[-1200:]}")


def parse_key_paths(stdout: str) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in {"docx", "pdf"}:
            paths[key] = Path(value.strip())
    return paths


def template_args(template: str, values: dict[str, str]) -> list[str]:
    rendered = template.format(**values)
    return shlex.split(rendered)


def optional_template_command(
    env_name: str,
    values: dict[str, str],
    *,
    cwd_env_name: str | None = None,
    timeout: int | None = None,
) -> str:
    template = os.environ.get(env_name)
    if not template:
        raise ServiceError(f"Missing required environment variable {env_name}.")
    cwd = Path(os.environ.get(cwd_env_name, str(ROOT))).expanduser() if cwd_env_name else ROOT
    return run_command(template_args(template, values), cwd=cwd, timeout=timeout)


def maybe_quit_zotero() -> None:
    if os.environ.get("SPOTIFY_ZOTERO_QUIT_BEFORE_WRITE", "0") not in {"1", "true", "TRUE", "yes"}:
        return
    run_command(["osascript", "-e", 'tell application "Zotero" to quit'])


def archive_to_zotero(report_path: Path, pdf_path: Path) -> dict[str, Any]:
    maybe_quit_zotero()
    month_tag = f"/{pdf_path.stem[:4]}"
    stdout = run_command(
        [
            PYTHON,
            "scripts/archive_reports_to_zotero.py",
            str(report_path),
            "--direct-pdf",
            "--replace-existing",
            "--backup",
            "--tag",
            "/unread",
            "--tag",
            month_tag,
        ]
    )
    verify_stdout = run_command([PYTHON, "scripts/verify_zotero_report_pdfs.py", str(pdf_path)])
    verification = json.loads(verify_stdout)
    results = verification.get("results") or []
    if not results or not all(item.get("all_zotero_matches_local") for item in results):
        raise ServiceError(f"Zotero hash verification failed: {verify_stdout}")
    return {"archive_stdout": stdout, "verification": verification}


def stage_external_files(docx_path: Path, pdf_path: Path) -> dict[str, Any]:
    month = pdf_path.stem[:4]
    drive_dir = ROOT / "reports" / "archive" / "pending" / month / "google-drive"
    discord_dir = ROOT / "reports" / "archive" / "pending" / month / "discord-todo"
    drive_dir.mkdir(parents=True, exist_ok=True)
    discord_dir.mkdir(parents=True, exist_ok=True)
    staged_docx = drive_dir / docx_path.name
    staged_pdf = discord_dir / pdf_path.name
    shutil.copy2(docx_path, staged_docx)
    shutil.copy2(pdf_path, staged_pdf)
    if sha256(staged_docx) != sha256(docx_path):
        raise ServiceError(f"Staged DOCX hash mismatch: {staged_docx}")
    if sha256(staged_pdf) != sha256(pdf_path):
        raise ServiceError(f"Staged PDF hash mismatch: {staged_pdf}")
    return {
        "drive_docx": str(staged_docx),
        "drive_docx_sha256": sha256(staged_docx),
        "discord_pdf": str(staged_pdf),
        "discord_pdf_sha256": sha256(staged_pdf),
    }


def upload_to_drive(docx_path: Path) -> str:
    values = {
        "docx": str(docx_path),
        "title": docx_path.stem,
        "filename": docx_path.name,
    }
    stdout = optional_template_command("SPOTIFY_GOOGLE_DRIVE_UPLOAD_CMD", values, timeout=1800)
    verify_template = os.environ.get("SPOTIFY_GOOGLE_DRIVE_VERIFY_CMD")
    if verify_template:
        verify_stdout = run_command(template_args(verify_template, values), timeout=600)
        if docx_path.name not in verify_stdout:
            raise ServiceError(f"Google Drive verification did not include {docx_path.name}: {verify_stdout[-1200:]}")
        return "\n".join(item for item in [stdout, verify_stdout] if item)
    return stdout


def send_to_discord(pdf_path: Path) -> str:
    channel_id = os.environ.get("SPOTIFY_DISCORD_CHANNEL_ID", "1508163671988109393")
    message = os.environ.get("SPOTIFY_DISCORD_MESSAGE", f"Spotify 播客情报研报：{pdf_path.stem}")
    values = {
        "pdf": str(pdf_path),
        "channel_id": channel_id,
        "message": message,
        "filename": pdf_path.name,
        "title": pdf_path.stem,
    }
    return optional_template_command(
        "SPOTIFY_DISCORD_SEND_CMD",
        values,
        cwd_env_name="SPOTIFY_DISCORD_CWD",
        timeout=1800,
    )


def run_service(args: argparse.Namespace) -> dict[str, Any]:
    load_project_env()
    progress("SERVICE start")
    log: dict[str, Any] = {
        "started_at": datetime.now().astimezone().isoformat(),
        "status": "running",
    }

    pipeline_args = [
        PYTHON,
        "scripts/run_report_pipeline.py",
        "--schedule-window",
        "current",
        "--gemini-mode",
        args.gemini_mode,
        "--model",
        args.model,
        "--sleep-seconds",
        str(args.sleep_seconds),
        "--timeout",
        str(args.timeout),
        "--cleanup-transcripts-on-pass",
    ]
    if args.require_zh_transcripts:
        pipeline_args.append("--require-zh-transcripts")
    progress("PIPELINE start")
    pipeline = parse_last_json(run_command(pipeline_args, timeout=args.pipeline_timeout))
    progress(f"PIPELINE status={pipeline.get('status')}")
    log["pipeline"] = pipeline
    status = pipeline.get("status")
    if status != "done":
        log["status"] = status or "blocked_pipeline"
        progress(f"SERVICE blocked status={log['status']}")
        return log
    if int(pipeline.get("new_episode_count") or 0) == 0:
        log["status"] = "done_no_new_episodes"
        progress("SERVICE done_no_new_episodes")
        return log

    report_path = Path(str(pipeline["gemini_report"]))
    progress(f"RENDER start report={report_path}")
    render_stdout = run_command([PYTHON, "scripts/render_delivery_reports.py", str(report_path)], timeout=1200)
    rendered = parse_key_paths(render_stdout)
    docx_path = rendered["docx"]
    pdf_path = rendered["pdf"]
    log["render"] = {
        "docx": str(docx_path),
        "pdf": str(pdf_path),
        "docx_sha256": sha256(docx_path),
        "pdf_sha256": sha256(pdf_path),
    }
    progress(f"RENDER done docx={docx_path} pdf={pdf_path}")

    progress("DELIVERY_AUDIT start")
    audit_stdout = run_command(
        [PYTHON, "scripts/audit_delivery_report_format.py", "--docx", str(docx_path), "--pdf", str(pdf_path)]
    )
    log["delivery_audit"] = json.loads(audit_stdout)
    progress("DELIVERY_AUDIT done")

    if not args.skip_zotero:
        progress("ZOTERO start")
        log["zotero"] = archive_to_zotero(report_path, pdf_path)
        progress("ZOTERO done")
    progress("STAGING start")
    log["staging"] = stage_external_files(docx_path, pdf_path)
    progress("STAGING done")

    if not args.skip_drive:
        progress("DRIVE start")
        log["google_drive"] = upload_to_drive(Path(log["staging"]["drive_docx"]))
        progress("DRIVE done")
    if not args.skip_discord:
        progress("DISCORD start")
        log["discord"] = send_to_discord(Path(log["staging"]["discord_pdf"]))
        progress("DISCORD done")

    manifest_path = Path(str(pipeline["manifest"]))
    if not args.skip_mark_seen:
        progress("MARK_SEEN start")
        log["mark_seen"] = run_command([PYTHON, "scripts/mark_manifest_seen.py", str(manifest_path)])
        progress("MARK_SEEN done")
    log["status"] = "done"
    progress("SERVICE done")
    return log


def main() -> None:
    load_project_env()
    parser = argparse.ArgumentParser(description="Production runner for the scheduled Spotify podcast report.")
    parser.add_argument("--model", default=os.environ.get("SPOTIFY_GEMINI_MODEL", "gemini-2.5-flash"))
    parser.add_argument("--gemini-mode", choices=["chunked", "single"], default="chunked")
    parser.add_argument("--sleep-seconds", type=int, default=int(os.environ.get("SPOTIFY_GEMINI_SLEEP_SECONDS", "70")))
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("SPOTIFY_GEMINI_TIMEOUT", "600")))
    parser.add_argument("--pipeline-timeout", type=int, default=int(os.environ.get("SPOTIFY_PIPELINE_TIMEOUT", "21600")))
    parser.add_argument(
        "--require-zh-transcripts",
        action="store_true",
        default=os.environ.get("SPOTIFY_REQUIRE_ZH_TRANSCRIPTS", "0") in {"1", "true", "TRUE", "yes"},
    )
    parser.add_argument("--skip-zotero", action="store_true")
    parser.add_argument("--skip-drive", action="store_true")
    parser.add_argument("--skip-discord", action="store_true")
    parser.add_argument("--skip-mark-seen", action="store_true")
    args = parser.parse_args()

    (ROOT / "data" / "service_logs").mkdir(parents=True, exist_ok=True)
    log: dict[str, Any]
    exit_code = 0
    with LOCK_PATH.open("w") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Another scheduled report service run is already active.")
        try:
            log = run_service(args)
        except Exception as exc:
            progress(f"SERVICE failed error={exc}")
            log = {
                "started_at": datetime.now().astimezone().isoformat(),
                "status": "failed",
                "error": str(exc),
            }
            exit_code = 1

    log["finished_at"] = datetime.now().astimezone().isoformat()
    log_path = ROOT / "data" / "service_logs" / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-scheduled-report.json"
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": log["status"], "log": str(log_path)}, ensure_ascii=False, indent=2))
    if log["status"] not in {"done", "done_no_new_episodes"}:
        raise SystemExit(exit_code or 1)


if __name__ == "__main__":
    main()
