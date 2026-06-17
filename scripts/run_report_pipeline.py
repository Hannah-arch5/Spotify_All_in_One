#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


class PipelineStepError(RuntimeError):
    def __init__(self, args: list[str], returncode: int, stdout: str, stderr: str):
        self.args_list = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(f"{' '.join(args)} failed with exit code {returncode}")


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
        raise PipelineStepError(args, completed.returncode, completed.stdout.strip(), completed.stderr.strip())
    if completed.stderr.strip():
        print(completed.stderr.strip())
    return completed.stdout.strip()


def _last_line(output: str) -> str:
    lines = output.splitlines()
    return lines[-1] if lines else ""


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run(args: argparse.Namespace) -> dict[str, str | int]:
    outputs: dict[str, str | int] = {}

    if args.manifest:
        manifest_path = args.manifest
    else:
        check_args = ["scripts/check_new_episodes.py"]
        if args.schedule_window:
            check_args.extend(["--schedule-window", args.schedule_window])
        else:
            check_args.extend(["--since-days", str(args.since_days)])
        manifest_path = Path(_last_line(_run(check_args)))
    outputs["manifest"] = str(manifest_path)
    manifest = _read_json(manifest_path)
    new_episode_count = manifest["summary"]["new_episode_count"]
    outputs["new_episode_count"] = new_episode_count
    if new_episode_count == 0:
        print(json.dumps(outputs, ensure_ascii=False, indent=2))
        return outputs

    outputs["episode_list"] = _last_line(_run(["scripts/render_episode_list.py", str(manifest_path)]))
    outputs["transcript_audit"] = _last_line(_run(["scripts/audit_transcripts.py", str(manifest_path)]))

    import_args = ["scripts/import_spotify_transcripts.py"]
    if args.move_imported_transcripts:
        import_args.append("--move")
    outputs["transcript_import"] = _last_line(_run(import_args))

    evidence_lines = _run(["scripts/build_evidence_pack.py", str(manifest_path)]).splitlines()
    evidence_pack = Path(evidence_lines[0])
    outputs["evidence_pack"] = str(evidence_pack)
    evidence = _read_json(evidence_pack)
    missing_count = evidence["summary"]["missing_count"]
    outputs["missing_transcripts"] = missing_count

    outputs["spotify_collection_queue"] = _last_line(_run(["scripts/build_spotify_collection_queue.py", str(evidence_pack)]))
    if missing_count:
        outputs["status"] = "blocked_missing_transcripts"
        print(json.dumps(outputs, ensure_ascii=False, indent=2))
        return outputs

    language_audit_args = ["scripts/audit_transcript_languages.py", str(evidence_pack)]
    if args.require_zh_transcripts:
        language_audit_args.append("--require-zh")
    try:
        language_audit_lines = _run(language_audit_args).splitlines()
    except PipelineStepError as exc:
        outputs["transcript_language_audit"] = str(ROOT / "data" / "runs" / f"{manifest['run_id']}-transcript-language-audit.json")
        outputs["status"] = "blocked_missing_zh_transcripts"
        outputs["transcript_language_error"] = (exc.stderr or exc.stdout or str(exc))[:1200]
        print(json.dumps(outputs, ensure_ascii=False, indent=2))
        return outputs
    if language_audit_lines:
        outputs["transcript_language_audit"] = language_audit_lines[0]

    package_dir = Path(_last_line(_run(["scripts/build_gemini_input_package.py", str(evidence_pack)])))
    outputs["gemini_package"] = str(package_dir)

    if args.dry_run:
        outputs["status"] = "dry_run_ready_for_gemini"
        print(json.dumps(outputs, ensure_ascii=False, indent=2))
        return outputs

    if args.gemini_mode == "single":
        generate_args = [
            "scripts/generate_gemini_report.py",
            "--package-dir",
            str(package_dir),
            "--model",
            args.model,
        ]
    else:
        generate_args = [
            "scripts/generate_chunked_gemini_report.py",
            "--package-dir",
            str(package_dir),
            "--model",
            args.model,
            "--sleep-seconds",
            str(args.sleep_seconds),
            "--timeout",
            str(args.timeout),
        ]
    try:
        report_path = Path(_last_line(_run(generate_args)))
    except PipelineStepError as exc:
        outputs["status"] = "blocked_gemini_generation"
        outputs["gemini_error"] = (exc.stderr or exc.stdout or str(exc))[:1200]
        status_path = ROOT / "data" / "gemini_chunks" / package_dir.name / "STATUS.json"
        if status_path.exists():
            outputs["gemini_status"] = str(status_path)
        print(json.dumps(outputs, ensure_ascii=False, indent=2))
        return outputs
    outputs["gemini_report"] = str(report_path)
    outputs["key_quote_cleanup"] = _last_line(_run(["scripts/clean_key_quote_blocks.py", str(report_path)]))

    review_stdout = _last_line(
        _run(
            [
                "scripts/check_gemini_report.py",
                str(report_path),
                "--manifest",
                str(package_dir / "episode-manifest.json"),
                "--evidence",
                str(package_dir / "transcript-evidence-full.json"),
            ]
        )
    )
    outputs["review_conclusion"] = review_stdout
    if review_stdout == "通过":
        if args.cleanup_transcripts_on_pass:
            outputs["transcript_cleanup"] = _last_line(_run(["scripts/import_spotify_transcripts.py", "--move"]))
        if args.mark_seen_on_pass and args.manifest:
            outputs["mark_seen_skipped"] = "mark_seen_on_pass is only supported for live --since-days runs; fixed-window manifests should be marked deliberately after review."
        elif args.mark_seen_on_pass:
            mark_seen_args = ["scripts/check_new_episodes.py"]
            if args.schedule_window:
                mark_seen_args.extend(["--schedule-window", args.schedule_window])
            else:
                mark_seen_args.extend(["--since-days", str(args.since_days)])
            mark_seen_args.append("--mark-seen")
            outputs["marked_seen_manifest"] = _last_line(_run(mark_seen_args))

    outputs["status"] = "done"
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the podcast report pipeline end to end.")
    parser.add_argument("--manifest", type=Path, help="Use an existing episode manifest instead of checking RSS.")
    parser.add_argument("--since-days", type=int, default=3)
    parser.add_argument(
        "--schedule-window",
        choices=["current"],
        help="Use the latest fixed Monday/Wednesday/Friday 15:00 Asia/Shanghai report window instead of --since-days.",
    )
    parser.add_argument("--model", default="gemini-2.5-flash")
    parser.add_argument("--gemini-mode", choices=["chunked", "single"], default="chunked")
    parser.add_argument("--sleep-seconds", type=int, default=70)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--move-imported-transcripts", action="store_true")
    parser.add_argument(
        "--require-zh-transcripts",
        action="store_true",
        help="Block before Gemini if any episode lacks a matched Chinese transcript.",
    )
    parser.add_argument(
        "--cleanup-transcripts-on-pass",
        action="store_true",
        help="After a passing report review, remove Downloads transcript JSON files already archived in the project.",
    )
    parser.add_argument("--mark-seen-on-pass", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Build inputs and prompt preview without calling Gemini.")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
