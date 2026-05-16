// Provides shared Leaflet map helpers.
(() => {
  window.AccessAtlas = window.AccessAtlas || {};
  const accessAtlas = window.AccessAtlas;
  const MISSING_SITE_CODE_LABEL = "code not set";

  function escapeHtml(value) {
    const span = document.createElement("span");
    span.textContent = value == null ? "" : String(value);
    return span.innerHTML;
  }

  function siteCodeLabel(value) {
    return value || MISSING_SITE_CODE_LABEL;
  }

  function siteCodeHtml(value) {
    const code = siteCodeLabel(value);
    const content = escapeHtml(code);
    return code === MISSING_SITE_CODE_LABEL
      ? `<span class="fst-italic">${content}</span>`
      : content;
  }

  function resolvedTheme() {
    return document.documentElement.getAttribute("data-bs-theme") === "dark"
      ? "dark"
      : "light";
  }

  function createBasemapController(map, basemapConfig, preference, mapElement) {
    let activeTileLayer = null;
    const configuredLayers = Array.isArray(basemapConfig?.layers)
      ? basemapConfig.layers
      : [];
    const layers = configuredLayers.filter(
      (layer) =>
        layer && typeof layer.id === "string" && typeof layer.label === "string",
    );
    const availableLayers = layers.filter((layer) => isLayerAvailable(layer));
    const layersById = new Map(availableLayers.map((layer) => [layer.id, layer]));
    const defaults =
      basemapConfig && typeof basemapConfig.defaults === "object"
        ? basemapConfig.defaults
        : {};
    const savedPreference =
      preference && typeof preference.value === "object" ? preference.value : {};
    const changeHandlers = new Set();

    function fallbackLayerId(theme) {
      if (layersById.has(defaults[theme])) {
        return defaults[theme];
      }
      return availableLayers[0]?.id || "";
    }

    const selectedByTheme = {
      light: layersById.has(savedPreference.light)
        ? savedPreference.light
        : fallbackLayerId("light"),
      dark: layersById.has(savedPreference.dark)
        ? savedPreference.dark
        : fallbackLayerId("dark"),
    };

    function currentLayerId() {
      const theme = resolvedTheme();
      return layersById.has(selectedByTheme[theme])
        ? selectedByTheme[theme]
        : fallbackLayerId(theme);
    }

    function currentLayer() {
      return layersById.get(currentLayerId()) || availableLayers[0] || null;
    }

    function notifyChange() {
      for (const handler of changeHandlers) {
        handler({
          layerId: currentLayerId(),
          theme: resolvedTheme(),
        });
      }
    }

    function tileEntries(layer) {
      if (Array.isArray(layer.tiles)) {
        return layer.tiles.filter((tile) => tile && typeof tile.url === "string");
      }
      return typeof layer?.url === "string" ? [layer] : [];
    }

    function isLayerAvailable(layer) {
      return layer?.available !== false && tileEntries(layer).length > 0;
    }

    function tileOptions(tile) {
      const options = {
        attribution: tile.attribution || "",
      };
      const maxZoom = Number(tile.maxZoom);
      if (Number.isFinite(maxZoom)) {
        options.maxZoom = maxZoom;
      }
      const minZoom = Number(tile.minZoom);
      if (Number.isFinite(minZoom)) {
        options.minZoom = minZoom;
      }
      const tileSize = Number(tile.tileSize);
      if (Number.isFinite(tileSize)) {
        options.tileSize = tileSize;
      }
      const zoomOffset = Number(tile.zoomOffset);
      if (Number.isFinite(zoomOffset)) {
        options.zoomOffset = zoomOffset;
      }
      const opacity = Number(tile.opacity);
      if (Number.isFinite(opacity)) {
        options.opacity = Math.max(0, Math.min(1, opacity));
      }
      const zIndex = Number(tile.zIndex);
      if (Number.isFinite(zIndex)) {
        options.zIndex = zIndex;
      }
      if (typeof tile.referrerPolicy === "string") {
        options.referrerPolicy = tile.referrerPolicy;
      }
      if (typeof tile.subdomains === "string" || Array.isArray(tile.subdomains)) {
        options.subdomains = tile.subdomains;
      }
      return options;
    }

    function savePreference() {
      const url = mapElement?.dataset.basemapPreferenceUrl;
      const key = preference?.key;
      const postJSON = accessAtlas.postJSON;
      if (!url || !key || typeof postJSON !== "function") {
        return;
      }
      postJSON(url, {
        key,
        value: {
          light: selectedByTheme.light,
          dark: selectedByTheme.dark,
        },
      }).catch(() => {});
    }

    function apply() {
      // Recreate the tile layer so theme changes and user layer choices update
      // attribution and provider-specific options without leaking old layers.
      const layer = currentLayer();
      if (!layer) {
        return;
      }
      if (activeTileLayer) {
        map.removeLayer(activeTileLayer);
      }
      const tileLayers = tileEntries(layer).map((tile) =>
        L.tileLayer(tile.url, tileOptions(tile)),
      );
      activeTileLayer =
        tileLayers.length === 1 ? tileLayers[0] : L.layerGroup(tileLayers);
      activeTileLayer.addTo(map);
      notifyChange();
    }

    function setLayer(layerId, options = {}) {
      if (!layersById.has(layerId)) {
        return;
      }
      selectedByTheme[resolvedTheme()] = layerId;
      apply();
      if (options.save !== false) {
        savePreference();
      }
    }

    const observer = new MutationObserver((mutations) => {
      if (mutations.some((mutation) => mutation.attributeName === "data-bs-theme")) {
        apply();
      }
    });

    observer.observe(document.documentElement, { attributes: true });
    return {
      apply,
      currentLayerId,
      isLayerAvailable,
      tileEntries,
      layers: () => layers.slice(),
      onChange(handler) {
        changeHandlers.add(handler);
        return () => changeHandlers.delete(handler);
      },
      setLayer,
    };
  }

  function createThemeTileController(map, tileLayerConfig) {
    const basemapConfig = {
      defaults: {
        light: "light",
        dark: "dark",
      },
      layers: [
        {
          id: "light",
          label: "Light",
          url: tileLayerConfig.light?.url,
          attribution: tileLayerConfig.light?.attribution,
          maxZoom: tileLayerConfig.maxZoom,
        },
        {
          id: "dark",
          label: "Dark",
          url: tileLayerConfig.dark?.url,
          attribution: tileLayerConfig.dark?.attribution,
          maxZoom: tileLayerConfig.maxZoom,
        },
      ].filter((layer) => layer.url),
    };
    return createBasemapController(map, basemapConfig, { value: {} }, null);
  }

  function fitLayersOrDefault(map, layers, defaultCenter, defaultZoom, pad = 0.05) {
    if (layers.length > 0) {
      map.fitBounds(L.featureGroup(layers).getBounds().pad(pad));
      return;
    }
    map.setView(defaultCenter, defaultZoom);
  }

  function createLongitudeNormalizer(longitudes) {
    // Longitudes wrap at +/-180. Pick the shortest display window so sites on
    // either side of the antimeridian render together instead of on separate
    // repeated world copies.
    const normalizedLongitudes = longitudes
      .map((longitude) => Number(longitude))
      .filter((longitude) => Number.isFinite(longitude))
      .map((longitude) => ((((longitude + 180) % 360) + 360) % 360) - 180)
      .sort((first, second) => first - second);

    if (normalizedLongitudes.length < 2) {
      const normalizer = (longitude) => Number(longitude);
      normalizer.crossesAntimeridian = false;
      return normalizer;
    }

    let largestGap = -1;
    let startIndex = 0;
    for (let index = 0; index < normalizedLongitudes.length; index += 1) {
      const current = normalizedLongitudes[index];
      const next =
        index === normalizedLongitudes.length - 1
          ? normalizedLongitudes[0] + 360
          : normalizedLongitudes[index + 1];
      const gap = next - current;
      if (gap > largestGap) {
        largestGap = gap;
        startIndex = (index + 1) % normalizedLongitudes.length;
      }
    }

    const displayStart = normalizedLongitudes[startIndex];

    const normalizer = (longitude) => {
      let normalized = ((((Number(longitude) + 180) % 360) + 360) % 360) - 180;
      if (normalized < displayStart) {
        normalized += 360;
      }
      return normalized;
    };
    normalizer.crossesAntimeridian = startIndex !== 0;
    return normalizer;
  }

  function normalizeLatLng(latitude, longitude, longitudeNormalizer) {
    return [Number(latitude), longitudeNormalizer(longitude)];
  }

  function minimumWorldFillZoom(map) {
    const size = map.getSize();
    const height = size?.y || 0;
    if (!Number.isFinite(height) || height <= 0) {
      return 2;
    }
    return Math.max(2, Math.ceil(Math.log2(height / 256)));
  }

  function configureMapConstraints(map) {
    // Leaflet repeats the world horizontally. Bound panning to adjacent world
    // copies so users can inspect antimeridian data without scrolling forever.
    const maxLatitude = 85.05112878;
    map.setMaxBounds([
      [-maxLatitude, -540],
      [maxLatitude, 540],
    ]);
    map.options.maxBoundsViscosity = 1;

    function applyMinZoom() {
      const minZoom = minimumWorldFillZoom(map);
      map.setMinZoom(minZoom);
      if (map.getZoom() < minZoom) {
        map.setZoom(minZoom, { animate: false });
      }
    }

    applyMinZoom();
    map.on("resize", applyMinZoom);
    return { applyMinZoom };
  }

  function markerScaleForZoom() {
    return "normal";
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
        // Use a shared Leaflet control wrapper so the jobs map, site map, and
        // access map all inherit one consistent home/reset interaction.
        const container = L.DomUtil.create("div", `leaflet-bar ${controlClassName}`);
        const button = L.DomUtil.create("button", "", container);
        button.type = "button";
        button.title = title;
        button.setAttribute("aria-label", ariaLabel);
        button.innerHTML = `<i class="ti ${iconClass}" aria-hidden="true"></i>`;

        L.DomEvent.disableClickPropagation(container);
        L.DomEvent.on(button, "click", (event) => {
          L.DomEvent.stop(event);
          onClick();
        });

        return container;
      },
    });

    map.addControl(new HomeControl({ position }));
  }

  function addFilterControl(map, onClick, options = {}) {
    const position = options.position || "topright";
    const title = options.title || "Open filters";
    const ariaLabel = options.ariaLabel || "Open filters";
    const initialCount = Number(options.count || 0);

    const FilterControl = L.Control.extend({
      onAdd() {
        const container = L.DomUtil.create(
          "div",
          "leaflet-bar access-atlas-map-filter-control",
        );
        const button = L.DomUtil.create("button", "", container);
        button.type = "button";
        button.title = title;
        button.setAttribute("aria-label", ariaLabel);
        button.innerHTML =
          '<i class="ti ti-adjustments-horizontal" aria-hidden="true"></i>';
        this._badge = L.DomUtil.create("span", "access-atlas-map-filter-badge", button);

        L.DomEvent.disableClickPropagation(container);
        L.DomEvent.on(button, "click", (event) => {
          L.DomEvent.stop(event);
          onClick();
        });

        this.setCount(initialCount);
        return container;
      },
      setCount(count) {
        const normalizedCount = Number(count);
        const badgeCount = Number.isFinite(normalizedCount)
          ? Math.max(0, normalizedCount)
          : 0;
        if (!this._badge) {
          return;
        }
        this._badge.textContent = String(badgeCount);
        this._badge.hidden = badgeCount === 0;
      },
    });

    const control = new FilterControl({ position });
    map.addControl(control);
    return control;
  }

  function addBasemapControl(map, basemapController, options = {}) {
    const position = options.position || "topright";
    const title = options.title || "Change map layer";
    const ariaLabel = options.ariaLabel || "Change map layer";
    const layers = basemapController?.layers?.() || [];

    if (layers.length < 2) {
      return null;
    }

    const BasemapControl = L.Control.extend({
      onAdd() {
        const container = L.DomUtil.create(
          "div",
          "leaflet-bar access-atlas-map-layer-control",
        );
        const button = L.DomUtil.create("button", "", container);
        const menu = L.DomUtil.create("div", "access-atlas-map-layer-menu", container);
        const menuId = `map-layer-menu-${Math.random().toString(36).slice(2)}`;
        const itemButtons = new Map();
        const itemPreviews = new Map();

        button.type = "button";
        button.title = title;
        button.setAttribute("aria-label", ariaLabel);
        button.setAttribute("aria-haspopup", "menu");
        button.setAttribute("aria-expanded", "false");
        button.setAttribute("aria-controls", menuId);
        button.innerHTML = '<i class="ti ti-layers-subtract" aria-hidden="true"></i>';

        menu.id = menuId;
        menu.hidden = true;
        menu.setAttribute("role", "menu");

        function setMenuOpen(isOpen) {
          menu.hidden = !isOpen;
          button.setAttribute("aria-expanded", isOpen ? "true" : "false");
          if (isOpen) {
            renderPreviews();
          }
        }

        function previewZoom(tile) {
          const currentZoom = Math.round(map.getZoom());
          const minZoom = Number(tile.minZoom);
          const maxZoom = Number(tile.maxZoom);
          return Math.max(
            Number.isFinite(minZoom) ? minZoom : 0,
            Math.min(Number.isFinite(maxZoom) ? maxZoom : 22, currentZoom),
          );
        }

        function previewTileUrl(tile) {
          if (!tile.url) {
            return "";
          }
          const mapZoom = previewZoom(tile);
          const tileSize = Number.isFinite(Number(tile.tileSize))
            ? Number(tile.tileSize)
            : 256;
          const zoomOffset = Number.isFinite(Number(tile.zoomOffset))
            ? Number(tile.zoomOffset)
            : 0;
          const tileZoom = mapZoom + zoomOffset;
          const scale = 2 ** tileZoom;
          const point = map
            .project(map.getCenter(), mapZoom)
            .divideBy(tileSize)
            .floor();
          const x = ((point.x % scale) + scale) % scale;
          const y = Math.max(0, Math.min(scale - 1, point.y));
          const subdomains = Array.isArray(tile.subdomains)
            ? tile.subdomains
            : String(tile.subdomains || "abc").split("");
          const subdomain =
            subdomains.length > 0
              ? subdomains[Math.abs(x + y) % subdomains.length]
              : "";
          return L.Util.template(tile.url, {
            r: L.Browser.retina ? "@2x" : "",
            s: subdomain,
            x,
            y,
            z: tileZoom,
          });
        }

        function renderPreviews() {
          for (const layer of layers) {
            const preview = itemPreviews.get(layer.id);
            if (!preview) {
              continue;
            }
            for (const tileImage of preview.querySelectorAll(
              ".access-atlas-map-layer-preview-tile",
            )) {
              tileImage.remove();
            }
            if (!basemapController.isLayerAvailable(layer)) {
              continue;
            }
            for (const tile of basemapController.tileEntries(layer)) {
              const tileUrl = previewTileUrl(tile);
              if (!tileUrl) {
                continue;
              }
              const tileImage = document.createElement("img");
              tileImage.className = "access-atlas-map-layer-preview-tile";
              tileImage.alt = "";
              tileImage.decoding = "async";
              if (typeof tile.referrerPolicy === "string") {
                tileImage.referrerPolicy = tile.referrerPolicy;
              }
              tileImage.src = tileUrl;
              preview.appendChild(tileImage);
            }
          }
        }

        function renderActiveLayer() {
          const activeLayerId = basemapController.currentLayerId();
          for (const [layerId, itemButton] of itemButtons) {
            const isActive = layerId === activeLayerId;
            itemButton.classList.toggle("is-active", isActive);
            itemButton.setAttribute("aria-checked", isActive ? "true" : "false");
          }
        }

        for (const layer of layers) {
          const itemButton = L.DomUtil.create(
            "button",
            "access-atlas-map-layer-item",
            menu,
          );
          itemButton.type = "button";
          itemButton.setAttribute("role", "menuitemradio");
          const preview = L.DomUtil.create(
            "span",
            "access-atlas-map-layer-preview",
            itemButton,
          );
          const isAvailable = basemapController.isLayerAvailable(layer);
          const disabledReason =
            typeof layer.disabledReason === "string"
              ? layer.disabledReason
              : "This map layer is not configured.";
          const label = L.DomUtil.create(
            "span",
            "access-atlas-map-layer-label",
            preview,
          );
          const check = L.DomUtil.create(
            "i",
            "ti ti-check access-atlas-map-layer-check",
            preview,
          );
          label.textContent = layer.label;
          check.setAttribute("aria-hidden", "true");
          itemButton.disabled = !isAvailable;
          itemButton.classList.toggle("is-unavailable", !isAvailable);
          if (!isAvailable) {
            itemButton.setAttribute("aria-disabled", "true");
            itemButton.title = disabledReason;
            const unavailable = L.DomUtil.create(
              "span",
              "access-atlas-map-layer-unavailable",
              preview,
            );
            unavailable.innerHTML =
              '<i class="ti ti-lock" aria-hidden="true"></i><span>Setup needed</span>';
          }
          itemButtons.set(layer.id, itemButton);
          itemPreviews.set(layer.id, preview);
          L.DomEvent.on(itemButton, "click", (event) => {
            L.DomEvent.stop(event);
            if (!isAvailable) {
              return;
            }
            basemapController.setLayer(layer.id);
          });
        }

        L.DomEvent.disableClickPropagation(container);
        L.DomEvent.disableScrollPropagation(container);
        L.DomEvent.on(button, "click", (event) => {
          L.DomEvent.stop(event);
          const nextOpen = menu.hidden;
          setMenuOpen(nextOpen);
        });
        document.addEventListener("click", (event) => {
          if (!container.contains(event.target)) {
            setMenuOpen(false);
          }
        });
        document.addEventListener("keydown", (event) => {
          if (event.key === "Escape") {
            setMenuOpen(false);
          }
        });
        basemapController.onChange(renderActiveLayer);
        map.on("moveend zoomend", () => {
          if (!menu.hidden) {
            renderPreviews();
          }
        });
        renderActiveLayer();

        return container;
      },
    });

    const control = new BasemapControl({ position });
    map.addControl(control);
    return control;
  }

  function createFullscreenSafeOffcanvasController(mapElement, options = {}) {
    const offcanvasId =
      typeof options === "string"
        ? options
        : options.offcanvasId || "list-filter-offcanvas";
    const map = typeof options === "object" ? options.map : null;
    const offcanvasElement = document.getElementById(offcanvasId);
    if (!offcanvasElement || !mapElement) {
      return null;
    }

    const originalParent = offcanvasElement.parentNode;
    const placeholder = document.createComment("list filter offcanvas");
    let fullscreenPanelVisible = false;
    let fullscreenEventsShielded = false;
    let mapKeyboardSuspended = false;
    let mapKeyboardWasEnabled = false;
    let fallbackHideTimeout = null;
    originalParent.insertBefore(placeholder, offcanvasElement);
    offcanvasElement.setAttribute("data-bs-backdrop", "false");
    const fullscreenShieldedEvents = [
      "click",
      "contextmenu",
      "dblclick",
      "keydown",
      // TomSelect relies on its document-level mousedown handler to keep
      // focus while selecting options, so do not stop mousedown here.
      "wheel",
    ];

    function mapIsFullscreen() {
      return (
        document.fullscreenElement === mapElement ||
        mapElement.matches(":fullscreen") ||
        mapElement.classList.contains("leaflet-pseudo-fullscreen")
      );
    }

    function moveForFullscreen() {
      if (mapIsFullscreen() && offcanvasElement.parentNode !== mapElement) {
        // Browser fullscreen only displays descendants of the fullscreen
        // element, so the shared offcanvas has to move into the Leaflet map
        // before it can appear over a fullscreen map.
        mapElement.appendChild(offcanvasElement);
      }
    }

    function stopMapEvent(event) {
      event.stopPropagation();
    }

    function setFullscreenEventShield(enabled) {
      if (fullscreenEventsShielded === enabled) {
        return;
      }
      fullscreenEventsShielded = enabled;
      const method = enabled ? "addEventListener" : "removeEventListener";
      for (const eventName of fullscreenShieldedEvents) {
        offcanvasElement[method](eventName, stopMapEvent);
      }
    }

    function setMapKeyboardSuspended(enabled) {
      const keyboard = map?.keyboard;
      if (!keyboard) {
        return;
      }
      // Let form widgets keep their normal document-level event flow while
      // preventing Leaflet from focusing the map and handling keyboard input.
      if (enabled && !mapKeyboardSuspended) {
        mapKeyboardWasEnabled = keyboard.enabled();
        if (mapKeyboardWasEnabled) {
          keyboard.disable();
        }
        mapKeyboardSuspended = true;
      } else if (!enabled && mapKeyboardSuspended) {
        if (mapKeyboardWasEnabled) {
          keyboard.enable();
        }
        mapKeyboardSuspended = false;
        mapKeyboardWasEnabled = false;
      }
    }

    function restoreParent() {
      if (
        offcanvasElement.parentNode !== originalParent &&
        placeholder.parentNode === originalParent
      ) {
        setMapKeyboardSuspended(false);
        setFullscreenEventShield(false);
        originalParent.insertBefore(offcanvasElement, placeholder.nextSibling);
      }
    }

    function getOffcanvasConstructor() {
      return globalThis.bootstrap?.Offcanvas || window.bootstrap?.Offcanvas;
    }

    function fallbackShow() {
      offcanvasElement.classList.add("show");
      offcanvasElement.style.visibility = "visible";
      offcanvasElement.removeAttribute("aria-hidden");
      offcanvasElement.setAttribute("aria-modal", "true");
      offcanvasElement.setAttribute("role", "dialog");
    }

    function finishFullscreenHide() {
      window.clearTimeout(fallbackHideTimeout);
      fallbackHideTimeout = null;
      fullscreenPanelVisible = false;
      setMapKeyboardSuspended(false);
      setFullscreenEventShield(false);
      offcanvasElement.classList.remove("list-filter-offcanvas--map-fullscreen");
      offcanvasElement.style.removeProperty("visibility");
      offcanvasElement.removeAttribute("aria-modal");
      offcanvasElement.setAttribute("aria-hidden", "true");
      restoreParent();
    }

    function hideFullscreenPanel() {
      if (!fullscreenPanelVisible) {
        return;
      }
      offcanvasElement.classList.remove("show");
      offcanvasElement.addEventListener("transitionend", finishFullscreenHide, {
        once: true,
      });
      fallbackHideTimeout = window.setTimeout(finishFullscreenHide, 400);
    }

    function fallbackHide() {
      offcanvasElement.classList.remove("show");
      offcanvasElement.style.removeProperty("visibility");
      offcanvasElement.removeAttribute("aria-modal");
      offcanvasElement.setAttribute("aria-hidden", "true");
      setMapKeyboardSuspended(false);
      setFullscreenEventShield(false);
      restoreParent();
    }

    function showFullscreenPanel() {
      moveForFullscreen();
      // Once the form panel lives inside Leaflet's fullscreen element, keep
      // clicks, wheels, and keys out of the map without blocking widget
      // selection flows that depend on document-level mouse events.
      setMapKeyboardSuspended(true);
      setFullscreenEventShield(true);
      offcanvasElement.classList.add("list-filter-offcanvas--map-fullscreen");
      offcanvasElement.classList.remove("show");
      offcanvasElement.style.visibility = "visible";
      offcanvasElement.removeAttribute("aria-hidden");
      offcanvasElement.setAttribute("aria-modal", "true");
      offcanvasElement.setAttribute("role", "dialog");
      offcanvasElement.getBoundingClientRect();
      window.requestAnimationFrame(() => {
        fullscreenPanelVisible = true;
        offcanvasElement.classList.add("show");
      });
    }

    function show() {
      if (mapIsFullscreen()) {
        showFullscreenPanel();
        return;
      }

      moveForFullscreen();
      const Offcanvas = getOffcanvasConstructor();
      if (typeof Offcanvas !== "function") {
        fallbackShow();
        return;
      }

      // Bootstrap calculates the offcanvas transition from its current DOM
      // position. In fullscreen the panel may have just moved into the map
      // element, so wait one frame before showing it to preserve animation.
      window.requestAnimationFrame(() => {
        try {
          Offcanvas.getOrCreateInstance(offcanvasElement, {
            backdrop: false,
            scroll: true,
          }).show();
        } catch (_error) {
          fallbackShow();
        }
      });
    }

    offcanvasElement.addEventListener("hidden.bs.offcanvas", restoreParent);
    offcanvasElement.addEventListener("click", (event) => {
      const dismissButton = event.target.closest('[data-bs-dismiss="offcanvas"]');
      if (dismissButton && fullscreenPanelVisible) {
        event.preventDefault();
        event.stopPropagation();
        hideFullscreenPanel();
        return;
      }
      if (!dismissButton || typeof getOffcanvasConstructor() === "function") {
        return;
      }
      event.preventDefault();
      fallbackHide();
    });
    document.addEventListener("fullscreenchange", () => {
      if (!document.fullscreenElement) {
        hideFullscreenPanel();
        restoreParent();
      }
    });

    return { show };
  }

  function addFullscreenControl(map, options = {}) {
    if (typeof L === "undefined") {
      return null;
    }

    const position = options.position || "topright";
    const enterTitle = options.title?.false || "Enter fullscreen";
    const exitTitle = options.title?.true || "Exit fullscreen";
    const enterAriaLabel = options.ariaLabel?.false || "Enter fullscreen";
    const exitAriaLabel = options.ariaLabel?.true || "Exit fullscreen";
    const controlOptions = {
      position,
      title: enterTitle,
      titleCancel: exitTitle,
      forceSeparateButton: true,
    };

    let control = null;
    // Support both plugin factory shapes because the fullscreen dependency has
    // changed API surface across versions and build targets.
    if (typeof L.control?.fullscreen === "function") {
      control = L.control.fullscreen(controlOptions);
    } else if (typeof L.Control?.FullScreen === "function") {
      control = new L.Control.FullScreen(controlOptions);
    } else {
      return null;
    }

    control.addTo(map);

    function buttonElement() {
      return control.getContainer()?.querySelector("a") || null;
    }

    function isFullscreenActive() {
      if (typeof map.isFullscreen === "function") {
        return map.isFullscreen();
      }
      return document.fullscreenElement != null;
    }

    function updateButtonState() {
      const button = buttonElement();
      if (!button) {
        return;
      }
      const active = isFullscreenActive();
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-label", active ? exitAriaLabel : enterAriaLabel);
      button.setAttribute("title", active ? exitTitle : enterTitle);
    }

    updateButtonState();
    const button = buttonElement();
    if (button) {
      button.addEventListener("click", () => {
        window.setTimeout(() => {
          button.blur();
        }, 0);
      });
    }
    map.on("fullscreenchange", updateButtonState);
    document.addEventListener("fullscreenchange", updateButtonState);
    return control;
  }

  function settleMapLayout(map, onLayout) {
    if (!map || typeof map.invalidateSize !== "function") {
      return;
    }

    const invalidateLayout = () => {
      map.invalidateSize({ pan: false });
    };

    const applyInitialLayout = () => {
      invalidateLayout();
      if (typeof onLayout === "function") {
        onLayout();
      }
    };

    /* Flex-based map layouts can report the wrong size during initial page
       render. Running after two animation frames waits for layout to settle
       before Leaflet computes bounds and tiles. */
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(applyInitialLayout);
    });
    window.addEventListener("resize", invalidateLayout);
  }

  accessAtlas.escapeHtml = escapeHtml;
  accessAtlas.siteCodeLabel = siteCodeLabel;
  accessAtlas.siteCodeHtml = siteCodeHtml;
  accessAtlas.createBasemapController = createBasemapController;
  accessAtlas.createThemeTileController = createThemeTileController;
  accessAtlas.fitLayersOrDefault = fitLayersOrDefault;
  accessAtlas.createLongitudeNormalizer = createLongitudeNormalizer;
  accessAtlas.normalizeLatLng = normalizeLatLng;
  accessAtlas.configureMapConstraints = configureMapConstraints;
  accessAtlas.markerScaleForZoom = markerScaleForZoom;
  accessAtlas.addHomeControl = addHomeControl;
  accessAtlas.addFilterControl = addFilterControl;
  accessAtlas.addBasemapControl = addBasemapControl;
  accessAtlas.createFullscreenSafeOffcanvasController =
    createFullscreenSafeOffcanvasController;
  accessAtlas.addFullscreenControl = addFullscreenControl;
  accessAtlas.settleMapLayout = settleMapLayout;
})();
