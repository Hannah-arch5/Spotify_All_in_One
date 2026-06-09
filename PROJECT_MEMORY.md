# Project Memory

> Global memory: before starting or continuing this project, read `/Users/hannah/Documents/Codex/GLOBAL_MEMORY.md` first.


Updated: 2026-05-26 CST

## Goal

Build a Monday / Wednesday / Friday podcast intelligence workflow.

## Codex Operating Requirements

These are hard user requirements, added on 2026-05-31:

- After every code or formatting change, Codex must run an audit/check relevant to the changed behavior before claiming success.
- Codex must proactively inspect edge cases and boundary conditions, then add or run tests/checks for those cases when behavior is uncertain.
- If an audit/test/check fails, Codex must debug and fix each failure, then rerun the audit/test/check until it passes.
- Do not rely on "it should work" reasoning for delivery artifacts. For Word/PDF/Zotero outputs, verify the actual generated artifact, and when possible visually inspect rendered pages or thumbnails.
- If a fallback renderer/tool path produces lower fidelity than the requested output, do not use it silently. Fail loudly unless the user explicitly approves the fallback.
- For report delivery formatting, final checks must include at minimum: heading hierarchy, title/label boldness, Markdown marker leakage, spacing/page-break behavior around major parts and intelligence entries, PDF text sanity, staged-file refresh, and Zotero active-file hash verification when Zotero is touched.

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
- Switched Google Translate API from GET to POST and restored a 1s delay per batch to resolve HTTP 414 and 429 failures causing missing Chinese transcripts.

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
- It returns `blocked_gemini_generation` instead of crashing if Gemini quota/API generation stops mid-run; check `data/gemini_chunks/<run_id>/STATUS.json` when present and rerun later because chunked generation resumes existing briefs.
- Default Gemini mode is now chunked generation with `gemini-2.5-flash`, matching the workflow that succeeded for the 26-episode trial and the Monday batch.
- Optional `--mark-seen-on-pass` marks episodes seen only after the generated report review conclusion is `通过`.
- Optional `--cleanup-transcripts-on-pass` removes Downloads transcript JSON files only after the report review conclusion is `通过`, using `scripts/import_spotify_transcripts.py --move` to verify archived copies first.

Preferred automation command:

```bash
/Users/hannah/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/run_report_pipeline.py --since-days 3 --gemini-mode chunked --model gemini-2.5-flash --sleep-seconds 70 --cleanup-transcripts-on-pass --mark-seen-on-pass
```

Automation schedule:

- One-time heartbeat `resume-spotify-report-trial` and one-time cron `evening-retry-spotify-trial` were deleted on 2026-05-26 because the 26-episode trial batch completed and passed review.
- Recurring cron: `spotify-mwf-podcast-report`, scheduled weekly Monday / Wednesday / Friday at 15:00 Asia/Shanghai.
  - Intended future cadence: every 2-3 days, expected around 10 episodes per report rather than 26.
  - This should usually fit Gemini free-tier constraints when chunked generation is used.
  - Updated on 2026-05-26 to prefer the verified `scripts/run_report_pipeline.py --gemini-mode chunked --model gemini-2.5-flash --sleep-seconds 70 --cleanup-transcripts-on-pass --mark-seen-on-pass` command.
  - Updated again on 2026-05-26 so passing reports must be rendered to PDF, archived into Zotero, and uploaded/staged for Google Drive before the run is considered complete.

GitHub publishing preferences:

- New project repositories should default to public unless the user explicitly asks for private.
- Repository names should use title-case words separated by hyphens, for example `Chrome-Spotify-Transcript-Downloader`.
- The STD plugin is published at `https://github.com/Hannah-arch5/Chrome-Spotify-Transcript-Downloader`.
- STD GitHub tags: `STD_v2.0` is the stable confirmed baseline; `STD_v2.1-zh` includes the optional Chinese transcript download enhancement.

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

## Archive Status

- Both completed reports have passed local review:
  - `20260523-222300`: `通过`, 0 errors, 0 warnings.
  - `20260525-201553`: `通过`, 0 errors, 0 warnings.
- Corrected delivery files were re-rendered on 2026-05-26 with `scripts/render_delivery_reports.py`.
  - Filename rule: `YYMMDD-Spotify播客情报研报`, where `YYMMDD` is the upload/published date of the first episode in the report, not the run date and not the report generation time.
  - Word:
    - `reports/word/260523-Spotify播客情报研报.docx`
    - `reports/word/260525-Spotify播客情报研报.docx`
  - PDF:
    - `reports/pdf/260523-Spotify播客情报研报.pdf`
    - `reports/pdf/260525-Spotify播客情报研报.pdf`
  - Format: landscape Letter, 1 inch margins, single-column body layout matching the reference Word file `/Users/hannah/Downloads/科技播客情报分析报告.docx`. The Word output uses the reference DOCX as a template, keeps `Google Sans` direct run fonts, Heading 1/2/3 title hierarchy, black headings, no colored heading treatment, inline bold keywords preserved, and no visible run/source metadata line.
  - Do not introduce bullet-dot symbols (`•`) when the reference Word style does not use them; Markdown `-` lines are rendered as normal paragraphs with bold labels instead.
  - Pagination rule: do not force every episode onto a fresh page. Parts and episodes should flow continuously to avoid large blank areas, but every part/episode/topic/insight title must stay with its following body. If a title would land near the bottom of a page with no meaningful body text, start it on the next page.
  - Current continuous-layout PDF page counts after this fix: `260525` is 16 pages, `260523` is 44 pages. Automated text checks found 0 page endings where a title was stranded at the bottom.
  - The `第二部分` heading is kept with `情报 1`, not left behind at the end of the summary.
  - On 2026-05-26, the `260525` report was found to be missing 第三/四/五部分 in the source Markdown. It was manually completed from the already-reviewed 8 episode briefs, then re-reviewed.
  - `scripts/check_gemini_report.py` now fails reports that lack any required top-level part from 第一部分 through 第五部分.
  - The `关键金句/结论` section must contain only meaningful quote/conclusion sentences and Chinese explanation. It must not include timestamps, `Timestamp`, `Speaker 1`, `发言者 1`, or similar evidence markers; those belong only in `证据锚点`.
  - `scripts/clean_key_quote_blocks.py` removes those markers from key quote blocks, and `scripts/check_gemini_report.py` fails future reports if they reappear.
  - Structural QA confirmed landscape orientation, single-column sections, required five-part structure, first-episode section placement, and extractable PDF text. Full DOCX page-image QA could not run because LibreOffice/`soffice` is not installed.
- Zotero archive corrected on 2026-05-26:
  - Target collection: `1.Spotify情报汇总`.
  - Direct top-level PDF items, not child attachments under report parent items:
    - `260523-Spotify播客情报研报`
    - `260525-Spotify播客情报研报`
  - Tags must include the leading slash: `/unread`, `/2605` (and future month tags as `/YYMM`). `scripts/archive_reports_to_zotero.py` now normalizes tag inputs to include `/`.
  - The earlier incorrect parent report items and wrong suffix-named direct PDF items were removed.
  - On 2026-05-26, Zotero direct PDF items were replaced again after the complete five-part `260525` report and reference-matched formatting were regenerated.
  - On 2026-05-26, Zotero direct PDF items were replaced again after the continuous pagination/no-orphan-heading fix.
  - On 2026-05-26 evening, Zotero was found to still be opening older direct PDF files because the active Zotero storage files matched the earlier staged PDFs, not the latest `reports/pdf/260523-Spotify播客情报研报.pdf` and `reports/pdf/260525-Spotify播客情报研报.pdf`. The active Zotero storage files were overwritten with the latest local PDFs and the staged Discord PDFs were refreshed. If Zotero still displays the old style, close the open PDF tab and reopen the attachment so Zotero reloads the file from disk.
  - A second evening check found the rendered Word/PDF still did not match the reference because `scripts/render_delivery_reports.py` unconditionally swapped page width/height even though the reference DOCX was already landscape. This produced portrait-looking PDFs in Zotero. Fixed by forcing Letter landscape dimensions to 27.94 cm x 21.59 cm, matching reference paragraph spacing (Heading 1/2/3 and normal body), applying `Google Sans` to ascii/hAnsi/eastAsia/cs runs, and exporting PDF through Microsoft Word. Re-rendered and replaced:
    - Zotero active PDF `storage/0KQ5R4BC/260523-Spotify播客情报研报.pdf`
    - Zotero active PDF `storage/3OP5X95H/260525-Spotify播客情报研报.pdf`
    - Staged Discord PDFs in `reports/archive/pending/2605/discord-todo/`
    - Staged Google Drive Word files in `reports/archive/pending/2605/google-drive/`
    - Verification: active Zotero PDFs have the same SHA-256 hashes as `reports/pdf/`, and PDF MediaBox is `792 x 612` landscape.
  - A follow-up visual review found three remaining causes of mismatch with the reference Word report:
    - The delivery renderer used the filename as the visible H1, losing the reference-style summarized bilingual report title.
    - Heading/body runs were explicitly written with `bold=False`, overriding inherited bold styles and making headings look too light.
    - Body paragraphs were forced to justified alignment and Markdown bold markers were stripped before DOCX rendering, causing awkward mixed Chinese/English spacing and loss of bold key phrases.
  - Fixed by using summarized bilingual display titles for existing completed runs, preserving inherited heading bold, only setting explicit bold for true emphasis runs, keeping body alignment inherited/left like the reference, and preserving Markdown `**...**` as bold runs. Re-rendered Word/PDF and replaced active Zotero PDFs plus staged Google Drive/Discord files again. Latest verified SHA-256:
    - `260525` PDF: `81bac757520b53212982e256c345199f64fc7f20372f96ae260d2df04360c98f`
    - `260523` PDF: `c5a4c03a1f811d1400c88861039fbdd2a68c251dea76bdc28b7bb55e250f5f7c`
  - On the next formatting pass, the renderer was updated to follow the reference Word structure more strictly:
    - All Heading 1/2/3 runs are explicitly bold.
    - Top-level part headings are normalized to reference-style bilingual names:
      - `第一部分：摘要与核心洞察总结 (Abstract & Executive Summary)`
      - `第二部分：核心情报深度梳理 (Detailed Intelligence Breakdown)`
      - `第三部分：深度专题分析 (Deep Thematic Analysis)`
      - `第四部分：深度洞察与第二层思维 (Deep Insights & Second-Level Thinking)`
      - `第五部分：结论与战略意义 (Conclusion & Strategic Implications)`
    - Part breaks get a blank line plus a horizontal separator.
    - Episode headings get spacing between entries.
    - Chinese translation lines under `关键金句 / 结论` are italicized.
    - DOCX verification for `260525` passed: required part titles present, headings explicitly bold, 4 horizontal rules, 14 italic Chinese translation lines.
  - Re-rendered local Word/PDF and refreshed staged Google Drive/Discord files. Latest local/staged verified hashes:
    - `260525` PDF: `77e232f18a7819da8093ff67ea57ccc6568bcc1d34d8499d79027bc145adc37d`
    - `260525` DOCX: `303aba5e7ac2a6f68ec11aff85a71919fe58405373afa36042505b64493a2339`
  - Zotero replacement for this latest pass could not be completed because sandbox escalation for writing `/Users/hannah/Zotero/storage/...` was rejected by the automatic approval reviewer due usage-limit/approval state. Do not assume Zotero has this newest formatting until the active Zotero attachment is manually replaced or the write is retried successfully.
  - Zotero database backups created before writes:
    - `/Users/hannah/Zotero/zotero.sqlite.backup-1779733077`
    - `/Users/hannah/Zotero/zotero.sqlite.backup-1779733816`
    - `/Users/hannah/Zotero/zotero.sqlite.backup-1779734613`
    - `/Users/hannah/Zotero/zotero.sqlite.backup-1779765281`
    - `/Users/hannah/Zotero/zotero.sqlite.backup-1779765613`
    - `/Users/hannah/Zotero/zotero.sqlite.backup-1779766254`
    - `/Users/hannah/Zotero/zotero.sqlite.backup-1779766700`
