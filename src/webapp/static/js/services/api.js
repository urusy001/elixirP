// src/webapp/static/js/services/api.js

const API_BASE = "/api/v1";

function buildUrl(path) {
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

export { API_BASE };