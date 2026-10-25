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

- Enumerate all pending scheduled reports before collection. If more than one report is pending, create separate dated manifests for the entire backlog and prepare all their transcripts before generating any report. This is the default workflow, not an exception that needs renewed permission.
- Prefer the project scripts and schedule logic already in the repo.
- For fixed windows, avoid overlapping reports. If a prior report included post-cutoff episodes, dedupe before generating the next report.
- Keep the manifest path explicit in all later commands.
- Run the late-arriving RSS audit against current RSS before accepting a manifest as complete:
  - `scripts/audit_late_rss_arrivals.py --since <previous-window-since> --until <current-window-until> --require-clean`
  - Include at least the current report window and the previous closed M/W/F window.
  - If the audit finds any episode that now appears in RSS but was not manifested or marked seen, treat it as a hard blocker. Use `published_at` to identify the original fixed M/W/F window. If that window's report is not yet generated or archived, add the episode to that original report. If the original report is already completed/archived, or the gap is too old to reopen cleanly, append the episode to the latest report as the final episode and record `迟到补入，原属 <YYMMDD> 窗口`. Never merge two complete windows wholesale or hide the original date.
  - This check exists because some feeds can publish or refresh late while backdating `published_at`, which can make an episode belong to an already delivered report window even though it was absent from RSS during the original run.

## 3. Transcript Collection

- For multiple pending reports, finish collection and complete Chinese backfill across every manifest first. Reuse already verified archives rather than downloading them again; do not merge windows or mark reports seen during preparation. Require each manifest's identity checks, language audit and `audit_transcript_archive_integrity.py --require-clean` to pass before entering report generation. A collection/translation blocker pauses batch generation until resolved or explicitly waived by Hannah.
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
  - Verify where the file actually landed. If STD instead produces `/Users/hannah/Downloads/download.json`, validate its target `spotifyEpisodeId` and metadata, move only that file into the original archive under a descriptive name, and compare SHA-256 before continuing. Do not import unrelated JSON or retain retry copies.
  - If the Spotify title has changed, retain the manifest's RSS title and record the manually verified Spotify identity in `spotify_episode_id` / `spotify_episode_url`; the evidence builder uses the exact ID and fails closed on missing or duplicate identities.
  - Perform collection through a permitted installed-plugin workflow rather than assigning the full queue to Hannah. Do not disable security controls or treat a blocked debugging interface as repaired merely because a separate permitted STD workflow succeeds.
  - Use one tab sequentially if Spotify complains about too many open tabs.
- Import transcripts:
  - `scripts/import_spotify_transcripts.py`
- Enforce archive uniqueness by `spotifyEpisodeId + language`:
  - Keep at most one original transcript and one complete Chinese transcript per episode.
  - Treat Chrome retry suffixes such as ` (1)` as duplicate downloads, not distinct archives.
  - Reject `_zh_INCOMPLETE` and any Chinese file containing an untranslated non-empty segment.
- Rerun evidence/language audit and confirm required transcript coverage.
- Back up the prepared subtitles independently of the report review boundary:
  - Local original archive: `data/transcripts/spotify_en/` (contains English and Chinese-program originals); Chinese archive: `data/transcripts/spotify_zh/`.
  - Google Drive `Spotify字幕` holds actual English original JSON; child `Spotify字幕-中文` holds complete Chinese JSON. Chinese-program originals belong to the Chinese destination through their complete Chinese archive artifact, not the English root.
  - Run `scripts/backup_spotify_transcripts_to_drive.py --evidence-pack <evidence-pack>` for each ready manifest. For multiple reports, finish their subtitle preparation/backups before generation. This subtitle-backup authorization does not authorize uploading an unreviewed DOCX/PDF.
  - Local `.env` pins `SPOTIFY_TRANSCRIPT_DRIVE_FOLDER_ID` and `SPOTIFY_TRANSCRIPT_ZH_DRIVE_FOLDER_ID`; `SPOTIFY_TRANSCRIPT_BACKUP_ENABLED=1` enables the pipeline/service integration. Keep these account-specific values out of Git. The pipeline backs up ready files before Gemini; final service delivery requires the complete current-report subtitle backup again before external report delivery/mark-seen.
  - Use incremental `copy`, never destructive `sync`; retain local files and cloud extras. Verify every selected remote file's unique name, size and MD5, and save the receipt under `data/service_logs/`. A full-history backup without `--evidence-pack` backs up all available valid archives and separately lists historical Chinese gaps; do not call those gaps complete. Never suppress current-report missing-Chinese failures.
