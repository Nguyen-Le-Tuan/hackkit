// Load a CDN script or stylesheet only when a page needs it (maps, charts).
// Resolves to the library's global, or rejects after a timeout so pages can fall back.

const loading = new Map();

export function loadScript(url, globalName, timeout = 9000) {
  if (globalName && window[globalName]) return Promise.resolve(window[globalName]);
  if (!loading.has(url)) {
    loading.set(
      url,
      new Promise((resolve, reject) => {
        const tag = document.createElement("script");
        tag.src = url;
        tag.async = true;
        const timer = setTimeout(() => reject(new Error(`Timed out loading ${url}`)), timeout);
        tag.onload = () => {
          clearTimeout(timer);
          if (globalName && !window[globalName]) reject(new Error(`${globalName} missing after ${url}`));
          else resolve(globalName ? window[globalName] : true);
        };
        tag.onerror = () => {
          clearTimeout(timer);
          reject(new Error(`Could not load ${url} (offline?)`));
        };
        document.head.append(tag);
      }),
    );
  }
  const promise = loading.get(url);
  promise.catch(() => loading.delete(url));
  return promise;
}

export function loadCss(url) {
  if (document.querySelector(`link[data-lazy="${url}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = url;
  link.dataset.lazy = url;
  document.head.append(link);
}
