# Project Memory

Updated: 2026-05-24 04:58 CST

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

## Next Practical Steps

1. Build the Gemini input package from `data/runs/20260523-222300-evidence-pack.json`.
2. Give Gemini the manifest/evidence package and the final prompt protocol.
3. After Gemini produces the report, build a checker that verifies the report includes exactly the expected 26 episodes and flags unsupported quotes/claims.
4. Later: add Google Drive export, Zotero import/tagging, PDF formatting, and Telegram sending.
