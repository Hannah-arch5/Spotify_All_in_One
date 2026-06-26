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
- For STD transcripts, open each Spotify episode detail page and click Spotify's native `Transcript` tab. Search/list pages are not enough. Never declare a transcript missing after only the initial partial page render; reload the verified episode detail URL and wait about `6.5` seconds for Spotify's Description/Transcript/Chapters tab list before deciding.
- The report main title is a delivery gate. It must be constructive, insight-led, and immediately communicate the report's central thesis. It must include an English translation. Do not use generic titles, run IDs, date piles, or vague labels such as only "Spotify 播客情报研报".
- Every episode, including episode 1, must have `关键金句 / 结论` with meaningful source-language original sentences and translation/explanation lines when useful. Translation/explanation lines must be italicized and must not use prefix labels such as `中文解释：`, `中文翻译：`, `中文翻译/解释：`, `英文解释：`, `英文翻译：`, or `英文翻译/解释：`. Do not satisfy quote safety by downgrading to `转述结论`; first return to transcript JSON and select exact, verifiable source lines. Use `转述结论` only when a real transcript scan confirms no meaningful verifiable original quote exists.
- Evidence anchors must be substantively useful. Do not include greetings, thanks, ad reads, housekeeping, ending pleasantries, repeated intros/outros, or generic "they discussed X" anchors unless the anchor contains a specific claim, example, mechanism, number, decision, or strategic implication.
- Pagination is a delivery gate. If a heading or subtitle-like bold heading and its following body would begin in the bottom quarter of a page, insert a page break before that heading. Do not force all major sections onto new pages; apply this only when the heading position is too low.
- Transcript archive deduplication is a completion gate. Treat `spotifyEpisodeId + language` as the unique identity and retain at most one original transcript plus one complete Chinese transcript per episode. Never archive Chrome retry copies such as ` (1)` as separate files. Never admit `_zh_INCOMPLETE` files or Chinese files with untranslated non-empty segments to the formal archive.
- Chinese transcripts are an archive/completeness artifact, not the default report-generation source. Generate the report from original/English transcripts unless the user explicitly asks to use Chinese transcripts for analysis.
- After report review passes and delivery succeeds, always run transcript cleanup with `scripts/import_spotify_transcripts.py --move`. Verify Downloads has zero leftover JSON files and audit the current run's episode IDs in both formal archive directories; duplicate IDs must be `0` before mark-seen.
- Mark episodes seen only after the required delivery gates pass, unless the user explicitly skips a blocked channel.
- Discord delivery must use the live Discord Studio directory: `/Users/hannah/.discord-studio/Discord_Studio`.
- When sending transcript/evidence to Gemini or files to Google Drive/Discord, respect Codex approval prompts. If approval is blocked, report it directly and do not work around it.

## Common User Triggers

- “做今天 Spotify 播客研报”
- “继续周三 Spotify 研报流程”
- “跑 MWF Spotify report skill”
- “检查 STD transcript 并交付研报”
- “调试 LaunchAgent / Drive / Discord / Zotero”
