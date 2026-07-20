#!/usr/bin/env node
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
let chromium;
try {
  ({ chromium } = require("playwright"));
} catch (_) {
  ({ chromium } = require("/Users/hannah/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright"));
}

const ROOT = path.resolve(__dirname, "..");
const DEFAULT_ZH_DIR = path.join(ROOT, "data", "transcripts", "spotify_zh");
const TRANSLATE_URL = "https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=auto&tl=zh-CN&dt=t";

function argValue(name, fallback = null) {
  const index = process.argv.indexOf(name);
  if (index === -1 || index + 1 >= process.argv.length) return fallback;
  return process.argv[index + 1];
}

function argValues(name) {
  const values = [];
  for (let index = 0; index < process.argv.length; index += 1) {
    if (process.argv[index] === name && index + 1 < process.argv.length) values.push(process.argv[index + 1]);
  }
  return values;
}

function hasArg(name) {
  return process.argv.includes(name);
}

function clean(value) {
  return String(value || "unknown").replace(/[\\/:*?"<>|#%]/g, "_").trim();
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function sha256(filePath) {
  return crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
}

function targetPath(sourceData, chineseDir) {
  const date = String(sourceData.publishedDate || "unknown").slice(0, 10);
  const podcast = clean(sourceData.podcastName);
  const title = clean(`${sourceData.episodeTitle || "unknown"}_zh`);
  const episodeId = clean(sourceData.spotifyEpisodeId);
  return path.join(chineseDir, `${date} - ${podcast} - ${title} - ${episodeId}.json`);
}

function isCompleteZh(filePath, sourceHash = null) {
  if (!fs.existsSync(filePath) || path.basename(filePath).toLowerCase().includes("_zh_incomplete")) return false;
  try {
    const data = readJson(filePath);
    if (sourceHash && data.sourceTranscriptSha256 && data.sourceTranscriptSha256 !== sourceHash) return false;
    if (!Array.isArray(data.segments) || data.segments.length === 0) return false;
    return !data.segments.some((segment) => segment && segment.text && !segment.translation);
  } catch (_) {
    return false;
  }
}

function cjkRatio(text) {
  const letters = Array.from(text).filter((char) => !/\s/.test(char));
  if (!letters.length) return 0;
  return letters.filter((char) => char >= "\u4e00" && char <= "\u9fff").length / letters.length;
}

function sourceIsChinese(segments) {
  let sample = "";
  for (const segment of segments) {
    if (segment && segment.text) sample += `${segment.text}\n`;
    if (sample.length >= 2000) break;
  }
  return cjkRatio(sample) >= 0.35;
}

function payloadToText(payload) {
  if (Array.isArray(payload) && payload.length && typeof payload[0] === "string") return payload.join("");
  if (Array.isArray(payload) && Array.isArray(payload[0]) && typeof payload[0][0] === "string") return payload[0][0];
  let translated = "";
  if (Array.isArray(payload) && Array.isArray(payload[0])) {
    for (const item of payload[0]) {
      if (item && item[0]) translated += String(item[0]);
    }
  }
  return translated;
}

function chunkIndices(segments, maxChars) {
  const chunks = [];
  let current = [];
  let currentChars = 0;
  for (let index = 0; index < segments.length; index += 1) {
    const text = String((segments[index] && segments[index].text) || "").trim().replace(/\n/g, " ");
    if (!text) continue;
    if (current.length && currentChars + text.length + 1 > maxChars) {
      chunks.push(current);
      current = [];
      currentChars = 0;
    }
    current.push(index);
    currentChars += text.length + 1;
  }
  if (current.length) chunks.push(current);
  return chunks;
}

async function sleep(ms) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function translateText(page, text, timeoutMs) {
  return page.evaluate(
    async ({ url, text, timeoutMs }) => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({ q: text }),
          signal: controller.signal,
        });
        const body = await response.text();
        if (!response.ok) throw new Error(`HTTP ${response.status}: ${body.slice(0, 200)}`);
        return body;
      } finally {
        clearTimeout(timeout);
      }
    },
    { url: TRANSLATE_URL, text, timeoutMs }
  );
}