- Google Drive archive status:
  - Target folder remains `1.Spotify情报汇总`.
  - Word files staged at `reports/archive/pending/2605/google-drive/`.
  - Retry on 2026-05-26 later in the session still failed before folder search/upload with `failed to get client` / MCP handshake transport closed.
  - Retry on 2026-05-31 found the target folder successfully: `https://drive.google.com/drive/folders/1lZXtX08qX_PXVT_sOnzmxwmJDTtt8b8R`. However, the currently exposed Google Drive tools include document import but no parent-folder parameter and no Drive metadata `update_file` / move-parent operation. To avoid creating loose uploads in Drive root, leave the Word files staged in `reports/archive/pending/2605/google-drive/` until a folder-aware upload/move tool is available or the user manually uploads them to the target folder.
  - 2026-06-01 update: the final Word files were uploaded through the Google Drive web UI after Chrome file-upload permission was enabled. The Google Drive connector folder listing confirmed both files are now present in the target folder:
    - `260523-Spotify播客情报研报.docx`
    - `260525-Spotify播客情报研报.docx`
  - The target folder listing showed only one same-title final file for each of `260523` and `260525`; no same-title old versions were found in the target folder.
- Discord todo delivery status:
  - Discord Operating Manual exists at `/Users/hannah/Documents/Codex/2026-05-22/whatsapp/MEMORY.md` under `## Discord Operating Manual`; read it before any Discord delivery work.
  - Existing Discord bot is `Hannah AIl in One Studio#8688`, with Discord Studio enabled in `/Users/hannah/Documents/Codex/2026-05-22/whatsapp/`.
  - Future Discord delivery must use the existing Discord bot / Discord Studio path by default. Do not use Chrome web Discord or request Chrome file-upload authorization unless the user explicitly asks for a manual fallback.
  - Bot attachment delivery was added on 2026-06-01 in `/Users/hannah/Documents/Codex/2026-05-22/whatsapp/`: `npm run send:discord -- <discord_channel_id> "message" [file ...]`.
  - Current general `#todo` channel id from the sent report URL is `1508163671988109393`.
  - Verification on 2026-06-01: `src/discord.js` and `scripts/send-discord.js` passed Node syntax checks; `package.json` parsed successfully; an isolated dry-run queue write in `/private/tmp` produced a Discord notification with one attachment path; the background bot service was restarted successfully and logs show `Discord studio connected as Hannah AIl in One Studio#8688`.
  - 2026-06-01 update: final PDFs were posted to Discord `#todo` through the logged-in Discord web UI. This delivery succeeded, but the workflow was not the desired fully automated bot path.
  - Sent files:
    - `260523-Spotify播客情报研报.pdf`
    - `260525-Spotify播客情报研报.pdf`
- Recurring Monday/Wednesday/Friday 15:00 automation `spotify-mwf-podcast-report` was updated to include the corrected date-prefixed filename, landscape Word/PDF formatting, direct-PDF Zotero import, Google Drive Word upload, and Discord todo delivery requirements.
  - Updated again on 2026-05-31 to make the strict reference-Word delivery details explicit: summarized bilingual H1 instead of filename, exact bilingual top-level part titles, explicit bold Heading 1/2/3 runs, blank line + horizontal separator between major parts, spacing between 情报 entries, and italic Chinese translation/explanation lines under `关键金句 / 结论`.

## 2026-05-31 Continuation Notes

- Local report formatting code is updated in `scripts/render_delivery_reports.py`; generated Word/PDF outputs in `reports/word/`, `reports/pdf/`, and pending Google Drive/Discord folders reflect the strict reference-Word formatting pass.
- Zotero still should not be assumed to contain the newest strict-format PDFs because writing directly to `/Users/hannah/Zotero/storage/...` requires sandbox approval, and current approval policy rejects sandbox escalation. Manual Zotero attachment replacement or a later approved write is still required.
- A catch-up RSS check was attempted with `scripts/check_new_episodes.py --since-days 7` and produced `data/runs/20260531-224426-manifest.json` plus `reports/markdown/20260531-224426-episode-list.md`, but all 26 RSS feeds failed with sandbox DNS errors. The resulting `0` new episodes is not a valid editorial conclusion; it only means RSS fetches were blocked. Escalated rerun was rejected by current approval policy, so the real May 27/29 catch-up remains pending until networked local execution is available.
- Backfill support was added:
  - `scripts/check_new_episodes.py` now supports fixed publish-time windows with `--since <ISO>` and `--until <ISO>`.
  - `scripts/run_report_pipeline.py` now supports `--manifest <path>` so a fixed-window manifest can flow through transcript audit, evidence pack, Gemini generation, review, and delivery rendering without rechecking RSS.
  - When `--manifest` is used, `--mark-seen-on-pass` is deliberately skipped with a status message; fixed-window manifests should be marked seen deliberately only after the exact backfill report is reviewed.
- Missing scheduled report windows to backfill:
  - Wednesday 2026-05-27 15:00 Asia/Shanghai cutoff: `2026-05-25T07:00:00+00:00 <= published_at < 2026-05-27T07:00:00+00:00`.
  - Friday 2026-05-29 15:00 Asia/Shanghai cutoff: `2026-05-27T07:00:00+00:00 <= published_at < 2026-05-29T07:00:00+00:00`.
- Google Drive connector status on 2026-05-31: target folder listing works, but the exposed Drive tools still lack a destination-folder argument on import and lack a move/update-parent operation. Do not upload to root as a workaround; keep files staged until folder-aware upload/move is available.
- Pending README `reports/archive/pending/2605/README.md` was updated with the Drive folder URL, Zotero replacement targets, latest hashes, and exact backfill commands.
- Added `scripts/backfill_missed_report_windows.py` to run the two missed fixed windows in one command and continue into the pipeline from each generated manifest. In the current sandbox it returns `blocked_feed_failures` because RSS DNS fails for all feeds, but it is ready for a network-enabled local run.
- Added `scripts/verify_zotero_report_pdfs.py` to compare local generated PDFs with active Zotero direct-PDF attachment storage files. Verification on 2026-05-31 confirmed Zotero still has older hashes:
  - `260523` local strict-format PDF hash `4bf47e6a658ec97436b0aee24b1dacb53745d3e6be0830690f1d37518864c6ba`; Zotero active hash `c5a4c03a1f811d1400c88861039fbdd2a68c251dea76bdc28b7bb55e250f5f7c`.
  - `260525` local strict-format PDF hash `77e232f18a7819da8093ff67ea57ccc6568bcc1d34d8499d79027bc145adc37d`; Zotero active hash `81bac757520b53212982e256c345199f64fc7f20372f96ae260d2df04360c98f`.
  - Conclusion: Zotero has not yet been updated to the newest strict-format PDFs.
  - Later on 2026-05-31, a network-enabled backfill check succeeded:
  - Wednesday missed window manifest: `data/runs/20260531-231754-385067-manifest.json`
    - Window: `2026-05-25T07:00:00+00:00 <= published_at < 2026-05-27T07:00:00+00:00`
    - RSS failures: 0
    - New episodes: 7
    - Collection queue: `reports/markdown/20260531-231754-385067-spotify-collection-queue.md`
    - Pipeline status: `blocked_missing_transcripts`, missing 7/7 transcripts.
  - Friday missed window manifest: `data/runs/20260531-231817-735040-manifest.json`
    - Window: `2026-05-27T07:00:00+00:00 <= published_at < 2026-05-29T07:00:00+00:00`
    - RSS failures: 0
    - New episodes: 15
    - Collection queue: `reports/markdown/20260531-231817-735040-spotify-collection-queue.md`
    - Pipeline status: `blocked_missing_transcripts`, missing 15/15 transcripts.
  - `scripts/check_new_episodes.py` now uses microsecond precision in `run_id` so two fast fixed-window checks cannot overwrite each other's manifest/report artifacts.
  - Script health check passed with `python3 -m py_compile` for the modified pipeline/backfill/render/Zotero verification scripts.
- After user visual review on 2026-05-31, the Zotero PDFs were still formatted incorrectly. Root cause:
  - The Gemini Markdown uses `#### 情报 ...` for episode intelligence headings.
  - `scripts/render_delivery_reports.py` only recognized `###` as a document heading in the DOCX body path, so `####` leaked into the rendered report as normal text.
  - When Microsoft Word PDF export failed inside the sandbox, the script silently used the simpler ReportLab fallback PDF path, which did not match the reference Word layout.
- Fixes applied on 2026-05-31:
  - `scripts/render_delivery_reports.py` now maps `#### ...` to Heading 3, preserving the reference heading hierarchy.
  - Metadata labels with mixed English/Chinese names such as `Transcript 来源：` are now bolded like the reference labels.
  - The renderer now fails if Microsoft Word PDF export is unavailable, unless `--allow-reportlab-fallback` is passed explicitly. Do not use the fallback for final Zotero/Drive/Discord delivery PDFs.
  - Re-rendered both completed reports with Microsoft Word export and refreshed local Word/PDF files plus staged Google Drive/Discord files.
  - Active Zotero storage PDFs were overwritten successfully and verified with `scripts/verify_zotero_report_pdfs.py`.
  - Current verified hashes:
    - `260523` PDF: `a501174abf0dcc73a23f5ada28421a6706a27838f36e2185c1b0fd3b4335709c`
    - `260523` DOCX: `06945d766c2a13acf3945ea378aa111a060249e8ebcc438e2a9835908f9fc644`
    - `260525` PDF: `bbb76f1ddac31fdeecbaedcd7a483ff1139055336502bd6ccdea1828ecac71c7`
    - `260525` DOCX: `be12403cb52ecedb221df50b483ad2bc89275eeb6df2443b81683a17ef4f8e8e`
  - Structural QA passed:
    - 0 Markdown heading residues starting with `#` in DOCX.
    - 5 required Heading 2 part titles present in both reports.
    - Episode headings are Heading 3.
    - All visible Heading 1/2/3 runs are explicitly bold.
    - Required labels (`原始标题`, `来源与发布者`, `原始链接`, `Transcript 来源`, `核心内容摘要`, `情报价值点`, `关键金句`) are bolded.
    - PDF text check found no `####` residue and confirmed normalized part titles.
  - Visual spot-check via Quick Look thumbnail of `260525` page 2 confirmed the earlier screenshot issue is fixed: no `####`, bold section/episode headings, blank spacing between major part transition and first intelligence item, and preserved bold keyword emphasis.
- User reported on 2026-05-31 that boldness was still not visually strong enough. Final stronger-bold pass:
  - Root cause: generated bold Chinese/complex-script runs had `w:b` but not always `w:bCs`; even after adding `w:bCs`, `Google Sans` bold rendered too lightly in Word-exported PDF.
  - `scripts/render_delivery_reports.py` now uses `PingFang SC Semibold` for all explicit bold heading/label/emphasis runs while preserving `Google Sans` for normal body text.
  - `scripts/audit_delivery_report_format.py` was added and must be run after delivery-renderer changes. It checks DOCX heading hierarchy, absence of Markdown heading residue, required five part headings, episode Heading 3 count, strong OOXML bold (`w:b` + `w:bCs`), required bold font for headings/labels, blank paragraphs before repeated episode headings, and PDF text sanity with Unicode normalization.
  - A failed audit caught PDF text extraction compatibility glyphs (`⼼` vs `心`); the audit now normalizes PDF text with Unicode NFKC to avoid false failures.
  - A visual page check caught `第二部分` and `情报 1` stranded near the bottom after strong-bold rendering. The renderer now starts major parts after the first on a new page and keeps episode metadata labels with following text where possible.
  - Final visual spot-check of `260525` page 3 confirmed `第二部分` starts at the top of a fresh page, major headings and labels are visibly heavy, and body keyword emphasis remains bold.
  - Final automated audit passed for both completed reports:
    - `260523`: 5 Heading 2 parts, 26 episode Heading 3 entries, required labels all present and strongly bolded, PDF 89 pages, no issues.
    - `260525`: 5 Heading 2 parts, 8 episode Heading 3 entries, required labels all present and strongly bolded, PDF 29 pages, no issues.
  - Replaced active Zotero PDFs again and verified local/Zotero hashes match.
  - Current verified final hashes:
    - `260523` PDF: `9cab35f1b82190ec0e40f4b51d15ce132c0a52ae67480734abedd5524cfc0ea6`
    - `260523` DOCX: `062988e870a67ceb152de921ca573cbb64f33962fb878a90402aab4316404ffb`
    - `260525` PDF: `e4c6dddfe746b74c83d9230f8ae1bc117b5a440e5f8fb31b43a045b74df63474`
    - `260525` DOCX: `2403275577a72a0588cda2ffa7bf9bb08e21bd958364d0ba505ab80d99b2f1bb`
