"use strict";

(() => {
    const copy = document.querySelector("[data-copy-note]");
    const print = document.querySelector("[data-print-note]");
    const status = document.querySelector("[data-copy-status]");
    const source = document.getElementById("note-plain-text");
    if (copy && source && navigator.clipboard?.writeText) {
        copy.hidden = false;
        copy.addEventListener("click", async () => {
            copy.disabled = true;
            try {
                await navigator.clipboard.writeText(JSON.parse(source.textContent));
                status.textContent = "Note text copied.";
            } catch {
                status.textContent = "Copy isn't available. Select the text or download the note instead.";
            } finally {
                copy.disabled = false;
            }
        });
    }
    if (print) {
        print.hidden = false;
        print.addEventListener("click", () => window.print());
    }
})();
