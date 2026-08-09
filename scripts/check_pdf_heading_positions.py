#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PDFTOTEXT = ROOT.parent / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "native" / "poppler" / "poppler" / "bin" / "pdftotext"
if not PDFTOTEXT.exists():
    PDFTOTEXT = Path("/Users/hannah/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/poppler/bin/pdftotext")


def _plain(value: str) -> str:
    return re.sub(r"\s+", "", html.unescape(value or ""))


def main() -> None:
    parser = argparse.ArgumentParser(description="Check PDF heading vertical positions.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("targets", nargs="+")
    args = parser.parse_args()

    with tempfile.NamedTemporaryFile(suffix=".html") as handle:
        subprocess.run(
            [str(PDFTOTEXT), "-bbox-layout", str(args.pdf), handle.name],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        root = ET.parse(handle.name).getroot()

    ns = {"x": "http://www.w3.org/1999/xhtml"}
    found: dict[str, tuple[int, float, float]] = {}
    for page_index, page in enumerate(root.findall(".//x:page", ns), start=1):
        page_height = float(page.attrib.get("height", "1") or 1)
        words = page.findall(".//x:word", ns)
        joined = "".join(_plain(word.text or "") for word in words)
        for target in args.targets:
            if target in found:
                continue
            target_plain = _plain(target)
            offset = joined.find(target_plain)
            if offset < 0:
                continue
            running = 0
            for word in words:
                text = _plain(word.text or "")
                next_running = running + len(text)
                if running <= offset < next_running:
                    y_min = float(word.attrib.get("yMin", "0") or 0)
                    found[target] = (page_index, y_min, y_min / page_height)
                    break
                running = next_running

    for target in args.targets:
        if target not in found:
            print(f"{target}: missing")
            continue
        page, y_min, zone = found[target]
        print(f"{target}: page={page} y={y_min:.1f} zone={zone:.3f}")


if __name__ == "__main__":
    main()