- User reported another formatting mismatch on 2026-05-31. Updated delivery rules:
  - A title that wraps across multiple physical lines is one paragraph and must not visually look like blank lines were inserted between wrapped lines.
  - Metadata block under each episode (`原始标题`, `来源与发布者`, `原始链接`, `Transcript 来源`) must be compact: no blank lines or paragraph spacing between those lines.
  - `核心内容摘要`, `情报价值点`, `关键金句 / 结论`, and `证据锚点` are content-block labels. Each label should sit directly against its content with no blank line after the label; only separate the blocks from each other.
  - Third/fourth/fifth-part subheadings follow the same principle: no blank line between a subheading and its body; only separate adjacent sub-blocks.
  - Body bold emphasis must not preserve generic long phrases. It should only remain for meaningful short professional terms/new concepts/deep research terms, or required structural labels.
- Renderer/audit changes for those rules:
  - `scripts/render_delivery_reports.py` now classifies metadata labels, content-block labels, and body paragraphs separately.
  - Heading line spacing is set explicitly so wrapped titles do not look double-spaced.
  - Metadata lines have `space_after=0`; content-block labels have `space_after=0`; block separation uses space before labels or explicit blank paragraphs between episodes/major parts.
  - Inline Markdown bold in body text is filtered by semantic rules; generic long phrases and generic colon labels are stripped.
  - `scripts/audit_delivery_report_format.py` now fails generic/overlong body bold runs, metadata/content labels with unwanted spacing after them, loose heading spacing, Markdown residue, missing part/episode structure, weak bold labels/headings, and PDF text issues.
  - Final delivery-format audit passed for both completed reports:
    - `260523`: 5 Heading 2 parts, 26 episode Heading 3 entries, required labels all present, PDF 76 pages, 0 issues.
    - `260525`: 5 Heading 2 parts, 8 episode Heading 3 entries, required labels all present, PDF 27 pages, 0 issues.
  - Visual spot-check of `260525` page 1 confirmed the wrapped main title has no blank-line look; visual spot-check of page 3 confirmed compact metadata and label/body spacing.
  - Replaced active Zotero PDFs again and verified local/Zotero hashes match.
  - Current verified final hashes:
    - `260523` PDF: `68fd9505e688dfab3be9a4e0737303506bc6bb25f7240a3edd600c39b48493d7`
    - `260523` DOCX: `3565a556ba70ee12cddaecad30ba7f7980597ac811b4522c225ac25b64e78a2f`
    - `260525` PDF: `d7a6bc6354449b8ff638d752c913e63b75d7c3b97d0f2bf3db93638c0c98884a`
    - `260525` DOCX: `606b4f5d9028dd99b41bae9ea49fd734e0896fd9b543a166dff88ec939e1ad5b`
- User reported another Zotero PDF mismatch on 2026-06-01. Updated delivery rules:
  - Every intelligence entry after the first must have a horizontal separator before it.
  - `Transcript 来源` must be removed from final Word/PDF delivery.
  - `原始标题`, `来源与发布者`, and `原始链接` must be compact with no blank lines between them.
  - Major sections after the first must not force-start on a new page when they can continue naturally; use separator spacing instead.
  - Body keyword emphasis must be visible and meaningful: short professional terms, emerging concepts, named tools/models, or deep research terms only.
- Renderer/audit changes for these rules:
  - `scripts/render_delivery_reports.py` skips `Transcript 来源` lines, restores horizontal rules between episode intelligence entries, removes forced page breaks before later major sections, keeps metadata lines compact, and auto-bolds a curated meaningful keyword set such as `SaaS末日论`, `token`, `OpenRouter`, `Anthropic`, `Cursor`, `GitHub Copilot`, `AEO`, `AI-First`, `AI代理`, `Agent经济`, `数字员工`, and `共享团队代理`.
  - `scripts/audit_delivery_report_format.py` now fails if `Transcript 来源` appears, if repeated episode headings lack nearby horizontal separators, if metadata/content-block spacing regresses, or if no meaningful body keyword emphasis is present.
  - Automated audit passed for both completed reports:
    - `260523`: 5 Heading 2 parts, 26 episode Heading 3 entries, required labels all present, PDF 76 pages, 0 issues.
    - `260525`: 5 Heading 2 parts, 8 episode Heading 3 entries, required labels all present, PDF 27 pages, 0 issues.
  - Visual spot-check of `260525` confirmed the separator before repeated intelligence entries, no `Transcript 来源`, compact metadata, `第三部分` continuing naturally instead of being forced to a fresh page, and visible meaningful keyword bolding.
  - Replaced active Zotero PDFs again and verified local/Zotero hashes match.
  - Current verified final hashes:
    - `260523` PDF: `7d31de78ccd71190201bd17757d0d94e1e842bbf496751a039c9876f978eb29d`
    - `260523` DOCX: `2489d77317ed8bbed302f0afce2e1fcb176f59fbdd1bfe01dce03f38b89f5e7c`
    - `260525` PDF: `512f9c74244caa3ab8cedf63a2a4309fca58a8425dbda0dfd6e94efa501fd3c8`
    - `260525` DOCX: `72377c568004e343fa6509726aa52fdda9829093acaaa85e4b33333894a1dc87`
- User reported on 2026-06-01 that body keyword bolding was noisy and body line spacing was inconsistent. Updated delivery rules:
  - Do not automatically bold body keywords. If semantic emphasis is uncertain, do not add it.
  - Body bold is allowed only for structural labels such as `原始标题`, `来源与发布者`, `原始链接`, `核心内容摘要`, `情报价值点`, `关键金句`, and `证据锚点`, plus document headings.
  - Body paragraphs, metadata lines, and content-label paragraphs must use fixed exact 14pt line spacing to avoid Word/PDF mixed-font line-height drift.
- Renderer/audit changes for these rules:
  - Removed automatic keyword emphasis from `scripts/render_delivery_reports.py`.
  - Removed old colon-label heuristics that bolded body phrases such as numbered claims or short topic labels.
  - `scripts/audit_delivery_report_format.py` now fails any non-structural body bold run and fails body paragraphs that are not exact 14pt line spacing.
  - Automated audit passed for both completed reports:
    - `260523`: 5 Heading 2 parts, 26 episode Heading 3 entries, required labels all present, PDF 64 pages, 0 issues.
    - `260525`: 5 Heading 2 parts, 8 episode Heading 3 entries, required labels all present, PDF 21 pages, 0 issues.
  - Visual spot-check of selected `260525` and `260523` PDF pages confirmed正文没有人为关键词加粗，正文行距稳定为窄行距。English/model names may still look slightly darker due to glyph/font rendering, but they are not bold runs in DOCX.
  - Replaced active Zotero PDFs again and verified local/Zotero hashes match.
  - Current verified final hashes:
    - `260523` PDF: `16aea0c1f411cfaa42b441091a4a5458babe93bca3ee31145d8506e0a8df5f2f`
    - `260523` DOCX: `7bbd1e7ee903e74a8738af1a44b43485ce4179a716e496cb98cf6a352c70ffbf`
    - `260525` PDF: `3e73be559a39309ce50786d35e9cd30dfaa7d62b1336a1e33d981fc86f8d53aa`
    - `260525` DOCX: `914a2a1aee975ff1f73eeac91c0f9f4f43e5b5e2b0183b05c6d00148d80292c1`
- User reported on 2026-06-01 that third/fourth/fifth-part subsection titles lost bold after body keyword bolding was removed. Updated delivery rules:
  - Third, fourth, and fifth-part subsection titles must be bold.
  - Markdown `### ...` in these parts renders as Heading 3 and remains strongly bold.
  - Leading subsection labels in these parts, such as `1. **核心结论：**` or `* **技术突破：**`, keep only the leading title/label bold.
  - Do not restore general body keyword emphasis.
- Renderer/audit changes for these rules:
  - `scripts/render_delivery_reports.py` now permits leading subsection-title bold only in parts 3-5.
  - `scripts/audit_delivery_report_format.py` now allows those later-part leading subsection-title bold runs while still failing other non-structural body bold.
  - Added final delivery format contract: `docs/REPORT_FORMAT_REQUIREMENTS.md`.
  - Automated audit passed for both completed reports:
    - `260523`: 5 Heading 2 parts, 26 episode Heading 3 entries, required labels all present, PDF 64 pages, 0 issues.
    - `260525`: 5 Heading 2 parts, 8 episode Heading 3 entries, required labels all present, PDF 21 pages, 0 issues.
  - Visual spot-check of pages containing parts 3-5 confirmed later-part subsection titles are bold while ordinary body text remains unbolded.
  - Replaced active Zotero PDFs again and verified local/Zotero hashes match.
  - Current verified final hashes:
    - `260523` PDF: `6f49b62ae9215021f3364b4b5b29c817b7ec6c058290596d04e0b3dbb2bdb8f0`
    - `260523` DOCX: `e7be74b95474385511f2347171424c0f3cb3afc12f7e64a147dbad540812ba88`
    - `260525` PDF: `d88042c8d3c2968805c2a076d01e604df9ab336e45e502dd076ec51704e94e3a`
    - `260525` DOCX: `103261f5593f079c335837cc0a977981afe826656728f421e74ad91d9867a055`
- Backfill transcript collection update on 2026-06-01:
  - Read `PROJECT_MEMORY.md`, checked git status, and verified tag `STD_v2.0` exists at `2fcf7ac0ec8f3ea41f0f25207190c8d1f82c9655`.
  - Collected Spotify transcripts via Chrome + STD for both generated backfill queues:
    - Wednesday manifest `data/runs/20260531-231754-385067-manifest.json`: 7/7 English transcript JSON files collected and imported; 6/7 Chinese translation JSON files collected.
    - Friday manifest `data/runs/20260531-231817-735040-manifest.json`: 15/15 English transcript JSON files collected and imported; 11/15 Chinese translation JSON files collected at import time.
  - `scripts/import_spotify_transcripts.py` imported/verified 22 English transcript files and 17 Chinese translation files into `data/transcripts/spotify_en` and `data/transcripts/spotify_zh`.
  - Reran both fixed-window pipelines with chunked `gemini-2.5-flash`:
    - `scripts/run_report_pipeline.py --manifest data/runs/20260531-231754-385067-manifest.json --gemini-mode chunked --model gemini-2.5-flash --sleep-seconds 70`
    - `scripts/run_report_pipeline.py --manifest data/runs/20260531-231817-735040-manifest.json --gemini-mode chunked --model gemini-2.5-flash --sleep-seconds 70`
  - Both runs now have `missing_transcripts: 0` and generated evidence packs/Gemini input packages successfully.
  - Both runs are blocked only at Gemini generation because the current shell has no `GEMINI_API_KEY` or `GOOGLE_API_KEY` environment variable.
- Backfill generation update on 2026-06-01:
  - Added project-local `.env` loading via `scripts/env_utils.py`; Gemini scripts now read `GEMINI_API_KEY` / `GOOGLE_API_KEY` from the shell first, then from project `.env`. `.env` remains gitignored.
  - Fixed `scripts/generate_chunked_gemini_report.py` final synthesis prompt so it uses the actual episode count instead of hard-coding 26 episode briefs. This prevented 7-episode backfill reports from hallucinating extra sections 8-26.
  - Wednesday backfill report `20260531-231754-385067`:
    - Generated and repaired final Markdown: `reports/markdown/20260531-231754-385067-gemini-report.md`.
    - Content/evidence review passed: `reports/markdown/20260531-231754-385067-gemini-review.md`.
    - Rendered delivery files:
      - `reports/word/260527-Spotify播客情报研报.docx`
      - `reports/pdf/260527-Spotify播客情报研报.pdf`
    - Delivery format audit passed: 5 Heading 2 parts, 7 episode Heading 3 entries, required labels all present, PDF 21 pages, 0 issues.
  - Friday backfill report `20260531-231817-735040`:
    - Earlier status: blocked at episode 11 by Gemini API quota after 10/15 episode briefs.
