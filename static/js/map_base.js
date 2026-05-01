(() => {
  window.AccessAtlas = window.AccessAtlas || {};
  const accessAtlas = window.AccessAtlas;

  function escapeHtml(value) {
    const span = document.createElement("span");
    span.textContent = value == null ? "" : String(value);
    return span.innerHTML;
  }

  function createThemeTileController(map, tileLayerConfig) {
    let activeTileLayer = null;

    function currentTheme() {
      return document.documentElement.getAttribute("data-bs-theme") === "dark"
        ? "dark"
        : "light";
    }

    function apply() {
      const themeLayer = tileLayerConfig[currentTheme()] || tileLayerConfig.light;
      if (activeTileLayer) {
        map.removeLayer(activeTileLayer);
      }
      activeTileLayer = L.tileLayer(themeLayer.url, {
        attribution: themeLayer.attribution,
        maxZoom: tileLayerConfig.maxZoom,
      }).addTo(map);
    }

    const observer = new MutationObserver((mutations) => {
      if (mutations.some((mutation) => mutation.attributeName === "data-bs-theme")) {
        apply();
      }
    });

    observer.observe(document.documentElement, { attributes: true });
    return { apply };
  }

  function fitLayersOrDefault(map, layers, defaultCenter, defaultZoom, pad = 0.2) {
    if (layers.length > 0) {
      map.fitBounds(L.featureGroup(layers).getBounds().pad(pad));
      return;
    }
    map.setView(defaultCenter, defaultZoom);
  }

  accessAtlas.escapeHtml = escapeHtml;
  accessAtlas.createThemeTileController = createThemeTileController;
  accessAtlas.fitLayersOrDefault = fitLayersOrDefault;
})();
