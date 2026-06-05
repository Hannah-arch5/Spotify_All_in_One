// content.js - Runs in the extension context on open.spotify.com
// [STD] Handles UI button creation, route changes, DOM scraping, API event listening, and download requests.

console.log("[STD] Content script successfully loaded.");

// 1. Inject injected.js at document_start
const script = document.createElement("script");
script.src = chrome.runtime.getURL("injected.js");
(document.head || document.documentElement).appendChild(script);
script.onload = function () {
  this.remove(); // Clean up after injection
};

// Global states
let currentEpisodeId = "";
const downloadedMap = new Map(); // episodeId -> transcriptHash
const pendingApiCaptures = new Map(); // episodeId -> { url, data, capturedAt }
const debugLogs = [];

function logDebug(msg) {
  const message = `[STD-DEBUG] ${msg}`;
  console.log(message);
  debugLogs.push(`[${new Date().toISOString()}] ${msg}`);
}

// Start Single Page Application (SPA) routing checker loop
setInterval(checkRouteChange, 1000);

function checkRouteChange() {
  const match = window.location.href.match(/episode\/([a-zA-Z0-9]+)/);
  const newEpisodeId = match ? match[1] : "";
  if (newEpisodeId !== currentEpisodeId) {
    console.log(`[STD] Route changed from ${currentEpisodeId || "none"} to ${newEpisodeId || "none"}`);
    currentEpisodeId = newEpisodeId;
    updatePanelUI();

    if (newEpisodeId && pendingApiCaptures.has(newEpisodeId)) {
      const pending = pendingApiCaptures.get(newEpisodeId);
      pendingApiCaptures.delete(newEpisodeId);
      logDebug(`Route matched cached API transcript for ${newEpisodeId}. Processing cached data.`);
      setTimeout(() => handleAPICaptured(pending.url, pending.data), 0);
    }
  }
}

// 2. Listen for messages from injected.js API interceptor
window.addEventListener("message", (event) => {
  if (event.source !== window) return;
  if (event.data && event.data.type === "SPOTIFY_TRANSCRIPT_API_CAPTURED") {
    const { url, data } = event.data;
    handleAPICaptured(url, data);
  }
});

function isDOMReadyForEpisode(oldTitle, episodeId) {
  if (!episodeId) return false;

  // 1. First, the browser URL must match the target episode ID
  if (!window.location.href.includes(episodeId)) {
    logDebug(`DOM check: Browser URL does not match target episode ID ${episodeId} yet.`);
    return false;
  }

  // 2. Locate the H1 inside the main content area
  const mainContent = document.querySelector('main, [role="main"], .main-view-container, .Root__main-view');
  if (!mainContent) {
    logDebug("DOM check: Main content container not found yet.");
    return false;
  }

  const h1 = mainContent.querySelector('h1');
  if (!h1) {
    logDebug("DOM check: H1 element inside main content area not found yet.");
    return false;
  }
  
  const currentTitle = h1.textContent.trim();
  logDebug(`DOM check: Current H1 title is "${currentTitle}".`);
  
  if (!currentTitle || currentTitle === "Library" || currentTitle === "Your Library") {
    logDebug("DOM check: H1 title is a placeholder or empty.");
    return false;
  }
  
  let isReady = false;
  if (oldTitle && currentTitle !== oldTitle) {
    logDebug("DOM check: H1 title has changed from the old title.");
    isReady = true;
  } else {
    // If the title is the same (e.g. on direct page loads/refreshes), check if the episode ID is referenced in DOM
    const hasEpisodeRef = mainContent.querySelector(`[href*="${episodeId}"], [data-uri*="${episodeId}"], [data-testid*="${episodeId}"]`);
    if (hasEpisodeRef) {
      logDebug(`DOM check: Found episode ID reference ${episodeId} in DOM.`);
      isReady = true;
    }
  }

  if (!isReady) {
    logDebug("DOM check: H1 title has not changed and no episode ID reference found in DOM yet.");
    return false;
  }
  
  // 3. Verify the show link is also present in the main content area (header rendering verification)
  const showLink = mainContent.querySelector('a[href^="/show/"], a[data-testid="show-link"]');
  if (!showLink) {
    logDebug("DOM check: Show link not found inside main content area yet.");
    return false;
  }
  
  logDebug(`DOM check success! H1 is "${currentTitle}", Show Link: "${showLink.innerText}".`);
  return true;
}

