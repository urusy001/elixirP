import {
    cartPageEl, checkoutPageEl, contactPageEl,
    detailEl,
    headerTitle,
    listEl,
    navBottomEl, orderDetailEl, ordersPageEl, paymentPageEl, processPaymentEl, profilePageEl,
    searchBtnEl,
    toolbarEl,
    tosOverlayEl
} from "./constants.js";

import { state } from "../state.js";
import { apiGet } from "../../services/api.js";

/**
 * Public
 */
export async function renderOrdersPage() {
    navBottomEl.style.display = "flex";
    headerTitle.textContent = "Мои заказы";
    tosOverlayEl.style.display = "none";
    listEl.style.display = "none";
    toolbarEl.style.display = "none";
    searchBtnEl.style.display = "none";
    detailEl.style.display = "none";
    cartPageEl.style.display = "none";
    checkoutPageEl.style.display = "none";
    contactPageEl.style.display = "none";
    paymentPageEl.style.display = "none";
    processPaymentEl.style.display = "none";
    profilePageEl.style.display = "none";
    ordersPageEl.style.display = "block";
    orderDetailEl.style.display = "none";

    // Ensure toggles are bound once
    initOrdersSectionToggles();

    // Fetch + render
    await loadAndRenderOrders();
}

/**
 * Fetch carts and render into two sections.
 */
async function loadAndRenderOrders() {
    const user = state.user;
    if (!user?.tg_id) {
        renderOrdersLists([], []);
        return;
    }

    let result;
    try {
        result = await apiGet(`/cart/?user_id=${user.tg_id}`);
    } catch (e) {
        console.error("Failed to load carts:", e);
        renderOrdersLists([], []);
        return;
    }

    // Accept either {data:[...]} or just [...]
    const carts = Array.isArray(result) ? result : (result?.data || result?.carts || []);
    const normalized = carts.map(normalizeCart);

    const active = normalized.filter((c) => c.is_active === true);
    const processed = normalized.filter((c) => c.is_active === false);

    // newest first
    active.sort((a, b) => b.created_ts - a.created_ts);
    processed.sort((a, b) => b.created_ts - a.created_ts);

    renderOrdersLists(active, processed);
}

/**
 * Render both lists + counters + empty states
 */
function renderOrdersLists(active, processed) {
    const activeList = document.getElementById("orders-active-list");
    const processedList = document.getElementById("orders-processed-list");

    const activeCount = document.getElementById("orders-active-count");
    const processedCount = document.getElementById("orders-processed-count");

    const activeEmpty = document.getElementById("orders-active-empty");
    const processedEmpty = document.getElementById("orders-processed-empty");

    if (!activeList || !processedList) return;

    activeList.innerHTML = "";
    processedList.innerHTML = "";

    activeCount.textContent = String(active.length);
    processedCount.textContent = String(processed.length);

    // Active
    if (active.length === 0) {
        activeEmpty.style.display = "block";
    } else {
        activeEmpty.style.display = "none";
        active.forEach((cart) => activeList.appendChild(renderOrderCard(cart)));
    }

    // Processed
    if (processed.length === 0) {
        processedEmpty.style.display = "block";
    } else {
        processedEmpty.style.display = "none";
        processed.forEach((cart) => processedList.appendChild(renderOrderCard(cart)));
    }

    // Optional: auto-collapse empty sections (feel free to delete)
    autoCollapseIfEmpty();
}

/**
 * Make section headers act like table headers (expand/collapse)
 * Also inject missing chevron and body wrapper if needed.
 */
function initOrdersSectionToggles() {
    const root = document.querySelector("#orders-page");
    if (!root) return;

    root.querySelectorAll(".orders-section").forEach((section) => {
        const header = section.querySelector(".orders-section-header");
        if (!header) return;

        // prevent double-bind
        if (header.dataset.toggleBound === "1") return;
        header.dataset.toggleBound = "1";

        // accessibility
        header.setAttribute("role", "button");
        header.tabIndex = 0;

        // ensure chevron exists
        if (!header.querySelector(".orders-section-chevron")) {
            const chev = document.createElement("span");
            chev.className = "orders-section-chevron";
            chev.textContent = "▾";
            header.appendChild(chev);
        }

        // ensure body wrapper exists (optional)
        if (!section.querySelector(".orders-section-body")) {
            // move everything except header into body
            const body = document.createElement("div");
            body.className = "orders-section-body";

            const childrenToMove = [];
            section.childNodes.forEach((node) => {
                if (node.nodeType === 1 && node.classList.contains("orders-section-header")) return;
                if (node.nodeType === 3 && node.textContent.trim() === "") return; // whitespace
                childrenToMove.push(node);
            });

            childrenToMove.forEach((n) => body.appendChild(n));
            section.appendChild(body);
        }

        const setCollapsed = (collapsed) => {
            section.classList.toggle("is-collapsed", collapsed);
            header.setAttribute("aria-expanded", String(!collapsed));
        };

        // default open
        setCollapsed(false);

        header.addEventListener("click", () => {
            setCollapsed(!section.classList.contains("is-collapsed"));
        });

        header.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                header.click();
            }
        });
    });
}