- 2026-06-02 continuation update:
  - Read `PROJECT_MEMORY.md`, checked git status, and verified `STD_v2.0` at `2fcf7ac0ec8f3ea41f0f25207190c8d1f82c9655`; current HEAD was `0bc1ca6fefccd69bc581c431279ee972f2767420`.
  - Friday backfill was found completed locally despite stale `STATUS.json`:
    - 15/15 episode briefs exist in `data/gemini_chunks/20260531-231817-735040/`.
    - Final Markdown exists: `reports/markdown/20260531-231817-735040-gemini-report.md`.
    - Review passed after rerun: `reports/markdown/20260531-231817-735040-gemini-review.md`, conclusion `通过`.
    - Rendered delivery files:
      - `reports/word/260529-Spotify播客情报研报.docx`
      - `reports/pdf/260529-Spotify播客情报研报.pdf`
    - Delivery format audit passed: 5 Heading 2 parts, 15 episode Heading 3 entries, required labels all present, PDF 37 pages, 0 issues.
  - Wednesday backfill was re-audited successfully:
    - `reports/word/260527-Spotify播客情报研报.docx`
    - `reports/pdf/260527-Spotify播客情报研报.pdf`
    - Delivery format audit passed: 5 Heading 2 parts, 7 episode Heading 3 entries, required labels all present, PDF 21 pages, 0 issues.
  - Staged archive files were verified against local finals:
    - `reports/archive/pending/2605/google-drive/260527-Spotify播客情报研报.docx` matches local DOCX.
    - `reports/archive/pending/2605/google-drive/260529-Spotify播客情报研报.docx` matches local DOCX.
    - `reports/archive/pending/2605/discord-todo/260527-Spotify播客情报研报.pdf` matches local PDF.
    - `reports/archive/pending/2605/discord-todo/260529-Spotify播客情报研报.pdf` matches local PDF.
  - Zotero direct-PDF verification passed for the two backfill reports:
    - `260527` local/Zotero SHA-256: `f960131fece478aecdcbe8c2a2dcbcfbbb46ea31b31f952a6aca7f0cd34aa1be`
    - `260529` local/Zotero SHA-256: `58d1e03429d1cf21f1bae470d4a1bfc75f474664d9866ee104ba23ff5153726b`
  - Google Drive target folder `1.Spotify情报汇总` was checked via connector. It already contained `260529`, and `260527` was uploaded through the logged-in Google Drive web UI. Connector folder listing confirmed all four May files are now present:
    - `260523-Spotify播客情报研报.docx`
    - `260525-Spotify播客情报研报.docx`
    - `260527-Spotify播客情报研报.docx`
    - `260529-Spotify播客情报研报.docx`
  - Discord proactive bot delivery for `260527` and `260529` was attempted through `npm run send:discord -- 1508163671988109393 ...`, but sandbox approval rejected it because sending local PDFs to Discord is an external upload requiring explicit user authorization. Do not work around this; ask the user to explicitly approve Discord delivery before retrying.

## Next Practical Steps

## 2026-06-02 Monday Report Continuation

- User confirmed Discord had already been sent for the backfill, so do not resend `260527`/`260529`.
- Monday regular run in progress: `20260602-021659-259621`.
  - Manifest: `data/runs/20260602-021659-259621-manifest.json`
  - New episodes: 12.
  - Evidence pack initially had 11/12 transcripts; missing episode was 小Lin说 `内存暴涨，谁在哭？谁在笑？`.
  - Spotify search/show page did not contain the 2026 episode; 小宇宙 page had show notes but no transcript.
  - Bilibili matching video: `https://www.bilibili.com/video/BV1A7V36BEc9/`.
  - Bilibili public metadata had no `subtitle.list` and `x/player/wbi/v2` reported `need_login_subtitle: true`, so no public native subtitle file was available without login.
  - Found a public third-party transcript reference:
    - Vocus article: `https://vocus.cc/article/6a1b9527fd897800014fcc48`
    - Public Google Drive TXT: `https://drive.google.com/file/d/1-QxFFMVjirkTj0hg0T10Z1pTpf_BOlx0/view?usp=sharing`
  - Created transcript JSON from the public TXT:
    - `data/transcripts/spotify_en/2026-06-01 - 小Lin说 - 内存暴涨，谁在哭？谁在笑？ - bilibili-BV1A7V36BEc9.json`
    - Source is marked `bilibili_public_transcript_txt`.
    - The TXT had no native timestamps, so segment timestamps are approximate/evenly distributed and marked with `timestamp_note`.
  - Rerun evidence pack reached 12/12 matched transcripts.
- Gemini generation:
  - `gemini-2.5-flash` generated episode briefs 1-8, then hit free-tier daily request quota.
  - Continued with `gemini-2.5-flash-lite`, which generated episode briefs 9-12 and final report.
  - Chunk dir: `data/gemini_chunks/20260602-021659-259621/`.
  - Final Markdown: `reports/markdown/20260602-021659-259621-gemini-report.md`.
  - Review passed after cleaning key-quote blocks that contained timestamp/direct-quote-style paraphrases:
    - Review: `reports/markdown/20260602-021659-259621-gemini-review.md`
    - Conclusion: `通过`, 12/12 episodes, 0 errors, 0 warnings.
- Delivery rendering:
  - DOCX generated: `reports/word/260601-Spotify播客情报研报.docx`
  - DOCX delivery-format audit passed: 5 Heading 2 parts, 12 episode Heading 3 entries, required labels all present, 0 issues.
  - PDF was not generated because Microsoft Word export requires sandbox escalation, and escalation was rejected due current usage-limit/approval state. Do not use `--allow-reportlab-fallback` for final delivery unless the user explicitly approves the lower-fidelity fallback.
  - Since PDF is not generated, do not mark this Monday batch seen/processed yet and do not archive to Zotero/Drive/Discord yet.

## Next Practical Steps

1. After sandbox escalation is available again, rerun Word PDF export for `reports/markdown/20260602-021659-259621-gemini-report.md` using `scripts/render_delivery_reports.py` without ReportLab fallback.
2. Run full delivery audit with both DOCX and PDF: `scripts/audit_delivery_report_format.py --docx reports/word/260601-Spotify播客情报研报.docx --pdf reports/pdf/260601-Spotify播客情报研报.pdf`.
3. If audit passes, archive `260601-Spotify播客情报研报.pdf` to Zotero as a direct PDF item, stage/upload `260601-Spotify播客情报研报.docx` to Google Drive folder `1.Spotify情报汇总`, and send the PDF to Discord `#todo` only if external delivery is authorized/expected.
4. Only after the generated report, delivery audit, archive, and delivery checks pass, mark the `20260602-021659-259621` episodes seen/processed.
5. Keep using content review plus delivery format audit before any final Word/PDF/Zotero/Drive/Discord delivery.
6. Reload the unpacked Chrome STD extension after plugin code changes if transcript capture behaves unexpectedly.

## 2026-06-03 Monday Report Delivery Continuation

- Continued the Monday regular run `20260602-021659-259621`.
- Confirmed `STD_v2.0` is still `2fcf7ac0ec8f3ea41f0f25207190c8d1f82c9655`.
- Generated final PDF through Microsoft Word export without ReportLab fallback:
  - DOCX: `reports/word/260601-Spotify播客情报研报.docx`
  - PDF: `reports/pdf/260601-Spotify播客情报研报.pdf`
- Full delivery-format audit passed:
  - DOCX: 5 Heading 2 parts, 12 episode Heading 3 entries, required labels all present, 0 issues.
  - PDF: 31 pages, 0 issues.
- Zotero archive:
  - First write attempt created backup `/Users/hannah/Zotero/zotero.sqlite.backup-1780460495` but failed because Zotero was open and locking the database.
  - Zotero was quit normally, then archive retried with a new backup `/Users/hannah/Zotero/zotero.sqlite.backup-1780460527`.
  - Direct PDF item archived successfully: `archived_direct_pdf=4371 title=260601-Spotify播客情报研报`.
  - Zotero verification passed:
    - Local/Zotero SHA-256: `69310ce2b3f47bf18856e54266ce9a6ba2762a0cd547d839e22e3bcc37242b04`
    - Active Zotero file: `/Users/hannah/Zotero/storage/HWE22WVQ/260601-Spotify播客情报研报.pdf`
- Local external-delivery staging:
  - Created `reports/archive/pending/2606/google-drive/260601-Spotify播客情报研报.docx`; SHA-256 matches local DOCX `32835caa8a5c8999ce2ce24bb26b16d358b914e66c4810cf1dcd79318715f82f`.
  - Created `reports/archive/pending/2606/discord-todo/260601-Spotify播客情报研报.pdf`; SHA-256 matches local PDF `69310ce2b3f47bf18856e54266ce9a6ba2762a0cd547d839e22e3bcc37242b04`.
- Google Drive:
  - Target folder `1.Spotify情报汇总` was opened in Chrome and listed via connector.
  - Existing folder contents include `260523`, `260525`, `260527`, and `260529` DOCX files, but not `260601`.
  - Chrome file upload failed with `fileChooser.setFiles failed` / `Not allowed`. The Codex Chrome extension needs "Allow access to file URLs" enabled before browser upload can proceed.
  - Do not upload the DOCX to Drive root as a workaround; retry folder upload only after file-upload permission is enabled or a folder-aware Drive upload/move tool is available.
- Discord:
  - Attempted to queue `260601` PDF to Discord `#todo` with `npm run send:discord -- 1508163671988109393 ...`.
  - The approval reviewer rejected the external upload because the user had not explicitly authorized this specific `260601` PDF transfer in the current run.
  - Do not work around this; ask for explicit authorization before retrying Discord delivery.
- Current status:
  - Generated report, review, DOCX/PDF render, format audit, Zotero archive, and local staging are complete.
  - Google Drive upload and Discord delivery are still blocked.
  - Do not mark `20260602-021659-259621` episodes seen/processed until Drive/Discord delivery policy is satisfied or the user explicitly decides those external steps can be skipped.

## 2026-06-03 Missed 2026-05-29 Gap Report

- User noticed three Spotify episodes shown in the UI but missing from both the prior Friday report and the Monday report:
  - The Joe Rogan Experience — `#2507 - Harland Williams`
  - Lex Fridman Podcast — `#497 – Biggest Mysteries in Physics: Antimatter, Dark Energy & ToE – Don Lincoln`
  - The a16z Show — `Why $1B Exits are Dead`
- Root cause:
  - Friday fixed-window report ended at `2026-05-29T07:00:00+00:00` / `2026-05-29 15:00 CST`.
  - Monday report was run at `2026-06-01T18:16:59+00:00` / `2026-06-02 02:16 CST` using `--since-days 3`, so its lower bound was `2026-05-29T18:16:59+00:00` / `2026-05-30 02:16 CST`.
  - The gap `2026-05-29T07:00:00+00:00` to `2026-05-29T18:16:59+00:00` was skipped.
  - The three missed episodes were exactly in that gap:
    - a16z: `2026-05-29T10:00:00+00:00` / `2026-05-29 18:00 CST`
    - Lex: `2026-05-29T16:22:02+00:00` / `2026-05-30 00:22 CST`
    - JRE: `2026-05-29T17:00:00+00:00` / `2026-05-30 01:00 CST`
- Created gap manifest:
  - `data/runs/20260603-123532-452672-manifest.json`
  - Summary: 3 configured missed episodes, 0 feed failures.
- Collected Spotify transcripts through Chrome + STD:
  - `data/transcripts/spotify_en/2026-05-29 - The Joe Rogan Experience - _2507 - Harland Williams - 62ehDou07zrd6LDFhgxbNY.json`
  - `data/transcripts/spotify_en/2026-05-29 - Lex Fridman Podcast - _497 – Biggest Mysteries in Physics_ Antimatter, Dark Energy & ToE - Don Lincoln - 4mMlXKv1UcNsMKESrsEi9j.json`
  - `data/transcripts/spotify_en/2026-05-29 - The a16z Show - Why $1B Exits are Dead - 7fENTLnNVumG8RhcbDD19g.json`
  - Also collected one Chinese translation: `data/transcripts/spotify_zh/2026-05-29 - The a16z Show - Why $1B Exits are Dead_zh - 7fENTLnNVumG8RhcbDD19g.json`
  - After verification, temporary JSON files in `/Users/hannah/Downloads/Spotify Transcript Collector/` were removed with `scripts/import_spotify_transcripts.py --move`.
- Evidence pack reached 3/3 matched transcripts:
  - `data/runs/20260603-123532-452672-evidence-pack.json`
  - `reports/markdown/20260603-123532-452672-evidence-pack.md`
- Generated supplemental Gemini report with `gemini-2.5-flash-lite`:
  - Markdown: `reports/markdown/20260603-123532-452672-gemini-report.md`
  - Review: `reports/markdown/20260603-123532-452672-gemini-review.md`
  - Review conclusion: `通过`, 3/3 episodes, 0 errors, 0 warnings.
