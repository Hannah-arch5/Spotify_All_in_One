---
name: spotify-mwf-report
description: Run or continue Hannah's Monday/Wednesday/Friday Spotify podcast intelligence report workflow. Use when the user asks to make today's, Monday, Wednesday, Friday, or MWF Spotify podcast report; continue Spotify report automation; collect STD transcripts; deliver the report to Zotero, Google Drive, and Discord; debug LaunchAgent/report delivery; or ensure transcript cleanup and mark-seen completion.
metadata:
  short-description: Run Spotify MWF podcast report workflow
---

# Spotify MWF Report

Use this skill for Hannah's recurring Spotify podcast intelligence report workflow.

## Start Here

1. Work in `/Users/hannah/Documents/Spotify All in One`.
2. Read `PROJECT_MEMORY.md` first. Trust the newest dated section over older blocker notes.
3. Check current state before doing heavy work:
   - `git status --short`
   - `git branch --show-current`
   - LaunchAgent state for `com.hannah.spotify-podcast-report`
   - latest `data/service_logs/*.json`
   - `/Users/hannah/Downloads/Spotify Transcript Collector/` JSON count
4. Follow the full workflow in `references/workflow.md`.

## Hard Rules

- Do not silently use lower-fidelity transcript/report fallbacks.
- For STD transcripts, open each Spotify episode detail page and click Spotify's native `Transcript` tab. Search/list pages are not enough.
- The report main title is a delivery gate. It must be constructive, insight-led, and immediately communicate the report's central thesis. It must include an English translation. Do not use generic titles, run IDs, date piles, or vague labels such as only "Spotify 播客情报研报".
- Every episode, including episode 1, must have `关键金句 / 结论` with at least one source-language original sentence and a translation/explanation when useful. Translation/explanation lines must be italicized and must not use prefix labels such as `中文解释：`, `中文翻译：`, `中文翻译/解释：`, `英文解释：`, `英文翻译：`, or `英文翻译/解释：`. If an exact quote cannot be verified, label it clearly as `转述结论` instead of presenting it as a quote.
- Evidence anchors must be substantively useful. Do not include greetings, thanks, ad reads, housekeeping, ending pleasantries, repeated intros/outros, or generic "they discussed X" anchors unless the anchor contains a specific claim, example, mechanism, number, decision, or strategic implication.
- After report review passes and delivery succeeds, always run transcript cleanup with `scripts/import_spotify_transcripts.py --move` and verify Downloads has zero leftover JSON files.
- Mark episodes seen only after the required delivery gates pass, unless the user explicitly skips a blocked channel.
- Discord delivery must use the live Discord Studio directory: `/Users/hannah/.discord-studio/Discord_Studio`.
- When sending transcript/evidence to Gemini or files to Google Drive/Discord, respect Codex approval prompts. If approval is blocked, report it directly and do not work around it.

## Common User Triggers

- “做今天 Spotify 播客研报”
- “继续周三 Spotify 研报流程”
- “跑 MWF Spotify report skill”
- “检查 STD transcript 并交付研报”
- “调试 LaunchAgent / Drive / Discord / Zotero”
