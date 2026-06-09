#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from env_utils import gemini_api_key


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "gemini-2.5-flash"
API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiQuotaError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _api_key() -> str:
    return gemini_api_key()


def _generate_text(
    prompt: str,
    *,
    model: str,
    max_output_tokens: int,
    temperature: float,
    timeout: int,
    max_retries: int = 3,
) -> str:
    endpoint = API_ENDPOINT.format(model=urllib.parse.quote(model, safe=""))
    url = f"{endpoint}?key={urllib.parse.quote(_api_key())}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
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
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response_body = response.read().decode("utf-8")
            break
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429:
                raise GeminiQuotaError(f"Gemini API quota exhausted: {body}") from exc
            if exc.code in {500, 502, 503, 504} and attempt < max_retries:
                time.sleep(45 * (attempt + 1))
                continue
            raise RuntimeError(f"Gemini API error {exc.code}: {body}") from exc
    else:
        raise RuntimeError("Gemini API request failed after retries.")

    data = json.loads(response_body)
    chunks: list[str] = []
    for candidate in data.get("candidates", []):
        content = candidate.get("content") or {}
        for part in content.get("parts", []):
            text = part.get("text")
            if text:
                chunks.append(str(text))
    if not chunks:
        raise RuntimeError(f"Gemini response did not contain text: {json.dumps(data, ensure_ascii=False)[:1000]}")
    return "\n\n".join(chunks).strip()


def _episode_prompt(run_id: str, episode: dict[str, Any]) -> str:
    transcript = episode.get("transcript") or {}
    transcript_text = transcript.get("plain_text") or "TRANSCRIPT MISSING"
    manifest = {
        "run_id": run_id,
        "index": episode["index"],
        "podcast_title": episode["podcast_title"],
        "episode_title": episode["episode_title"],
        "published_at": episode["published_at"],
        "rss_episode_url": episode.get("rss_episode_url"),
        "spotify_episode_url": episode.get("spotify_episode_url"),
        "description_preview": episode.get("description_preview"),
        "transcript_source": transcript.get("source"),
        "transcript_language": transcript.get("transcript_language"),
    }
    return f"""你是播客情报分析员。请只基于本 episode 的 transcript 和 manifest 生成结构化中文 brief，不要引用其他 episode，不要根据标题脑补。

输出必须使用 Markdown，并严格包含：

#### 情报 {episode['index']}：[自拟情报标题]

- 原始标题：{episode['episode_title']}
- 来源与发布者：Spotify | {episode['podcast_title']} | 核心主讲人及职位；如 transcript 中无法确认，写“未在 transcript 中明确”
- 原始链接：{episode.get('spotify_episode_url') or episode.get('rss_episode_url') or episode.get('audio_url') or 'unknown'}
- Transcript 来源：Spotify transcript
- 核心内容摘要：约 600 字，必须来自 transcript。
- 情报价值点：约 150-250 字。
- 关键金句 / 结论：2 条；如 transcript 为英文，至少 1 条必须包含英文原句或高度接近原文，下一行直接写斜体中文翻译/解释，例如 `*这句话说明……*`。如 transcript 为中文但需要英文翻译，也直接写斜体英文译文。不要写 `中文解释：`、`中文翻译：`、`中文翻译/解释：`、`英文解释：`、`英文翻译：`、`英文翻译/解释：` 等标签。如无法核验原句，必须写成 `转述结论`，不要伪装成直接引语；不要在这一部分写 timestamp、Speaker 1、发言者 1 等证据标记，时间戳只放在证据锚点。
- 证据锚点：至少 3 个 timestamp + 简短证据说明。证据必须有信息价值，能支撑具体观点、机制、数字、例子、分歧或战略判断。不要使用寒暄、感谢、广告、片头片尾、泛泛介绍、互相称赞或结束语作为证据锚点。

Manifest JSON:
```json
{json.dumps(manifest, ensure_ascii=False, indent=2)}
```

Transcript:
```text
{transcript_text}
```
"""


