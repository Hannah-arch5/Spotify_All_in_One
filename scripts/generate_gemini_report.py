#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from env_utils import gemini_api_key


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "gemini-2.5-pro"
API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _latest_package_dir() -> Path:
    packages = sorted((ROOT / "data" / "gemini_inputs").glob("*"))
    packages = [path for path in packages if path.is_dir()]
    if not packages:
        raise SystemExit("No Gemini input package found. Run scripts/build_gemini_input_package.py first.")
    return packages[-1]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _build_prompt(package_dir: Path) -> str:
    prompt_path = package_dir / "gemini-prompt.md"
    manifest_path = package_dir / "episode-manifest.json"
    evidence_path = package_dir / "transcript-evidence-full.json"

    missing = [path for path in [prompt_path, manifest_path, evidence_path] if not path.exists()]
    if missing:
        missing_list = ", ".join(str(path) for path in missing)
        raise SystemExit(f"Gemini package is missing required files: {missing_list}")

    return "\n\n".join(
        [
            "# Instruction",
            _read_text(prompt_path),
            "# Episode Manifest JSON",
            _read_text(manifest_path),
            "# Transcript Evidence Pack JSON",
            _read_text(evidence_path),
        ]
    )


def _extract_text(response: dict[str, Any]) -> str:
    chunks: list[str] = []
    for candidate in response.get("candidates", []):
        content = candidate.get("content") or {}
        for part in content.get("parts", []):
            text = part.get("text")
            if text:
                chunks.append(str(text))
    if not chunks:
        raise RuntimeError(f"Gemini response did not contain text: {json.dumps(response, ensure_ascii=False)[:1000]}")
    return "\n\n".join(chunks).strip()


def generate(
    package_dir: Path,
    output_path: Path | None = None,
    model: str = DEFAULT_MODEL,
    max_output_tokens: int = 65536,
    temperature: float = 0.2,
    timeout: int = 600,
    dry_run: bool = False,
) -> Path:
    package_dir = package_dir.resolve()
    prompt = _build_prompt(package_dir)
    run_id = package_dir.name
    output_path = output_path or ROOT / "reports" / "markdown" / f"{run_id}-gemini-report.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if dry_run:
        preview_path = output_path.with_suffix(".prompt-preview.txt")
        preview_path.write_text(prompt[:20000], encoding="utf-8")
        print(preview_path)
        return preview_path

    api_key = gemini_api_key()

    endpoint = API_ENDPOINT.format(model=urllib.parse.quote(model, safe=""))
    url = f"{endpoint}?key={urllib.parse.quote(api_key)}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Gemini API error {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Gemini API request failed: {exc}") from exc

    data = json.loads(response_body)
    report = _extract_text(data)
    header = [
        f"<!-- generated_at: {datetime.now().astimezone().isoformat()} -->",
        f"<!-- gemini_model: {model} -->",
        f"<!-- source_package: {package_dir} -->",
        "",
    ]
    output_path.write_text("\n".join(header) + report + "\n", encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a podcast intelligence report with Gemini API.")
    parser.add_argument("--package-dir", type=Path, help="Gemini input package directory. Defaults to the latest package.")
    parser.add_argument("--output", type=Path, help="Markdown report output path.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model. Defaults to {DEFAULT_MODEL}.")
    parser.add_argument("--max-output-tokens", type=int, default=65536)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--dry-run", action="store_true", help="Write a prompt preview without calling Gemini.")
    args = parser.parse_args()

    print(
        generate(
            args.package_dir or _latest_package_dir(),
            output_path=args.output,
            model=args.model,
            max_output_tokens=args.max_output_tokens,
            temperature=args.temperature,
            timeout=args.timeout,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
