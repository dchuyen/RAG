const WEB_SEARCH_SETTINGS_KEY = "gemini-chat-web-search-settings";
const clampInteger = (input, fallback) => Math.min(
  50,
  Math.max(1, Number.parseInt(input.value, 10) || fallback),
);

export function initializeSettings() {
  const settingsToggle = document.querySelector("#settings-toggle");
  const settingsDialog = document.querySelector("#settings-dialog");
  const settingsForm = document.querySelector("#settings-form");
  const settingsClose = document.querySelector("#settings-close");
  const settingsSave = document.querySelector("#settings-save");
  const webSearchEnabledInput = document.querySelector("#web-search-enabled");
  const webSearchMaxPagesInput = document.querySelector("#web-search-max-pages");
  const preRerankCountInput = document.querySelector("#pre-rerank-count");
  const resultCountInput = document.querySelector("#result-count");
  const crossEncoderEnabledInput = document.querySelector("#cross-encoder-enabled");
  const cacheLookupEnabledInput = document.querySelector("#cache-lookup-enabled");
  const cacheWriteEnabledInput = document.querySelector("#cache-write-enabled");

  function loadWebSearchSettings() {
    let settings = {
      enabled: true,
      maxPages: 10,
      preRerankCount: 5,
      resultCount: 3,
      useCrossEncoder: true,
      cacheLookupEnabled: false,
      cacheWriteEnabled: false,
    };
    try {
      const stored = JSON.parse(localStorage.getItem(WEB_SEARCH_SETTINGS_KEY));
      if (stored && typeof stored.enabled === "boolean") settings.enabled = stored.enabled;
      if (
        stored
        && Number.isInteger(stored.maxPages)
        && stored.maxPages >= 1
        && stored.maxPages <= 50
      ) {
        settings.maxPages = stored.maxPages;
      }
      if (
        stored
        && Number.isInteger(stored.preRerankCount)
        && stored.preRerankCount >= 1
        && stored.preRerankCount <= 50
      ) {
        settings.preRerankCount = stored.preRerankCount;
      }
      if (
        stored
        && Number.isInteger(stored.resultCount)
        && stored.resultCount >= 1
        && stored.resultCount <= 50
      ) {
        settings.resultCount = stored.resultCount;
      }
      if (stored && typeof stored.useCrossEncoder === "boolean") {
        settings.useCrossEncoder = stored.useCrossEncoder;
      }
      if (stored && typeof stored.cacheLookupEnabled === "boolean") {
        settings.cacheLookupEnabled = stored.cacheLookupEnabled;
      }
      if (stored && typeof stored.cacheWriteEnabled === "boolean") {
        settings.cacheWriteEnabled = stored.cacheWriteEnabled;
      }
    } catch {
      // Use defaults when settings are missing or invalid.
    }

    webSearchEnabledInput.checked = settings.enabled;
    webSearchMaxPagesInput.value = String(settings.maxPages);
    preRerankCountInput.value = String(settings.preRerankCount);
    resultCountInput.value = String(settings.resultCount);
    crossEncoderEnabledInput.checked = settings.useCrossEncoder;
    cacheLookupEnabledInput.checked = settings.cacheLookupEnabled;
    cacheWriteEnabledInput.checked = settings.cacheWriteEnabled;
    [
      webSearchMaxPagesInput,
      preRerankCountInput,
      resultCountInput,
      crossEncoderEnabledInput,
      cacheLookupEnabledInput,
      cacheWriteEnabledInput,
    ].forEach((input) => {
      input.disabled = !settings.enabled;
    });
  }

  function closeSettings() {
    if (typeof settingsDialog.close === "function") {
      settingsDialog.close();
    } else {
      settingsDialog.removeAttribute("open");
    }
  }

  function getRequestSettings() {
    return {
      web_search_enabled: webSearchEnabledInput.checked,
      max_web_pages: clampInteger(webSearchMaxPagesInput, 10),
      pre_rerank_count: clampInteger(preRerankCountInput, 5),
      result_count: clampInteger(resultCountInput, 3),
      use_cross_encoder: crossEncoderEnabledInput.checked,
      cache_lookup_enabled: cacheLookupEnabledInput.checked,
      cache_write_enabled: cacheWriteEnabledInput.checked,
    };
  }

  loadWebSearchSettings();

  if (settingsToggle) {
    settingsToggle.addEventListener("click", () => {
      if (typeof settingsDialog.showModal === "function") {
        settingsDialog.showModal();
      } else {
        settingsDialog.setAttribute("open", "");
      }
    });
  }

  webSearchEnabledInput.addEventListener("change", () => {
    [
      webSearchMaxPagesInput,
      preRerankCountInput,
      resultCountInput,
      crossEncoderEnabledInput,
      cacheLookupEnabledInput,
      cacheWriteEnabledInput,
    ].forEach((input) => {
      input.disabled = !webSearchEnabledInput.checked;
    });
  });

  settingsClose.addEventListener("click", closeSettings);
  settingsSave.addEventListener("click", () => {
    const requestSettings = getRequestSettings();
    const settings = {
      enabled: requestSettings.web_search_enabled,
      maxPages: requestSettings.max_web_pages,
      preRerankCount: requestSettings.pre_rerank_count,
      resultCount: requestSettings.result_count,
      useCrossEncoder: requestSettings.use_cross_encoder,
      cacheLookupEnabled: requestSettings.cache_lookup_enabled,
      cacheWriteEnabled: requestSettings.cache_write_enabled,
    };
    webSearchMaxPagesInput.value = String(settings.maxPages);
    preRerankCountInput.value = String(settings.preRerankCount);
    resultCountInput.value = String(settings.resultCount);
    try {
      localStorage.setItem(WEB_SEARCH_SETTINGS_KEY, JSON.stringify(settings));
    } catch {
      // Settings can remain active for the current page session.
    }
    closeSettings();
  });
  settingsForm.addEventListener("submit", (event) => event.preventDefault());
  settingsDialog.addEventListener("click", (event) => {
    if (event.target === settingsDialog) closeSettings();
  });

  return { getRequestSettings };
}

export function initializeTheme(themeToggle) {
  function applyTheme(theme) {
    const isDark = theme === "dark";
    document.body.classList.toggle("theme-dark", isDark);
    document.documentElement.style.colorScheme = isDark ? "dark" : "light";
    if (themeToggle) {
      themeToggle.textContent = isDark ? "☀" : "☾";
      themeToggle.setAttribute("aria-label", isDark ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối");
      themeToggle.setAttribute("aria-pressed", String(isDark));
    }
    try {
      localStorage.setItem("gemini-chat-theme", theme);
    } catch {
      // Ignore storage errors in restricted/private browsing contexts.
    }
  }

  const initialize = () => {
    try {
      const savedTheme = localStorage.getItem("gemini-chat-theme");
      applyTheme(savedTheme === "dark" ? "dark" : "light");
    } catch {
      applyTheme("light");
    }
  };
  const toggleTheme = () => {
    const nextTheme = document.body.classList.contains("theme-dark") ? "light" : "dark";
    applyTheme(nextTheme);
  };

  initialize();
  if (themeToggle) themeToggle.addEventListener("click", toggleTheme);
}
