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

  function addHomeControl(map, onClick, options = {}) {
    const controlClassName =
      options.controlClassName || "access-atlas-map-home-control";
    const position = options.position || "topleft";
    const title = options.title || "Reset map view";
    const ariaLabel = options.ariaLabel || "Reset map view";
    const iconClass = options.iconClass || "ti-home";

    const HomeControl = L.Control.extend({
      onAdd() {
        const container = L.DomUtil.create("div", `leaflet-bar ${controlClassName}`);
        const button = L.DomUtil.create("button", "", container);
        button.type = "button";
        button.title = title;
        button.setAttribute("aria-label", ariaLabel);
        button.innerHTML = `<i class="ti ${iconClass}" aria-hidden="true"></i>`;

        L.DomEvent.disableClickPropagation(container);
        L.DomEvent.on(button, "click", () => {
          onClick();
        });

        return container;
      },
    });

    map.addControl(new HomeControl({ position }));
  }

  function settleMapLayout(map, onLayout) {
    if (!map || typeof map.invalidateSize !== "function") {
      return;
    }

    const applyLayout = () => {
      map.invalidateSize({ pan: false });
      if (typeof onLayout === "function") {
        onLayout();
      }
    };

    /* Flex-based map layouts can report the wrong size during initial page
       render. Running after two animation frames waits for layout to settle
       before Leaflet computes bounds and tiles. */
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(applyLayout);
    });
    window.addEventListener("resize", applyLayout);
  }

  accessAtlas.escapeHtml = escapeHtml;
  accessAtlas.createThemeTileController = createThemeTileController;
  accessAtlas.fitLayersOrDefault = fitLayersOrDefault;
  accessAtlas.addHomeControl = addHomeControl;
  accessAtlas.settleMapLayout = settleMapLayout;
})();
