# Changelog & Extension Documentation (V2.1.9)

This extension has been completely updated to handle automated and manual podcast transcript collection from Spotify Web Player.

* **Critical Fixes & Decoupling (V2.1.9)**:
  * **Relative Day-of-Week Parsing**: Added a multi-language mapping of week days (e.g. Wednesday, Monday, 周三, 星期一, miércoles, etc.) in `parseRelativeDate`. These are automatically resolved to their corresponding calendar dates in the past week relative to the browser's current local time, enabling accurate date parsing for fresh podcast episodes published within the last 7 days.

* **Critical Fixes & Decoupling (V2.1.8)**:
  * **H2 Boundary Constraint on DOM Date Scraping**: Restructured `findPublishedDate` to do a linear scan of elements in document order and stop immediately upon hitting the first `H2` heading element (e.g. "About" or "More episodes like this"). This prevents the scanner from matching publication dates of other episodes listed in the recommendations section at the bottom of the page.

* **Critical Fixes & Decoupling (V2.1.7)**:
  * **Fix Sibling Concatenation Bug**: Replaced `el.textContent` with `el.innerText || el.textContent` in DOM date scraping and split compound strings on both newlines (`\n`) and bullet points (`•`, `·`, `●`). This resolves the bug where `"May 15"` and `"30 min"` concatenated without spaces into `"May 1530 min"`, causing it to match `"1530"` as the year.
  * **Restrict Year Regex Match boundaries**: Constrained all 4-digit year matchers in `parseDateFromString` to `(?:19|20)\d{2}`. This prevents durations (like `"1530 min"` or other random numbers) from being parsed as years.
  * **Bypass Title Check Wait on Refreshes**: Updated `isDOMReadyForEpisode` to return `true` immediately if the target episode ID is found anywhere in the DOM (e.g. in links/buttons inside the main content view). This removes the 3-second delay when direct-loading or refreshing an episode page.

* **Critical Fixes & Decoupling (V2.1.6)**:
  * **Decoupled API Episode ID Tracking**: Extracted the target episode ID directly from the intercepted transcript API URL instead of using the polled route-changed URL state. This completely removes the race condition where fast-loading APIs were associated with previous episode metadata.
  * **Main Content H1 Constraints**: Restricted the query selectors for `h1` and `showLink` strictly to the `main` content pane (`main`, `[role="main"]`), preventing the scraper from grabbing static left-sidebar titles like `"Your Library"` or buddy-feed components.
  * **Precise Route-Load Synchronization**: Added a browser URL check inside the polling loop to ensure DOM metadata is only scraped once the browser's address bar matches the intercepted API's episode ID.
* **Critical Fixes & Diagnostics (V2.1.5)**:
  * **Anchored Relative Date Matchers**: Fixed a major bug where podcasts containing keywords like "today" (e.g. `"Today, Explained"`) or "yesterday" (e.g. `"Yesterday's News"`) in their names were matching the relative date regex as substrings, forcing the published date to fallback to today's date. Anchored all relative date matches using `^` and `$`.
  * **Fixed Playlist Link Race Condition**: Removed the `hasNewId` DOM check from `isDOMReadyForEpisode` that was matching playlist sidebar items containing the new episode ID before React re-rendered the main content pane. This completely stops metadata from previous episodes leaking into new downloads.
  * **Embedded Diagnostics Payload**: Embedded a `debugLogs` array directly inside the downloaded JSON payload. If there are any discrepancies in title or date matching, you can inspect the JSON's `debugLogs` to trace exactly what DOM elements the extension scanned and what checks succeeded.
* **Performance & Synchronization (V2.1.4)**:
  * **SPA Re-render Synchronization**: Fixed a major SPA route transition issue where the downloader immediately read the *old* page's DOM (names, titles, dates) before React finished re-rendering the new episode's page. Implemented `isDOMReadyForEpisode` to watch for the H1 text change or new episode ID attributes, guaranteeing that we never download transcripts with misaligned metadata.
  * **Fast Polling Optimization**: Reduced the polling interval from 500ms to 200ms, checking up to 15 times (3s max). Once the DOM is ready, the download is triggered *instantly* with zero unnecessary delay (under 400ms on typical navigation).
* **Bug Fix (V2.1.3)**: Corrected an `Uncaught ReferenceError: Cannot access 'month' before initialization` runtime crash on line 662 of `content.js` caused by a typo referencing `month[1]` instead of `match[1]` during Month-Year parsing.

---

## 📂 Changed Files
* **`manifest.json`**: Standard MV3 downloads declaration.
* **`background.js`**: 
  * Implemented a `chrome.downloads.onDeterminingFilename` listener to explicitly force Chrome to use our custom filename and subdirectory structure (`Spotify Transcript Collector/`), bypassing default UUID-based naming issues (like `626d0097-f22b-42c9-8eef-6148913030f9.json`) and conflicts.