def _final_prompt(run_id: str, episode_briefs: list[str]) -> str:
    joined = "\n\n---\n\n".join(episode_briefs)
    episode_count = len(episode_briefs)
    return f"""请基于以下 {episode_count} 个已经按 manifest 顺序生成的 episode brief，生成最终中文播客情报研报。

要求：
- 必须先输出一个一级标题 `# ...`。标题必须建设性、观点明确，让读者一眼抓住本期研报的核心主题；标题必须包含英文翻译，格式如 `# 中文标题 (English Title)`。不要使用日期、run id、窗口信息或泛泛的“Spotify 播客情报研报”作为主标题。
- 不要新增 brief 之外的 episode。
- 第二部分必须且只能包含情报 1 到情报 {episode_count}。
- 第二部分必须逐字保留每个 brief 的 `#### 情报 N` 结构、原始标题、原始链接、Transcript 来源、关键金句和证据锚点。
- 可以润色每个 brief 的中文表达，但不得删除任何 episode，不得改变顺序。
- 情报 1 的 `关键金句 / 结论` 必须和其他 episode 同质量：如果源 transcript 为英文，至少保留 1 条英文原句或高度接近原文，并在下一行直接写斜体中文翻译/解释；不要只留下转述结论，不要写 `中文解释：`、`中文翻译：`、`中文翻译/解释：`、`英文解释：`、`英文翻译：`、`英文翻译/解释：` 等标签。
- 证据锚点必须有信息价值。删除寒暄、感谢、广告、片头片尾、泛泛介绍、互相称赞或结束语等低价值锚点。
- 第一部分写约 700 字摘要。
- 第三部分做真正的跨节目专题分析：抽出贯穿多集的结构性主题，不要按 episode 逐个总结。
- 第四部分写第二层思维：必须提出跨节目抽象判断和背后机制，不要复述单集内容。
- 第五部分写结论与战略意义：必须形成统一战略判断，不要写成泛泛建议清单。
- 输出 Markdown。

Run ID: {run_id}

Episode briefs:

{joined}
"""


def generate_chunked(
    package_dir: Path,
    *,
    model: str,
    sleep_seconds: int,
    resume: bool,
    timeout: int,
) -> Path:
    evidence_path = package_dir / "transcript-evidence-full.json"
    evidence = _read_json(evidence_path)
    run_id = evidence["run_id"]
    chunk_dir = ROOT / "data" / "gemini_chunks" / run_id
    chunk_dir.mkdir(parents=True, exist_ok=True)

    briefs: list[str] = []
    episodes = evidence["episodes"]
    for offset, episode in enumerate(episodes):
        index = int(episode["index"])
        brief_path = chunk_dir / f"{index:02d}-episode-brief.md"
        meta_path = chunk_dir / f"{index:02d}-episode-brief.json"
        if resume and brief_path.exists():
            brief = brief_path.read_text(encoding="utf-8")
            print(f"resume {index}/{len(episodes)} {brief_path}")
        else:
            print(f"generate {index}/{len(episodes)} {episode['episode_title']}")
            try:
                brief = _generate_text(
                    _episode_prompt(run_id, episode),
                    model=model,
                    max_output_tokens=8192,
                    temperature=0.2,
                    timeout=timeout,
                )
            except GeminiQuotaError as exc:
                status_path = chunk_dir / "STATUS.json"
                _write_json(
                    status_path,
                    {
                        "status": "blocked_quota",
                        "blocked_at": datetime.now().astimezone().isoformat(),
                        "model": model,
                        "next_episode_index": index,
                        "completed_episode_count": len(briefs),
                        "error": str(exc)[:2000],
                    },
                )
                print(status_path)
                raise SystemExit(f"Quota exhausted after {len(briefs)} completed episodes. Resume later.") from exc
            brief_path.write_text(brief + "\n", encoding="utf-8")
            _write_json(
                meta_path,
                {
                    "created_at": datetime.now().astimezone().isoformat(),
                    "model": model,
                    "run_id": run_id,
                    "episode_index": index,
                    "episode_title": episode["episode_title"],
                },
            )
            if offset < len(episodes) - 1 and sleep_seconds > 0:
                time.sleep(sleep_seconds)
        briefs.append(brief)

    final_path = ROOT / "reports" / "markdown" / f"{run_id}-gemini-report.md"
    final_path.parent.mkdir(parents=True, exist_ok=True)
    print("generate final report")
    try:
        final_report = _generate_text(
            _final_prompt(run_id, briefs),
            model=model,
            max_output_tokens=65536,
            temperature=0.2,
            timeout=timeout,
        )
    except GeminiQuotaError as exc:
        status_path = chunk_dir / "STATUS.json"
        _write_json(
            status_path,
            {
                "status": "blocked_quota_final_report",
                "blocked_at": datetime.now().astimezone().isoformat(),
                "model": model,
                "completed_episode_count": len(briefs),
                "error": str(exc)[:2000],
            },
        )
        print(status_path)
        raise SystemExit("Quota exhausted before final report. Resume later.") from exc
    header = [
        f"<!-- generated_at: {datetime.now().astimezone().isoformat()} -->",
        f"<!-- gemini_model: {model} -->",
        f"<!-- source_package: {package_dir.resolve()} -->",
        f"<!-- chunk_dir: {chunk_dir} -->",
        "",
    ]
    final_path.write_text("\n".join(header) + final_report + "\n", encoding="utf-8")
    print(final_path)
    return final_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Gemini report in per-episode chunks.")
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--sleep-seconds", type=int, default=65)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    generate_chunked(
        args.package_dir,
        model=args.model,
        sleep_seconds=args.sleep_seconds,
        resume=not args.no_resume,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
