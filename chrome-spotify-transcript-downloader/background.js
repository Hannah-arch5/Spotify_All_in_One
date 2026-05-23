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
  }
});
