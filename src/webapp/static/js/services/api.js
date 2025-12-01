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

// optional generic helper if you want
async function apiRequest(method, path, data) {
    const url = buildUrl(path);

    const options = {
        method,
        credentials: "same-origin",
        headers: {}
    };

    if (data !== undefined) {
        options.headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(data);
    }

    return handle(await fetch(url, options));
}

export async function apiGet(path) {
    return apiRequest("GET", path);
}

export async function apiPost(path, data) {
    return apiRequest("POST", path, data);
}

export async function apiPut(path, data) {
    return apiRequest("PUT", path, data);
}

export async function apiPatch(path, data) {
    return apiRequest("PATCH", path, data);
}

export async function apiDelete(path, data) {
    // some backends ignore body on DELETE; if yours doesn’t need it,
    // you can call apiRequest("DELETE", path) without data
    return apiRequest("DELETE", path, data);
}

export { API_BASE };