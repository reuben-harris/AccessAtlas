(function () {
  const key = "access-atlas-theme";
  const applyTheme = (theme) => {
    document.documentElement.setAttribute("data-bs-theme", theme);
    localStorage.setItem(key, theme);
  };

  const current = localStorage.getItem(key) || "light";
  applyTheme(current);

  document.addEventListener("click", (event) => {
    if (!event.target.matches("[data-theme-toggle]")) {
      return;
    }
    const next = document.documentElement.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
    applyTheme(next);
  });
})();
