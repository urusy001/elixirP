async function handle(res) {
    if (!res.ok) {
        let body = null;
        try {
            body = await res.json();
        } catch {
        }
        const msg = body?.error || body?.detail || `HTTP ${res.status}`;
        throw new Error(msg);
    }
    const text = await res.text();
    return text ? JSON.parse(text) : null;
}

export async function apiGet(url) {
    return handle(await fetch(url, {credentials: "same-origin"}));
}

export async function apiPost(url, data) {
    return handle(await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        credentials: "same-origin",
        body: JSON.stringify(data),
    }));
}