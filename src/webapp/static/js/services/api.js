// src/webapp/static/js/services/api.js

const API_BASE = "/api/v1";
const WEBAPP_ORIGIN = "https://elixirpeptides.devsivanschostakov.org";

function buildUrl(path) {
    if (path.startsWith(WEBAPP_ORIGIN)) {
        let relative = path.slice(WEBAPP_ORIGIN.length);
        if (!relative.startsWith("/")) {
            relative = "/" + relative;
        }
        return WEBAPP_ORIGIN + API_BASE + relative;
    }

    if (path.startsWith("http://") || path.startsWith("https://")) {
        return path;
    }

    if (!path.startsWith("/")) {
        path = "/" + path;
    }
    return API_BASE + path;
}

async function handle(res) {
    if (!res.ok) {
        let body = null;
        try { body = await res.json(); } catch {}
        const msg = body?.error || body?.detail || `HTTP ${res.status}`;
        throw new Error(msg);
    }
    const text = await res.text();
    return text ? JSON.parse(text) : null;
}

export async function apiGet(path) {
    const url = buildUrl(path);
    return handle(await fetch(url, { credentials: "same-origin" }));
}

export async function apiPost(path, data) {
    const url = buildUrl(path);
    return handle(await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify(data),
    }));
}

export { API_BASE, WEBAPP_URL };