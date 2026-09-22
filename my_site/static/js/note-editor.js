"use strict";

(() => {
    const form = document.querySelector("[data-note-editor]");
    if (!form) return;
    const content = form.elements.content;
    const status = form.querySelector("[data-save-status]");
    const count = form.querySelector("[data-word-count]");
    const save = form.querySelector('button[type="submit"]');
    const originalLabel = save.textContent;
    const editor = () => window.tinymce?.get(content.id);
    let submitting = false;
    let guardActive = false;
    const rejectedSubmission = form.dataset.unsaved === "true";

    const snapshot = () => ({
        title: form.elements.title.value,
        content: editor()?.initialized ? editor().getContent() : content.value,
        categories: Array.from(form.querySelectorAll('[name="categories"]:checked'), (input) => input.value),
        visibility: form.elements.visibility.value,
    });
    const baseline = snapshot();
    const beforeUnload = (event) => {
        event.preventDefault();
        event.returnValue = "";
    };
    const setGuard = (enabled) => {
        if (enabled === guardActive) return;
        window[enabled ? "addEventListener" : "removeEventListener"]("beforeunload", beforeUnload);
        guardActive = enabled;
    };
    const update = () => {
        const dirty = rejectedSubmission || JSON.stringify(snapshot()) !== JSON.stringify(baseline);
        setGuard(dirty && !submitting);
        const label = submitting ? "Saving…" : dirty ? "Unsaved changes" : "No unsaved changes";
        if (status.textContent !== label) status.textContent = label;
        status.dataset.state = submitting ? "saving" : dirty ? "dirty" : "clean";
        const fragment = document.createElement("template");
        fragment.innerHTML = snapshot().content;
        const doc = fragment.content;
        doc.querySelectorAll("script, style, template").forEach((node) => node.remove());
        // Preserve word boundaries between paragraphs and explicit line breaks.
        doc.querySelectorAll("p, div, li, br, h1, h2, h3, h4, h5, h6").forEach((node) => node.append(" "));
        const text = (doc.textContent || "").replace(/[\u200b\u200c\u200d\ufeff]/g, "").trim();
        const words = text ? text.split(/\s+/u).length : 0;
        count.textContent = `${words} ${words === 1 ? "word" : "words"}`;
    };
    const shortcut = (event) => {
        if (!event.isComposing && (event.ctrlKey || event.metaKey) && event.key === "Enter") {
            event.preventDefault();
            if (!submitting) form.requestSubmit(save);
        }
    };
    const connect = (instance) => {
        if (instance.id !== content.id || instance.notesConnected) return;
        instance.notesConnected = true;
        const ready = () => {
            // TinyMCE normalizes markup during initialization; this is not a user edit.
            baseline.content = instance.getContent();
            update();
        };
        instance.on("input change undo redo SetContent", update);
        instance.on("keydown", shortcut);
        if (instance.initialized) ready();
        else instance.on("init", ready);
    };
    window.tinymce?.on("AddEditor", (event) => connect(event.editor));
    if (editor()) connect(editor());
    form.addEventListener("input", update);
    form.addEventListener("change", update);
    form.addEventListener("keydown", shortcut);
    form.addEventListener("submit", (event) => {
        if (submitting) {
            event.preventDefault();
            return;
        }
        editor()?.save();
        submitting = true;
        save.disabled = true;
        save.textContent = "Saving…";
        form.setAttribute("aria-busy", "true");
        update();
    });
    // Restore controls when the browser returns to a cached form after submission.
    window.addEventListener("pageshow", () => {
        submitting = false;
        save.disabled = false;
        save.textContent = originalLabel;
        form.removeAttribute("aria-busy");
        update();
    });
    form.querySelector("[data-editor-feedback]").hidden = false;
    form.querySelector("[data-save-shortcut]").hidden = false;
    update();
})();