- For late-arriving RSS backfills, transcript coverage must be checked exactly like a normal run: original/English transcript first, then Chinese archive completeness or a recorded blocker. The final report should include the backfilled item at the end of 第二部分 unless Hannah explicitly asks to rebuild the older report.
- Chinese transcript gaps must be handled promptly. For multiple pending reports, full original and Chinese coverage across the backlog is the generation gate. For a single report, original coverage remains the main generation gate unless Hannah requires Chinese first. Chinese must not be used as the report-generation source by default. If any Chinese archives are missing, immediately start or queue backfill and follow through until complete or explicitly recorded as a temporary external-service/plugin blocker.
- After English/original coverage is complete, start or record a resumable Chinese backfill:
  - Use `scripts/translate_spotify_transcripts_to_zh.py --evidence-pack <evidence-pack> --status-json data/background_jobs/<run_id>-zh-translation-status.json`.
  - If command-line translation/proxy access is blocked but the user's logged-in Comet browser can reach the Google Translate-style endpoint, use `scripts/translate_spotify_transcripts_to_zh_cdp.js --evidence-pack <evidence-pack> --status-json data/background_jobs/<run_id>-zh-cdp-translation-status.json --port 9223` as a non-Gemini backfill route.
  - Source must be the exact archived original transcript JSON referenced by the evidence pack.
  - The translator writes `sourceTranscriptSha256`, provider metadata, and complete segment translations; it must skip already complete Chinese files.
  - If Google Translate is rate-limited, paused, or blocked, record the completed/missing Chinese count in `PROJECT_MEMORY.md`, create/retain a resumable status file under `data/background_jobs/`, and resume as soon as the blocker clears. Do not let Chinese gaps silently persist across runs. The multiple-report batch gate requires resolving these gaps before generation; for a single report, original coverage can permit generation while backfill continues unless Hannah requires otherwise.

## 4. Gemini Report

- When multiple reports were pending, confirm that every dated manifest has passed transcript preparation before generating the oldest report. Then make and review/deliver each report separately in date order; advance collection does not waive the PDF review boundary or the per-report completion gates.
- Use the repo's pipeline scripts, usually chunked Gemini mode.
- For a long window, generate resumable episode briefs with `generate_chunked_gemini_report.py --briefs-only`, review them against the originals, then use `assemble_gemini_report_from_briefs.py` for compact integrated synthesis. This avoids spending an extra oversized full-report request. Keep editorial provenance honest and review synthesis for unsupported cross-episode claims.
- Compact synthesis inputs must retain the core summary and its concrete mechanism, not only value claims and memorable quotes. Distinguish speaker views, vendor test results and report inferences in the integrated sections; preserve uncertainty rather than laundering a prediction or allegation into fact. Chinese-source sentences containing English technical terms do not need a duplicate Chinese translation.
- If Hannah asks to finish all pending reports before uploading, complete each separate dated draft and its native-PDF QA in order, then present the batch for approval. Do not upload or mark any issue seen while the batch is pending. Otherwise preserve the normal per-issue review/delivery sequence.
- If Codex requests approval because transcript/evidence will be sent to Gemini, ask/accept explicit user approval and do not bypass a rejection.
- After generation, run the Gemini review checker with `data/gemini_inputs/<run_id>/episode-manifest.json` as the manifest whenever that file exists; it contains the Spotify episode URLs used in the report. Do not use the raw run manifest for this check when it lacks `spotify_episode_url`.
- If review says `需修改`, fix concrete findings and rerun review until `通过`.
- If native Word Save/Export is unexpectedly disabled while the desktop is available, cancel the export dialog, use Word's Window -> Bring All to Front, then retry the same local PDF destination. This restored saving on 2026-10-25; AX `noWindowsAvailable` alone does not prove the Mac is locked. Do not change browser permissions or substitute a lower-fidelity PDF.
- Convert suspicious non-verbatim quote blocks to explicit paraphrased conclusions rather than keeping them in quotation marks.
- Before rendering, manually inspect the Markdown for the following hard gates:
  - Main title is constructive and thesis-led: it should tell the user what this report is really about, not merely repeat the date/run/window. It must include an English translation.
  - Sections 3/4/5 are integrated cross-episode analysis, second-order thinking, and strategic conclusions. They must not read as per-episode summaries grouped under loose topics.
  - Episode 1 has the same `关键金句 / 结论` quality as every other episode, including meaningful source-language original sentences and italicized translation/explanation lines when useful. Translation lines must not include labels like `中文解释：`, `中文翻译：`, `中文翻译/解释：`, `英文解释：`, `英文翻译：`, or `英文翻译/解释：`.
  - Evidence anchors are meaningful: remove greetings, thanks, ad reads, housekeeping, closing pleasantries, and generic low-value anchors. Keep anchors with concrete claims, examples, mechanisms, numbers, decisions, disagreements, or strategic implications.
  - Every English evidence anchor is a transcript-verifiable source sentence followed immediately by an unlabeled italic Chinese translation on its own line. Chinese-source anchors stay as one Chinese source line and are not redundantly translated.
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
  - Every English evidence anchor is followed immediately by an unlabeled italic Chinese translation; Chinese-source anchors are not duplicated. This must pass both the Markdown checker and the final DOCX audit.
  - Verify source/translation semantic alignment after normalization and again in the PDF. If a long English anchor needs trimming, select a shorter meaningful original and update its Chinese translation together; preserving the old translation after source-only trimming is not acceptable.
  - Pagination quality: if a heading or subtitle-like bold heading and the following body begin in the bottom quarter of a page, insert `<!-- pagebreak -->` before that heading and rerender. Do not force all major sections onto new pages; apply the break only when the heading position is too low.
  - Line-breaking quality: punctuation must stay attached to the end of the preceding line in the final PDF. Do not accept punctuation as the first character on a new line; fix and rerender before delivery.
  - PDF page count is plausible.
  - No audit issues.
