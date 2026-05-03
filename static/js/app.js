(() => {
  for (const element of document.querySelectorAll('[data-bs-toggle="popover"]')) {
    new bootstrap.Popover(element);
  }
})();
