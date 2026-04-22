(function () {
  const storageKey = "access-atlas-theme-mode";
  const modes = ["system", "light", "dark"];
  const modeIcons = {
    system: "ti-device-desktop",
    light: "ti-sun",
    dark: "ti-moon",
  };
  const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

  function getCookie(name) {
    const cookie = document.cookie
      .split(";")
      .map((item) => item.trim())
      .find((item) => item.startsWith(`${name}=`));
    return cookie ? decodeURIComponent(cookie.slice(name.length + 1)) : "";
  }

  function isMode(mode) {
    return modes.includes(mode);
  }

  function resolvedTheme(mode) {
    if (mode === "dark" || (mode === "system" && mediaQuery.matches)) {
      return "dark";
    }
    return "light";
  }

  function currentMode() {
    const toggle = document.querySelector("[data-theme-cycle]");
    if (toggle && isMode(toggle.dataset.themeCurrentMode)) {
      return toggle.dataset.themeCurrentMode;
    }
    const stored = localStorage.getItem(storageKey);
    return isMode(stored) ? stored : "system";
  }

  function nextMode(mode) {
    const index = modes.indexOf(mode);
    return modes[(index + 1) % modes.length];
  }

  function updateControl(mode) {
    document.querySelectorAll("[data-theme-cycle]").forEach((button) => {
      const label = `Theme: ${mode.charAt(0).toUpperCase()}${mode.slice(1)}`;
      const icon = button.querySelector("i");
      button.dataset.themeCurrentMode = mode;
      button.setAttribute("aria-label", label);
      button.setAttribute("title", label);

      if (icon) {
        icon.className = `ti ${modeIcons[mode]}`;
      }
    });
  }

  function applyTheme(mode) {
    const cleanedMode = isMode(mode) ? mode : "system";
    const theme = resolvedTheme(cleanedMode);
    document.documentElement.setAttribute("data-bs-theme", theme);
    document.body?.setAttribute("data-bs-theme", theme);
    localStorage.setItem(storageKey, cleanedMode);
    updateControl(cleanedMode);
  }

  function saveThemePreference(mode) {
    const toggle = document.querySelector("[data-theme-cycle]");
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
    const toggle = event.target.closest("[data-theme-cycle]");
    if (!toggle) {
      return;
    }

    const mode = nextMode(currentMode());
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