function handleAPICaptured(url, data) {
  // Extract episode ID directly from the intercepted transcript API URL
  const apiMatch = url.match(/episode\/([a-zA-Z0-9]+)/);
  const apiEpisodeId = apiMatch ? apiMatch[1] : "";
  if (!apiEpisodeId) {
    logDebug("Could not extract episode ID from intercepted URL.");
    return;
  }

  const segments = parseAPIJson(data);
  if (!segments) {
    logDebug("Intercepted API data did not contain valid transcript segments.");
    return;
  }

  const hash = getTranscriptHash(segments);
  const existingHash = downloadedMap.get(apiEpisodeId);

  if (existingHash === hash) {
    logDebug(`API transcript for ${apiEpisodeId} matches already downloaded version. Skipping.`);
    return;
  }

  if (!window.location.href.includes(apiEpisodeId)) {
    pendingApiCaptures.set(apiEpisodeId, { url, data, capturedAt: Date.now() });
    logDebug(`API transcript for ${apiEpisodeId} does not match current URL. Cached for later route match.`);
    return;
  }

  // Clear previous debug logs for this new session
  debugLogs.length = 0;
  logDebug(`Captured API request for episode ID: ${apiEpisodeId}`);

  // Capture the old title immediately before navigation re-renders the DOM
  const mainContent = document.querySelector('main, [role="main"], .main-view-container, .Root__main-view');
  const h1 = mainContent ? mainContent.querySelector('h1') : document.querySelector('h1');
  const oldTitle = h1 ? h1.textContent.trim() : "";
  logDebug(`Old title at capture time: "${oldTitle}"`);

  let retryCount = 0;
  const maxRetries = 15; // 15 * 200ms = 3 seconds total wait time
  const retryInterval = 200;

  function attemptExtraction() {
    // Re-check if browser is still on (or transitioning to) the same episode ID
    if (!window.location.href.includes(apiEpisodeId)) {
      pendingApiCaptures.set(apiEpisodeId, { url, data, capturedAt: Date.now() });
      logDebug(`Browser URL changed away from target episode ${apiEpisodeId}. Cached for later route match.`);
      return;
    }

    // Wait until the DOM has fully updated to the new episode
    const isReady = isDOMReadyForEpisode(oldTitle, apiEpisodeId);
    if (!isReady && retryCount < maxRetries) {
      retryCount++;
      logDebug(`DOM not ready. Retrying in ${retryInterval}ms... (Attempt ${retryCount}/${maxRetries})`);
      setTimeout(attemptExtraction, retryInterval);
      return;
    }

    const metadata = getPageMetadata();
    logDebug(`Extracted page metadata: Title: "${metadata.episodeTitle}", Show: "${metadata.podcastName}", Date: "${metadata.publishedDate}"`);
    
    // Determine episode title & podcast show name
    let episodeTitle = metadata.episodeTitle;
    if (!episodeTitle || episodeTitle === "Your Library" || episodeTitle === "Library" || episodeTitle === "unknown_episode") {
      episodeTitle = data.episodeName || data.name || "unknown_episode";
      logDebug(`Fell back to API episode title: "${episodeTitle}"`);
    }
    
    let podcastName = metadata.podcastName || data.showName || "unknown_podcast";
    
    // Date prioritization
    let publishedDate = "unknown";
    if (metadata.publishedDate && metadata.publishedDate !== "unknown") {
      publishedDate = metadata.publishedDate;
    } else if (data.publishedAt && typeof data.publishedAt === 'string') {
      const dateMatch = data.publishedAt.match(/^(\d{4}-\d{2}-\d{2})/);
      if (dateMatch) {
        publishedDate = dateMatch[1];
        logDebug(`Fell back to API publishedAt date: "${publishedDate}"`);
      }
    }

    const isAutoGenerated = data.isAutoGenerated !== undefined ? data.isAutoGenerated : 
                            (data.autoGenerated !== undefined ? data.autoGenerated : "unknown");

    const payload = {
      source: "spotify_api",
      capturedAt: new Date().toISOString(),
      spotifyEpisodeId: apiEpisodeId,
      episodeUrl: window.location.href,
      podcastName: podcastName,
      episodeTitle: episodeTitle,
      publishedDate: publishedDate,
      duration: data.duration || null,
      transcriptLanguage: data.language || null,
      isAutoGenerated: isAutoGenerated,
      segments: segments,
      raw: data,
      debugLogs: [...debugLogs] // Inject copy of debugging logs
    };

    downloadedMap.set(apiEpisodeId, hash);
    
    const finalMeta = {
      episodeTitle: episodeTitle,
      podcastName: podcastName,
      publishedDate: publishedDate
    };
    
    logDebug(`Triggering auto-download with filename date: ${publishedDate}`);
    triggerDownload(payload, finalMeta);
    
    const translateCb = document.getElementById('std-auto-translate-cb');
    if (translateCb && translateCb.checked) {
      setTimeout(async () => {
        logDebug(`Starting background translation...`);
        const statusEl = document.getElementById('std-status-text');
        if (statusEl) statusEl.innerHTML = `<span style="color: #FFA500;">Translating transcript...</span>`;
        
        await batchTranslateSegments(payload.segments);
        
        const translatedMeta = { ...finalMeta };
        translatedMeta.episodeTitle = finalMeta.episodeTitle + "_zh";
        triggerDownload(payload, translatedMeta);
        
        if (statusEl) statusEl.innerHTML = `<span style="color: #00FF00;">✓ Translation downloaded.</span>`;
      }, 500);
    }
  }

  // Start the extraction attempts
  attemptExtraction();
}

