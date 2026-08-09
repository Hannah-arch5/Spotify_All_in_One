# Spotify Podcast Report Production Automation

This project should run scheduled production reports outside an interactive Codex session. Codex is useful for development and diagnosis, but external uploads and local app control are intentionally approval-gated in Codex.

## Production entrypoint

Use:

```bash
/Users/hannah/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 /Users/hannah/Documents/Spotify\ All\ in\ One/scripts/run_scheduled_report_service.py
```

The service runner performs these steps in order:

1. Check the fixed Monday / Wednesday / Friday 15:00 Asia/Shanghai schedule window.
2. Build episode list, transcript audit, evidence pack, Spotify collection queue, Gemini input package, Gemini report, and Gemini review.
3. Optionally block before Gemini if Chinese transcript coverage is incomplete.
4. Render Word/PDF through Microsoft Word, without ReportLab fallback.
5. Run delivery-format audit.
6. Archive the direct PDF item to Zotero and verify Zotero/local PDF hashes match.
7. Stage the Word file for Google Drive and the PDF for Discord, verifying hashes.
8. Upload the Word file to Google Drive using the configured command.
9. Send the PDF to Discord using the configured command.
10. Mark the manifest episodes as processed only after all required delivery checks pass.

## Environment

Copy `.env.example` to `.env` and fill in real values. `.env` is ignored by git.

Important variables:

- `GEMINI_API_KEY`: Gemini API key.
- `SPOTIFY_REQUIRE_ZH_TRANSCRIPTS=1`: block if any episode lacks a Chinese transcript.
- `SPOTIFY_ZOTERO_QUIT_BEFORE_WRITE=1`: quit Zotero before local sqlite writes.
- `SPOTIFY_GOOGLE_DRIVE_UPLOAD_CMD`: command that uploads the DOCX to `1.Spotify情报汇总`.
- `SPOTIFY_GOOGLE_DRIVE_VERIFY_CMD`: optional command that verifies Drive upload visibility.
- `SPOTIFY_DISCORD_SEND_CMD`: command that sends the PDF to Discord.
- `SPOTIFY_DISCORD_CWD`: working directory for the Discord command.
- `SPOTIFY_DISCORD_CHANNEL_ID`: target Discord channel.

Example command templates:

```dotenv
SPOTIFY_GOOGLE_DRIVE_UPLOAD_CMD=rclone copy "{docx}" "gdrive:1.Spotify情报汇总/" --checksum
SPOTIFY_GOOGLE_DRIVE_VERIFY_CMD=rclone lsf "gdrive:1.Spotify情报汇总/" --files-only
SPOTIFY_DISCORD_CWD=/Users/hannah/.discord-studio/Discord_Studio
SPOTIFY_DISCORD_SEND_CMD=npm run send:discord -- "{channel_id}" "{message}" "{pdf}"
```

The runner does not invoke a shell for these templates; it expands placeholders and splits arguments with shell-style quoting.

## LaunchAgent example

Save this as `~/Library/LaunchAgents/com.hannah.spotify-podcast-report.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.hannah.spotify-podcast-report</string>

  <key>ProgramArguments</key>
  <array>
    <string>/Users/hannah/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3</string>
    <string>/Users/hannah/Documents/Spotify All in One/scripts/run_scheduled_report_service.py</string>
  </array>

  <key>WorkingDirectory</key>
  <string>/Users/hannah/Documents/Spotify All in One</string>

  <key>StartCalendarInterval</key>
  <array>
    <dict>
      <key>Weekday</key>
      <integer>1</integer>
      <key>Hour</key>
      <integer>15</integer>
      <key>Minute</key>
      <integer>0</integer>
    </dict>
    <dict>
      <key>Weekday</key>
      <integer>3</integer>
      <key>Hour</key>
      <integer>15</integer>
      <key>Minute</key>
      <integer>0</integer>
    </dict>
    <dict>
      <key>Weekday</key>
      <integer>5</integer>
      <key>Hour</key>
      <integer>15</integer>
      <key>Minute</key>
      <integer>0</integer>
    </dict>
  </array>

  <key>StandardOutPath</key>
  <string>/Users/hannah/Documents/Spotify All in One/data/service_logs/launchd.stdout.log</string>

  <key>StandardErrorPath</key>
  <string>/Users/hannah/Documents/Spotify All in One/data/service_logs/launchd.stderr.log</string>

  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
```

Load it with:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.hannah.spotify-podcast-report.plist
```

Run once on demand with:

```bash
launchctl kickstart -k gui/$(id -u)/com.hannah.spotify-podcast-report
```

## Notes

- The service writes structured run logs to `data/service_logs/`.
- If a step fails, the service exits non-zero and does not mark episodes processed.
- Zotero local DB writes are safe only when Zotero is not holding the sqlite lock. Prefer Zotero API for long-term robustness if available.
- Google Drive upload must be folder-aware. Do not upload to Drive root as a workaround.
