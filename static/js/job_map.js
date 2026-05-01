(() => {
  const mapElement = document.getElementById("job-map");
  const dataElement = document.getElementById("job-map-data");
  const statusControlsElement = document.getElementById("job-map-status-controls");
  const statusLayersElement = document.getElementById("job-map-status-layers");
  const preferenceElement = document.getElementById("job-map-preference");
  const tileLayerElement = document.getElementById("job-map-tile-layer");
  const escapeHtml = window.AccessAtlas?.escapeHtml;
  const createThemeTileController = window.AccessAtlas?.createThemeTileController;
  const fitLayersOrDefault = window.AccessAtlas?.fitLayersOrDefault;

  if (
    !mapElement ||
    !dataElement ||
    !statusControlsElement ||
    !statusLayersElement ||
    !preferenceElement ||
    !tileLayerElement ||
    typeof escapeHtml !== "function" ||
    typeof createThemeTileController !== "function" ||
    typeof fitLayersOrDefault !== "function" ||
    typeof L === "undefined"
  ) {
    return;
  }

  const sites = JSON.parse(dataElement.textContent);
  const statusLayers = JSON.parse(statusLayersElement.textContent);
  const preference = JSON.parse(preferenceElement.textContent);
  const tileLayer = JSON.parse(tileLayerElement.textContent);
  const savedPreference = preference.value || {};
  const postJSON = window.AccessAtlas?.postJSON;
  const statusByValue = new Map(
    statusLayers.map((statusLayer) => [statusLayer.value, statusLayer]),
  );
  const visibleStatuses = new Set(
    statusLayers
      .filter((statusLayer) => statusLayer.visible)
      .map((statusLayer) => statusLayer.value),
  );

  const map = L.map(mapElement).setView([-41.2865, 174.7762], 5);
  const markerLayer = L.layerGroup().addTo(map);
  const tileController = createThemeTileController(map, tileLayer);
  let viewportSaveTimeout = null;
  let visibleMarkers = [];

  function currentViewport() {
    const center = map.getCenter();
    return {
      lat: center.lat,
      lng: center.lng,
      zoom: map.getZoom(),
    };
  }

  function savePreference() {
    const url = statusControlsElement.dataset.preferenceUrl;

    if (!url) {
      return;
    }

    if (typeof postJSON !== "function") {
      return;
    }

    postJSON(url, {
      key: preference.key,
      value: {
        visible_statuses: Array.from(visibleStatuses),
        viewport: currentViewport(),
      },
    }).catch(() => {});
  }

  function queueViewportSave() {
    window.clearTimeout(viewportSaveTimeout);
    viewportSaveTimeout = window.setTimeout(savePreference, 500);
  }

  function makeMarkerIcon(statusLayer, jobCount) {
    return L.divIcon({
      className: "job-map-marker",
      html: `
        <span class="job-map-marker-pin" style="--job-map-marker-color: ${escapeHtml(statusLayer.color)};">
          <span class="job-map-marker-count">${jobCount}</span>
        </span>
      `,
      iconAnchor: [13, 32],
      iconSize: [26, 32],
      popupAnchor: [0, -28],
    });
  }

  function getDominantStatus(jobs) {
    return jobs
      .map((job) => statusByValue.get(job.statusValue))
      .filter(Boolean)
      .sort((first, second) => second.rank - first.rank)[0];
  }

  function getVisibleJobs(jobs) {
    return jobs.filter((job) => visibleStatuses.has(job.statusValue));
  }

  function buildPopup(site, jobs) {
    const jobList = jobs
      .map((job) => {
        const statusLayer = statusByValue.get(job.statusValue);
        const statusColor = statusLayer ? statusLayer.color : "#667382";
        return `
          <li>
            <a href="${escapeHtml(job.url)}">${escapeHtml(job.title)}</a>
            <span class="job-map-popup-status" style="--job-map-status-color: ${escapeHtml(statusColor)};">${escapeHtml(job.status)}</span>
          </li>
        `;
      })
      .join("");

    return `
      <div class="job-map-popup-title">
        <a href="${escapeHtml(site.url)}">${escapeHtml(site.code)} - ${escapeHtml(site.name)}</a>
      </div>
      <ul class="job-map-popup-list">${jobList}</ul>
    `;
  }

  function drawMarkers() {
    markerLayer.clearLayers();
    const markers = [];

    for (const entry of sites) {
      const site = entry.site;
      const jobs = getVisibleJobs(entry.jobs);
      const latitude = Number(site.latitude);
      const longitude = Number(site.longitude);
      const dominantStatus = getDominantStatus(jobs);

      if (
        jobs.length === 0 ||
        !dominantStatus ||
        !Number.isFinite(latitude) ||
        !Number.isFinite(longitude)
      ) {
        return;
      }

      const marker = L.marker([latitude, longitude], {
        icon: makeMarkerIcon(dominantStatus, jobs.length),
      });
      marker.bindPopup(buildPopup(site, jobs));
      marker.addTo(markerLayer);
      markers.push(marker);
    }

    return markers;
  }

  function fitMarkers(markers) {
    fitLayersOrDefault(map, markers, [-41.2865, 174.7762], 5);
  }

  function updateStatusButton(button, enabled) {
    button.classList.toggle("is-active", enabled);
    button.setAttribute("aria-pressed", enabled ? "true" : "false");
  }

  function buildStatusControls() {
    statusControlsElement.replaceChildren();

    for (const statusLayer of statusLayers) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "job-map-status-button";
      button.style.setProperty("--job-map-status-color", statusLayer.color);
      button.textContent = statusLayer.label;
      updateStatusButton(button, visibleStatuses.has(statusLayer.value));

      button.addEventListener("click", () => {
        if (visibleStatuses.has(statusLayer.value)) {
          visibleStatuses.delete(statusLayer.value);
          updateStatusButton(button, false);
        } else {
          visibleStatuses.add(statusLayer.value);
          updateStatusButton(button, true);
        }
        visibleMarkers = drawMarkers();
        savePreference();
      });

      statusControlsElement.appendChild(button);
    }
  }

  const HomeControl = L.Control.extend({
    onAdd() {
      const container = L.DomUtil.create("div", "leaflet-bar job-map-home-control");
      const button = L.DomUtil.create("button", "", container);
      button.type = "button";
      button.title = "Reset map view";
      button.setAttribute("aria-label", "Reset map view");
      button.innerHTML = '<i class="ti ti-home" aria-hidden="true"></i>';

      L.DomEvent.disableClickPropagation(container);
      L.DomEvent.on(button, "click", () => {
        fitMarkers(visibleMarkers);
        savePreference();
      });

      return container;
    },
  });

  function addHomeControl() {
    map.addControl(new HomeControl({ position: "topleft" }));
  }

  buildStatusControls();
  addHomeControl();
  tileController.apply();
  visibleMarkers = drawMarkers();
  if (
    savedPreference.viewport &&
    Number.isFinite(Number(savedPreference.viewport.lat)) &&
    Number.isFinite(Number(savedPreference.viewport.lng)) &&
    Number.isInteger(savedPreference.viewport.zoom)
  ) {
    map.setView(
      [Number(savedPreference.viewport.lat), Number(savedPreference.viewport.lng)],
      savedPreference.viewport.zoom,
    );
  } else {
    fitMarkers(visibleMarkers);
  }

  map.on("moveend zoomend", queueViewportSave);
})();