function handleManualDownload() {
  if (!currentEpisodeId) return;

  console.log("[STD] Manual download button clicked. Extracting transcript from DOM...");
  const segments = extractSegmentsFromDOM();

  if (segments) {
    const hash = getTranscriptHash(segments);
    const metadata = getPageMetadata();

    const payload = {
      source: "spotify_dom",
      capturedAt: new Date().toISOString(),
      spotifyEpisodeId: currentEpisodeId,
      episodeUrl: window.location.href,
      podcastName: metadata.podcastName,
      episodeTitle: metadata.episodeTitle,
      publishedDate: metadata.publishedDate,
      isAutoGenerated: "unknown",
      segments: segments,
      debugLogs: [...debugLogs]
    };

    downloadedMap.set(currentEpisodeId, hash);
    triggerDownload(payload, metadata);

    const translateCb = document.getElementById('std-auto-translate-cb');
    if (translateCb && translateCb.checked) {
      setTimeout(async () => {
        const statusEl = document.getElementById('std-status-text');
        if (statusEl) statusEl.innerHTML = `<span style="color: #FFA500;">Translating transcript...</span>`;
        
        await batchTranslateSegments(payload.segments);
        
        const translatedMeta = { ...metadata };
        translatedMeta.episodeTitle = metadata.episodeTitle + "_zh";
        triggerDownload(payload, translatedMeta);
        
        if (statusEl) statusEl.innerHTML = `<span style="color: #00FF00;">✓ Translation downloaded.</span>`;
      }, 500);
    }
  } else {
    alert("No transcript elements visible in DOM. Please open or expand the Transcript view on Spotify first!");
  }
}

