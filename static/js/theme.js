(function () {
  const storageKey = "access-atlas-theme-mode";
  const modes = new Set(["system", "light", "dark"]);
  const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

  function getCookie(name) {
    const cookie = document.cookie
      .split(";")
      .map((item) => item.trim())
      .find((item) => item.startsWith(`${name}=`));
    return cookie ? decodeURIComponent(cookie.slice(name.length + 1)) : "";
  }

  function resolvedTheme(mode) {
    if (mode === "dark" || (mode === "system" && mediaQuery.matches)) {
      return "dark";
    }
    return "light";
  }

  function currentMode() {
    const active = document.querySelector("[data-theme-mode].active");
    if (active && modes.has(active.dataset.themeMode)) {
      return active.dataset.themeMode;
    }
    const toggle = document.querySelector("[data-theme-menu-toggle]");
    if (toggle && modes.has(toggle.dataset.themeCurrentMode)) {
      return toggle.dataset.themeCurrentMode;
    }
    const stored = localStorage.getItem(storageKey);
    return modes.has(stored) ? stored : "system";
  }

  function updateControls(mode) {
    document.querySelectorAll("[data-theme-menu-toggle]").forEach((button) => {
      const label = `Theme: ${mode.charAt(0).toUpperCase()}${mode.slice(1)}`;
      button.dataset.themeCurrentMode = mode;
      button.setAttribute("aria-label", label);
      button.setAttribute("title", label);
    });
    document.querySelectorAll("[data-theme-mode]").forEach((button) => {
      button.classList.toggle("active", button.dataset.themeMode === mode);
    });
  }

  function applyTheme(mode) {
    const cleanedMode = modes.has(mode) ? mode : "system";
    const theme = resolvedTheme(cleanedMode);
    document.documentElement.setAttribute("data-bs-theme", theme);
    document.body?.setAttribute("data-bs-theme", theme);
    localStorage.setItem(storageKey, cleanedMode);
    updateControls(cleanedMode);
  }

  function saveThemePreference(mode) {
    const toggle = document.querySelector("[data-theme-menu-toggle]");
    const url = toggle?.dataset.themePreferenceUrl;
    const key = toggle?.dataset.themePreferenceKey;

    if (!url || !key) {
      return;
    }

    fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: JSON.stringify({ key, value: { mode } }),
    }).catch(() => {});
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-theme-mode]");
    if (!button) {
      return;
    }
    const mode = button.dataset.themeMode;
    applyTheme(mode);
    saveThemePreference(mode);
  });

  mediaQuery.addEventListener("change", () => {
    if (currentMode() === "system") {
      applyTheme("system");
    }
  });

  applyTheme(currentMode());
})();