* **`injected.js`**: Injected script monkey-patching both `window.fetch` and `XMLHttpRequest` at page start. Captures responses matching `transcript`, `episode-transcripts`, or `transcript-read-along`.
* **`content.js`**: 
  * **Episode Release Date Prioritization**: Enforced that the date prefix in the filename is the **actual upload/publish date of the episode** (scraped from the HTML meta tags, JSON-LD, or DOM release date strings), rather than the transcript's on-the-fly generation date (which is usually today's download date).
  * **Intelligent Metadata Polling**: Instead of a static 1.5s delay, the script now dynamically polls the DOM for metadata/date elements up to 10 times at a 500ms interval (maximum 5 seconds). If the metadata is found sooner, the download triggers instantly.
  * **Buddy Feed/Sidebar Date Isolation**: Confined general DOM date scanning exclusively to the main content area (e.g. `main` or `[role="main"]`). This completely prevents the script from being fooled by relative timestamps inside the "Friend Activity" or buddy-feed sidebars (e.g., "today", "1h ago"), which previously aborted retries prematurely and leaked today's date into the filename.
  * **Show-Link Wrapper Proximity Target**: Added a parent-level loop from the H1 (title) to find the nearest element wrapping the podcast show link, perfectly isolating the episode banner header for target-rich date scanning.
  * **Robust Multi-Language Date Recognition**: Refactored the parsing engine to support relative and absolute dates across English, Chinese (simplified/traditional), Spanish, Portuguese, German, French, and Italian.
  * **Year-Omission Fallback**: Added auto-detection and estimation of the current year for dates that omit it (e.g. "May 24" or "5月24日").
  * **Bullet-Split Parsing**: Implemented bullet (`•`, `·`, `●`) separator splitting for compound metadata blocks (e.g., "Show Name • Date • Duration") to isolate the date string and prevent regex mismatching.
  * **Expanded DOM Traversal**: Removed the zero-child element restriction (`el.children.length === 0`) to prevent skipping elements that wrap date strings alongside styling tags or screen-reader nodes (`.sr-only`), and restricted evaluation to nodes under 100 characters.
  * Monitors SPA routing changes (every 1s), displays a premium monochrome floating UI panel, and manages hash-based content deduplication.

---

## 📄 Transcript JSON Output Format
Each downloaded `.json` file contains:
```json
{
  "source": "spotify_dom" | "spotify_api",
  "capturedAt": "2026-05-24T01:50:16Z",
  "spotifyEpisodeId": "3E1adYXk5KvfGFlEJbdhY1",
  "episodeUrl": "https://open.spotify.com/episode/...",
  "podcastName": "Modern Wisdom",
  "episodeTitle": "The New Way Of The Superior Man - David Deida - #1101",
  "duration": 5077.28, // Optional
  "transcriptLanguage": "en-us", // Optional
  "isAutoGenerated": true | false | "unknown",
  "segments": [
    {
      "start": 0.16,
      "end": 3.4,
      "timestamp": "0:00",
      "speaker": "Speaker 1" | null,
      "text": "..."
    }
  ],
  "raw": {} // Present only if source is "spotify_api" (raw API response)
}
```

---

## 🗂️ Download Directory & Filename Rules
* **Directory**: Saved automatically inside the subdirectory `Spotify Transcript Collector/` under your default Downloads folder.
* **Filename Pattern**:
  `{published_date_or_unknown} - {podcast_name} - {episode_title} - {spotify_episode_id}.json`
  * Date Format: `YYYY-MM-DD` (Standardized `YYYY-MM-DD` parsed directly from the API response or DOM tags).
  * Safe Strings: Files and folders are cleaned of illegal path/filename characters (like `\`, `/`, `:`, `*`, `?`, `"`, `<`, `>`, `|`, `#`, `%`) by replacing them with `_`.

---

## 🧪 How to Test & Reload
1. Open Google Chrome and go to `chrome://extensions/`.
2. Toggle on **Developer mode** (top right corner).
3. Find the **Spotify Podcast Transcript Downloader** extension card.
4. Click the **Reload (circular arrow icon)** on the card to apply the new changes.
5. **IMPORTANT**: Disable or remove any older versions of the extension to prevent conflict.
6. Open any Spotify Podcast Episode page:
   `https://open.spotify.com/episode/...`
7. Verify that it automatically captures the transcript, showing `✓ Transcript captured and downloaded.` in the floating panel, and downloads it with the correct filename inside `Downloads/Spotify Transcript Collector/`.