async function batchTranslateSegments(segments) {
  if (!segments || segments.length === 0) return;
  console.log(`[STD] Starting batch translation for ${segments.length} segments...`);
  
  let currentChunkText = "";
  let currentChunkIndices = [];
  
  const flushChunk = async (text, indices) => {
    if (!text) return;
    try {
      const url = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=zh-CN&dt=t`;
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: `q=${encodeURIComponent(text)}`
      });
      const res = await response.json();
      
      let translatedText = "";
      if (res && res[0]) {
        res[0].forEach(item => {
          if (item[0]) translatedText += item[0];
        });
      }
      
      const translations = translatedText.split('\n').map(s => s.trim());
      for (let i = 0; i < indices.length; i++) {
        segments[indices[i]].translation = translations[i] || "";
      }
      
      // Add a small delay to avoid Google Translate API rate limit (HTTP 429)
      await new Promise(r => setTimeout(r, 1000));
    } catch (err) {
      console.error("[STD] Translation chunk failed:", err);
    }
  };

  for (let i = 0; i < segments.length; i++) {
    const textToTranslate = segments[i].text.trim().replace(/\n/g, " ");
    if (!textToTranslate) continue;
    
    // Chunk size kept at 4500, but now safe because it's a POST request
    if (currentChunkText.length + textToTranslate.length > 4500) {
      await flushChunk(currentChunkText, currentChunkIndices);
      currentChunkText = "";
      currentChunkIndices = [];
    }
    
    if (currentChunkText.length > 0) {
      currentChunkText += '\n';
    }
    currentChunkText += textToTranslate;
    currentChunkIndices.push(i);
  }
  
  if (currentChunkText.length > 0) {
    await flushChunk(currentChunkText, currentChunkIndices);
  }
  console.log(`[STD] Batch translation complete.`);
}

function triggerDownload(payload, metadata) {
  const dateStr = metadata.publishedDate || "unknown";
  
  // Clean elements of the filename to avoid macOS/Windows naming issues
  const cleanPodcast = metadata.podcastName.replace(/[\\/:*?"<>|#%]/g, "_").trim();
  const cleanEpisode = metadata.episodeTitle.replace(/[\\/:*?"<>|#%]/g, "_").trim();

  // Naming format: {published_date_or_unknown} - {podcast_name} - {episode_title} - {spotify_episode_id}.json
  const filename = `${dateStr} - ${cleanPodcast} - ${cleanEpisode} - ${payload.spotifyEpisodeId || currentEpisodeId}.json`;

  try {
    const jsonStr = JSON.stringify(payload, null, 2);
    // Create Blob in content script context (which has DOM window support)
    const blob = new Blob([jsonStr], { type: "application/json;charset=utf-8" });
    const blobUrl = URL.createObjectURL(blob);

    chrome.runtime.sendMessage({
      type: 'DOWNLOAD_JSON',
      url: blobUrl,
      filename: filename
    }, (response) => {
      // Revoke Blob URL after 10s to release memory
      setTimeout(() => URL.revokeObjectURL(blobUrl), 10000);

      if (response && response.success) {
        console.log(`[STD] Successfully downloaded transcript: ${filename}`);
        updatePanelUI();
      } else {
        console.error(`[STD] Download failed:`, response ? response.error : 'No response from background.js');
      }
    });
  } catch (err) {
    console.error("[STD] Error creating blob URL in content script:", err);
  }
}

function parseAPIJson(data) {
  const segments = [];

  // Structure 1: Spotify standard sections array
  if (data && Array.isArray(data.section)) {
    let currentSpeaker = null;
    for (const item of data.section) {
      const startMs = item.startMs || 0;
      const startSec = startMs / 1000.0;

      let text = "";
      if (item.text && item.text.sentence) {
        text = item.text.sentence.text || "";
      } else if (item.text) {
        text = item.text.text || "";
      }

      let title = "";
      if (item.title) {
        title = item.title.title || item.title.text || "";
      }

      if (title && !text) {
        currentSpeaker = title.trim();
        continue;
      }

      if (!text) continue;

      segments.push({
        start: startSec,
        end: null,
        timestamp: formatSecondsToTimestamp(startSec),
        speaker: item.speaker || currentSpeaker,
        text: text.trim()
      });
    }
  }
  // Structure 2: Generic segments array fallback
  else if (data && Array.isArray(data.segments)) {
    for (const item of data.segments) {
      const startMs = item.startMs !== undefined ? item.startMs : (item.start || 0) * 1000;
      const startSec = startMs / 1000.0;
      const endSec = item.endMs !== undefined ? item.endMs / 1000.0 : (item.end || null);

      segments.push({
        start: startSec,
        end: endSec,
        timestamp: item.timestamp || formatSecondsToTimestamp(startSec),
        speaker: item.speaker || null,
        text: (item.text || item.words || "").trim()
      });
    }
  }

  if (segments.length === 0) return null;

  // Sort and assign end times if null
  segments.sort((a, b) => a.start - b.start);
  for (let i = 0; i < segments.length; i++) {
    if (segments[i].end === null) {
      if (i < segments.length - 1) {
        segments[i].end = segments[i + 1].start;
      } else {
        segments[i].end = null;
      }
    }
  }

  return segments;
}

// Scrapes and parses the visible transcript from the DOM
function extractSegmentsFromDOM() {
  const segments = [];
  const timeRegex = /^\d{1,2}:\d{2}(?::\d{2})?$/;

  const allElements = document.querySelectorAll('*');
  const timeElements = [];
  allElements.forEach(el => {
    if (el.children.length === 0 && el.textContent) {
      const text = el.textContent.trim();
      if (timeRegex.test(text)) {
        timeElements.push(el);
      }
    }
  });

  if (timeElements.length === 0) {
    // Fallback: try parsing body innerText using a general pattern-matching parser
    return parseBodyTextFallback();
  }

  const processedParents = new Set();

  timeElements.forEach(timeEl => {
    let container = timeEl.parentElement;
    for (let depth = 0; depth < 3; depth++) {
      if (!container) break;
      const text = container.textContent || "";
      const remainingText = text.replace(timeRegex, "").trim();
      if (remainingText.length > 3) {
        break;
      }
      container = container.parentElement;
    }

    if (!container || processedParents.has(container)) return;
    processedParents.add(container);

    const rawText = container.innerText || container.textContent || "";
    const lines = rawText.split('\n').map(l => l.trim()).filter(Boolean);

    let timestampStr = timeEl.textContent.trim();
    let textContent = "";
    let speaker = null;

    const timeIdx = lines.indexOf(timestampStr);
    if (timeIdx !== -1) {
      if (lines.length === 2) {
        textContent = lines[1 - timeIdx];
      } else if (lines.length >= 3) {
        if (timeIdx === 1) {
          speaker = lines[0];
          textContent = lines.slice(2).join(" ");
        } else if (timeIdx === 0) {
          speaker = lines[1];
          textContent = lines.slice(2).join(" ");
        } else {
          textContent = lines.filter((_, i) => i !== timeIdx).join(" ");
        }
      } else {
        textContent = lines.filter((_, i) => i !== timeIdx).join(" ");
      }
    } else {
      textContent = rawText.replace(timestampStr, "").trim();
    }

    if (speaker && textContent.startsWith(speaker)) {
      textContent = textContent.substring(speaker.length).trim();
      if (textContent.startsWith(":") || textContent.startsWith("-")) {
        textContent = textContent.substring(1).trim();
      }
    }

    const startSec = parseTimestampToSeconds(timestampStr);
    segments.push({
      start: startSec,
      end: null,
      timestamp: timestampStr,
      speaker: speaker || null,
      text: textContent.trim()
    });
  });

  if (segments.length === 0) return null;

  segments.sort((a, b) => a.start - b.start);

  const uniqueSegments = [];
  const seenTimes = new Set();
  segments.forEach(seg => {
    if (!seenTimes.has(seg.start)) {
      seenTimes.add(seg.start);
      uniqueSegments.push(seg);
    }
  });

  for (let i = 0; i < uniqueSegments.length; i++) {
    if (i < uniqueSegments.length - 1) {
      uniqueSegments[i].end = uniqueSegments[i + 1].start;
    } else {
      uniqueSegments[i].end = null;
    }
  }

  return uniqueSegments;
}

// Fallback text parser when DOM structure is heavily obfuscated
function parseBodyTextFallback() {
  const text = document.body?.innerText || "";
  const startIdx = text.indexOf("Transcript\nThis transcript was generated automatically");
  if (startIdx < 0) return null;
  const endCandidates = [
    text.indexOf("More episodes like this", startIdx),
    text.indexOf("About", startIdx),
    text.indexOf("Listeners also like", startIdx),
  ].filter((index) => index > startIdx);
  const endIdx = endCandidates.length ? Math.min(...endCandidates) : text.length;
  const targetText = text.slice(startIdx, endIdx).trim();

  const lines = targetText.split('\n').map(l => l.trim()).filter(Boolean);
  const segments = [];
  const timeRegex = /^\d{1,2}:\d{2}(?::\d{2})?$/;
  
  const timeIndices = [];
  for (let idx = 0; idx < lines.length; idx++) {
    if (timeRegex.test(lines[idx])) {
      timeIndices.push(idx);
    }
  }

  for (let t = 0; t < timeIndices.length; t++) {
    const currentIdx = timeIndices[t];
    const nextIdx = t < timeIndices.length - 1 ? timeIndices[t + 1] : lines.length;
    const prevIdx = t > 0 ? timeIndices[t - 1] : -1;

    const timestamp = lines[currentIdx];
    const start = parseTimestampToSeconds(timestamp);
    
    const linesAfter = lines.slice(currentIdx + 1, nextIdx);
    const linesBefore = lines.slice(prevIdx + 1, currentIdx);

    let speaker = null;
    let segmentText = "";

    if (linesBefore.length > 0 && linesAfter.length > 0) {
      const possibleSpeaker = linesBefore[linesBefore.length - 1];
      if (possibleSpeaker.length < 30) {
        speaker = possibleSpeaker;
      }
      segmentText = linesAfter.join(" ");
    } else if (linesAfter.length >= 2) {
      const possibleSpeaker = linesAfter[0];
      if (possibleSpeaker.startsWith("Speaker") || possibleSpeaker.length < 20) {
        speaker = possibleSpeaker;
        segmentText = linesAfter.slice(1).join(" ");
      } else {
        segmentText = linesAfter.join(" ");
      }
    } else if (linesAfter.length === 1) {
      segmentText = linesAfter[0];
    }

    if (segmentText) {
      segments.push({
        start: start,
        end: null,
        timestamp: timestamp,
        speaker: speaker || null,
        text: segmentText.trim()
      });
    }
  }

  if (segments.length === 0) return null;

  segments.sort((a, b) => a.start - b.start);
  for (let i = 0; i < segments.length; i++) {
    if (i < segments.length - 1) {
      segments[i].end = segments[i + 1].start;
    } else {
      segments[i].end = null;
    }
  }

  return segments;
}

function parseTimestampToSeconds(timestampStr) {
  const parts = timestampStr.split(':').map(Number);
  if (parts.length === 2) {
    return parts[0] * 60 + parts[1];
  } else if (parts.length === 3) {
    return parts[0] * 3600 + parts[1] * 60 + parts[2];
  }
  return 0;
}

function formatSecondsToTimestamp(totalSecs) {
  const h = Math.floor(totalSecs / 3600);
  const m = Math.floor((totalSecs % 3600) / 60);
  const s = Math.floor(totalSecs % 60);
  if (h > 0) {
    return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  } else {
    return `${m}:${s.toString().padStart(2, '0')}`;
  }
}

function getTranscriptHash(segments) {
  const str = segments.map(s => s.text).join("");
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash |= 0;
  }
  return hash.toString();
}

function formatLocalDate(dateObj) {
  const year = dateObj.getFullYear();
  const month = String(dateObj.getMonth() + 1).padStart(2, '0');
  const day = String(dateObj.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function parseRelativeDate(text) {
  const now = new Date();
  
  let match = text.match(/^(\d+)\s+days?\s+ago$/i) || text.match(/^(\d+)\s*天前$/);
  if (match) {
    const days = parseInt(match[1], 10);
    const date = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
    const formatted = formatLocalDate(date);
    logDebug(`Relative Date Match: "${text}" -> days ago: ${days} -> date: ${formatted}`);
    return formatted;
  }
  
  match = text.match(/^(\d+)\s+hours?\s+ago$/i) || text.match(/^(\d+)\s*小时前$/);
  if (match) {
    const hours = parseInt(match[1], 10);
    const date = new Date(now.getTime() - hours * 60 * 60 * 1000);
    const formatted = formatLocalDate(date);
    logDebug(`Relative Date Match: "${text}" -> hours ago: ${hours} -> date: ${formatted}`);
    return formatted;
  }

  match = text.match(/^(\d+)\s+weeks?\s+ago$/i) || text.match(/^(\d+)\s*周前$/) || text.match(/^(\d+)\s*星期前$/);
  if (match) {
    const weeks = parseInt(match[1], 10);
    const date = new Date(now.getTime() - weeks * 7 * 24 * 60 * 60 * 1000);
    const formatted = formatLocalDate(date);
    logDebug(`Relative Date Match: "${text}" -> weeks ago: ${weeks} -> date: ${formatted}`);
    return formatted;
  }

  match = text.match(/^(\d+)\s+months?\s+ago$/i) || text.match(/^(\d+)\s*个月前$/);
  if (match) {
    const months = parseInt(match[1], 10);
    const date = new Date(now.getTime() - months * 30 * 24 * 60 * 60 * 1000);
    const formatted = formatLocalDate(date);
    logDebug(`Relative Date Match: "${text}" -> months ago: ${months} -> date: ${formatted}`);
    return formatted;
  }

  match = text.match(/^(\d+)\s+years?\s+ago$/i) || text.match(/^(\d+)\s*年前$/);
  if (match) {
    const years = parseInt(match[1], 10);
    const date = new Date(now.getTime() - years * 365 * 24 * 60 * 60 * 1000);
    const formatted = formatLocalDate(date);
    logDebug(`Relative Date Match: "${text}" -> years ago: ${years} -> date: ${formatted}`);
    return formatted;
  }
  
  if (/^yesterday$/i.test(text) || /^昨天$/.test(text)) {
    const date = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    const formatted = formatLocalDate(date);
    logDebug(`Relative Date Match: "${text}" -> yesterday -> date: ${formatted}`);
    return formatted;
  }
  
  if (/^today$/i.test(text) || /^今天$/.test(text)) {
    const formatted = formatLocalDate(now);
    logDebug(`Relative Date Match: "${text}" -> today -> date: ${formatted}`);
    return formatted;
  }
  
  // Day of week mapping
  const DAYS_OF_WEEK = {
    // English
    sunday: 0, monday: 1, tuesday: 2, wednesday: 3, thursday: 4, friday: 5, saturday: 6,
    sun: 0, mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6,
    
    // Chinese
    '周日': 0, '周一': 1, '周二': 2, '周三': 3, '周四': 4, '周五': 5, '周六': 6,
    '星期日': 0, '星期一': 1, '星期二': 2, '星期三': 3, '星期四': 4, '星期五': 5, '星期六': 6,
    
    // Spanish
    domingo: 0, lunes: 1, martes: 2, miércoles: 3, miercoles: 3, jueves: 4, viernes: 5, sábado: 6, sabado: 6,
    // French
    dimanche: 0, lundi: 1, mardi: 2, mercredi: 3, jeudi: 4, vendredi: 5, samedi: 6,
    // German
    sonntag: 0, montag: 1, dienstag: 2, mittwoch: 3, donnerstag: 4, freitag: 5, samstag: 6,
    // Portuguese
    segunda: 1, terça: 2, terca: 2, quarta: 3, quinta: 4, sexta: 5,
    // Italian
    domenica: 0, lunedì: 1, lunedi: 1, martedì: 2, martedi: 2, mercoledì: 3, mercoledi: 3, giovedì: 4, giovedi: 4, venerdì: 5, venerdi: 5
  };

  const cleanLower = text.toLowerCase().replace(/[\.,#%]/g, "").trim();
  const targetDayNum = DAYS_OF_WEEK[cleanLower];
  if (targetDayNum !== undefined) {
    const todayNum = now.getDay();
    let diff = (todayNum - targetDayNum + 7) % 7;
    if (diff === 0) {
      diff = 7;
    }
    const date = new Date(now.getTime() - diff * 24 * 60 * 60 * 1000);
    const formatted = formatLocalDate(date);
    logDebug(`Relative Date Match (Day of Week): "${text}" -> target: ${targetDayNum}, diff: ${diff} -> date: ${formatted}`);
    return formatted;
  }
  
  return null;
}

function getMonthNumber(monthStr) {
  const clean = monthStr.toLowerCase().substring(0, 3);
  const monthsMap = {
    jan: '01', feb: '02', mar: '03', apr: '04', may: '05', jun: '06',
    jul: '07', aug: '08', sep: '09', oct: '10', nov: '11', dec: '12',
    ene: '01', abr: '04', ago: '08', dic: '12',
    set: '09', dez: '12', okt: '10', mai: '05',
    déc: '12', dev: '12', fév: '02'
  };
  if (clean.startsWith('ma')) {
    if (clean === 'may' || clean === 'mai' || clean === 'mar') {
      return clean === 'mar' ? '03' : '05';
    }
  }
  return monthsMap[clean] || '01';
}

function parseDateFromString(str) {
  if (!str) return null;
  const text = str.trim();
  const currentYear = new Date().getFullYear();

  // 1. Check relative dates
  const relDate = parseRelativeDate(text);
  if (relDate) return relDate;

  // 2. YYYY-MM-DD or YYYY/MM/DD (restricting year to 1900-2099)
  let match = text.match(/\b((?:19|20)\d{2})[-/](\d{1,2})[-/](\d{1,2})\b/);
  if (match) {
    const year = match[1];
    const month = match[2].padStart(2, '0');
    const day = match[3].padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  // 3. YYYY年MM月DD日
  match = text.match(/((?:19|20)\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日/);
  if (match) {
    const year = match[1];
    const month = match[2].padStart(2, '0');
    const day = match[3].padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  // 4. MM月DD日 (current year fallback, e.g. "5月24日")
  match = text.match(/^(\d{1,2})\s*月\s*(\d{1,2})\s*日$/) || (text.length < 15 && text.match(/(\d{1,2})\s*月\s*(\d{1,2})\s*日/));
  if (match) {
    if (!text.includes('年')) {
      const year = currentYear;
      const month = match[1].padStart(2, '0');
      const day = match[2].padStart(2, '0');
      return `${year}-${month}-${day}`;
    }
  }

  const monthsRegexStr = 'Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|ene(?:ro)?|feb(?:rero)?|mar(?:zo)?|abr(?:il)?|may(?:o)?|jun(?:io)?|jul(?:io)?|ago(?:sto)?|sep(?:tiembre)?|oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?|set(?:embro)?|dez(?:embro)?|märz|okt(?:ober)?|janv(?:ier)?|févr(?:ier)?|mars|avr(?:il)?|juin|juil(?:let)?|août|sept(?:embre)?|déc(?:embre)?';

  // 5. Month DD, YYYY
  const monthFirstRegex = new RegExp('\\b(' + monthsRegexStr + ')\\.?\\s+(\\d{1,2}),?\\s+((?:19|20)\\d{2})\\b', 'i');
  match = text.match(monthFirstRegex);
  if (match) {
    const month = getMonthNumber(match[1]);
    const day = match[2].padStart(2, '0');
    const year = match[3];
    return `${year}-${month}-${day}`;
  }

  // 6. DD Month YYYY
  const dayFirstRegex = new RegExp('\\b(\\d{1,2})\\.?\\s*(?:de\\s+)?(' + monthsRegexStr + ')\\.?\\s*(?:de\\s+)?((?:19|20)\\d{2})\\b', 'i');
  match = text.match(dayFirstRegex);
  if (match) {
    const day = match[1].padStart(2, '0');
    const month = getMonthNumber(match[2]);
    const year = match[3];
    return `${year}-${month}-${day}`;
  }

  // 7. Month DD (current year fallback, e.g. "May 24")
  const monthDDRegex = new RegExp('^(' + monthsRegexStr + ')\\.?\\s+(\\d{1,2})$', 'i');
  match = text.match(monthDDRegex);
  if (!match && text.length < 20) {
    const looseMonthDD = new RegExp('\\b(' + monthsRegexStr + ')\\.?\\s+(\\d{1,2})\\b', 'i');
    match = text.match(looseMonthDD);
  }
  if (match) {
    const month = getMonthNumber(match[1]);
    const day = match[2].padStart(2, '0');
    const year = currentYear;
    return `${year}-${month}-${day}`;
  }

  // 8. DD Month (current year fallback, e.g. "24 May" or "24 de mai.")
  const ddMonthRegex = new RegExp('^(\\d{1,2})\\.?\\s*(?:de\\s+)?(' + monthsRegexStr + ')\\.?$', 'i');
  match = text.match(ddMonthRegex);
  if (!match && text.length < 20) {
    const looseDDMonth = new RegExp('\\b(\\d{1,2})\\.?\\s*(?:de\\s+)?(' + monthsRegexStr + ')\\b', 'i');
    match = text.match(looseDDMonth);
  }
  if (match) {
    const day = match[1].padStart(2, '0');
    const month = getMonthNumber(match[2]);
    const year = currentYear;
    return `${year}-${month}-${day}`;
  }

  // 9. YYYY年MM月 (Month Year)
  match = text.match(/((?:19|20)\d{2})\s*年\s*(\d{1,2})\s*月/);
  if (match) {
    const year = match[1];
    const month = match[2].padStart(2, '0');
    return `${year}-${month}`;
  }

  // 10. Month YYYY (Month Year)
  const monthYearRegex = new RegExp('\\b(' + monthsRegexStr + ')\\.?\\s+((?:19|20)\\d{2})\\b', 'i');
  match = text.match(monthYearRegex);
  if (match) {
    const month = getMonthNumber(match[1]);
    const year = match[2];
    return `${year}-${month}`;
  }

  return null;
}

function extractDateFromText(text) {
  if (!text) return null;
  const cleanText = text.trim();
  if (cleanText.length === 0 || cleanText.length > 100) return null;

  // Split by bullets, middle-dots, or newlines to check parts
  const parts = cleanText.split(/[\n•·●]/).map(p => p.trim()).filter(Boolean);
  for (const part of parts) {
    const parsed = parseDateFromString(part);
    if (parsed) return parsed;
  }

  return null;
}

function findPublishedDate() {
  const mainContent = document.querySelector('main, [role="main"], .main-view-container, .Root__main-view');
  const searchRoot = mainContent || document;
  
  logDebug("Starting findPublishedDate DOM scanning...");
  
  // Scan elements under the main content area in exact document order
  const allElements = Array.from(searchRoot.querySelectorAll('span, div, p, time, a, h2'));
  for (const el of allElements) {
    if (el.tagName === 'H2') {
      logDebug(`Hit H2 element: "${el.innerText || el.textContent}". Stopping date scan.`);
      break;
    }
    
    // Skip H1 itself and larger window containers
    if (el.tagName === 'H1' || el.tagName === 'HTML' || el.tagName === 'BODY') continue;

    // Prioritize datetime attribute if it is a time element
    if (el.tagName === 'TIME') {
      const datetime = el.getAttribute('datetime');
      if (datetime) {
        const match = datetime.match(/^(\d{4}-\d{2}-\d{2})/);
        if (match) {
          logDebug(`Found date from TIME datetime attribute: "${datetime}" -> ${match[1]}`);
          return match[1];
        }
      }
    }

    const text = el.innerText ? el.innerText.trim() : (el.textContent ? el.textContent.trim() : "");
    if (!text || text.length > 100) continue; // Skip empty or overly large container texts
    
    const parsed = extractDateFromText(text);
    if (parsed) {
      logDebug(`Found episode date: "${text}" -> ${parsed}`);
      return parsed;
    }
  }

  logDebug("Completed findPublishedDate scan. No date found.");
  return null;
}

function findPublishedDateFromMeta() {
  const metaRelease = document.querySelector('meta[property="music:release_date"], meta[property="og:release_date"]');
  if (metaRelease && metaRelease.content) {
    const parsed = parseDateFromString(metaRelease.content.trim());
    if (parsed) return parsed;
  }

  const jsonLdScripts = document.querySelectorAll('script[type="application/ld+json"]');
  for (const script of jsonLdScripts) {
    try {
      const json = JSON.parse(script.textContent);
      if (json && json.datePublished) {
        const parsed = parseDateFromString(json.datePublished);
        if (parsed) return parsed;
      }
      if (json && json["@graph"]) {
        for (const item of json["@graph"]) {
          if (item.datePublished) {
            const parsed = parseDateFromString(item.datePublished);
            if (parsed) return parsed;
          }
        }
      }
    } catch (e) {}
  }
  return null;
}

function findPodcastNameFromMeta() {
  const metaShow = document.querySelector('meta[property="og:audio:artist"], meta[property="music:creator"]');
  if (metaShow && metaShow.content) {
    return metaShow.content.trim();
  }
  return null;
}

// Scrapes episode title from og:title, stripping suffix
function findEpisodeTitleFromMeta() {
  const ogTitle = document.querySelector('meta[property="og:title"]');
  if (ogTitle && ogTitle.content) {
    let title = ogTitle.content.trim();
    if (title.endsWith(" - Podcast on Spotify")) {
      title = title.substring(0, title.length - " - Podcast on Spotify".length);
    }
    return title;
  }
  return null;
}

function getPageMetadata() {
  const metaTitle = findEpisodeTitleFromMeta();
  const metaPodcast = findPodcastNameFromMeta();
  const metaDate = findPublishedDateFromMeta();

  const mainContent = document.querySelector('main, [role="main"], .main-view-container, .Root__main-view');

  let episodeTitle = metaTitle;
  if (!episodeTitle) {
    const h1 = mainContent ? mainContent.querySelector('h1') : document.querySelector('h1');
    episodeTitle = h1 ? h1.innerText.trim() : "";
  }

  let podcastName = metaPodcast;
  if (!podcastName) {
    const searchRoot = mainContent || document;
    const showLink = searchRoot.querySelector('a[href^="/show/"], a[data-testid="show-link"]');
    podcastName = showLink ? showLink.innerText.trim() : "";
  }

  let publishedDate = metaDate || findPublishedDate() || "unknown";

  // Filter out page-loading placeholder titles like "Your Library" or "Library"
  if (episodeTitle === "Your Library" || episodeTitle === "Library") {
    episodeTitle = "";
  }

  return {
    episodeTitle: episodeTitle || "unknown_episode",
    podcastName: podcastName || "unknown_podcast",
    publishedDate: publishedDate
  };
}

// 3. UI and Panel creation logic
function ensurePanelCreated() {
  if (!document.body) return;
  if (document.getElementById('std-extension-panel')) return;

  const panel = document.createElement('div');
  panel.id = "std-extension-panel";
  panel.style.cssText = `
    position: fixed;
    bottom: 100px;
    right: 24px;
    z-index: 99999;
    background-color: #121212;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 8px;
    padding: 12px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #E0E0E0;
    font-size: 11px;
    width: 220px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
    pointer-events: auto;
    display: none;
  `;

  panel.innerHTML = `
    <div style="font-weight: bold; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 6px;">
      <span style="letter-spacing: 0.5px; color: #FFFFFF;">STD TRANSCRIPT</span>
      <span style="font-size: 9px; color: #6A6A6A;">V2.0</span>
    </div>
    <div id="std-status-text" style="margin-bottom: 10px; line-height: 1.4; color: #8E8E93;">
      No transcript found yet. Open/expand Transcript on Spotify.
    </div>
    <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 10px; cursor: pointer;">
      <input type="checkbox" id="std-auto-translate-cb" style="margin: 0; cursor: pointer;" checked>
      <span style="color: #E0E0E0;">Auto-Translate to Chinese</span>
    </label>
    <button id="std-download-btn" style="
      width: 100%;
      padding: 6px 8px;
      background-color: #282828;
      border: 1px solid rgba(255, 255, 255, 0.2);
      border-radius: 4px;
      color: #FFFFFF;
      font-size: 10px;
      font-weight: bold;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 4px;
      transition: background-color 0.2s, border-color 0.2s;
    ">
      ⤓ Download Visible Transcript
    </button>
  `;

  document.body.appendChild(panel);

  const btn = document.getElementById('std-download-btn');
  btn.addEventListener('click', handleManualDownload);

  btn.addEventListener('mouseenter', () => {
    btn.style.backgroundColor = '#3E3E3E';
    btn.style.borderColor = 'rgba(255, 255, 255, 0.4)';
  });
  btn.addEventListener('mouseleave', () => {
    btn.style.backgroundColor = '#282828';
    btn.style.borderColor = 'rgba(255, 255, 255, 0.2)';
  });
}

function updatePanelUI() {
  if (!document.body) {
    // Wait until document.body is ready to perform UI modifications
    setTimeout(updatePanelUI, 100);
    return;
  }
  
  ensurePanelCreated();
  const statusEl = document.getElementById('std-status-text');
  const btn = document.getElementById('std-download-btn');
  const panel = document.getElementById('std-extension-panel');

  if (!currentEpisodeId) {
    if (panel) panel.style.display = 'none';
    return;
  }

  if (panel) panel.style.display = 'block';

  const currentHash = downloadedMap.get(currentEpisodeId);
  if (statusEl && btn) {
    if (currentHash) {
      statusEl.innerHTML = `<span style="color: #FFFFFF; font-weight: bold;">✓ Transcript captured and downloaded.</span>`;
      btn.innerText = "⤓ Download Again";
    } else {
      statusEl.innerHTML = `<span style="color: #8E8E93;">No transcript found yet. Open/expand Transcript on Spotify.</span>`;
      btn.innerText = "⤓ Download Visible Transcript";
    }
  }
}
