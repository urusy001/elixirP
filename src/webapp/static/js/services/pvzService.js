export function getSelectedPVZCode() {
    const els = Array.from(document.querySelectorAll(".cdek-1smek3"));
    for (const el of els) {
        const match = el.textContent.trim().match(/- (\S+)$/);
        if (match) return match[1];
    }
    return null;
}

export async function fetchPVZByCode(code) {
    try {
        const res = await fetch(`/delivery/cdek?action=offices&code=${encodeURIComponent(code)}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (data?.length) renderPVZInfo(data[0]);
    } catch (err) {
        console.error("❌ Error fetching PVZ info:", err);
    }
}

export function renderPVZInfo(pvz) {
    if (!pvz) return;
    let infoDiv = document.querySelector(".my-pvz-info");
    if (!infoDiv) {
        infoDiv = document.createElement("div");
        infoDiv.className = "my-pvz-info";
        infoDiv.style.marginTop = "10px";
        infoDiv.style.fontSize = "14px";
        infoDiv.style.color = "#333";
        document.querySelector(".cdek-2ew9g8")?.appendChild(infoDiv);
    }
    infoDiv.innerHTML = `
    ${pvz.phones?.length ? `<p><b>Телефон:</b> ${pvz.phones.map(p => p.number).join(", ")}</p>` : ""}
    ${pvz.email ? `<p><b>Email:</b> ${pvz.email}</p>` : ""}
    ${pvz.note ? `<p><b>Примечание:</b> ${pvz.note}</p>` : ""}
  `;
}