- Record final DOCX/PDF paths and hashes.

## 6. Zotero

- If local Zotero DB writes are used, quit Zotero first when configured or when a lock is likely.
- Archive as direct PDF with `/unread` and month tag such as `/2606`.
- If an exact-title item already exists, repair missing required tags rather than treating a blind skip as success. Preserve intentional `/read` or `/reading`; never reset either state to `/unread`.
- Verify the local PDF hash and required tags together with `scripts/verify_zotero_report_pdfs.py --require-tags <pdf>`. Delivery is incomplete if either `/unread` or the scheduled month tag is missing.
- For a collection-wide unread repair, scope only to `1.Spotify情报汇总` and its descendants, exclude deleted and unrelated items, quit Zotero normally, back up the SQLite database, preserve every existing tag, and run `scripts/audit_zotero_report_tags.py --repair --require-clean --receipt <path>`. Reopen Zotero only after the clean receipt is saved.
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
- Run `scripts/audit_transcript_archive_integrity.py <evidence-pack> --require-clean`; it must confirm one original and one complete Chinese transcript per episode, with zero missing, duplicate, or incomplete IDs.
- Rerun `scripts/backup_spotify_transcripts_to_drive.py --evidence-pack <evidence-pack>` if any subtitle changed during backfill/cleanup. Require its verified cloud receipt before mark-seen; the approved report uploads remain separate.
- Rerun the late-arriving RSS audit after cleanup and before mark-seen. A clean result is required for completion.
- Require the Zotero PDF hash and tag verification to pass before mark-seen. A successful file copy with missing `/unread` or month tag is not complete.
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

## Semiannual Local Retention

- Drive is the long-term full archive; local subtitle JSON normally spans 6-12 months. The existing cleanup automation now runs January 1 and July 1 at 15:00 Asia/Shanghai, replacing the quarterly 90-day preview.
- First run a fresh full subtitle Drive backup and require both language receipts to verify. Preview `scripts/prune_transcripts.py --keep-months 6 --backup-receipt <fresh-receipt.json>`, inspect the saved plan, then use the same arguments plus `--delete` for the authorized scheduled cleanup. Separate English/Chinese receipts can be supplied by repeating `--backup-receipt`.
- A receipt older than one hour, incorrect folder, changed local SHA-256, unknown publication date, pending report reference, or outstanding Chinese backfill blocks deletion of the affected file. A Chinese original may be cleared only if the verified cloud Chinese artifact preserves its complete original data and source hash. Keep exceptions and report them; never force deletion to hit a size limit.
- Use publication dates, not download/modification dates. Never delete Drive backups, report documents or unrelated files. Record actual deleted count/bytes and protected exceptions in Memory. Subtitle retention does not change report windows or mark-seen state.

## 10. Final Response

- State what was completed and what remains blocked.
- Include concrete paths and verification results.
- If a delivery channel was blocked by approval policy, say so plainly and do not imply it succeeded.
