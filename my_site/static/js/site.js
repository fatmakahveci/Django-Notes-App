"use strict";

(() => {
    const summary = document.querySelector("[data-error-summary]");
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