- Rendered supplemental delivery files:
  - DOCX: `reports/word/260529-Spotify播客情报研报-补漏3集.docx`
  - PDF: `reports/pdf/260529-Spotify播客情报研报-补漏3集.pdf`
  - Delivery audit passed: 5 Heading 2 parts, 3 episode Heading 3 entries, required labels all present, PDF 13 pages, 0 issues.
  - Supplemental hashes:
    - DOCX SHA-256: `1da8832b8c8d1476725fd2a04820d50143b0a0cc2add166f76c85b8648a9f792`
    - PDF SHA-256: `e26d44c8c04ecc38ffc10bf931f9bb7f5a6f674db78993e7287931cbd3f6f113`
- Renderer initially wrote supplemental files to the default `260529-Spotify播客情报研报.*` names. The supplemental files were copied to `-补漏3集` names, then the original 15-episode `260529` delivery files were restored from archive staging.
  - Restored original `260529` DOCX hash matches archive staging: `58ad5f3db3d7a548186ee14f53a6b32edee1af92fe8c065b229594c5bcf670c1`
  - Restored original `260529` PDF hash matches archive staging: `58d1e03429d1cf21f1bae470d4a1bfc75f474664d9866ee104ba23ff5153726b`
  - Original `260529` delivery audit still passes: 15 episode Heading 3 entries, PDF 37 pages, 0 issues.
- Important process fix:
  - Avoid `--since-days 3` for delayed Monday runs because it can create a gap after the prior Friday 15:00 CST cutoff.
  - Prefer fixed schedule windows based on the last completed cutoff: Friday 15:00 CST -> Monday 15:00 CST, Monday 15:00 CST -> Wednesday 15:00 CST, Wednesday 15:00 CST -> Friday 15:00 CST, or use a persisted last-success cutoff.
  - Do not mark `20260603-123532-452672` seen/processed until the user decides how to deliver/archive this supplemental `-补漏3集` report.

## 2026-06-03 Combined Monday 15-Episode Report

- User requested that the three missed 2026-05-29 gap episodes be added into the Monday report, not only kept as a separate supplement.
- Added fixed schedule-window support:
  - New helper: `src/schedule.py`
  - `scripts/check_new_episodes.py --schedule-window current` now uses the latest fixed Monday/Wednesday/Friday 15:00 Asia/Shanghai report window.
  - `scripts/run_report_pipeline.py --schedule-window current` passes that fixed window through the pipeline.
  - Verified examples:
    - `2026-06-01T18:16:59+00:00` -> `2026-05-29T07:00:00+00:00 <= published_at < 2026-06-01T07:00:00+00:00`
    - `2026-06-03T07:05:00+00:00` -> `2026-06-01T07:00:00+00:00 <= published_at < 2026-06-03T07:00:00+00:00`
  - `README.md` was updated so normal automation uses `--schedule-window current` instead of `--since-days 3`.
- Created combined Monday manifest:
  - `data/runs/20260603-131000-260601-combined-manifest.json`
  - Source manifests:
    - `data/runs/20260602-021659-259621-manifest.json`
    - `data/runs/20260603-123532-452672-manifest.json`
  - Window: `2026-05-29T07:00:00+00:00 <= published_at < 2026-06-01T07:00:00+00:00`
  - Episode count: 15.
- Generated combined report with `gemini-2.5-flash-lite`:
  - Markdown: `reports/markdown/20260603-131000-260601-combined-gemini-report.md`
  - Review: `reports/markdown/20260603-131000-260601-combined-gemini-review.md`
  - Review conclusion: `通过`, 15/15 episodes, 0 errors, 0 warnings.
  - Manual cleanup performed after Gemini:
    - Restored required `第一部分` through `第五部分` headings.
    - Replaced the second part with the 15 per-episode briefs so every episode has `核心内容摘要` and `情报价值点`.
    - Removed non-verbatim English quote marks in key/evidence blocks where strict transcript quote matching could not confirm exact wording.
    - Rewrote episode 10 from an over-repeated brief into a concise transcript-grounded summary with 3 timestamp anchors.
- Rendered final Monday delivery files, replacing the earlier 12-episode `260601` files:
  - DOCX: `reports/word/260601-Spotify播客情报研报.docx`
  - PDF: `reports/pdf/260601-Spotify播客情报研报.pdf`
  - Delivery audit passed: 5 Heading 2 parts, 15 episode Heading 3 entries, required labels all present, PDF 31 pages, 0 issues.
  - Final hashes:
    - Markdown SHA-256: `7399ec73784d1aaa7c079cc586940c89db1d876f8381595be2937270395c1821`
    - DOCX SHA-256: `c520e01826f5577a8379a5eae98803fa56edac95d91069987f339acae60c952a`
    - PDF SHA-256: `3aeed93d755962f04a209e46afe67c7e18e58fef61869bc2b5e8028abab44f0b`
- 2026-06-03 continuation:
  - Re-ran the delivery-format audit for the combined `260601` report; it passed again with 5 Heading 2 parts, 15 episode Heading 3 entries, required labels all present, PDF 31 pages, 0 issues.
  - Zotero still contained the older 12-episode `260601` PDF at `/Users/hannah/Zotero/storage/HWE22WVQ/260601-Spotify播客情报研报.pdf` with SHA-256 `69310ce2b3f47bf18856e54266ce9a6ba2762a0cd547d839e22e3bcc37242b04`.
  - First Zotero replacement attempt created backup `/Users/hannah/Zotero/zotero.sqlite.backup-1780465294` but failed because Zotero was open and locking the database.
  - Zotero was quit normally, then replacement succeeded with backup `/Users/hannah/Zotero/zotero.sqlite.backup-1780465331`.
  - Active Zotero direct PDF now matches the combined local PDF:
    - Zotero item: `archived_direct_pdf=4371 title=260601-Spotify播客情报研报`
    - Active file: `/Users/hannah/Zotero/storage/DCIUSXCU/260601-Spotify播客情报研报.pdf`
    - Local/Zotero SHA-256: `3aeed93d755962f04a209e46afe67c7e18e58fef61869bc2b5e8028abab44f0b`
  - Staged external-delivery files match the combined local finals:
    - `reports/archive/pending/2606/google-drive/260601-Spotify播客情报研报.docx` SHA-256 `c520e01826f5577a8379a5eae98803fa56edac95d91069987f339acae60c952a`
    - `reports/archive/pending/2606/discord-todo/260601-Spotify播客情报研报.pdf` SHA-256 `3aeed93d755962f04a209e46afe67c7e18e58fef61869bc2b5e8028abab44f0b`
  - Google Drive remains blocked: current connector tools still cannot upload a DOCX to a specified parent folder, and Chrome upload previously failed until the Codex Chrome extension gets file URL/file upload permission. Do not upload to Drive root as a workaround.
  - Discord remains blocked: sending `260601` PDF to `#todo` is an external upload and needs explicit user authorization for this specific final combined PDF.
  - Do not mark the combined Monday window seen/processed until Google Drive/Discord are completed or the user explicitly decides those external steps can be skipped.
- Full automation note:
  - Codex approval prompts cannot be bypassed inside an interactive Codex session for external uploads or local app control.
  - To make Google Drive, Discord, Zotero, and Word PDF export fully automatic, run the pipeline from a local LaunchAgent/cron/service with pre-authorized credentials and OS permissions, rather than through Codex's sandbox approval layer.
  - Required pre-authorization path:
    - Google Drive: use a folder-aware API uploader with OAuth refresh token or service account access to `1.Spotify情报汇总`; avoid Chrome UI upload.
    - Discord: use the existing bot token/service queue outside Codex approvals.
    - Zotero: use local DB writes only when Zotero is closed, or Zotero Web API with an API key; verify active-file hashes after archive.
    - Word PDF export: grant macOS Automation permission for the Python/osascript runner to control Microsoft Word once.
  - The automation service should write logs and final hashes, then mark episodes seen only after report review, delivery audit, Zotero hash verification, Drive upload verification, and Discord send confirmation pass.

## 2026-06-03 Production Automation Upgrade

- User approved moving toward a fully automatic production runner that does not depend on repeated Codex interactive approvals.
- Added Chinese transcript coverage audit:
  - Script: `scripts/audit_transcript_languages.py`
  - Outputs:
    - `data/runs/<run_id>-transcript-language-audit.json`
    - `reports/markdown/<run_id>-transcript-language-audit.md`
  - `scripts/run_report_pipeline.py --require-zh-transcripts` now blocks before Gemini if any episode lacks a matched Chinese transcript.
  - Integration check on combined Monday report `20260603-131000-260601-combined` correctly blocked with `blocked_missing_zh_transcripts`.
  - Current combined Monday language coverage: 15/15 English/original transcripts, 5/15 Chinese transcripts, 10 missing Chinese transcripts.
- Added direct manifest marking:
  - Script: `scripts/mark_manifest_seen.py`
  - Purpose: mark exactly the episodes in a known manifest as processed after all delivery checks pass, avoiding a later `--schedule-window current --mark-seen` rerun that might target a different cutoff if the service is delayed.
  - Dry check with a temporary sqlite DB marked 15 manifest episodes without touching real `data/state.sqlite`.
- Added production service runner:
  - Script: `scripts/run_scheduled_report_service.py`
  - It runs the fixed schedule-window pipeline, renders Word/PDF, audits delivery formatting, archives direct PDF to Zotero, verifies Zotero/local PDF hashes, stages Drive/Discord files, runs configured Google Drive and Discord commands, then marks the manifest episodes seen only after required checks pass.
  - It writes structured logs to `data/service_logs/`.
  - It uses a lock file to prevent overlapping runs.
  - If a step fails, it writes a failure log and exits non-zero; episodes are not marked processed.
- Added production configuration/documentation:
  - `.env.example`
  - `docs/PRODUCTION_AUTOMATION.md`
  - README now points normal production automation to `scripts/run_scheduled_report_service.py`.
- Required local pre-authorization/configuration for hands-off automation:
  - `.env` must contain `GEMINI_API_KEY`.
  - Google Drive upload must be folder-aware via `SPOTIFY_GOOGLE_DRIVE_UPLOAD_CMD`; do not upload to root.
  - Discord delivery must use `SPOTIFY_DISCORD_SEND_CMD` with the existing bot/studio path.
  - Zotero local DB writes should use `SPOTIFY_ZOTERO_QUIT_BEFORE_WRITE=1`, or the workflow should migrate to Zotero API for long-term robustness.
  - Optional strict Chinese coverage gate: `SPOTIFY_REQUIRE_ZH_TRANSCRIPTS=1`.
- 2026-06-03 setup continuation:
  - Installed `rclone` v1.74.2 through Homebrew.
  - Configured rclone Google Drive remote `gdrive` through OAuth.
  - Verified `gdrive:` can list the root folder and includes `1.Spotify情报汇总/`.
  - Added production runner values to `.env`:
    - `SPOTIFY_ZOTERO_QUIT_BEFORE_WRITE=1`
    - `SPOTIFY_GOOGLE_DRIVE_UPLOAD_CMD=rclone copy "{docx}" "gdrive:1.Spotify情报汇总/" --checksum`
    - `SPOTIFY_GOOGLE_DRIVE_VERIFY_CMD=rclone lsf "gdrive:1.Spotify情报汇总/" --files-only`
    - `SPOTIFY_DISCORD_CHANNEL_ID=1508163671988109393`
    - `SPOTIFY_DISCORD_CWD=/Users/hannah/.discord-studio/Discord_Studio`
    - `SPOTIFY_DISCORD_SEND_CMD=npm run send:discord -- "{channel_id}" "{message}" "{pdf}"`
  - Uploaded current final Word file to Google Drive:
    - Source: `reports/archive/pending/2606/google-drive/260601-Spotify播客情报研报.docx`
    - Target folder: `gdrive:1.Spotify情报汇总/`
    - Verification listing confirmed `260601-Spotify播客情报研报.docx` is present.
  - Discord send for `260601-Spotify播客情报研报.pdf` was requested but rejected by the approval reviewer as external disclosure of local report content. Do not retry or work around unless the user explicitly approves this specific PDF send after being informed of the risk, or explicitly decides Discord can be skipped.
  - Do not mark the combined Monday window seen/processed until Discord is either completed with explicit approval or explicitly skipped by the user.
