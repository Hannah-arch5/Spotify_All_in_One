# Project Memory

Updated: 2026-05-24

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

- `Gemini研报生成协议.md`
- `Gemini研报复查清单.md`
- `Gemini最终Prompt模板.md`

## Next Practical Steps

1. Reload the Chrome extension and re-download the Modern Wisdom test transcript once so the JSON uses the latest parser.
2. Batch-open/check the 26 accepted episodes and collect available Spotify transcript JSON files.
3. Create an evidence pack format for Gemini: manifest + transcript file paths + per-episode metadata.
4. Build a checker that verifies Gemini's report includes exactly the expected episodes and flags unsupported quotes/claims.
5. Later: add Google Drive export, Zotero import/tagging, PDF formatting, and Telegram sending.