async function translateIndices(page, segments, indices, options) {
  if (!indices.length) return true;
  const text = indices.map((index) => String(segments[index].text || "").trim().replace(/\n/g, " ")).join("\n");
  for (let attempt = 1; attempt <= options.maxRetries; attempt += 1) {
    try {
      const raw = await translateText(page, text, options.timeoutMs);
      const translated = payloadToText(JSON.parse(raw));
      const translations = translated.split("\n").map((line) => line.trim());
      if (translations.length >= indices.length && indices.every((_, offset) => translations[offset])) {
        indices.forEach((index, offset) => {
          segments[index].translation = translations[offset];
        });
        if (options.delayMs > 0) await sleep(options.delayMs);
        return true;
      }
      if (indices.length > 1) {
        const middle = Math.ceil(indices.length / 2);
        const leftOk = await translateIndices(page, segments, indices.slice(0, middle), options);
        const rightOk = await translateIndices(page, segments, indices.slice(middle), options);
        return leftOk && rightOk;
      }
      throw new Error(`Translate returned ${translations.filter(Boolean).length}/${indices.length} lines`);
    } catch (error) {
      if (attempt === options.maxRetries) return false;
      await sleep(Math.min(60000, 5000 * attempt));
    }
  }
  return false;
}

function sourcePathsFromEvidence(evidencePackPath, onlyIndices) {
  const pack = readJson(evidencePackPath);
  const paths = [];
  for (const episode of pack.episodes || []) {
    if (onlyIndices.size && !onlyIndices.has(Number(episode.index || 0))) continue;
    const transcriptPath = episode.transcript && episode.transcript.path;
    if (!transcriptPath) continue;
    paths.push(path.resolve(ROOT, transcriptPath));
  }
  return Array.from(new Set(paths));
}

async function translateFile(page, sourcePath, options) {
  const sourceData = readJson(sourcePath);
  const sourceHash = sha256(sourcePath);
  const outputPath = targetPath(sourceData, options.chineseDir);
  if (!options.force && isCompleteZh(outputPath, sourceHash)) {
    return { source: sourcePath, target: outputPath, status: "skipped_complete" };
  }
  const segments = Array.isArray(sourceData.segments) ? sourceData.segments.filter((segment) => segment && typeof segment === "object").map((segment) => ({ ...segment })) : [];
  if (!segments.length) return { source: sourcePath, target: outputPath, status: "blocked_no_segments" };

  if (sourceIsChinese(segments)) {
    for (const segment of segments) {
      if (segment.text && !segment.translation) segment.translation = segment.text;
    }
    const output = {
      ...sourceData,
      sourceTranscriptSha256: sourceHash,
      translationProvider: "source_already_zh",
      translationTargetLanguage: "zh-CN",
      translatedAt: new Date().toISOString(),
      segments,
      debugLogs: [...(sourceData.debugLogs || []), `Source transcript is already Chinese; copied text into translation for ${segments.length} segments.`],
    };
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    const tmpPath = `${outputPath}.tmp`;
    fs.writeFileSync(tmpPath, JSON.stringify(output, null, 2), "utf8");
    if (!isCompleteZh(tmpPath, sourceHash)) {
      fs.unlinkSync(tmpPath);
      return { source: sourcePath, target: outputPath, status: "blocked_validation_failed" };
    }
    fs.renameSync(tmpPath, outputPath);
    return { source: sourcePath, target: outputPath, status: "copied_source_chinese", segments_count: segments.length };
  }

  for (const chunk of chunkIndices(segments, options.maxChars)) {
    const ok = await translateIndices(page, segments, chunk, options);
    if (!ok) {
      const missing = segments.flatMap((segment, index) => (segment.text && !segment.translation ? [index] : []));
      return {
        source: sourcePath,
        target: outputPath,
        status: "blocked_incomplete_translation",
        missing_translation_segments_count: missing.length,
        first_missing_indices: missing.slice(0, 20),
      };
    }
  }

  const missing = segments.flatMap((segment, index) => (segment.text && !segment.translation ? [index] : []));
  if (missing.length) {
    return {
      source: sourcePath,
      target: outputPath,
      status: "blocked_incomplete_translation",
      missing_translation_segments_count: missing.length,
      first_missing_indices: missing.slice(0, 20),
    };
  }

  const output = {
    ...sourceData,
    sourceTranscriptSha256: sourceHash,
    translationProvider: "google_translate_clients5_comet_cdp",
    translationTargetLanguage: "zh-CN",
    translatedAt: new Date().toISOString(),
    segments,
    debugLogs: [...(sourceData.debugLogs || []), `Translated from ${path.basename(sourcePath)} with google_translate_clients5_comet_cdp; complete=${segments.length} segments.`],
  };
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  const tmpPath = `${outputPath}.tmp`;
  fs.writeFileSync(tmpPath, JSON.stringify(output, null, 2), "utf8");
  if (!isCompleteZh(tmpPath, sourceHash)) {
    fs.unlinkSync(tmpPath);
    return { source: sourcePath, target: outputPath, status: "blocked_validation_failed" };
  }
  fs.renameSync(tmpPath, outputPath);
  return { source: sourcePath, target: outputPath, status: "translated_complete", segments_count: segments.length };
}