- 2026-06-03 title-fix continuation:
  - User noticed the combined Monday report H1 incorrectly displayed the run id/date string `20260603-131000-260601-combined`.
  - Root cause: `scripts/render_delivery_reports.py` only had display-title overrides for the earlier completed runs, so the combined run used Gemini's raw Markdown H1.
  - Added `TITLE_OVERRIDES["20260603-131000-260601-combined"]`:
    - `AI范式转移与产业重构情报研报：代币短缺、视频代理、算力内存与资本新秩序 (Podcast Intelligence Report: AI Paradigm Shift, Video Agents, Compute Memory & the New Capital Order)`
  - Re-rendered final delivery files:
    - DOCX: `reports/word/260601-Spotify播客情报研报.docx`
    - PDF: `reports/pdf/260601-Spotify播客情报研报.pdf`
  - Verified DOCX first paragraph is the corrected bilingual title, not the run id.
  - Delivery-format audit passed again: 5 Heading 2 parts, 15 episode Heading 3 entries, required labels all present, PDF 31 pages, 0 issues.
  - Updated Zotero direct PDF after quitting Zotero to release the sqlite lock:
    - First attempt backup: `/Users/hannah/Zotero/zotero.sqlite.backup-1780466616`, failed due database lock.
    - Successful backup: `/Users/hannah/Zotero/zotero.sqlite.backup-1780466651`.
    - Active Zotero PDF: `/Users/hannah/Zotero/storage/O511MHKZ/260601-Spotify播客情报研报.pdf`.
    - Local/Zotero SHA-256: `6177b2173720c7272f00e0e92ec291b59c40f930d2b972e381ec417431cdd5c2`.
  - Refreshed staged external-delivery copies:
    - Google Drive DOCX SHA-256: `65e8f2a91f21f1ff1807a957b9ded9d119c7f9725ca623225a5827bacb889e9f`.
    - Discord PDF SHA-256: `6177b2173720c7272f00e0e92ec291b59c40f930d2b972e381ec417431cdd5c2`.
  - Re-uploaded corrected DOCX to Google Drive target folder `1.Spotify情报汇总`; verification listing confirmed `260601-Spotify播客情报研报.docx` is present.
  - User authorized sending the corrected PDF to Discord, but the approval reviewer rejected the action because the Codex usage limit was reached and suggested trying again at 17:20. Do not work around; retry after usage limit resets or send via the production service outside Codex.
  - Do not mark the combined Monday window seen/processed until Discord is either completed or explicitly skipped by the user.

## 2026-06-04 Context Compression Checkpoint

- User asked to stop/confirm the LaunchAgent test process, reorganize state, then compress context.
- LaunchAgent status:
  - Label: `com.hannah.spotify-podcast-report`
  - Registered path: `/Users/hannah/Library/LaunchAgents/com.hannah.spotify-podcast-report.plist`
  - Project plist: `launchd/com.hannah.spotify-podcast-report.plist`
  - Current state after check: `not running`
  - Last exit code: `1`
  - This exit is expected because the service reached `blocked_missing_transcripts`, not because LaunchAgent is broken.
  - Latest progress log:
    - Service started at `2026-06-04T00:25:47+08:00`.
    - Pipeline started with `scripts/run_report_pipeline.py --schedule-window current`.
    - Pipeline finished at `2026-06-04T00:26:30+08:00`.
    - Pipeline status: `blocked_missing_transcripts`.
    - Service returned `blocked_missing_transcripts`.
  - Latest structured service log: `data/service_logs/20260604-002630-scheduled-report.json`.
- LaunchAgent validation result:
  - The plist loaded successfully.
  - Explicit PATH was added so launchd can find Homebrew tools such as `rclone`, `npm`, and `yt-dlp`.
  - The agent can start the production runner and write logs.
  - The current blocker is content readiness: missing transcripts for today's report, not LaunchAgent startup.
- Monday combined report `260601`:
  - Title was fixed and re-rendered.
  - Final title: `AI范式转移与产业重构情报研报：代币短缺、视频代理、算力内存与资本新秩序 (Podcast Intelligence Report: AI Paradigm Shift, Video Agents, Compute Memory & the New Capital Order)`.
  - Format audit passed after re-render.
  - Zotero active PDF hash matches local final PDF.
  - Google Drive DOCX was re-uploaded and verified present in `1.Spotify情报汇总`.
  - Discord PDF send is still not completed because Codex approval rejected external Discord upload. Do not work around.
  - Do not mark Monday combined window seen/processed unless Discord is completed or the user explicitly decides to skip Discord.
- Today's Wednesday report:
  - Current fixed window: `2026-06-01T07:00:00+00:00 <= published_at < 2026-06-03T07:00:00+00:00`.
  - Initial manifest from LaunchAgent/service included 11 episodes.
  - Four episodes overlap with the Monday combined report and must be deduped before generating today's report:
    - The AI Daily Brief — `The AI Token Shortage Begins [AI Monthly Recap]`
    - Latent Space — `Why Video Agent models are next — Ethan He, xAI Grok Imagine`
    - The a16z Show — `Building AI Agents for Enterprise Operations`
    - 小Lin说 — `内存暴涨，谁在哭？谁在笑？`
  - Deduped manifest prepared: `data/runs/20260603-235829-112249-dedup-manifest.json`
  - Deduped Wednesday episode count: 7.
  - Deduped Wednesday episodes:
    1. All-In — `Bill Ackman: Investment Strategy, What the Market is Missing, How AI Breaks Businesses`
    2. The AI Daily Brief — `Should Americans Get Shares in AI Companies?`
    3. The a16z Show — `Steven Sinofsky on AI PCs, NVIDIA, and the Future of Computing`
    4. The Joe Rogan Experience — `JRE MMA Show #180 with Daniel Rodriguez`
    5. Latent Space — `GitHub's plan for Agents — Kyle Daigle, GitHub`
    6. All-In — `OpenAI CFO Sarah Friar on IPO, AI Rivalries, New Device, and Spending $100B+ on Compute`
    7. Exchanges — `The AI Investment Boom: When Will It Pay Off?`
  - Dry pipeline on the deduped manifest stopped with `blocked_missing_transcripts`; all 7 deduped episodes still need transcripts.
  - Spotify search pages were opened in Chrome, but no transcript JSON files appeared in `/Users/hannah/Downloads/Spotify Transcript Collector/`.
  - Next practical step after compression: collect the 7 missing transcripts through the Chrome STD extension by opening each Spotify episode detail page, then run `scripts/import_spotify_transcripts.py`, rerun the deduped manifest pipeline, generate/review/render/audit/archive/upload.
- YouTube fallback:
  - `yt-dlp` was installed through Homebrew and is available.
  - Test on a JRE YouTube URL failed because YouTube required sign-in / bot confirmation.
  - Do not use browser cookies as a workaround unless the user explicitly approves that privacy-sensitive route.
- Safety note for resuming:
  - First step after context compression should be a short state check, not a new long pipeline:
    1. Query LaunchAgent status.
    2. Check `data/service_logs/20260604-002630-scheduled-report.json`.
    3. Check Downloads transcript collector for new JSON files.
    4. Rerun evidence pack for `data/runs/20260603-235829-112249-dedup-manifest.json`.

## 2026-06-04 Wednesday Transcript Collection Update

- User correctly pointed out that Wednesday transcripts should be collected through the STD Chrome extension workflow.
- Root cause of earlier `7 missing transcripts`: Spotify search pages had been opened, but the browser had not clicked into each episode detail page and opened Spotify's native `Transcript` tab. STD only captures after the episode detail page loads the transcript API.
- Chrome extension control was connected successfully through the Chrome plugin.
- Used single-tab sequential Spotify workflow to avoid Spotify's "too many tabs open" limit.
- Resolved and opened the 7 deduped Wednesday episode pages:
  1. `https://open.spotify.com/episode/381MqxuiIutkTG0dbKrQU1`
  2. `https://open.spotify.com/episode/6Sig5fANfXNu0dHby9FPMQ`
  3. `https://open.spotify.com/episode/1vWW7f3EwP2KBlm9iHoamR`
  4. `https://open.spotify.com/episode/10JAK7y5qD0Dr3bt5tIBjB`
  5. `https://open.spotify.com/episode/3v3GmnMM9rOVneekv9SQj8`
  6. `https://open.spotify.com/episode/7FZyUO0nCj396NQ6pp7Vjp`
  7. `https://open.spotify.com/episode/4VOy3s3wRnI4KSMCgC0AS8`
- Clicked the native Spotify `Transcript` tab on each page. STD captured all 7 English/original transcripts.
- Imported transcript files into the project:
  - `imported=12 skipped=0 removed=0 english_seen=7 chinese_seen=5`
- Reran pipeline on `data/runs/20260603-235829-112249-dedup-manifest.json`:
  - Evidence pack: `data/runs/20260603-235829-112249-dedup-evidence-pack.json`
  - Transcript coverage: 7/7 matched, 0 missing.
  - Language audit: 7/7 English/original, 5/7 Chinese, 2 missing Chinese (`JRE MMA Show #180`, `GitHub's plan for Agents`).
  - Gemini input package: `data/gemini_inputs/20260603-235829-112249-dedup`
- Current blocker:
  - Gemini generation failed in sandbox due network, then escalated rerun was rejected because it would send collected transcript/evidence content to the external Gemini API.
  - Discord send for Monday `260601` also remains blocked by external-upload policy.
  - Need explicit user approval after being informed of this data-export risk before retrying Gemini/Discord, or use a local/non-external report generation path.

## 2026-06-04 Wednesday Report Delivery Update

- User explicitly approved sending Wednesday transcript/evidence to Gemini API.
- Gemini chunked generation completed for deduped Wednesday manifest:
  - Manifest: `data/runs/20260603-235829-112249-dedup-manifest.json`
  - Report: `reports/markdown/20260603-235829-112249-dedup-gemini-report.md`
  - Review: `reports/markdown/20260603-235829-112249-dedup-gemini-review.md`
- Initial Gemini review returned `需修改` with two warning-only quote findings. The two non-verbatim quote blocks were converted to explicit conclusion/paraphrase text.
- Rerun review passed:
  - `scripts/check_gemini_report.py ...` returned `通过`.
- Rendered final Wednesday delivery files:
  - DOCX: `reports/word/260603-Spotify播客情报研报.docx`
  - PDF: `reports/pdf/260603-Spotify播客情报研报.pdf`
- Delivery audit passed:
  - 5 Heading 2 sections.
  - 7 episode Heading 3 entries.
  - Required labels all counted 7 times.
  - PDF page count: 21.
  - No audit issues.
- Final hashes:
  - DOCX SHA-256: `56201e089c3da69328d75e5582cef9d1147a190ee17a0f762a146bb682e11337`
  - PDF SHA-256: `2b80e07d294d64438501c73ef1b60bb8343803f702a2cddc970fd945de81ef01`
- Zotero archive completed after quitting Zotero:
  - Backup: `/Users/hannah/Zotero/zotero.sqlite.backup-1780506552`
  - Direct PDF item: `archived_direct_pdf=4372 title=260603-Spotify播客情报研报`
  - Active Zotero PDF: `/Users/hannah/Zotero/storage/N60TB8B1/260603-Spotify播客情报研报.pdf`
  - Zotero PDF hash matches local final PDF: `2b80e07d294d64438501c73ef1b60bb8343803f702a2cddc970fd945de81ef01`
- Staged external delivery copies:
  - Drive DOCX: `reports/archive/pending/2606/google-drive/260603-Spotify播客情报研报.docx`
  - Discord PDF: `reports/archive/pending/2606/discord-todo/260603-Spotify播客情报研报.pdf`
  - Staged hashes match local final files.
- Google Drive upload attempt for `260603` was rejected by Codex tenant approval policy as external disclosure to Google Drive, even though the user had requested Drive setup/upload. Do not work around by indirect execution.
- Monday `260601` Discord send remains blocked by the same external-upload policy. Do not mark Monday or Wednesday manifests seen/processed until Discord/Drive delivery is completed or the user explicitly chooses to skip the blocked channel(s).
- LaunchAgent state after this update:
  - `com.hannah.spotify-podcast-report` is loaded and `not running`.
  - Schedule remains Monday/Wednesday/Friday 15:00.
  - Last exit code remains `1` from the earlier blocked run, not a current active process.

## 2026-06-04 External Delivery Completed + Transcript Cleanup

- User explicitly acknowledged external disclosure risk and authorized:
  - Upload Wednesday `260603` DOCX to Google Drive.
  - Send Monday `260601` PDF and Wednesday `260603` PDF to Discord `#todo`.
- Google Drive upload completed:
  - Uploaded `reports/archive/pending/2606/google-drive/260603-Spotify播客情报研报.docx`
  - Verified `rclone lsf gdrive:1.Spotify情报汇总/ --files-only` includes `260603-Spotify播客情报研报.docx`.
