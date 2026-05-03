(() => {
  const ganttElement = document.getElementById("trip-gantt");
  const dataElement = document.getElementById("trip-gantt-data");
  const viewModeButtons = Array.from(
    document.querySelectorAll(".trip-gantt-view-mode"),
  );

  if (!ganttElement || !dataElement || typeof Gantt === "undefined") {
    return;
  }

  const rows = JSON.parse(dataElement.textContent);
  function escapeHtml(value) {
    const span = document.createElement("span");
    span.textContent = value == null ? "" : String(value);
    return span.innerHTML;
  }

  function taskLabel(siteVisit) {
    return `${siteVisit.siteCode} - ${siteVisit.siteName}`;
  }

  function typeBadge(task) {
    if (task.record_type === "trip") {
      return '<span class="badge trip-gantt-type-badge trip-gantt-type-badge--trip">Trip</span>';
    }

    if (task.has_explicit_time) {
      return '<span class="badge trip-gantt-type-badge trip-gantt-type-badge--visit">Timed visit</span>';
    }

    return '<span class="badge trip-gantt-type-badge trip-gantt-type-badge--date-only">Date only</span>';
  }

  function badgeClass(status) {
    return `trip-gantt-status-badge trip-gantt-status-badge--${status || "draft"}`;
  }

  function buildTasks() {
    const tasks = [];

    for (const row of rows) {
      tasks.push({
        id: row.id,
        name: row.tripName,
        start: row.start,
        end: row.end,
        progress: 0,
        custom_class: "trip-gantt-trip-row",
        url: row.tripUrl,
        record_type: "trip",
        status: row.status,
        status_label: row.statusLabel,
      });

      for (const siteVisit of row.siteVisits) {
        tasks.push({
          id: siteVisit.id,
          name: `\u00A0\u00A0${taskLabel(siteVisit)}`,
          start: siteVisit.start,
          end: siteVisit.end,
          progress: 0,
          custom_class: "trip-gantt-site-visit-row",
          url: siteVisit.url,
          record_type: "site_visit",
          trip_name: row.tripName,
          site_code: siteVisit.siteCode,
          site_name: siteVisit.siteName,
          status: siteVisit.status,
          status_label: siteVisit.statusLabel,
        });
      }
    }

    return tasks;
  }

  function popupHtml(task) {
    if (task.record_type === "trip") {
      return `
        <div class="trip-gantt-popup">
          <div class="trip-gantt-popup-code"><a href="${escapeHtml(task.url)}">${escapeHtml(task.name)}</a></div>
          <div class="trip-gantt-popup-meta">
            ${typeBadge(task)}
            <span class="badge ${badgeClass(task.status)}">${escapeHtml(task.status_label)}</span>
          </div>
        </div>
      `;
    }

    return `
      <div class="trip-gantt-popup">
        <div class="trip-gantt-popup-code"><a href="${escapeHtml(task.url)}">${escapeHtml(task.site_code)}</a></div>
        <div class="trip-gantt-popup-name">${escapeHtml(task.site_name)}</div>
        <div class="trip-gantt-popup-trip">${escapeHtml(task.trip_name)}</div>
        <div class="trip-gantt-popup-meta">
          ${typeBadge(task)}
          <span class="badge ${badgeClass(task.status)}">${escapeHtml(task.status_label)}</span>
        </div>
      </div>
    `;
  }

  const tasks = buildTasks();
  const viewModes = [
    {
      name: "Day",
      padding: "7d",
      step: "1d",
      column_width: 64,
      date_format: "YYYY-MM-DD",
      lower_text: "D",
      upper_text(currentDate, previousDate) {
        if (!previousDate || currentDate.getMonth() !== previousDate.getMonth()) {
          return currentDate.toLocaleString(undefined, { month: "long" });
        }

        return "";
      },
      thick_line(currentDate) {
        return currentDate.getDay() === 1;
      },
    },
    {
      name: "Week",
      padding: "1m",
      step: "7d",
      column_width: 180,
      date_format: "YYYY-MM-DD",
      lower_text(currentDate, previousDate) {
        const endDate = new Date(currentDate);
        endDate.setDate(endDate.getDate() + 6);
        const startDay = currentDate.getDate();
        const endDay = endDate.getDate();
        const startMonth = currentDate.toLocaleString(undefined, {
          month: "short",
        });
        const endMonth = endDate.toLocaleString(undefined, { month: "short" });

        if (startMonth === endMonth) {
          return `${startDay} - ${endDay} ${endMonth}`;
        }

        return `${startDay} ${startMonth} - ${endDay} ${endMonth}`;
      },
      upper_text(currentDate, previousDate) {
        if (!previousDate || currentDate.getMonth() !== previousDate.getMonth()) {
          return currentDate.toLocaleString(undefined, { month: "long" });
        }

        return "";
      },
      thick_line(currentDate) {
        return currentDate.getDate() >= 1 && currentDate.getDate() <= 7;
      },
      upper_text_frequency: 4,
    },
  ];
  const gantt = new Gantt(ganttElement, tasks, {
    view_mode: "Day",
    view_modes: viewModes,
    readonly: true,
    popup_on: "click",
    scroll_to: "start",
    today_button: true,
    infinite_padding: false,
    popup({ task }) {
      return popupHtml(task);
    },
  });

  function setActiveViewMode(viewMode) {
    for (const button of viewModeButtons) {
      button.classList.toggle("is-active", button.dataset.viewMode === viewMode);
    }
  }

  for (const button of viewModeButtons) {
    button.addEventListener("click", () => {
      const viewMode = button.dataset.viewMode;

      if (!viewMode) {
        return;
      }

      gantt.change_view_mode(viewMode, true);
      setActiveViewMode(viewMode);
    });
  }
})();
