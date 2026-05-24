# Project Memory

Updated: 2026-05-24 23:44 CST

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

- `data/transcripts/spotify/`
- Use `scripts/import_spotify_transcripts.py` to copy newly downloaded Spotify JSON files into the project.
- Use `scripts/import_spotify_transcripts.py --move` after verification to remove duplicate JSON files from Downloads.
- Use `scripts/prune_transcripts.py` to preview cleanup of archived transcripts older than 90 days.
- Use `scripts/prune_transcripts.py --delete` to actually remove old archived transcripts after preview.
- As of 2026-05-24, Downloads has been cleaned: 0 transcript JSON files remain there; 26 JSON files are archived in `data/transcripts/spotify/`.

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

End-to-end pipeline:

- Script: `scripts/run_report_pipeline.py`
- It runs RSS check, readable episode list, transcript audit/import, evidence pack, Spotify collection queue, Gemini input package, Gemini generation, and Gemini report review.
- It stops with `blocked_missing_transcripts` if any transcript is missing.
- Optional `--mark-seen-on-pass` marks episodes seen only after the generated report review conclusion is `通过`.

Automation schedule:

- One-time heartbeat: `resume-spotify-report-trial`, scheduled for 2026-05-25 15:05 Asia/Shanghai.
  - First try to resume the 26-episode trial from episode 20.
  - If Gemini quota is still blocked, stop retrying the trial and switch to Monday's newest RSS/transcript workflow.
  - Generate the latest episode list, transcript audit, imported transcript status, evidence pack if possible, and Spotify transcript collection queue.
  - Do not mark seen.
- One-time cron: `evening-retry-spotify-trial`, scheduled for 2026-05-25 21:05 Asia/Shanghai.
  - Retry the 26-episode trial if afternoon quota was still blocked.
  - Run report review if the final Markdown is produced.
  - Do not mark the trial batch seen unless user approves after review.
- Recurring cron: `spotify-mwf-podcast-report`, scheduled weekly Monday / Wednesday / Friday at 15:00 Asia/Shanghai.
  - Intended future cadence: every 2-3 days, expected around 10 episodes per report rather than 26.
  - This should usually fit Gemini free-tier constraints when chunked generation is used.

## Next Practical Steps

1. On 2026-05-25 15:05, resume `scripts/generate_chunked_gemini_report.py` after Gemini daily quota reset.
2. If quota is still blocked, check Monday's latest podcast updates and collect/download their Spotify transcripts first; retry the 26-episode trial around 21:05.
3. After any final Markdown report is produced, run `scripts/check_gemini_report.py` against it.
4. If review passes, ask/confirm before marking the 26-episode trial batch as seen.
5. Later: add Google Drive export, Zotero import/tagging, PDF formatting, and Telegram sending.