- Discord delivery completed:
  - Initial manual send commands wrote to old queue path `/Users/hannah/Documents/Codex/2026-05-22/whatsapp`, which is no longer consumed by the live service.
  - Live Discord Studio service cwd is `/Users/hannah/.discord-studio/Discord_Studio` (confirmed from PID 425 lsof before restart).
  - Updated project config to use live cwd:
    - `.env`
    - `.env.example`
    - `docs/PRODUCTION_AUTOMATION.md`
    - this memory file
  - Restarted the wedged Discord Studio process and reran watchdog.
  - Live queue sent both messages:
    - `260601`: `notification_sent` id `1780507668664-588dd6b9-74d4-43f5-aae9-b88c622fe05c-discord`, sent at `2026-06-03T17:29:08.550Z`
    - `260603`: `notification_sent` id `1780507680101-77ef0430-1f97-4ace-bd5c-49e83f39892c-discord`, sent at `2026-06-03T17:29:09.512Z`
- Transcript cleanup completed:
  - STD Downloads directory had 12 JSON files from the Wednesday collection: 7 English/original and 5 Chinese.
  - Ran `scripts/import_spotify_transcripts.py --move`.
  - Result: `imported=0 skipped=12 removed=12 english_seen=7 chinese_seen=5`.
  - Verified `/Users/hannah/Downloads/Spotify Transcript Collector/` now has `0` transcript JSON files.
  - Root cause of missed cleanup in this manual continuation: the manual path imported transcripts first but did not rerun the `--cleanup-transcripts-on-pass` cleanup step after report pass/delivery. The scheduled service already includes `--cleanup-transcripts-on-pass`; future manual continuations must explicitly run `scripts/import_spotify_transcripts.py --move` after report review/delivery succeeds.
- Seen/processed marking completed after external delivery:
  - Monday combined manifest: `marked_seen=15 manifest=data/runs/20260603-131000-260601-combined-manifest.json`
  - Wednesday deduped manifest: `marked_seen=7 manifest=data/runs/20260603-235829-112249-dedup-manifest.json`

## 2026-06-04 Memory / Git / GitHub / Skillization Note

- Memory status:
  - `PROJECT_MEMORY.md` has been updated with the completed Wednesday report, Drive upload, Discord delivery, transcript cleanup, correct Discord Studio cwd, and seen/processed marking.
  - Future compressed contexts should resume from the completed state, not from the earlier `blocked_missing_transcripts` state.
- Git status:
  - Current branch: `feature/transpod-auto-translate`.
  - Worktree is dirty with project changes, generated data, automation docs/scripts, `.env.example`, launchd files, and report artifacts under `data/`.
  - Do not commit blindly: review generated `data/` content and decide which artifacts belong in git versus `.gitignore` before staging.
- GitHub status:
  - `git remote -v` currently returns no configured remote.
  - GitHub cannot be updated/pushed from this repo until a remote is added or the user identifies the target GitHub repository.
- Skillization recommendation:
  - The Monday/Wednesday/Friday Spotify report workflow is suitable for a dedicated Codex skill because it is repetitive, fragile, and has important validation gates.
  - Suggested skill name: `spotify-mwf-report`.
  - Trigger wording should include requests like: “做今天/周一/周三/周五 Spotify 播客研报”, “继续 Spotify 研报自动化”, “检查 STD transcript 并交付研报”.
  - Skill should encode the mandatory sequence: read memory, check git/LaunchAgent, collect missing transcripts via Spotify episode detail page + native Transcript tab + STD, import transcripts, generate/review report, render Word/PDF, audit, Zotero archive + hash verify, stage/upload Drive, send Discord through `/Users/hannah/.discord-studio/Discord_Studio`, cleanup Downloads transcripts with `scripts/import_spotify_transcripts.py --move`, mark seen only after required delivery succeeds, then update memory.
- Skill creation completed:
  - Installed locally at `/Users/hannah/.codex/skills/spotify-mwf-report/`.
  - Source copy in project at `.codex-skills/spotify-mwf-report/`.
  - GitHub archive repo: `https://github.com/Hannah-arch5/spotify-mwf-report-skill`
  - Repo visibility was changed from private to public per user preference.
  - Initial commit: `2361bb5 Add Spotify MWF report Codex skill`
  - Added GitHub repo description and README overview.
  - README commit: `3787252 Add repository overview`
  - To trigger in future, say “做今天 Spotify 播客研报”, “继续周三 Spotify 研报流程”, “跑 MWF Spotify report skill”, or “检查 STD transcript 并交付研报”.
- GitHub visibility preference:
  - Future GitHub uploads/repos should default to public unless the user explicitly says a specific repo or upload should be private.

## 2026-06-06 Friday 260605 Spotify Report Delivered

- Used `spotify-mwf-report` skill workflow for the latest fixed M/W/F window.
- Window:
  - Manifest: `data/runs/20260606-054802-713197-manifest.json`
  - Fixed schedule window: `2026-06-03T07:00:00+00:00` to `2026-06-05T07:00:00+00:00` (2026-06-03 15:00 to 2026-06-05 15:00 Asia/Shanghai).
  - Episode count: 17.
- Transcript collection:
  - STD Chrome/Spotify detail-page workflow used; opened episode detail pages and clicked native Spotify `Transcript`.
  - Imported English/original transcripts: 17.
  - Imported Chinese translated transcripts: 7.
  - Evidence pack: `data/runs/20260606-054802-713197-evidence-pack.json`.
  - Evidence summary after final import: `matched_count=17`, `missing_count=0`.
  - Language audit: `data/runs/20260606-054802-713197-transcript-language-audit.json`.
- Gemini report:
  - Package: `data/gemini_inputs/20260606-054802-713197/`.
  - Chunk directory: `data/gemini_chunks/20260606-054802-713197/`.
  - Final Markdown: `reports/markdown/20260606-054802-713197-gemini-report.md`.
  - Final title corrected before render:
    `AI生态重构与社会韧性情报研报：代币效率、代理评估、形式化验证与平台新秩序 (Podcast Intelligence Report: AI Ecosystem Restructuring, Token Efficiency, Agent Evals & Platform Strategy)`.
  - Review initially failed on 3 mistyped Spotify links and 6 non-verbatim quoted conclusions; fixed links and converted suspicious quotes to explicit paraphrased conclusions.
  - Final review: `通过`, with `0` errors/warnings after rerun.
  - Review files:
    - `data/runs/20260606-054802-713197-gemini-review.json`
    - `reports/markdown/20260606-054802-713197-gemini-review.md`
- Render/audit:
  - Word: `reports/word/260605-Spotify播客情报研报.docx`
  - PDF: `reports/pdf/260605-Spotify播客情报研报.pdf`
  - Delivery-format audit passed:
    - H2 count: 5.
    - Episode heading count: 17.
    - Required labels all counted 17 times.
    - PDF page count: 45.
    - No audit issues.
  - Visual spot checks passed on first page, middle page, and final page. First page title has no Run ID/date pileup.
  - Final hashes:
    - DOCX SHA-256: `a4ee2627115f6ada8dd9c2c3c9e28d9e0caaeeb9d1e8a09192a825e06d09cfee`
    - PDF SHA-256: `488f015606d66ff83d2665c89b733a4a9fc4ab03fe887bc21fe12b2324cb7d0d`
- Zotero archive:
  - Quit Zotero first to avoid sqlite lock.
  - Backup: `/Users/hannah/Zotero/zotero.sqlite.backup-1780699081`
  - Direct PDF item: `archived_direct_pdf=4374 title=260605-Spotify播客情报研报`
  - Active Zotero PDF: `/Users/hannah/Zotero/storage/V3B6RSCE/260605-Spotify播客情报研报.pdf`
  - Zotero PDF hash matches local final PDF: `488f015606d66ff83d2665c89b733a4a9fc4ab03fe887bc21fe12b2324cb7d0d`
- External delivery:
  - Staged Drive DOCX: `reports/archive/pending/2606/google-drive/260605-Spotify播客情报研报.docx`
  - Staged Discord PDF: `reports/archive/pending/2606/discord-todo/260605-Spotify播客情报研报.pdf`
  - Staged hashes match local final files.
  - Google Drive upload completed through `rclone copy` to `gdrive:1.Spotify情报汇总/`.
  - Google Drive verification listing includes `260605-Spotify播客情报研报.docx`.
  - Discord delivery completed through live Discord Studio cwd `/Users/hannah/.discord-studio/Discord_Studio`.
  - Discord sent record: `notification_sent` id `1780699151582-ebac0cf7-cccf-4b2e-a9a2-afa12c67c4de-discord`, sent at `2026-06-05T22:39:14.296Z`.
- Transcript cleanup:
  - Ran `scripts/import_spotify_transcripts.py --move` after delivery.
  - Result: `imported=0 skipped=24 removed=24 english_seen=17 chinese_seen=7`.
  - Verified `/Users/hannah/Downloads/Spotify Transcript Collector/` has `0` JSON files.
- Seen/processed marking:
  - `marked_seen=17 manifest=data/runs/20260606-054802-713197-manifest.json`
- Git status after delivery:
  - Current branch remains `feature/transpod-auto-translate`.
  - Worktree remains dirty with prior project/code/docs/generated-data changes. Do not stage generated `data/` blindly.
  - `git remote -v` was previously empty for this project repo; GitHub push for this repo still requires a configured remote/target repository.

## 2026-06-08 Monday 260608 Spotify Report Delivered (Transcript-Ready 15 Episodes)

- Used `spotify-mwf-report` skill workflow for the latest fixed M/W/F window.
- Window:
  - Source manifest: `data/runs/20260608-172952-597227-manifest.json`
  - Fixed schedule window: `2026-06-05T07:00:00+00:00` to `2026-06-08T07:00:00+00:00` (2026-06-05 15:00 to 2026-06-08 15:00 Asia/Shanghai).
  - Source episode count: 17.
  - Delivered transcript-ready manifest: `data/runs/20260608-172952-597227-transcript-ready-manifest.json`
  - Delivered episode count: 15.
- Transcript collection:
  - STD Chrome/Spotify detail-page workflow used; opened episode detail pages and clicked native Spotify `Transcript`.
  - Imported/available transcripts after final import: `english_seen=16`, `chinese_seen=5`.
  - Source evidence pack after retries: `data/runs/20260608-172952-597227-evidence-pack.json`, with `matched_count=15`, `missing_count=2`.
  - Delivered evidence pack: `data/runs/20260608-172952-597227-transcript-ready-evidence-pack.json`, with `matched_count=15`, `missing_count=0`.
  - Two episodes were excluded from the delivered report because no real transcript was available and no lower-fidelity fallback was used:
    - 厚雪长波 | `能分析数据不等于真的理解宏观经济，但AI快做到了`
    - All-In with Chamath, Jason, Sacks & Friedberg | `Inside the Private Stock Market Boom: SpaceX, Anthropic, OpenAI & the Rise of Secondaries`
  - Notes on missing transcripts:
    - The 厚雪长波 episode could not be found as an exact Spotify episode via search; Xiaoyuzhou/RSS pages exposed show notes and metadata but no accessible transcript text.
    - The All-In episode had an exact Spotify page, but the page had no native `Transcript` tab; Libsyn/RSS pages had notes only.
- Gemini report:
  - Package: `data/gemini_inputs/20260608-172952-597227-transcript-ready/`.
  - Chunk directory: `data/gemini_chunks/20260608-172952-597227-transcript-ready/`.
  - Final Markdown: `reports/markdown/20260608-172952-597227-transcript-ready-gemini-report.md`.
  - `gemini-2.5-flash` generated the first 6 episode briefs, then hit free-tier quota. Resumed with `gemini-2.5-flash-lite` for episodes 7-15 and final synthesis.
  - Review initially returned `需修改` with 7 non-verbatim quote warnings. Fixed by converting suspicious quoted text to explicit paraphrased conclusions.
  - Final review: `通过`.
  - Review files:
    - `data/runs/20260608-172952-597227-transcript-ready-gemini-review.json`
    - `reports/markdown/20260608-172952-597227-transcript-ready-gemini-review.md`
- Render/audit:
  - Word: `reports/word/260608-Spotify播客情报研报.docx`
  - PDF: `reports/pdf/260608-Spotify播客情报研报.pdf`
  - Delivery-format audit passed:
    - H2 count: 5.
    - Episode heading count: 15.
    - Required labels all counted 15 times.
    - PDF page count: 39.
    - No audit issues.
  - Final hashes:
    - DOCX SHA-256: `e0c8c8de662131582550f72c928255815e27c3013700363e5c6830b8165cedce`
    - PDF SHA-256: `1ade42621513cec525fc9b4f59da9a5f5c9342dea06f5abf0b9a308ae9a49b15`