/**
 * Card renderer.
 * If you already have order detail routing, replace openOrderDetail(cart) with your function.
 */
function renderOrderCard(cart) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "order-card";
    const statusClass = cart.is_active ? "order-card-status--active" : "order-card-status--processed";
    const statusText = cart.status;
    const dateText = cart.created_at ? formatDateTime(cart.created_at) : "—";
    const totalText = formatMoney(cart.sum);
    const deliveryText = (cart.delivery_string && String(cart.delivery_string).trim()) ? cart.delivery_string : "Доставка не указана";

    btn.innerHTML = `
    <div class="order-card-top">
      <div class="order-card-id-row">
        <div class="order-card-id">${escapeHtml(cart.name || `Заказ #${cart.id}`)}</div>
        <span class="order-card-status ${statusClass}">${statusText}</span>
      </div>

      <div class="order-card-meta">
        <span class="order-card-date">${escapeHtml(dateText)}</span>
        <span class="order-card-total">${escapeHtml(totalText)}</span>
      </div>
    </div>

    <div class="order-card-bottom">
      <div class="order-card-delivery">${escapeHtml(deliveryText)}</div>
      <div class="order-card-chevron">›</div>
    </div>
  `;

    btn.addEventListener("click", () => {
        // TODO: hook into your existing order detail navigation
        // openOrderDetail(cart);
        console.log("Open order:", cart);
    });

    return btn;
}

/**
 * Normalize backend cart shape to stable fields.
 * Works with your SQLAlchemy model output (typical FastAPI JSON).
 */
function normalizeCart(raw) {
    const created = raw.created_at || raw.createdAt || raw.created;
    const updated = raw.updated_at || raw.updatedAt || raw.updated;

    const createdTs = created ? Date.parse(created) : 0;

    return {
        id: raw.id,
        name: raw.name,
        user_id: raw.user_id ?? raw.userId,
        sum: toNumber(raw.sum),
        delivery_sum: toNumber(raw.delivery_sum),
        delivery_string: raw.delivery_string,
        commentary: raw.commentary,
        is_active: Boolean(raw.is_active),
        created_at: created,
        updated_at: updated,
        created_ts: Number.isFinite(createdTs) ? createdTs : 0,
        items: Array.isArray(raw.items) ? raw.items : []
    };
}

/**
 * Optional: collapse sections that are empty (nice UX).
 * Delete if you dislike.
 */
function autoCollapseIfEmpty() {
    const activeSection = document.querySelector("#orders-page .orders-section:nth-of-type(1)");
    const processedSection = document.querySelector("#orders-page .orders-section:nth-of-type(2)");

    const activeCount = document.getElementById("orders-active-count");
    const processedCount = document.getElementById("orders-processed-count");

    if (activeSection && activeCount && Number(activeCount.textContent) === 0) {
        activeSection.classList.add("is-collapsed");
    }
    if (processedSection && processedCount && Number(processedCount.textContent) === 0) {
        processedSection.classList.add("is-collapsed");
    }
}

/* =========================
   Helpers
   ========================= */

function toNumber(v) {
    if (v == null) return 0;
    const n = Number(String(v).replace(",", "."));
    return Number.isFinite(n) ? n : 0;
}

function formatMoney(v) {
    const n = toNumber(v);
    // ₽ formatting: keep it simple
    const rounded = Math.round(n * 100) / 100;
    const parts = rounded.toFixed(2).split(".");
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    return `${parts.join(".")} ₽`;
}

function formatDateTime(iso) {
    // iso like "2025-12-16T12:34:56.123Z" or without Z
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);

    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const yy = String(d.getFullYear());
    const hh = String(d.getHours()).padStart(2, "0");
    const mi = String(d.getMinutes()).padStart(2, "0");

    return `${dd}.${mm}.${yy} ${hh}:${mi}`;
}

function escapeHtml(s) {
    return String(s ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}