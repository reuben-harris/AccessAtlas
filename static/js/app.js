(() => {
  for (const element of document.querySelectorAll('[data-bs-toggle="popover"]')) {
    new bootstrap.Popover(element);
  }

  for (const link of document.querySelectorAll("[data-bug-report-link]")) {
    link.addEventListener("click", () => {
      const url = new URL(link.href);
      const body = [
        "<!-- Notes -->",
        "Do not include passwords, tokens, private access details, or other secrets.",
        "<!-- -->",
        "",
        "## Explain your issue",
        "",
        "## Page",
        window.location.href,
      ].join("\n");

      // Build the issue context at click time so the report points at the page
      // the user was actually viewing, not the page that rendered the shell.
      if (!url.searchParams.has("title")) {
        url.searchParams.set("title", "Bug report: ");
      }
      if (!url.searchParams.has("body")) {
        url.searchParams.set("body", body);
      }
      link.href = url.toString();
    });
  }
})();
