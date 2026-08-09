// injected.js - Runs in the page execution context
// Monkey-patches window.fetch and XMLHttpRequest to capture Spotify's transcript API calls

(function() {
  "use strict";
  console.log("[STD] API Interceptor script successfully injected.");

  const INTERCEPT_KEYWORDS = ['transcript', 'episode-transcripts', 'transcript-read-along'];

  function shouldIntercept(url) {
    if (!url || typeof url !== 'string') return false;
    const lowerUrl = url.toLowerCase();
    return INTERCEPT_KEYWORDS.some(kw => lowerUrl.includes(kw));
  }

  // 1. Monkey patch fetch API
  const originalFetch = window.fetch;
  window.fetch = function(...args) {
    const promise = originalFetch.apply(this, args);
    promise.then(response => {
      let url = "";
      if (args[0]) {
        url = typeof args[0] === 'string' ? args[0] : (args[0].url || "");
      }
      
      if (shouldIntercept(url)) {
        try {
          const clone = response.clone();
          clone.json().then(data => {
            console.log("[STD] Intercepted fetch API response:", url);
            window.postMessage({
              type: 'SPOTIFY_TRANSCRIPT_API_CAPTURED',
              url: url,
              data: data
            }, '*');
          }).catch(err => {
            // Try to extract raw text if not standard JSON
            clone.text().then(text => {
              try {
                const parsed = JSON.parse(text);
                console.log("[STD] Intercepted fetch text parsed as JSON:", url);
                window.postMessage({
                  type: 'SPOTIFY_TRANSCRIPT_API_CAPTURED',
                  url: url,
                  data: parsed
                }, '*');
              } catch (e) {
                // Ignore raw non-JSON text
              }
            }).catch(() => {});
          });
        } catch (e) {
          console.error("[STD] Error cloning fetch response:", e);
        }
      }
    }).catch(err => {});
    
    return promise;
  };

  // 2. Monkey patch XMLHttpRequest
  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    this._stdUrl = url;
    return originalOpen.apply(this, [method, url, ...rest]);
  };

  XMLHttpRequest.prototype.send = function(...args) {
    this.addEventListener('load', function() {
      const url = this._stdUrl;
      if (shouldIntercept(url)) {
        try {
          const data = JSON.parse(this.responseText);
          console.log("[STD] Intercepted XHR response:", url);
          window.postMessage({
            type: 'SPOTIFY_TRANSCRIPT_API_CAPTURED',
            url: url,
            data: data
          }, '*');
        } catch (e) {
          // Ignore non-JSON text responses
        }
      }
    });
    return originalSend.apply(this, args);
  };
})();
