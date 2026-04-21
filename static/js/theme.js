(function () {
  const key = "access-atlas-theme";
  const applyTheme = (theme) => {
    document.documentElement.setAttribute("data-bs-theme", theme);
    document.body?.setAttribute("data-bs-theme", theme);
    localStorage.setItem(key, theme);
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      const nextTheme = theme === "dark" ? "light" : "dark";
      const label = `Switch to ${nextTheme} theme`;
      button.setAttribute("aria-label", label);
      button.setAttribute("title", label);
    });
  };

  const current = localStorage.getItem(key) || "light";
  applyTheme(current);

  document.addEventListener("click", (event) => {
    const toggle = event.target.closest("[data-theme-toggle]");
    if (!toggle) {
      return;
    }
    const next = document.documentElement.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
    applyTheme(next);
  });
})();
