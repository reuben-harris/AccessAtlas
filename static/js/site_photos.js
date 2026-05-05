(() => {
  const selectionForm = document.querySelector("[data-site-photo-selection-form]");
  if (!selectionForm) {
    return;
  }

  const checkboxes = selectionForm.querySelectorAll("[data-site-photo-select]");
  const actionButtons = selectionForm.querySelectorAll(
    "[data-site-photo-selection-action]",
  );
  const selectionSummary = selectionForm.querySelector(
    "[data-site-photo-selection-summary]",
  );
  const selectionCount = selectionForm.querySelector(
    "[data-site-photo-selection-count]",
  );
  const clearSelectionButton = selectionForm.querySelector(
    "[data-site-photo-selection-clear]",
  );

  const refreshSelectionState = () => {
    let selectedCount = 0;
    for (const checkbox of checkboxes) {
      const card = checkbox.closest(".site-photo-card");
      card?.classList.toggle("is-selected", checkbox.checked);
      if (checkbox.checked) {
        selectedCount += 1;
      }
    }
    for (const button of actionButtons) {
      button.disabled = selectedCount === 0;
    }
    if (selectionSummary) {
      selectionSummary.hidden = selectedCount === 0;
    }
    if (selectionCount) {
      const noun = selectedCount === 1 ? "photo" : "photos";
      selectionCount.textContent = `Selected ${selectedCount} ${noun}`;
    }
  };

  for (const checkbox of checkboxes) {
    checkbox.addEventListener("change", refreshSelectionState);
  }

  for (const button of selectionForm.querySelectorAll("[data-site-photo-toggle]")) {
    button.addEventListener("click", () => {
      const checkbox = button
        .closest(".site-photo-card")
        ?.querySelector("[data-site-photo-select]");
      if (!checkbox) {
        return;
      }
      checkbox.checked = !checkbox.checked;
      checkbox.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  clearSelectionButton?.addEventListener("click", () => {
    for (const checkbox of checkboxes) {
      checkbox.checked = false;
    }
    refreshSelectionState();
  });

  refreshSelectionState();
})();
