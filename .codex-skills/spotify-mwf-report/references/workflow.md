# Spotify MWF Report Workflow

## 1. Orient

- Read `/Users/hannah/Documents/Codex/GLOBAL_MEMORY.md`, then `PROJECT_MEMORY.md`.
- Check `git status --short`, current branch, and whether a GitHub remote exists.
- Check LaunchAgent:
  - `launchctl print gui/501/com.hannah.spotify-podcast-report`
  - Confirm whether it is running or merely has an old nonzero exit code.
- Check recent service logs in `data/service_logs/`.
- Never restart from an old blocker if a newer memory section says delivery completed.

## 2. Determine Window And Manifest

- Prefer the project scripts and schedule logic already in the repo.
- For fixed windows, avoid overlapping reports. If a prior report included post-cutoff episodes, dedupe before generating the next report.
- Keep the manifest path explicit in all later commands.
- Run the late-arriving RSS audit against current RSS before accepting a manifest as complete:
  - `scripts/audit_late_rss_arrivals.py --since <previous-window-since> --until <current-window-until> --require-clean`
  - Include at least the current report window and the previous closed M/W/F window.
  - If the audit finds any episode that now appears in RSS but was not manifested or marked seen, treat it as a hard blocker. Collect transcripts and add the episode to the latest/current report as the final episode, with a clear note that identifies its original intended M/W/F window, such as `迟到补入，原属 <YYMMDD> 窗口`. Do not create a separate supplement PDF by default. Only regenerate a past-window report instead when Hannah explicitly asks for that.
  - This check exists because some feeds can publish or refresh late while backdating `published_at`, which can make an episode belong to an already delivered report window even though it was absent from RSS during the original run.

## 3. Transcript Collection

- First run the project pipeline/evidence step to learn exactly which transcripts are missing.
- Preferred CDP native transcript workflow:
  - Use the user's logged-in Comet/Chrome session with a local DevTools port when available.
  - Run `scripts/capture_spotify_transcripts_cdp.js` with the current manifest and verified Spotify URL candidates.
  - The script opens each Spotify episode detail page, waits for the tab area, clicks `Transcript`, captures Spotify's native transcript API, and writes STD-compatible original transcript JSON into `/Users/hannah/Downloads/Spotify Transcript Collector/`.
  - The captured transcript API URL must include the exact target Spotify episode ID before the file is saved. If it does not match, discard the response and retry; stale/cached responses from another episode must never be archived under the current episode filename.
  - Import with `scripts/import_spotify_transcripts.py`, then rerun the pipeline/evidence audit. This is the first-choice path because it is faster, avoids Gemini token use, and captures the same native transcript source.
- STD fallback workflow:
  - Use Chrome with the user's logged-in Spotify session and STD extension.
  - Open each Spotify episode detail page, not a search result page.
  - Click the native Spotify `Transcript` tab.
  - Do not decide "no transcript" from the first partial DOM render. Reload the verified episode detail URL and wait about `6.5` seconds for Spotify's Description/Transcript/Chapters tab list; only declare missing after that tab list is available and no `Transcript` tab appears.
  - Wait for STD to download JSON files into `/Users/hannah/Downloads/Spotify Transcript Collector/`.
  - Use one tab sequentially if Spotify complains about too many open tabs.
- Import transcripts:
  - `scripts/import_spotify_transcripts.py`
- Enforce archive uniqueness by `spotifyEpisodeId + language`:
  - Keep at most one original transcript and one complete Chinese transcript per episode.
  - Treat Chrome retry suffixes such as ` (1)` as duplicate downloads, not distinct archives.
  - Reject `_zh_INCOMPLETE` and any Chinese file containing an untranslated non-empty segment.
- Rerun evidence/language audit and confirm required transcript coverage.
- For late-arriving RSS backfills, transcript coverage must be checked exactly like a normal run: original/English transcript first, then Chinese archive completeness or a recorded blocker. The final report should include the backfilled item at the end of 第二部分 unless Hannah explicitly asks to rebuild the older report.
- Chinese transcript gaps must be handled promptly. English/original transcript coverage is still the main generation gate unless the user explicitly requires Chinese, and Chinese transcripts must not be used as the report-generation source by default. However, Chinese transcripts are required archive/completeness artifacts: if any are missing, immediately start or queue backfill and keep retrying until complete or explicitly recorded as a temporary external-service/plugin blocker.
- After English/original coverage is complete, start or record a resumable Chinese backfill:
  - Use `scripts/translate_spotify_transcripts_to_zh.py --evidence-pack <evidence-pack> --status-json data/background_jobs/<run_id>-zh-translation-status.json`.
  - Source must be the exact archived original transcript JSON referenced by the evidence pack.
  - The translator writes `sourceTranscriptSha256`, provider metadata, and complete segment translations; it must skip already complete Chinese files.
  - If Google Translate is rate-limited, paused, or blocked, record the completed/missing Chinese count in `PROJECT_MEMORY.md`, create/retain a resumable status file under `data/background_jobs/`, and resume as soon as the blocker clears. Do not let Chinese gaps silently persist across runs. Do not delay Gemini/report delivery after original/English coverage is complete.

## 4. Gemini Report