- Zotero archive:
  - First attempt failed with `sqlite3.OperationalError: database is locked` because Zotero was open.
  - Quit Zotero, then archived successfully.
  - Direct PDF item: `archived_direct_pdf=4375 title=260608-Spotify播客情报研报`
  - Active Zotero PDF: `/Users/hannah/Zotero/storage/CRSSW8CA/260608-Spotify播客情报研报.pdf`
  - Zotero PDF hash matches local final PDF: `1ade42621513cec525fc9b4f59da9a5f5c9342dea06f5abf0b9a308ae9a49b15`
- External delivery:
  - Staged Drive DOCX: `reports/archive/pending/2606/google-drive/260608-Spotify播客情报研报.docx`
  - Staged Discord PDF: `reports/archive/pending/2606/discord-todo/260608-Spotify播客情报研报.pdf`
  - Staged hashes match local final files.
  - Google Drive upload completed through `rclone copy` to `gdrive:1.Spotify情报汇总/`.
  - Google Drive verification listing includes `260608-Spotify播客情报研报.docx`.
  - Discord delivery completed through live Discord Studio cwd `/Users/hannah/.discord-studio/Discord_Studio`.
  - Discord sent record: `notification_sent` id `1780915508154-2eca5a5a-a744-4c0a-aa4b-5fe9a01d451d-discord`, sent at `2026-06-08T10:46:05.518Z`.
  - Discord delivery workaround: `SPOTIFY_DISCORD_SEND_CMD` parsing failed because `.env` command quoting was stripped by `load_project_env()`. Direct `npm run send:discord` was used successfully. Fix `env_utils.load_project_env()` quoting behavior before relying on scheduled Discord sends.
  - Discord Studio watchdog issue observed: default port 3000 was already occupied and the watchdog log showed repeated `EADDRINUSE`; a temporary `PORT=3001 npm start` run consumed the queue and confirmed send. Investigate service/port ownership before trusting unattended delivery.
- Transcript cleanup:
  - Ran `scripts/import_spotify_transcripts.py --move` after delivery.
  - Result: `imported=0 skipped=21 removed=21 english_seen=16 chinese_seen=5`.
  - Verified `/Users/hannah/Downloads/Spotify Transcript Collector/` has `0` JSON files.
- Seen/processed marking:
  - `marked_seen=15 manifest=data/runs/20260608-172952-597227-transcript-ready-manifest.json`
  - The original 17-episode source manifest was not marked as fully delivered because 2 episodes still lack real transcripts.
- LaunchAgent/Git status after delivery:
  - LaunchAgent `com.hannah.spotify-podcast-report` remains `state = not running`, `runs = 1`, `last exit code = 78: EX_CONFIG`; manual delivery succeeded, but scheduled automation still needs config debugging.
  - Current branch remains `feature/transpod-auto-translate`.
  - `git remote -v` is empty for this project repo, so GitHub updates for this project still require a configured target remote.
  - Worktree remains dirty with prior code/docs/generated-data changes plus this report's generated artifacts. Do not stage generated `data/` blindly.

## 2026-06-08 260608 Report Revision Note

- User flagged that sections 3/4/5 of the 260608 report were too fragmented and read like per-episode summaries rather than integrated analysis.
- Root cause:
  - The chunked Gemini workflow generated strong per-episode briefs, but the final synthesis prompt over-preserved episode-level bullets.
  - Because the run resumed across `gemini-2.5-flash` and `gemini-2.5-flash-lite` after quota limits, the final synthesis was structurally safe but analytically conservative.
- Fix applied locally:
  - Rewrote sections 3/4/5 in `reports/markdown/20260608-172952-597227-transcript-ready-gemini-report.md` into integrated cross-episode analysis:
    - Section 3 now synthesizes production systems, organization systems, capital systems, infrastructure systems, and human judgment systems.
    - Section 4 now frames second-order shifts: execution scarcity to judgment scarcity, asset ownership to context ownership, speed to controllability, and model choice to trusted workflow systems.
    - Section 5 now gives unified strategic conclusions rather than audience-by-audience generic advice.
  - Reran Gemini report review: `通过`.
  - Rerendered local Word/PDF:
    - Word: `reports/word/260608-Spotify播客情报研报.docx`
    - PDF: `reports/pdf/260608-Spotify播客情报研报.pdf`
  - Reran delivery-format audit:
    - H2 count: 5.
    - Episode heading count: 15.
    - Required labels all counted 15 times.
    - PDF page count: 38.
    - No audit issues.
  - Revised local hashes:
    - DOCX SHA-256: `58f1741924e3efd0e94506334c44b97157262da03a3669dfbacdd6785a824e6d`
    - PDF SHA-256: `4828fd288deff6ed1d866d7e94eccd14a08768f02df531a2441834e4c2f145a2`
- Important: external copies on Google Drive, Discord, and Zotero still correspond to the originally delivered version unless explicitly re-uploaded/re-sent/re-archived.

## 2026-06-08 Mandatory Report Quality Gates

- User feedback from the 260608 PDF review must be treated as hard delivery gates for all future Spotify M/W/F reports, not optional style preferences.
- Main title gate:
  - The main report title must be constructive, insight-led, and immediately communicate the report's central thesis.
  - The title must include an English translation.
  - Never deliver a generic title, date pileup, run ID pileup, or a title that only says `Spotify 播客情报研报`.
  - A user should understand the report's main strategic theme from the title alone.
- Episode quote gate:
  - Every episode, including episode 1, must have `关键金句 / 结论` with the same quality standard.
  - For non-Chinese transcripts, include at least one source-language original sentence plus a Chinese translation/explanation on the next line.
  - Translation/explanation lines must be italicized and must not include labels like `中文解释：`, `中文翻译：`, `中文翻译/解释：`, `英文解释：`, `英文翻译：`, or `英文翻译/解释：`; write the translated/explanatory sentence directly.
  - If a quote cannot be verified as exact or near-exact from transcript, label it as `转述结论`; do not present it as a direct quote.
  - Root cause of the 260608 episode-1 issue: the quote cleanup/review step converted suspicious quote text into paraphrased conclusions to pass quote safety, but there was no second gate requiring episode 1 to still retain source-language original + translation quality. This is now a hard gate.
- Evidence-anchor gate:
  - Evidence anchors must be meaningful and should support a claim, example, mechanism, number, decision, disagreement, or strategic implication.
  - Do not include greetings, mutual thanks, ad reads, housekeeping, closing pleasantries, repeated intros/outros, or generic low-value anchors.
  - Screenshot example from user: an ending anchor like `[1:18:11] 播客结束时，Zach Braff 和主持人互相表达了感谢和欣赏。` is not meaningful evidence and must be removed before delivery.
- Synthesis gate:
  - Sections 3/4/5 must be integrated cross-episode analysis, second-order thinking, and strategic conclusions.
  - They must not read like episode-by-episode summaries grouped under loose topics.
- Process update:
  - These gates have been added to `/Users/hannah/.codex/skills/spotify-mwf-report/SKILL.md`, `/Users/hannah/.codex/skills/spotify-mwf-report/references/workflow.md`, and the project skill copy under `.codex-skills/spotify-mwf-report/`.
  - If the skill changes, sync the public GitHub skill archive as well.

## 2026-06-08 260608 Quote Formatting Correction

- User clarified the quote translation formatting rule:
  - Under `关键金句 / 结论`, all translation/explanation lines must be italicized.
  - Do not write label prefixes such as `中文解释：`, `中文翻译：`, `中文翻译/解释：`, `英文解释：`, `英文翻译：`, or `英文翻译/解释：`.
  - The correct format is source quote on one line, then a direct italicized translation/explanation on the next line.
- Applied to `reports/markdown/20260608-172952-597227-transcript-ready-gemini-report.md`:
  - Removed all `中文解释` / `中文翻译` label prefixes from quote translation lines.
  - Ensured translation/explanation lines use italic Markdown.
  - Episode 1 now has source-language original quotes plus direct italicized Chinese lines.
- Updated automation:
  - `scripts/generate_chunked_gemini_report.py` prompt now forbids translation labels and requires direct italic Chinese lines.
  - `scripts/audit_delivery_report_format.py` now fails if quote translation lines contain translation labels, and checks episode 1 for italicized Chinese translation/explanation.
  - Local skill and project skill workflow now record the same rule.
- Validation:
  - Reran Gemini report review: `通过`.
  - Rerendered DOCX/PDF with Microsoft Word.
  - Reran delivery-format audit: no issues; H2 count 5; episode heading count 15; required labels all counted 15 times; PDF page count 39.
  - Latest local hashes:
    - DOCX SHA-256: `d9ed42e6a9bab031b0c6da65428d103fe63cd869e4ed83b5d14fdcb5b84bc228`
    - PDF SHA-256: `36d6e9eaf143bb06a27e8ccfae1e908d50aac7e139275c000be2a75ec7737dcf`

## 2026-06-10 260608 Final Formatting Hardening

- User clarified four additional formatting requirements:
  - `英文翻译/解释：` label text is also forbidden; no translation/explanation prefix labels of any language should appear under `关键金句 / 结论`.
  - All translation/explanation lines, Chinese or English, must be italicized consistently.
  - The main title must read like a constructive thesis/synthesis sentence, not a list of abstract keywords.
  - Headings and subtitle-like bold lines must stay with their following body text; do not allow a heading alone at the bottom of a page.
- Applied to the 260608 report:
  - New main title: `把 AI 从效率工具变成可信生产系统：重构组织、所有权与判断力 (Turning AI from an Efficiency Tool into a Trusted Production System: Rebuilding Organizations, Ownership, and Judgment)`
  - Removed all `中文翻译/解释`, `中文解释`, `英文翻译/解释`, and related label prefixes from the Markdown.
  - Ensured translation/explanation lines are Markdown italic lines.
  - Fixed previously non-italic translation/explanation lines in episodes 14 and 15.
  - Rerendered DOCX/PDF with Microsoft Word.
  - Verified PDF page 34 no longer has a section/title orphan at the bottom; third-part title and following content remain together.
- Automation hardening:
  - `scripts/render_delivery_reports.py` now treats all key-quote translation/explanation lines as italic, not only Chinese lines.
  - `scripts/render_delivery_reports.py` now applies `keep_with_next` to generated report title and later-section bold subtitle paragraphs.
  - `scripts/audit_delivery_report_format.py` now blocks translation labels in Chinese or English, checks translation/explanation line italics, checks heading pagination flags, and checks later-section subtitle pagination flags.
  - Local skill and project skill copies now include the same no-label italic translation rule.
- Validation:
  - Reran Gemini report review: `通过`.
  - Reran delivery-format audit: no issues; H2 count 5; episode heading count 15; required labels all counted 15 times; PDF page count 39.
  - Latest local hashes:
    - DOCX SHA-256: `76b9344f8ea8c0fa6530b1a787871e1f9295ff66d5846d82d4d9d78826e187b4`
    - PDF SHA-256: `e6a136147e20fe8f4e3ade153975a6b755afb696ddce896fc0adf21336e8202b`

## 2026-06-10 Conditional Pagination Correction

- User clarified that part/section headings should not always start on a new page.
- Hard rule:
  - If a heading or subtitle-like bold heading and its following body would begin in the bottom quarter of a page, insert a page break before that heading.
  - If the heading is above the bottom quarter and there is enough readable space, do not force a new page.
  - This is a position-based rule, not a fixed "parts 3/4/5 always start new page" rule.
- Applied to the 260608 report:
  - The fifth part heading was appearing at the bottom of page 37.
  - Inserted `<!-- pagebreak -->` immediately before `## 第五部分：结论与战略意义` in the Markdown.
  - `scripts/render_delivery_reports.py` now supports `<!-- pagebreak -->` markers.
  - Rerendered DOCX/PDF with Microsoft Word.
  - Verified page 37 no longer contains `第五部分`; the fifth part now starts on page 38 with its body.
- Validation:
  - Gemini report review: `通过`.
  - Delivery-format audit: no issues; H2 count 5; episode heading count 15; required labels all counted 15 times; PDF page count 39.
  - Latest local hashes:
    - DOCX SHA-256: `785a0c23ebbba5a403e4bcf28fec9c2b69c6d6ba30e2a31bf9aaf2b137b2505a`
    - PDF SHA-256: `2adfdf687bfda077a8676247e8a6be4c787810d627fa570e606fd83aa8872483`
