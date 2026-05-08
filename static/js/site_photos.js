import PhotoSwipeLightbox from "../vendor/photoswipe/photoswipe-lightbox.esm.min.js";

(() => {
  const selectionForm = document.querySelector("[data-site-photo-selection-form]");
  if (!selectionForm) {
    return;
  }

  const checkboxes = selectionForm.querySelectorAll("[data-site-photo-select]");
  const groupCheckboxes = selectionForm.querySelectorAll(
    "[data-site-photo-group-select]",
  );
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

  function checkboxesForGroup(groupId) {
    return selectionForm.querySelectorAll(
      `[data-site-photo-select][data-site-photo-group="${CSS.escape(groupId)}"]`,
    );
  }

  const refreshSelectionState = () => {
    let selectedCount = 0;
    for (const checkbox of checkboxes) {
      const card = checkbox.closest(".site-photo-card");
      card?.classList.toggle("is-selected", checkbox.checked);
      if (checkbox.checked) {
        selectedCount += 1;
      }
    }
    for (const checkbox of groupCheckboxes) {
      const groupId = checkbox.dataset.sitePhotoGroupSelect;
      const groupPhotos = groupId ? Array.from(checkboxesForGroup(groupId)) : [];
      checkbox.checked =
        groupPhotos.length > 0 && groupPhotos.every((photo) => photo.checked);
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

  for (const checkbox of groupCheckboxes) {
    checkbox.addEventListener("change", () => {
      const groupId = checkbox.dataset.sitePhotoGroupSelect;
      if (!groupId) {
        return;
      }
      for (const photoCheckbox of checkboxesForGroup(groupId)) {
        photoCheckbox.checked = checkbox.checked;
      }
      refreshSelectionState();
    });
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

  const lightbox = new PhotoSwipeLightbox({
    gallery: "[data-site-photo-selection-form]",
    children: "[data-site-photo-view]",
    pswpModule: () => import("../vendor/photoswipe/photoswipe.esm.min.js"),
  });
  lightbox.on("uiRegister", () => {
    lightbox.pswp.ui.registerElement({
      name: "site-photo-date",
      order: 9,
      isButton: false,
      appendTo: "root",
      html: "",
      onInit: (element, pswp) => {
        const updateDate = () => {
          const photoLink = pswp.currSlide?.data.element;
          element.textContent = photoLink?.dataset.sitePhotoDate || "";
        };
        pswp.on("change", updateDate);
        updateDate();
      },
    });
  });
  lightbox.init();

  refreshSelectionState();
})();
