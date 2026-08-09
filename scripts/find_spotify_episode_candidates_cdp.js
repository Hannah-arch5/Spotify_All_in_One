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
const DEFAULT_PORT = 9223;

function argValue(name, fallback = null) {
  const index = process.argv.indexOf(name);
  if (index === -1 || index + 1 >= process.argv.length) return fallback;
  return process.argv[index + 1];
}

function hasArg(name) {
  return process.argv.includes(name);
}

function normalize(value) {
  return String(value || "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[’‘“”]/g, "'")
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function tokens(value) {
  return normalize(value).split(" ").filter(Boolean);
}

function tokenScore(left, right) {
  const wanted = tokens(left);
  const seen = new Set(tokens(right));
  if (!wanted.length || !seen.size) return 0;
  let hits = 0;
  for (const token of wanted) {
    if (seen.has(token)) hits += 1;
  }
  return hits / wanted.length;
}

function scoreCandidate(episode, candidate) {
  const wantedTitle = episode.episode_title || "";
  const wantedPodcast = episode.podcast_title || "";
  const haystack = `${candidate.title || ""} ${candidate.aria || ""} ${candidate.href || ""}`;
  const titleScore = tokenScore(wantedTitle, haystack);
  const podcastScore = tokenScore(wantedPodcast, haystack);
  return Math.max(titleScore * 0.82 + podcastScore * 0.18, titleScore);
}

function searchUrl(episode) {
  const query = `${episode.podcast_title} ${episode.episode_title}`;
  return `https://open.spotify.com/search/${encodeURIComponent(query)}/episodes`;
}

function searchUrls(episode) {
  const title = String(episode.episode_title || "");
  const strippedTitle = title
    .replace(/\|.*$/, "")
    .replace(/#\d+.*$/, "")
    .replace(/\([^)]*\)/g, " ")
    .replace(/[–—-]\s*#[0-9]+.*/, "")
    .trim();
  const queries = [
    `${episode.podcast_title} ${title}`,
    title,
    strippedTitle,
    `${episode.podcast_title} ${strippedTitle}`,
  ].filter((value, index, all) => value && all.indexOf(value) === index);
  return queries.map((query) => `https://open.spotify.com/search/${encodeURIComponent(query)}/episodes`);
}

async function linksFromSearch(page, url) {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(5500);
  return page.evaluate(() => {
    const rows = [];
    const seen = new Set();
    for (const anchor of document.querySelectorAll('a[href*="/episode/"]')) {
      const href = new URL(anchor.href, location.href).href.split("?")[0];
      if (seen.has(href)) continue;
      seen.add(href);
      const box = anchor.closest('[role="row"], [data-testid], li, div') || anchor;
      rows.push({
        href,
        title: anchor.textContent || "",
        aria: anchor.getAttribute("aria-label") || box.textContent || "",
      });
    }
    return rows.slice(0, 12);
  });
}

async function main() {
  const manifestPath = path.resolve(ROOT, argValue("--manifest"));
  const outPath = path.resolve(
    ROOT,
    argValue("--out", manifestPath.replace(/-manifest\.json$/, "-spotify-url-candidates.json")),
  );
  const port = Number(argValue("--port", DEFAULT_PORT));
  const executablePath = argValue("--executable");
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  const episodes = manifest.new_episodes || manifest.episodes || [];
  const launched = hasArg("--launch");
  const browser = launched
    ? await chromium.launch({ headless: true, executablePath: executablePath || undefined })
    : await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
  const context = launched ? await browser.newContext() : browser.contexts()[0];
  const page = await context.newPage();
  const results = [];

  for (let index = 0; index < episodes.length; index += 1) {
    const episode = episodes[index];
    const candidates = [];
    try {
      const seen = new Set();
      for (const url of searchUrls(episode)) {
        const links = await linksFromSearch(page, url);
        for (const link of links) {
          if (seen.has(link.href)) continue;
          seen.add(link.href);
          candidates.push({
            href: link.href,
            title: link.title,
            aria: link.aria,
            score: scoreCandidate(episode, link),
          });
        }
        candidates.sort((left, right) => right.score - left.score);
        if (candidates[0] && candidates[0].score >= 0.9) break;
      }
    } catch (error) {
      results.push({ index: index + 1, error: error.message, best: null, candidates: [] });
      continue;
    }
    candidates.sort((left, right) => right.score - left.score);
    const best = candidates[0] ? { href: candidates[0].href, score: Number(candidates[0].score.toFixed(3)) } : null;
    results.push({ index: index + 1, best, candidates: candidates.slice(0, 5) });
    process.stderr.write(`${index + 1}. ${best ? best.score : "none"} ${best ? best.href : "no match"}\n`);
  }

  await page.close();
  await browser.close();
  fs.writeFileSync(outPath, JSON.stringify(results, null, 2));
  console.log(outPath);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
