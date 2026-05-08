(() => {
  function initializeDatePickers() {
    const flatpickr = window.flatpickr;
    if (typeof flatpickr !== "function") {
      return;
    }

    // Flatpickr replaces native browser pickers while keeping server-friendly
    // ISO-style values in the underlying text inputs.
    flatpickr(".date-picker", {
      allowInput: true,
      dateFormat: "Y-m-d",
      disableMobile: true,
    });
    flatpickr(".datetime-picker", {
      allowInput: true,
      dateFormat: "Y-m-d H:i:S",
      disableMobile: true,
      enableSeconds: true,
      enableTime: true,
      time_24hr: true,
    });
    flatpickr(".time-picker", {
      allowInput: true,
      dateFormat: "H:i",
      disableMobile: true,
      enableTime: true,
      noCalendar: true,
      time_24hr: true,
    });
  }

  function selectedOption(select) {
    return select.options[select.selectedIndex];
  }

  function filterValues(control) {
    if (control instanceof HTMLSelectElement && control.multiple) {
      return Array.from(control.selectedOptions).map((option) => option.value);
    }
    return [control.value];
  }

  function setEmptyOperatorState(field) {
    const operator = field.querySelector("[data-filter-operator]");
    const valueControl = field.querySelector("[data-filter-value]");
    if (!(operator instanceof HTMLSelectElement) || !valueControl) {
      return;
    }

    const option = selectedOption(operator);
    const noValue = option?.dataset.noValue === "true";
    if (
      valueControl instanceof HTMLInputElement ||
      valueControl instanceof HTMLTextAreaElement
    ) {
      valueControl.dataset.originalPlaceholder ??=
        valueControl.getAttribute("placeholder") || "";
    }
    valueControl.toggleAttribute("disabled", noValue);
    if (valueControl.tomselect) {
      if (noValue) {
        valueControl.tomselect.clear(true);
        valueControl.tomselect.disable();
      } else {
        valueControl.tomselect.enable();
      }
    }
    if (noValue) {
      if (valueControl instanceof HTMLSelectElement) {
        for (const item of valueControl.options) {
          item.selected = false;
        }
      } else if (
        valueControl instanceof HTMLInputElement ||
        valueControl instanceof HTMLTextAreaElement
      ) {
        valueControl.value = "";
        valueControl.placeholder = "Automatically set";
      }
    } else if (
      valueControl instanceof HTMLInputElement ||
      valueControl instanceof HTMLTextAreaElement
    ) {
      valueControl.placeholder = valueControl.dataset.originalPlaceholder || "";
    }
  }

  function applyFilterTomSelectItemColors(select) {
    if (!(select instanceof HTMLSelectElement) || !select.tomselect) {
      return;
    }

    const colorsByValue = new Map(
      Array.from(select.options)
        .filter((option) => option.dataset.filterItemColor)
        .map((option) => [option.value, option.dataset.filterItemColor]),
    );

    for (const item of select.tomselect.control.querySelectorAll("[data-value]")) {
      const color = colorsByValue.get(item.getAttribute("data-value") || "");
      item.classList.toggle("list-filter-colored-item", Boolean(color));
      if (color) {
        item.style.setProperty("--list-filter-item-color", color);
      } else {
        item.style.removeProperty("--list-filter-item-color");
      }
    }
  }

  function initializeFilterTomSelects(form) {
    const TomSelect = window.TomSelect;
    if (typeof TomSelect !== "function") {
      return;
    }

    for (const select of form.querySelectorAll("[data-filter-tomselect]")) {
      if (!(select instanceof HTMLSelectElement) || select.tomselect) {
        continue;
      }

      new TomSelect(select, {
        closeAfterSelect: false,
        create: false,
        hideSelected: true,
        plugins: ["remove_button"],
      });
      applyFilterTomSelectItemColors(select);
      new MutationObserver(() => applyFilterTomSelectItemColors(select)).observe(
        select.tomselect.control,
        { childList: true },
      );
    }
  }

  initializeDatePickers();

  for (const form of document.querySelectorAll("[data-list-filter-form]")) {
    initializeFilterTomSelects(form);
    const fields = Array.from(form.querySelectorAll("[data-filter-field]"));
    for (const field of fields) {
      const operator = field.querySelector("[data-filter-operator]");
      if (operator instanceof HTMLSelectElement) {
        operator.addEventListener("change", () => setEmptyOperatorState(field));
      }
      setEmptyOperatorState(field);
    }

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const formData = new FormData(form);

      for (const field of fields) {
        const valueControl = field.querySelector("[data-filter-value]");
        if (
          !(
            valueControl instanceof HTMLInputElement ||
            valueControl instanceof HTMLSelectElement ||
            valueControl instanceof HTMLTextAreaElement
          )
        ) {
          continue;
        }

        const baseName = valueControl.name;
        const operator = field.querySelector("[data-filter-operator]");
        const option =
          operator instanceof HTMLSelectElement ? selectedOption(operator) : null;
        const suffix = option?.dataset.paramSuffix || "";
        const noValue = option?.dataset.noValue === "true";
        const submittedValue = option?.dataset.submittedValue || "";
        formData.delete(baseName);

        if (noValue) {
          formData.append(`${baseName}${suffix}`, submittedValue);
          continue;
        }

        for (const value of filterValues(valueControl)) {
          if (String(value).trim()) {
            formData.append(`${baseName}${suffix}`, value);
          }
        }
      }

      const params = new URLSearchParams();
      for (const [key, value] of formData.entries()) {
        if (key !== "page" && String(value).trim()) {
          params.append(key, String(value));
        }
      }

      const action = form.getAttribute("action") || window.location.pathname;
      const query = params.toString();
      window.location.href = query ? `${action}?${query}` : action;
    });
  }

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
