// Renders the Jobs map.
(() => {
  const mapElement = document.getElementById("job-map");
  const dataElement = document.getElementById("job-map-data");
  const statusLayersElement = document.getElementById("job-map-status-layers");
  const preferenceElement = document.getElementById("job-map-preference");
  const basemapConfigElement = document.getElementById("map-basemap-config");
  const basemapPreferenceElement = document.getElementById("map-basemap-preference");
  const bulkForm = document.getElementById("job-map-bulk-form");
  const selectionListElement = document.querySelector("[data-job-map-selection-list]");
  const selectionSummaryElement = document.querySelector(
    "[data-job-map-selection-summary]",
  );
  const selectionSubmitButton = document.querySelector(
    "[data-job-map-selection-submit]",
  );
  const escapeHtml = window.AccessAtlas?.escapeHtml;
  const siteCodeHtml = window.AccessAtlas?.siteCodeHtml;
  const createBasemapController = window.AccessAtlas?.createBasemapController;
  const fitLayersOrDefault = window.AccessAtlas?.fitLayersOrDefault;
  const sharedAddHomeControl = window.AccessAtlas?.addHomeControl;
  const addFilterControl = window.AccessAtlas?.addFilterControl;
  const addBasemapControl = window.AccessAtlas?.addBasemapControl;
  const addFullscreenControl = window.AccessAtlas?.addFullscreenControl;
  const createFullscreenSafeOffcanvasController =
    window.AccessAtlas?.createFullscreenSafeOffcanvasController;
  const createMapBulkSelectionController =
    window.AccessAtlas?.createMapBulkSelectionController;
  const settleMapLayout = window.AccessAtlas?.settleMapLayout;
  const createLongitudeNormalizer = window.AccessAtlas?.createLongitudeNormalizer;
  const normalizeLatLng = window.AccessAtlas?.normalizeLatLng;
  const configureMapConstraints = window.AccessAtlas?.configureMapConstraints;
  const markerScaleForZoom = window.AccessAtlas?.markerScaleForZoom;

  if (
    !mapElement ||
    !dataElement ||
    !statusLayersElement ||
    !preferenceElement ||
    !basemapConfigElement ||
    !basemapPreferenceElement ||
    !bulkForm ||
    !selectionListElement ||
    !selectionSummaryElement ||
    !selectionSubmitButton ||
    typeof escapeHtml !== "function" ||
    typeof siteCodeHtml !== "function" ||
    typeof createBasemapController !== "function" ||
    typeof fitLayersOrDefault !== "function" ||
    typeof sharedAddHomeControl !== "function" ||
    typeof addFilterControl !== "function" ||
    typeof addBasemapControl !== "function" ||
    typeof addFullscreenControl !== "function" ||
    typeof createFullscreenSafeOffcanvasController !== "function" ||
    typeof createMapBulkSelectionController !== "function" ||
    typeof settleMapLayout !== "function" ||
    typeof createLongitudeNormalizer !== "function" ||
    typeof normalizeLatLng !== "function" ||
    typeof configureMapConstraints !== "function" ||
    typeof markerScaleForZoom !== "function" ||
    typeof L === "undefined"
  ) {
    return;
  }

  const sites = JSON.parse(dataElement.textContent);
  const statusLayers = JSON.parse(statusLayersElement.textContent);
  const preference = JSON.parse(preferenceElement.textContent);
  const basemapConfig = JSON.parse(basemapConfigElement.textContent);
  const basemapPreference = JSON.parse(basemapPreferenceElement.textContent);
  const savedPreference = preference.value || {};
  const postJSON = window.AccessAtlas?.postJSON;
  const initialFilterCount = Number(mapElement.dataset.filterCount || 0);
  const statusByValue = new Map(
    statusLayers.map((statusLayer) => [statusLayer.value, statusLayer]),
  );
  const longitudeNormalizer = createLongitudeNormalizer(
    sites.map((entry) => entry.site?.longitude),
  );
  const map = L.map(mapElement).setView([-41.2865, 174.7762], 5);
  const filterPanel = createFullscreenSafeOffcanvasController(mapElement, { map });
  const selectionPanel = createFullscreenSafeOffcanvasController(mapElement, {
    map,
    offcanvasId: "job-map-selection-offcanvas",
  });
  configureMapConstraints(map);
  const markerLayer = L.layerGroup().addTo(map);
  const basemapController = createBasemapController(
    map,
    basemapConfig,
    basemapPreference,
    mapElement,
  );
  let viewportSaveTimeout = null;
  let visibleMarkers = [];
  let selectionController = null;
  const jobIndex = new Map();
  const selectableJobIdsBySite = new Map();

  for (const entry of sites) {
    const site = entry.site;
    const selectableIds = [];
    for (const job of entry.jobs) {
      const jobId = String(job.id);
      const jobData = { ...job, site };
      jobIndex.set(jobId, jobData);
      if (job.bulkEditable) {
        selectableIds.push(jobId);
      }
    }
    selectableJobIdsBySite.set(String(site.id), selectableIds);
  }

  function currentViewport() {
    const center = map.getCenter();
    return {
      lat: center.lat,
      lng: center.lng,
      zoom: map.getZoom(),
    };
  }

  function savePreference() {
    const url = mapElement.dataset.preferenceUrl;

    if (!url) {
      return;
    }

    if (typeof postJSON !== "function") {
      return;
    }

    postJSON(url, {
      key: preference.key,
      value: {
        viewport: currentViewport(),
      },
    }).catch(() => {});
  }

  function queueViewportSave() {
    window.clearTimeout(viewportSaveTimeout);
    viewportSaveTimeout = window.setTimeout(savePreference, 500);
  }

  function markerSize() {
    const scale = markerScaleForZoom(map.getZoom());
    if (scale === "world") {
      return { anchor: [4, 10], count: 0, iconSize: [8, 10], pin: 8 };
    }
    if (scale === "far") {
      return { anchor: [6, 15], count: 6, iconSize: [12, 15], pin: 12 };
    }
    return { anchor: [13, 32], count: 11, iconSize: [26, 32], pin: 26 };
  }

  function makeMarkerIcon(statusLayer, jobCount) {
    const size = markerSize();
    return L.divIcon({
      className: "job-map-marker",
      html: `
        <span class="job-map-marker-pin" style="--job-map-marker-color: ${escapeHtml(statusLayer.color)}; --job-map-marker-size: ${size.pin}px; --job-map-marker-count-size: ${size.count}px;">
          <span class="job-map-marker-count">${jobCount}</span>
        </span>
      `,
      iconAnchor: size.anchor,
      iconSize: size.iconSize,
      popupAnchor: [0, -Math.max(size.iconSize[1] - 4, 6)],
    });
  }

  function getDominantStatus(jobs) {
    // One marker can represent multiple jobs at a site. Rank is the product
    // decision for the marker summary: open work should visually outrank
    // terminal work, so unassigned wins before assigned, completed, cancelled.
    return jobs
      .map((job) => statusByValue.get(job.statusValue))
      .filter(Boolean)
      .sort((first, second) => second.rank - first.rank)[0];
  }

  function bulkSelection() {
    return window.AccessAtlas?.bulkSelection;
  }

  function selectedJobIds() {
    const selectedIds = bulkSelection()?.selectedIds?.("job-map-bulk-form");
    return Array.isArray(selectedIds) ? selectedIds.map(String) : [];
  }

  function statusColorFor(job) {
    return statusByValue.get(job.statusValue)?.color || "#667382";
  }

  function escapeAttribute(value) {
    return escapeHtml(value).replaceAll('"', "&quot;").replaceAll("'", "&#39;");
  }

  let activeFallbackPopover = null;
  let fallbackPopoverListenersReady = false;

  function hideFallbackPopover() {
    if (!activeFallbackPopover) {
      return;
    }

    activeFallbackPopover.element.remove();
    activeFallbackPopover = null;
  }

  function positionFallbackPopover(trigger, element) {
    const margin = 8;
    const triggerRect = trigger.getBoundingClientRect();
    const elementRect = element.getBoundingClientRect();
    const viewportWidth = document.documentElement.clientWidth;
    const left = Math.min(
      Math.max(margin, triggerRect.left),
      Math.max(margin, viewportWidth - elementRect.width - margin),
    );
    let top = triggerRect.top - elementRect.height - margin;

    if (top < margin) {
      top = triggerRect.bottom + margin;
    }

    element.style.left = `${left}px`;
    element.style.top = `${Math.max(margin, top)}px`;
  }

  function showFallbackPopover(trigger) {
    const content = trigger.getAttribute("data-bs-content");

    if (!content) {
      return;
    }

    if (activeFallbackPopover?.trigger === trigger) {
      return;
    }

    hideFallbackPopover();
    const element = document.createElement("div");
    element.className = "popover bs-popover-auto show job-map-fallback-popover";
    element.setAttribute("role", "tooltip");
    element.innerHTML = `<div class="popover-body">${escapeHtml(content)}</div>`;
    document.body.append(element);
    activeFallbackPopover = { element, trigger };
    positionFallbackPopover(trigger, element);
  }

  function bindFallbackPopoverListeners() {
    if (fallbackPopoverListenersReady) {
      return;
    }

    document.addEventListener("click", (event) => {
      if (
        activeFallbackPopover &&
        !activeFallbackPopover.trigger.contains(event.target) &&
        !activeFallbackPopover.element.contains(event.target)
      ) {
        hideFallbackPopover();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        hideFallbackPopover();
      }
    });
    window.addEventListener("resize", hideFallbackPopover);
    window.addEventListener("scroll", hideFallbackPopover, true);
    fallbackPopoverListenersReady = true;
  }

  function initializeFallbackPopover(element) {
    if (element.dataset.jobMapPopoverFallback === "true") {
      return;
    }

    element.dataset.jobMapPopoverFallback = "true";
    element.addEventListener("click", (event) => {
      if (event.target.closest("a")) {
        return;
      }

      event.stopPropagation();
      showFallbackPopover(element);
      element.focus({ preventScroll: true });
    });
    element.addEventListener("focus", () => {
      showFallbackPopover(element);
    });
    element.addEventListener("blur", () => {
      window.setTimeout(() => {
        if (activeFallbackPopover?.trigger === element) {
          hideFallbackPopover();
        }
      }, 150);
    });
  }

  function initializePopovers(root) {
    const Popover = window.bootstrap?.Popover;
    if (!root) {
      return;
    }
    for (const element of root.querySelectorAll('[data-bs-toggle="popover"]')) {
      if (typeof Popover === "function" && !Popover.getInstance(element)) {
        new Popover(element);
        continue;
      }

      bindFallbackPopoverListeners();
      initializeFallbackPopover(element);
    }
  }

  function popoverAttributes(reason) {
    return `tabindex="0" data-bs-toggle="popover" data-bs-trigger="click focus" data-bs-container="body" data-bs-content="${escapeAttribute(reason)}"`;
  }

  function buildPopupCheckbox(job) {
    if (!job.bulkEditable) {
      return `
        <span class="job-map-popup-checkbox-wrap job-map-popup-checkbox-wrap--locked">
          <input class="form-check-input" type="checkbox" disabled tabindex="-1" aria-hidden="true">
          <i class="ti ti-lock" aria-hidden="true"></i>
        </span>
      `;
    }

    const checkbox = `
      <input
        class="form-check-input"
        type="checkbox"
        name="pk"
        value="${escapeHtml(String(job.id))}"
        form="job-map-bulk-form"
        data-bulk-selection-checkbox
        aria-label="Select ${escapeHtml(job.title)}"
      >
    `;
    return `<span class="job-map-popup-checkbox-wrap">${checkbox}</span>`;
  }

  function buildSiteSelect(site) {
    const siteId = String(site.id);
    const selectableIds = selectableJobIdsBySite.get(siteId) || [];
    const disabledReason = "There are no selectable jobs for this site.";
    const checkbox =
      selectableIds.length === 0
        ? `
      <span class="job-map-popup-checkbox-wrap job-map-popup-checkbox-wrap--locked">
        <input class="form-check-input" type="checkbox" disabled tabindex="-1" aria-hidden="true">
        <i class="ti ti-lock" aria-hidden="true"></i>
      </span>
    `
        : `
      <input
        class="form-check-input"
        type="checkbox"
        data-job-map-site-toggle
        data-site-id="${escapeHtml(siteId)}"
        aria-label="Select all visible jobs for ${escapeHtml(site.name)}"
      >
    `;
    const tagName = selectableIds.length === 0 ? "span" : "label";
    const siteSelectClass =
      selectableIds.length === 0
        ? "job-map-popup-site-select job-map-popup-site-select--disabled"
        : "job-map-popup-site-select";
    const popoverAttributesHtml =
      selectableIds.length === 0 ? ` ${popoverAttributes(disabledReason)}` : "";

    return `
      <${tagName} class="${siteSelectClass}"${popoverAttributesHtml}>
        ${selectableIds.length === 0 ? checkbox : `<span class="job-map-popup-checkbox-wrap">${checkbox}</span>`}
        <span>Select all visible jobs for this site</span>
      </${tagName}>
    `;
  }

  function buildPopup(site, jobs) {
    const listClass =
      jobs.length > 15
        ? "job-map-popup-list job-map-popup-list--scroll"
        : "job-map-popup-list";
    const jobList = jobs
      .map((job) => {
        const disabledReason =
          job.bulkDisabledReason || "This job cannot be selected for bulk edit.";
        const tagName = job.bulkEditable ? "label" : "span";
        const selectionClass = job.bulkEditable
          ? "job-map-popup-selection"
          : "job-map-popup-selection job-map-popup-selection--disabled";
        const popoverAttributesHtml = job.bulkEditable
          ? ""
          : ` ${popoverAttributes(disabledReason)}`;
        return `
          <li>
            <${tagName} class="${selectionClass}"${popoverAttributesHtml}>
              ${buildPopupCheckbox(job)}
              <a href="${escapeHtml(job.url)}">${escapeHtml(job.title)}</a>
            </${tagName}>
            <span class="job-map-popup-status" style="--job-map-status-color: ${escapeHtml(statusColorFor(job))};">${escapeHtml(job.status)}</span>
          </li>
        `;
      })
      .join("");

    return `
      <div class="job-map-popup-title">
        <a href="${escapeHtml(site.url)}">${siteCodeHtml(site.code)} - ${escapeHtml(site.name)}</a>
      </div>
      ${buildSiteSelect(site)}
      <ul class="${listClass}">${jobList}</ul>
    `;
  }

  function updateSiteToggles(root = document) {
    const selectedIds = new Set(selectedJobIds());
    for (const toggle of root.querySelectorAll("[data-job-map-site-toggle]")) {
      const siteIds = selectableJobIdsBySite.get(toggle.dataset.siteId || "") || [];
      const selectedCount = siteIds.filter((jobId) => selectedIds.has(jobId)).length;
      toggle.checked = siteIds.length > 0 && selectedCount === siteIds.length;
      toggle.indeterminate = selectedCount > 0 && selectedCount < siteIds.length;
    }
  }

  function renderSelectedJobsTable(jobs) {
    const rows = jobs
      .map(
        (job) => `
          <tr>
            <td>
              <a href="${escapeHtml(job.url)}">${escapeHtml(job.title)}</a>
            </td>
            <td>${siteCodeHtml(job.site.code)} - ${escapeHtml(job.site.name)}</td>
            <td>
              <span class="job-map-popup-status" style="--job-map-status-color: ${escapeHtml(statusColorFor(job))};">${escapeHtml(job.status)}</span>
            </td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-secondary" type="button" data-map-bulk-selection-drop value="${escapeHtml(String(job.id))}">
                <i class="ti ti-x" aria-hidden="true"></i>Drop
              </button>
            </td>
          </tr>
        `,
      )
      .join("");

    return `
      <div class="table-responsive">
        <table class="table table-vcenter card-table job-map-selection-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Site</th>
              <th>Status</th>
              <th class="text-end">Actions</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `;
  }

  function drawMarkers() {
    markerLayer.clearLayers();
    const markers = [];

    for (const entry of sites) {
      const site = entry.site;
      const jobs = entry.jobs;
      const latitude = Number(site.latitude);
      const longitude = Number(site.longitude);
      const dominantStatus = getDominantStatus(jobs);

      if (
        jobs.length === 0 ||
        !dominantStatus ||
        !Number.isFinite(latitude) ||
        !Number.isFinite(longitude)
      ) {
        continue;
      }

      const marker = L.marker(
        normalizeLatLng(latitude, longitude, longitudeNormalizer),
        {
          icon: makeMarkerIcon(dominantStatus, jobs.length),
        },
      );
      marker.statusLayer = dominantStatus;
      marker.jobCount = jobs.length;
      marker.bindPopup(buildPopup(site, jobs));
      marker.on("popupopen", (event) => {
        window.AccessAtlas?.syncBulkSelection?.();
        const popupElement = event.popup.getElement();
        initializePopovers(popupElement);
        updateSiteToggles(popupElement);
      });
      marker.addTo(markerLayer);
      markers.push(marker);
    }

    return markers;
  }

  function fitMarkers(markers) {
    fitLayersOrDefault(map, markers, [-41.2865, 174.7762], 5);
  }

  function mountHomeControl() {
    sharedAddHomeControl(map, () => {
      fitMarkers(visibleMarkers);
      savePreference();
    });
  }

  mountHomeControl();
  addFullscreenControl(map);
  if (filterPanel) {
    addFilterControl(map, filterPanel.show, {
      count: initialFilterCount,
    });
  }
  addBasemapControl(map, basemapController);
  selectionController = createMapBulkSelectionController({
    map,
    formId: "job-map-bulk-form",
    panelController: selectionPanel,
    listElement: selectionListElement,
    summaryElement: selectionSummaryElement,
    submitButton: selectionSubmitButton,
    itemById: (jobId) => jobIndex.get(String(jobId)),
    itemLabelSingular: "job",
    itemLabelPlural: "jobs",
    emptyHtml: '<div class="empty">Select jobs on the map to review them here.</div>',
    renderItems: renderSelectedJobsTable,
  });
  bulkForm.addEventListener("access-atlas:bulk-selection-change", () => {
    updateSiteToggles();
  });
  document.addEventListener("change", (event) => {
    const target = event.target;
    if (!target.matches?.("[data-job-map-site-toggle]")) {
      return;
    }
    const jobIds = selectableJobIdsBySite.get(target.dataset.siteId || "") || [];
    if (target.checked) {
      bulkSelection()?.add?.("job-map-bulk-form", jobIds);
    } else {
      bulkSelection()?.remove?.("job-map-bulk-form", jobIds);
    }
  });
  selectionController?.render();
  basemapController.apply();
  visibleMarkers = drawMarkers();

  function applySavedViewport() {
    // A saved viewport wins over fit-to-data so users can return to the same
    // planning area they were inspecting previously.
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
      return;
    }

    fitMarkers(visibleMarkers);
  }

  applySavedViewport();
  settleMapLayout(map, applySavedViewport);
  map.on("zoomend", () => {
    for (const marker of visibleMarkers) {
      marker.setIcon(makeMarkerIcon(marker.statusLayer, marker.jobCount));
    }
  });
  map.on("moveend zoomend", queueViewportSave);
})();
