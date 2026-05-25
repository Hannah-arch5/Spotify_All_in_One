# Project Memory

Updated: 2026-05-25 20:51 CST

## Goal

Build a Monday / Wednesday / Friday podcast intelligence workflow.

Core requirements:

- Check followed Spotify podcasts every 2-3 days.
- Avoid missed episodes and duplicated episodes.
- Sort report items only by episode publish time, newest first.
- Use real transcripts as the evidence base. Do not use audio ASR by default because it is too expensive.
- Let Gemini write the final long-form report, but force Gemini to work from collected transcripts and source metadata.
- Codex should collect episodes/transcripts, package evidence, and review Gemini's report for omissions, duplicates, and hallucinations.
- Keep Google Drive backup, Zotero import, tags, and Telegram delivery as later pipeline stages.

## Current Podcast List

The follow list is stored in `config/podcasts.yaml`.

Important list decisions:

- `Your Episodes` is excluded because it is a Spotify saved playlist, not a podcast source.
- `明朝那些事儿` was removed because it appears inactive.
- The screenshot/display order is only for maintaining the follow list.
- The report itself must sort by episode publish date/time descending.

## RSS Episode Collection

Current scripts:

- `scripts/check_new_episodes.py`
- `scripts/render_episode_list.py`
- `scripts/audit_transcripts.py`
- `scripts/parse_spotify_transcript_text.py`
- `scripts/import_spotify_transcripts.py`
- `scripts/prune_transcripts.py`
- `scripts/build_evidence_pack.py`
- `scripts/build_spotify_collection_queue.py`

Default check window:

- Future runs should check the last 3 days by default.
- Only mark episodes as seen after a report batch is confirmed.

Important command:

```bash
/Users/hannah/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/check_new_episodes.py
```

## First Accepted Batch

The user accepted the initial 26-episode batch for the first report.

Known manifest:

- `data/runs/20260523-222300-manifest.json`

Known readable list:

- `reports/markdown/20260523-222300-episode-list.md`

These output folders are ignored by git because they are run artifacts.

Current transcript coverage for this accepted batch:

- Evidence pack: `data/runs/20260523-222300-evidence-pack.json`
- Human-readable coverage report: `reports/markdown/20260523-222300-evidence-pack.md`
- Spotify collection queue: `reports/markdown/20260523-222300-spotify-collection-queue.md`
- Status as of 2026-05-24 04:58 CST: 26/26 transcripts matched, 0 missing, 0 unmatched transcript files.

## Transcript Strategy

Audio transcription / ASR was rejected for now because it is too costly.

Preferred transcript path:

1. Spotify transcript capture through Chrome extension.
2. YouTube / Language Reactor only as fallback where Spotify has no transcript.
3. Manual copy fallback can use `scripts/parse_spotify_transcript_text.py`.

YouTube test result:

- `youtube-transcript-api` and `yt-dlp` were blocked/unreliable in this environment.
- Language Reactor can display full subtitles, but automated extraction is brittle.

## Spotify Transcript Downloader

Extension directory:

- `chrome-spotify-transcript-downloader/`

Chrome download output:

- `/Users/hannah/Downloads/Spotify Transcript Collector/`

Project transcript archive:

- English/original transcripts: `data/transcripts/spotify_en/`
- Chinese translated transcripts: `data/transcripts/spotify_zh/`
- Use `scripts/import_spotify_transcripts.py` to copy newly downloaded Spotify JSON files into the project.
- Use `scripts/import_spotify_transcripts.py --move` after verification to remove duplicate JSON files from Downloads.
- User preference: after transcripts are confirmed archived and the report/review is OK, delete temporary JSON copies in `/Users/hannah/Downloads/Spotify Transcript Collector/`.
- Use `scripts/prune_transcripts.py` to preview cleanup of archived transcripts older than 90 days.
- Use `scripts/prune_transcripts.py --delete` to actually remove old archived transcripts after preview.
- As of 2026-05-24, Downloads has been cleaned: 0 transcript JSON files remain there; 26 English JSON files are archived in `data/transcripts/spotify_en/`.

Important files:

- `chrome-spotify-transcript-downloader/manifest.json`
- `chrome-spotify-transcript-downloader/content.js`
- `chrome-spotify-transcript-downloader/injected.js`
- `chrome-spotify-transcript-downloader/background.js`

Tested Spotify episode:

- `https://open.spotify.com/episode/3E1adYXk5KvfGFlEJbdhY1?nd=1`
- Modern Wisdom, "The New Way Of The Superior Man - David Deida - #1101"

Test result:

