#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _run(args: list[str]) -> str:
    completed = subprocess.run(
        [PYTHON, *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
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

    manifest_path = Path(
        _last_line(
            _run(
                [
                    "scripts/check_new_episodes.py",
                    "--since-days",
                    str(args.since_days),
                ]
            )
        )
    )
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

    package_dir = Path(_last_line(_run(["scripts/build_gemini_input_package.py", str(evidence_pack)])))
    outputs["gemini_package"] = str(package_dir)

    generate_args = [
        "scripts/generate_gemini_report.py",
        "--package-dir",
        str(package_dir),
        "--model",
        args.model,
    ]
    if args.dry_run:
        generate_args.append("--dry-run")
    report_path = Path(_last_line(_run(generate_args)))
    outputs["gemini_report"] = str(report_path)

    if not args.dry_run:
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
        if args.mark_seen_on_pass and review_stdout == "通过":
            outputs["marked_seen_manifest"] = _last_line(
                _run(
                    [
                        "scripts/check_new_episodes.py",
                        "--since-days",
                        str(args.since_days),
                        "--mark-seen",
                    ]
                )
            )

    outputs["status"] = "done"
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the podcast report pipeline end to end.")
    parser.add_argument("--since-days", type=int, default=3)
    parser.add_argument("--model", default="gemini-2.5-pro")
    parser.add_argument("--move-imported-transcripts", action="store_true")
    parser.add_argument("--mark-seen-on-pass", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Build inputs and prompt preview without calling Gemini.")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
