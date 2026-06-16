// background.js - Service Worker for Spotify Transcript Downloader
// [STD] Handles the Chrome downloads API, forcing filenames using onDeterminingFilename

console.log("[STD] Background service worker initialized.");

const pendingDownloads = new Map(); // url -> filename

function cleanFilename(str) {
  // Replace characters that are forbidden/unsafe, including URL/Special characters like # and %
  return str.replace(/[\\/:*?"<>|#%]/g, "_").trim();
}

// Register onDeterminingFilename listener to force Chrome to respect the filename and subfolder.
// This overrides browser defaults or conflicts from other extensions.
chrome.downloads.onDeterminingFilename.addListener((item, suggest) => {
  if (pendingDownloads.has(item.url)) {
    const rawFilename = pendingDownloads.get(item.url);
    pendingDownloads.delete(item.url);
    
    // Clean filename elements to ensure OS/Browser compatibility
    const filename = "Spotify Transcript Collector/" + cleanFilename(rawFilename.split('/').pop());
    console.log(`[STD] Mapped download item URL. Suggesting filename: ${filename}`);
    
    suggest({
      filename: filename,
      conflictAction: 'overwrite'
    });
  } else {
    // If it's not initiated by our extension, call suggest() with no arguments to prevent hanging
    suggest();
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'DOWNLOAD_JSON') {
    try {
      const url = message.url;
      if (!url) {
        throw new Error("No download URL provided in message.");
      }
      
      const rawFilename = message.filename || "transcript.json";
      
      // Store the mapping of URL to desired filename before calling downloads API
      pendingDownloads.set(url, rawFilename);
      console.log(`[STD] Registered pending download: ${rawFilename}`);
      
      chrome.downloads.download({
        url: url,
        // We still specify filename here as a fallback hint, though onDeterminingFilename handles the override
        filename: "Spotify Transcript Collector/" + cleanFilename(rawFilename.split('/').pop()),
        conflictAction: 'overwrite',
        saveAs: false
      }, (downloadId) => {
        if (chrome.runtime.lastError) {
          console.error("[STD] Background download failed:", chrome.runtime.lastError.message);
          // If downloads API failed immediately, clean up the map
          pendingDownloads.delete(url);
          sendResponse({ success: false, error: chrome.runtime.lastError.message });
        } else {
          console.log("[STD] Background download initiated, ID:", downloadId);
          sendResponse({ success: true, downloadId });
        }
      });
    } catch (err) {
      console.error("[STD] Error in background downloader logic:", err);
      sendResponse({ success: false, error: err.message });
    }
    return true; // Keep connection open for asynchronous response
  } else if (message.type === 'BACKGROUND_TRANSLATE_AND_DOWNLOAD') {
    (async () => {
      try {
        const payload = message.payload;
        const metadata = message.metadata;
        
        console.log(`[STD] Background translation started for: ${metadata.episodeTitle}`);
        const translationSuccess = await batchTranslateSegments(payload.segments);
        
        const translatedMeta = { ...metadata };
        const suffix = translationSuccess ? "_zh" : "_zh_INCOMPLETE";
        translatedMeta.episodeTitle = metadata.episodeTitle + suffix;
        
        const dateStr = translatedMeta.publishedDate || "unknown";
        const cleanPodcast = cleanFilename(translatedMeta.podcastName);
        const cleanEpisode = cleanFilename(translatedMeta.episodeTitle);
        const filename = `${dateStr} - ${cleanPodcast} - ${cleanEpisode} - ${payload.spotifyEpisodeId}.json`;
        
        // Generate a Data URI for background download (no DOM Blob needed)
        const jsonStr = JSON.stringify(payload, null, 2);
        // Safely encode utf-8 to base64
        const dataUrl = 'data:application/json;base64,' + btoa(unescape(encodeURIComponent(jsonStr)));
        
        pendingDownloads.set(dataUrl, filename);
        console.log(`[STD] Background translation complete. Initiating download: ${filename}`);
        
        chrome.downloads.download({
          url: dataUrl,
          filename: "Spotify Transcript Collector/" + cleanFilename(filename),
          conflictAction: 'overwrite',
          saveAs: false
        }, (downloadId) => {
          if (chrome.runtime.lastError) {
             console.error("[STD] Translated background download failed:", chrome.runtime.lastError.message);
             pendingDownloads.delete(dataUrl);
          } else {
             console.log("[STD] Translated background download initiated, ID:", downloadId);
          }
        });
        sendResponse({ success: true });
      } catch (err) {
        console.error("[STD] Background translation/download failed:", err);
        sendResponse({ success: false, error: err.message });
      }
    })();
    return true;
  }
});

async function batchTranslateSegments(segments) {
  if (!segments || segments.length === 0) return false;
  console.log(`[STD] Starting batch translation for ${segments.length} segments...`);
  
  let currentChunkText = "";
  let currentChunkIndices = [];

  const buildChunkText = (indices) => indices
    .map(index => segments[index].text.trim().replace(/\n/g, " "))
    .filter(Boolean)
    .join('\n');
  
  const flushChunk = async (text, indices) => {
    if (!text) return true;
    for (let attempt = 1; attempt <= 5; attempt++) {
      try {
      const url = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=zh-CN&dt=t`;
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: `q=${encodeURIComponent(text)}`
      });
      if (!response.ok) {
        throw new Error(`Translate HTTP ${response.status}`);
      }
      const res = await response.json();
      
      let translatedText = "";
      if (res && res[0]) {
        res[0].forEach(item => {
          if (item[0]) translatedText += item[0];
        });
      }
      
      const translations = translatedText.split('\n').map(s => s.trim());
      const hasAllTranslations = translations.length >= indices.length && indices.every((_, i) => translations[i]);
      if (!hasAllTranslations) {
        if (indices.length > 1) {
          const middle = Math.ceil(indices.length / 2);
          const leftIndices = indices.slice(0, middle);
          const rightIndices = indices.slice(middle);
          const leftOk = await flushChunk(buildChunkText(leftIndices), leftIndices);
          const rightOk = await flushChunk(buildChunkText(rightIndices), rightIndices);
          return leftOk && rightOk;
        }
        throw new Error(`Translate returned ${translations.filter(Boolean).length}/${indices.length} non-empty lines`);
      }
      for (let i = 0; i < indices.length; i++) {
        segments[indices[i]].translation = translations[i];
      }
      
      // Keep requests slow enough to avoid Google Translate rate limits.
      await new Promise(r => setTimeout(r, 5000));
      return true;
      } catch (err) {
        console.error(`[STD] Translation chunk failed attempt ${attempt}/5:`, err);
        if (attempt === 5) return false;
        await new Promise(r => setTimeout(r, 15000 * attempt));
      }
    }
  };

  for (let i = 0; i < segments.length; i++) {
    const textToTranslate = segments[i].text.trim().replace(/\n/g, " ");
    if (!textToTranslate) continue;
    
    // Smaller chunks reduce empty/partial translation responses and rate-limit pressure.
    // 4500 is safe for POST requests and halves the total number of requests.
    if (currentChunkText.length + textToTranslate.length > 4500) {
      const ok = await flushChunk(currentChunkText, currentChunkIndices);
      if (!ok) return false;
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
    const ok = await flushChunk(currentChunkText, currentChunkIndices);
    if (!ok) return false;
  }
  const missingCount = segments.filter(segment => segment && segment.text && !segment.translation).length;
  if (missingCount > 0) {
    console.error(`[STD] Batch translation incomplete: ${missingCount} missing translations.`);
    return false;
  }
  console.log(`[STD] Batch translation complete.`);
  return true;
}