- The extension panel appeared.
- It auto-captured the Spotify transcript API.
- It downloaded JSON to `/Users/hannah/Downloads/Spotify Transcript Collector/`.
- A test file was generated for episode ID `3E1adYXk5KvfGFlEJbdhY1`.
- The first accepted 26-episode batch was collected successfully through Spotify pages.

Fixes applied after Antigravity's version:

- Cache API transcript captures if Spotify preloads a transcript for an episode that is not yet the current browser URL. Process it only when the route later matches.
- Do not misclassify Spotify API `title: Speaker 1` blocks as transcript text. Treat them as speaker labels.
- Accept visible timestamps like `0:16` and `1:24:37` in DOM/manual transcript parsing.

Codex expansion updates (up to V2.1.9):

- Added multi-language relative day-of-week parsing for episodes published within the last 7 days.
- Restricted DOM date scanning exclusively to the main content area (stopping at H2 boundaries) to avoid recommendation leak.
- Decoupled API Episode ID tracking directly from the intercepted URL to eliminate race conditions.
- Added fast polling (200ms) and bypassed title check waits to trigger downloads almost instantly when DOM is ready.
- Fixed string concatenation bugs and restricted year regex matching.
- Embedded `debugLogs` array into the downloaded JSON payload for diagnostics.

User needs to reload the unpacked extension in Chrome after code changes:

- Open `chrome://extensions/`.
- Click Reload on "Spotify Podcast Transcript Downloader".

## Gemini Report Protocol

Gemini should still write the final report because the user likes its style.

Codex/Gemini contract:

- Gemini receives episode manifest + transcript evidence pack.
- Gemini may use relevant macro/background knowledge for analysis.
- Gemini must ground episode summaries and quotes in the transcript.
- Gemini must not invent episodes, sources, quotes, or claims unsupported by transcripts/source links.
- Codex should review the Gemini output against the manifest and transcripts before final delivery.

Key docs:

- `docs/gemini/Gemini研报生成协议.md`
- `docs/gemini/Gemini研报复查清单.md`
- `docs/gemini/Gemini最终Prompt模板.md`
- `docs/plugin/ANTIGRAVITY_PLUGIN_NOTES.md`

Gemini input packaging:

- Script: `scripts/build_gemini_input_package.py`
- First package output: `data/gemini_inputs/20260523-222300/`
- Package files:
  - `episode-manifest.json`
  - `transcript-evidence-full.json`
  - `transcript-evidence-full.md`
  - `gemini-prompt.md`
  - `source-manifest-original.json`
- The package includes all 26 accepted episodes and 26 matched Spotify transcripts.

Gemini report review:

- Script: `scripts/check_gemini_report.py`
- Intended use after Gemini returns Markdown:

```bash
/Users/hannah/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/check_gemini_report.py reports/markdown/20260523-222300-gemini-report.md --manifest data/gemini_inputs/20260523-222300/episode-manifest.json --evidence data/gemini_inputs/20260523-222300/transcript-evidence-full.json
```

Gemini API automation:

- Script: `scripts/generate_gemini_report.py`
- Default model: `gemini-2.5-pro`
- Reads `GEMINI_API_KEY` or `GOOGLE_API_KEY` from environment.
- Output: `reports/markdown/<run_id>-gemini-report.md`
- The API key must stay out of git; `.env` is ignored.

Gemini quota findings on 2026-05-24:

- The provided key can access model metadata for `gemini-2.5-pro`.
- `gemini-2.5-pro` generation failed with free-tier quota 0.
- `gemini-2.5-flash` small generation works, but full 26-episode package exceeded the 250k input token/minute free-tier quota.
- Chunked generation with `scripts/generate_chunked_gemini_report.py` works per episode.
- Completed chunked briefs: 19/26 in `data/gemini_chunks/20260523-222300/`.
- The run stopped at episode 20 because `gemini-2.5-flash` free tier hit 20 generate requests/day.
- Expected daily quota reset is likely midnight Pacific Time, about 15:00 Asia/Shanghai. If not reset at 15:05 on 2026-05-25, retry around 21:05 or after a full 24 hours from the last successful request.
- Resume later with:

```bash
GEMINI_API_KEY=<key> /Users/hannah/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/generate_chunked_gemini_report.py --package-dir data/gemini_inputs/20260523-222300 --model gemini-2.5-flash --sleep-seconds 70
```

