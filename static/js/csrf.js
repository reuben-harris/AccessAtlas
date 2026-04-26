(function () {
  // Shared frontend helper for authenticated JSON POST requests.
  // Centralizing CSRF handling here keeps map/theme scripts consistent
  // and avoids duplicating cookie parsing logic across files.
  const accessAtlas = (window.AccessAtlas = window.AccessAtlas || {});

  function getCookie(name) {
    const cookie = document.cookie
      .split(";")
      .map((item) => item.trim())
      .find((item) => item.startsWith(`${name}=`));
    return cookie ? decodeURIComponent(cookie.slice(name.length + 1)) : "";
  }

  function getCsrfToken() {
    // Django expects the CSRF token in X-CSRFToken for same-origin POSTs.
    return getCookie("csrftoken");
  }

  function postJSON(url, payload) {
    // Use this for app-side preference and settings writes.
    // It automatically includes credentials and CSRF protection.
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify(payload),
    });
  }

  accessAtlas.getCsrfToken = getCsrfToken;
  accessAtlas.postJSON = postJSON;
})();
