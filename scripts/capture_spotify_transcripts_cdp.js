#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
let chromium;
try {
  ({ chromium } = require("playwright"));
} catch (_) {
  ({ chromium } = require("/Users/hannah/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright"));
}

const ROOT = path.resolve(__dirname, "..");
const DEFAULT_OUT_DIR = path.join(process.env.HOME || "", "Downloads", "Spotify Transcript Collector");
const DEFAULT_PORT = 9223;

function argValue(name, fallback = null) {
  const index = process.argv.indexOf(name);
  if (index === -1 || index + 1 >= process.argv.length) return fallback;
  return process.argv[index + 1];
}

function hasArg(name) {
  return process.argv.includes(name);
}

function clean(value) {
  return String(value || "unknown").replace(/[\\/:*?"<>|#%]/g, "_").trim();
}

function formatTimestamp(value) {
  let seconds = Math.max(0, Math.floor(Number(value) || 0));
  const hours = Math.floor(seconds / 3600);
  seconds -= hours * 3600;
  const minutes = Math.floor(seconds / 60);
  seconds -= minutes * 60;
  return hours
    ? `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`
    : `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function parseSpotifyTranscript(data) {
  const segments = [];
  let currentSpeaker = null;
  if (Array.isArray(data && data.section)) {
    for (const item of data.section) {
      const startSec = Number(item.startMs || 0) / 1000;
      let text = "";
      if (item.text && item.text.sentence) text = item.text.sentence.text || "";
      else if (item.text) text = item.text.text || "";

      let title = "";
      if (item.title) title = item.title.title || item.title.text || "";
      if (title && !text) {
        currentSpeaker = title.trim();
        continue;
      }
      if (!text.trim()) continue;
      segments.push({
        start: startSec,
        end: null,
        timestamp: formatTimestamp(startSec),
        speaker: item.speaker || currentSpeaker,
        text: text.trim(),
      });
    }
  } else if (Array.isArray(data && data.segments)) {
    for (const item of data.segments) {
      const startSec = item.startMs !== undefined ? Number(item.startMs) / 1000 : Number(item.start || 0);
      const endSec = item.endMs !== undefined ? Number(item.endMs) / 1000 : item.end || null;
      const text = String(item.text || item.words || "").trim();
      if (!text) continue;
      segments.push({
        start: startSec,
        end: endSec,
        timestamp: item.timestamp || formatTimestamp(startSec),
        speaker: item.speaker || null,
        text,
      });
    }
  }
  segments.sort((left, right) => left.start - right.start);
  for (let index = 0; index < segments.length; index += 1) {
    if (segments[index].end === null) {
      segments[index].end = index < segments.length - 1 ? segments[index + 1].start : null;
    }
  }
  return segments;
}

function extractSpotifyEpisodeId(url) {
  const match = String(url || "").match(/\/episode\/([A-Za-z0-9]+)/);
  return match ? match[1] : null;
}

function canonicalPodcastName(name) {
  const overrides = {
    "The AI Daily Brief": "The AI Daily Brief: Artificial Intelligence News and Analysis",
    "Lenny's Podcast: Product | Growth | Career": "Lenny's Podcast: Product | Career | Growth",
  };
  return overrides[name] || name;
}

async function main() {
  if (hasArg("--help")) {
    console.log(`Usage:
  node scripts/capture_spotify_transcripts_cdp.js --manifest data/runs/RUN-manifest.json --candidates data/runs/RUN-spotify-url-candidates.json

Requires Comet or Chrome to be running with a local DevTools port, for example:
  open -na /Applications/Comet.app --args --remote-debugging-port=9223 --user-data-dir="$HOME/Library/Application Support/Comet"
`);
    return;
  }

  const manifestPath = path.resolve(ROOT, argValue("--manifest"));
  const candidatesPath = path.resolve(ROOT, argValue("--candidates"));
  const outDir = path.resolve(argValue("--out-dir", DEFAULT_OUT_DIR));
  const port = Number(argValue("--port", DEFAULT_PORT));
  const executablePath = argValue("--executable");
  const launched = hasArg("--launch");
  fs.mkdirSync(outDir, { recursive: true });

  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  const candidates = JSON.parse(fs.readFileSync(candidatesPath, "utf8"));
  const browser = launched
    ? await chromium.launch({ headless: true, executablePath: executablePath || undefined })
    : await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
  const context = launched ? await browser.newContext() : browser.contexts()[0];
  const results = [];

  for (const row of candidates.filter((item) => item.best && item.best.href && item.best.score >= 0.9)) {
    const episode = manifest.new_episodes[row.index - 1];
    const page = await context.newPage();
    let captured = null;
    const spotifyEpisodeId = extractSpotifyEpisodeId(row.best.href);
    if (!spotifyEpisodeId) {
      results.push({ index: row.index, status: "invalid_spotify_url", url: row.best.href });
      await page.close();
      continue;
    }
    page.on("response", async (response) => {
      const url = response.url();
      if (
        /transcript-read-along|episode-transcripts|transcript/i.test(url) &&
        url.includes("/episode/") &&
        url.includes(`/episode/${spotifyEpisodeId}`)
      ) {
        try {
          captured = { url, data: await response.json() };
        } catch (_) {
          // Ignore non-JSON transcript-adjacent responses.
        }
      }
    });

    process.stderr.write(`OPEN ${row.index} ${row.best.href}\n`);
    try {
      await page.goto(row.best.href, { waitUntil: "domcontentloaded", timeout: 60000 });
      await page.waitForTimeout(6500);
    } catch (error) {
      results.push({ index: row.index, status: "open_failed", url: row.best.href, error: error.message });
      await page.close();
      continue;
    }
    try {
      await page.getByText("Transcript", { exact: true }).first().click({ timeout: 10000 });
    } catch (error) {
      process.stderr.write(`CLICK_FAIL ${row.index} ${error.message}\n`);
    }
    for (let attempt = 0; attempt < 20 && !captured; attempt += 1) {
      await page.waitForTimeout(1000);
    }

    if (!captured) {
      results.push({ index: row.index, status: "missing", url: row.best.href });
      await page.close();
      continue;
    }

    const segments = parseSpotifyTranscript(captured.data);
    const payload = {
      source: "spotify_api_cdp",
      capturedAt: new Date().toISOString(),
      spotifyEpisodeId,
      episodeUrl: row.best.href,
      podcastName: canonicalPodcastName(episode.podcast_title),
      episodeTitle: episode.episode_title,
      publishedDate: String(episode.published_at || "").slice(0, 10),
      duration: episode.duration || null,
      transcriptLanguage: captured.data.language || null,
      isAutoGenerated: captured.data.isAutoGenerated ?? captured.data.autoGenerated ?? "unknown",
      segments,
      raw: captured.data,
      debugLogs: [`Captured via browser DevTools Protocol from ${captured.url}`],
    };
    const filename = `${payload.publishedDate} - ${clean(payload.podcastName)} - ${clean(payload.episodeTitle)} - ${clean(spotifyEpisodeId)}.json`;
    fs.writeFileSync(path.join(outDir, filename), JSON.stringify(payload, null, 2));
    results.push({ index: row.index, status: "saved", segments: segments.length, filename });
    process.stderr.write(`SAVED ${row.index} segments=${segments.length} ${filename}\n`);
    await page.close();
  }

  await browser.close();
  console.log(JSON.stringify(results, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