- The chunked script resumes existing episode briefs by default.
- 2026-05-25 update:
  - Quota had reset; chunked generation resumed successfully.
  - All 26 episode briefs completed in `data/gemini_chunks/20260523-222300/`.
  - Final Gemini Markdown report produced: `reports/markdown/20260523-222300-gemini-report.md`.
  - Review result after tightening quote checks and marking non-exact quotes as close paraphrases: `通过`.
  - Review files: `data/runs/20260523-222300-gemini-review.json` and `reports/markdown/20260523-222300-gemini-review.md`.
  - The accepted 26-episode trial batch was marked as processed in `data/state.sqlite` so future M/W/F checks do not repeat it.

End-to-end pipeline:

- Script: `scripts/run_report_pipeline.py`
- It runs RSS check, readable episode list, transcript audit/import, evidence pack, Spotify collection queue, Gemini input package, Gemini generation, and Gemini report review.
- It stops with `blocked_missing_transcripts` if any transcript is missing.
- Optional `--mark-seen-on-pass` marks episodes seen only after the generated report review conclusion is `通过`.

Automation schedule:

- One-time heartbeat `resume-spotify-report-trial` and one-time cron `evening-retry-spotify-trial` are obsolete because the 26-episode trial batch completed and passed review.
- Recurring cron: `spotify-mwf-podcast-report`, scheduled weekly Monday / Wednesday / Friday at 15:00 Asia/Shanghai.
  - Intended future cadence: every 2-3 days, expected around 10 episodes per report rather than 26.
  - This should usually fit Gemini free-tier constraints when chunked generation is used.

## Current Monday Batch

Run generated after marking the 26-episode trial batch seen:

- Manifest: `data/runs/20260525-201553-manifest.json`
- Episode list: `reports/markdown/20260525-201553-episode-list.md`
- Transcript audit: `reports/markdown/20260525-201553-transcript-audit.md`
- Evidence pack: `data/runs/20260525-201553-evidence-pack.json`
- Evidence report: `reports/markdown/20260525-201553-evidence-pack.md`
- Spotify collection queue: `reports/markdown/20260525-201553-spotify-collection-queue.md`
- Gemini input package: `data/gemini_inputs/20260525-201553/`
- Gemini chunk briefs: `data/gemini_chunks/20260525-201553/`
- Final Gemini report: `reports/markdown/20260525-201553-gemini-report.md`
- Gemini review: `reports/markdown/20260525-201553-gemini-review.md`
- Review JSON: `data/runs/20260525-201553-gemini-review.json`
- Mark-seen manifest: `data/runs/20260525-205316-manifest.json`
- Status: 8 new episodes, 8/8 transcripts matched, Gemini report generated, review `通过`, then marked seen/processed so the Wednesday run will not repeat them.

Current Monday new episodes:

1. The a16z Show — `Why AI Isn’t Killing SaaS Yet`
2. The Diary Of A CEO with Steven Bartlett — `Bruno Fernandes: Roy Keane Twisted My Words. They Offered Me £200M, I Said No.`
3. Modern Wisdom — `Mostly Wise: Matt McCusker, Andrew Huberman & Tom Segura - #1102`
4. 硅谷101 — `E238｜聊聊Harness时代AI-First的组织架构：从信任人到信任AI`
5. 厚雪长波 — `关于白酒是周期见底还是永久衰退的一次审视`
6. Behind the Craft — `How This 5x Founder Runs His Startup Solo With AI Agents (OpenClaw, Codex, Devin) | Ryan Carson`
7. Lenny's Podcast: Product | Growth | Career — `The AI paradox: More automation, more humans, more work | Dan Shipper`
8. The AI Daily Brief — `Why Agents Still Need Humans`

Monday batch notes:

- All 8 Spotify transcript JSON files were collected through the Chrome extension and imported into `data/transcripts/spotify_en/`.
- After archive verification and report review pass, the 8 temporary JSON files in `/Users/hannah/Downloads/Spotify Transcript Collector/` were deleted; Downloads now has 0 transcript JSON files.
- Gemini `gemini-2.5-flash` generated 8 episode briefs and the final report successfully.
- The first Gemini final report hallucinated leftover sections 9-26 from the earlier 26-episode trial. It was corrected by truncating the report to the real 8 sections, fixing two mistyped Spotify episode IDs, and rerunning `scripts/check_gemini_report.py`.
- Final review conclusion is `通过`.
- After the pass, `scripts/check_new_episodes.py --since-days 3 --mark-seen` was run and produced `data/runs/20260525-205316-manifest.json`.

## Next Practical Steps

1. Next scheduled run should collect new RSS episodes on Wednesday 2026-05-27 at 15:00 Asia/Shanghai.
2. Keep using chunked `gemini-2.5-flash`; watch for final-summary hallucinations and always run `scripts/check_gemini_report.py`.
3. Later: add Google Drive export, Zotero import/tagging, PDF formatting, and Telegram sending.