async function main() {
  if (hasArg("--help")) {
    console.log("Usage: node scripts/translate_spotify_transcripts_to_zh_cdp.js --evidence-pack data/runs/RUN-evidence-pack.json");
    return;
  }
  const evidencePack = argValue("--evidence-pack");
  const sourceArgs = argValues("--source");
  const onlyIndices = new Set(argValues("--only-index").map(Number));
  const chineseDir = path.resolve(ROOT, argValue("--chinese-dir", DEFAULT_ZH_DIR));
  const statusJson = argValue("--status-json");
  const port = Number(argValue("--port", "9223"));
  const maxChars = Number(argValue("--max-chars", "700"));
  const timeoutMs = Number(argValue("--timeout-ms", "25000"));
  const delayMs = Number(argValue("--delay-ms", "500"));
  const maxRetries = Number(argValue("--max-retries", "3"));
  const force = hasArg("--force");

  let sourcePaths = [];
  if (evidencePack) sourcePaths = sourcePaths.concat(sourcePathsFromEvidence(path.resolve(ROOT, evidencePack), onlyIndices));
  sourcePaths = sourcePaths.concat(sourceArgs.map((value) => path.resolve(ROOT, value)));
  sourcePaths = Array.from(new Set(sourcePaths));
  if (!sourcePaths.length) throw new Error("No source transcripts provided.");

  const browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
  const context = browser.contexts()[0];
  const page = await context.newPage();
  await page.goto("https://open.spotify.com/", { waitUntil: "domcontentloaded", timeout: 30000 }).catch(() => {});

  const results = [];
  for (const sourcePath of sourcePaths) {
    const result = await translateFile(page, sourcePath, {
      chineseDir,
      maxChars,
      timeoutMs,
      delayMs,
      maxRetries,
      force,
    });
    results.push(result);
    console.log(JSON.stringify(result));
  }
  await page.close();
  await browser.close();

  const payload = {
    created_at: new Date().toISOString(),
    source_count: sourcePaths.length,
    complete_count: results.filter((item) => ["translated_complete", "skipped_complete", "copied_source_chinese"].includes(item.status)).length,
    blocked_count: results.filter((item) => item.status.startsWith("blocked")).length,
    results: results.sort((left, right) => left.source.localeCompare(right.source)),
  };
  if (statusJson) {
    fs.mkdirSync(path.dirname(path.resolve(ROOT, statusJson)), { recursive: true });
    fs.writeFileSync(path.resolve(ROOT, statusJson), JSON.stringify(payload, null, 2), "utf8");
  }
  if (payload.blocked_count) process.exit(2);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
