(function () {
  document.querySelectorAll('[data-bs-toggle="popover"]').forEach((element) => {
    new bootstrap.Popover(element);
  });

  document.querySelectorAll("select[data-searchable-select]").forEach((select) => {
    if (select.dataset.searchableSelectEnhanced === "true") {
      return;
    }

    const search = document.createElement("input");
    search.type = "search";
    search.className = "form-control searchable-select-input";
    search.placeholder = select.dataset.searchPlaceholder || "Search options";
    search.setAttribute("aria-label", search.placeholder);
    select.before(search);
    select.dataset.searchableSelectEnhanced = "true";

    const options = Array.from(select.options);
    const optionText = new Map(
      options.map((option) => [option, option.textContent.toLowerCase()])
    );

    search.addEventListener("input", () => {
      const query = search.value.trim().toLowerCase();
      let firstMatch = null;

      options.forEach((option) => {
        const isEmptyOption = option.value === "";
        const matches = !query || optionText.get(option).includes(query);
        option.hidden = !isEmptyOption && !matches;
        if (!firstMatch && !isEmptyOption && matches) {
          firstMatch = option;
        }
      });

      if (firstMatch && select.selectedOptions[0]?.hidden) {
        firstMatch.selected = true;
      }
    });
  });
})();