- Use the repo's pipeline scripts, usually chunked Gemini mode.
- If Codex requests approval because transcript/evidence will be sent to Gemini, ask/accept explicit user approval and do not bypass a rejection.
- After generation, run the Gemini review checker with `data/gemini_inputs/<run_id>/episode-manifest.json` as the manifest whenever that file exists; it contains the Spotify episode URLs used in the report. Do not use the raw run manifest for this check when it lacks `spotify_episode_url`.
- If review says `需修改`, fix concrete findings and rerun review until `通过`.
- Convert suspicious non-verbatim quote blocks to explicit paraphrased conclusions rather than keeping them in quotation marks.
- Before rendering, manually inspect the Markdown for the following hard gates:
  - Main title is constructive and thesis-led: it should tell the user what this report is really about, not merely repeat the date/run/window. It must include an English translation.
  - Sections 3/4/5 are integrated cross-episode analysis, second-order thinking, and strategic conclusions. They must not read as per-episode summaries grouped under loose topics.
  - Episode 1 has the same `关键金句 / 结论` quality as every other episode, including meaningful source-language original sentences and italicized translation/explanation lines when useful. Translation lines must not include labels like `中文解释：`, `中文翻译：`, `中文翻译/解释：`, `英文解释：`, `英文翻译：`, or `英文翻译/解释：`.
  - Evidence anchors are meaningful: remove greetings, thanks, ad reads, housekeeping, closing pleasantries, and generic low-value anchors. Keep anchors with concrete claims, examples, mechanisms, numbers, decisions, disagreements, or strategic implications.
  - If exact quote verification is weak, return to transcript JSON and select exact, verifiable source lines; do not downgrade to `转述结论` unless a real transcript scan confirms no meaningful verifiable original quote exists.

## 5. Render And Audit

- Render Word/PDF with `scripts/render_delivery_reports.py`.
- Do not accept lower-fidelity PDF fallback for final delivery unless the user explicitly approves it.
- Run `scripts/audit_delivery_report_format.py` on the DOCX and PDF.
- Confirm:
  - Main title is constructive, has English translation, and has no run ID/date pileup.
  - Expected main sections.
  - Episode heading count matches manifest.
  - Required labels match episode count.
  - `关键金句 / 结论` exists for every episode including episode 1, with meaningful source-language original quotes plus italicized unlabeled translation/explanation. `转述结论` is allowed only after transcript-level verification proves no meaningful quote exists.
  - Evidence anchors are substantive and do not contain low-value greetings/thanks/housekeeping as final anchors.
  - Pagination quality: if a heading or subtitle-like bold heading and the following body begin in the bottom quarter of a page, insert `<!-- pagebreak -->` before that heading and rerender. Do not force all major sections onto new pages; apply the break only when the heading position is too low.
  - Line-breaking quality: punctuation must stay attached to the end of the preceding line in the final PDF. Do not accept punctuation as the first character on a new line; fix and rerender before delivery.
  - PDF page count is plausible.
  - No audit issues.
- Record final DOCX/PDF paths and hashes.

## 6. Zotero

- If local Zotero DB writes are used, quit Zotero first when configured or when a lock is likely.
- Archive as direct PDF with `/unread` and month tag such as `/2606`.
- Verify local PDF hash matches active Zotero storage PDF with `scripts/verify_zotero_report_pdfs.py`.
- Record Zotero storage path and hash in memory.

## 7. External Delivery

- Stage files:
  - DOCX to `reports/archive/pending/<YYMM>/google-drive/`
  - PDF to `reports/archive/pending/<YYMM>/discord-todo/`
- Verify staged hashes match local finals.
- Google Drive:
  - Use configured rclone command.
  - Verify listing contains the uploaded DOCX.
- Discord:
  - Use `/Users/hannah/.discord-studio/Discord_Studio` as `SPOTIFY_DISCORD_CWD`.
  - Queue with `npm run send:discord -- <channel_id> <message> <pdf>`.
  - Verify live queue has `notification_sent`.
  - If an old queue path was used by mistake, mark old queued items as superseded to avoid future duplicate sends.

## 8. Cleanup And Mark Seen

- Always clean STD Downloads after report review and required delivery succeed:
  - `scripts/import_spotify_transcripts.py --move`
  - Verify `/Users/hannah/Downloads/Spotify Transcript Collector/` has zero JSON files.
- Audit the current evidence pack's episode IDs in `data/transcripts/spotify_en/` and `data/transcripts/spotify_zh/` after cleanup. Confirm each language has at most one file per episode and report `duplicate_ids=0` for both directories. A missing complete Chinese transcript may be reported as a gap; an incomplete or duplicate file must not be retained to make coverage appear complete.
- Rerun the late-arriving RSS audit after cleanup and before mark-seen. A clean result is required for completion.
- Mark manifests seen only after delivery gates pass:
  - `scripts/mark_manifest_seen.py <manifest>`
- If any required external delivery is blocked and not skipped by the user, or transcript archive deduplication fails, do not mark seen.

## 9. Memory And Git

- Update `PROJECT_MEMORY.md` with:
  - Manifest, episode count, report paths.
  - Final constructive bilingual title.
  - Review/audit result.
  - Confirmation that title, episode 1 quote quality, and evidence-anchor quality gates passed.
  - Zotero path/hash.
  - Drive verification.
  - Discord `notification_sent` ids.
  - Transcript cleanup result.
  - Formal original/Chinese transcript counts and duplicate-ID audit result.
  - Mark-seen result.
  - Any root cause found during debugging.
- For git:
  - Do not stage generated data blindly.
  - Separate code/docs/config changes from large generated artifacts.
  - If no remote exists, tell the user GitHub cannot be updated until a target repo is configured.

## 10. Final Response

- State what was completed and what remains blocked.
- Include concrete paths and verification results.
- If a delivery channel was blocked by approval policy, say so plainly and do not imply it succeeded.
