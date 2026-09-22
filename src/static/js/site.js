"use strict";

(() => {
    const summary = document.querySelector("[data-error-summary]");
    const selectAll = document.querySelector("[data-select-all]");
    if (selectAll) {
        const inputs = Array.from(document.querySelectorAll('input[form="bulk-notes"][name="notes"]'));
        const count = document.querySelector("[data-selection-count]");
        document.querySelector("[data-select-all-label]").hidden = false;
        count.hidden = false;
        const update = () => {
            const selected = inputs.filter((input) => input.checked).length;
            count.textContent = `${selected} ${selected === 1 ? "note" : "notes"} selected`;
            selectAll.checked = selected === inputs.length;
            selectAll.indeterminate = selected > 0 && selected < inputs.length;
        };
        selectAll.addEventListener("change", () => {
            inputs.forEach((input) => { input.checked = selectAll.checked; });
            update();
        });
        inputs.forEach((input) => input.addEventListener("change", () => {
            if (input.checked) document.querySelector(".bulk-tools").open = true;
            update();
        }));
        update();
    }
    const importError = document.querySelector("#import-error");
    if (importError) importError.focus();
    if (!summary) return;
    summary.focus();
    summary.addEventListener("click", (event) => {
        const link = event.target.closest('a[href^="#"]');
        if (!link) return;
        const target = document.getElementById(link.hash.slice(1));
        if (!target) return;
        event.preventDefault();
        const editor = window.tinymce?.get(target.id);
        if (editor?.initialized) {
            editor.focus();
        } else {
            target.focus();
            target.scrollIntoView({ block: "center" });
        }
    });
})();
