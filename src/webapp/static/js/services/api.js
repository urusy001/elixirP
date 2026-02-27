const API_BASE = "/api/v1";
const WEBAPP_ORIGIN = "https://elixirpeptides.devsivanschostakov.org";
const ABSOLUTE_URL_RE = /^https?:\/\//i;

function normalizePath(path) {
    if (!path.startsWith("/")) return `/${path}`;
    return path;
}

function buildUrl(path) {
    if (path.startsWith(WEBAPP_ORIGIN)) return `${WEBAPP_ORIGIN}${API_BASE}${normalizePath(path.slice(WEBAPP_ORIGIN.length))}`;
    if (ABSOLUTE_URL_RE.test(path)) return path;
    return `${API_BASE}${normalizePath(path)}`;
}

async function parseResponseBody(response) {
    const text = await response.text();
    if (!text) return null;
    try { return JSON.parse(text); } catch { return text; }
}

async function apiRequest(method, path, data) {
    const response = await fetch(buildUrl(path), {
        method,
        credentials: "same-origin",
        headers: data === undefined ? {} : { "Content-Type": "application/json" },
        body: data === undefined ? undefined : JSON.stringify(data),
    });
    const body = await parseResponseBody(response);
    if (!response.ok) {
        const detail = body && typeof body === "object" ? (body.error || body.detail) : null;
        throw new Error(detail || `HTTP ${response.status}`);
    }
    return body;
}

export async function apiGet(path) { return apiRequest("GET", path); }
export async function apiPost(path, data) { return apiRequest("POST", path, data); }
export async function apiPut(path, data) { return apiRequest("PUT", path, data); }
export async function apiPatch(path, data) { return apiRequest("PATCH", path, data); }
export async function apiDelete(path, data) { return apiRequest("DELETE", path, data); }
export { API_BASE };
