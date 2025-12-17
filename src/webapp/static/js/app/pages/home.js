import { searchProducts } from "../../services/productService.js";
import { hideLoader, showLoader, withLoader } from "../ui/loader.js";
import { navigateTo } from "../router.js";
import { saveCart, state } from "../state.js";
import { hideBackButton, hideMainButton, showBackButton, showMainButton } from "../ui/telegram.js";

import {
    cartPageEl,
    checkoutPageEl,
    contactPageEl,
    detailEl,
    headerTitle,
    listEl,
    navBottomEl,
    orderDetailEl,
    ordersPageEl,
    paymentPageEl,
    processPaymentEl,
    profilePageEl,
    searchBtnEl,
    toolbarEl,
    tosOverlayEl
} from "./constants.js";

import { apiPost, apiGet } from "../../services/api.js"; // ✅ make sure apiGet exists

let page = 0;
let loading = false;
let mode = "home";

/** =========================
 *  TG CATEGORY FILTER STATE
 *  ========================= */
const filters = {
    tgCategoryIds: new Set(),      // selected ids
    tgCategoryMode: "any",         // any|all (backend supports both; UI currently uses any)
};

let tgCategoriesCache = null;     // [{id,name,description,product_count}]
let filterModalEl = null;

/** =========================
 *  CARD IMAGE SWITCH
 *  ========================= */
function updateCardImage(selectElement) {
    const card = selectElement.closest(".product-card");
    const img = card?.querySelector(".product-img");
    const selectedOption = selectElement.selectedOptions[0];
    if (!img || !selectedOption) return;

    const featureImgSrc = selectedOption.dataset.featureImg;
    const productImgSrc = img.dataset.productImg;
    const defaultImgSrc = "/static/images/product.png";

    const setFallbackToProduct = () => {
        img.onerror = () => {
            img.onerror = null;
            img.src = defaultImgSrc;
        };
        img.src = productImgSrc;
    };

    img.onerror = setFallbackToProduct;
    img.src = featureImgSrc;
}

/** =========================
 *  PRODUCT CARD HTML
 *  ========================= */
function productCardHTML(p) {
    const onecId = p.onec_id || (p.url ? p.url.split("/product/")[1] : "0");
    const rawFeatures = Array.isArray(p.features) ? p.features : [];

    const availableFeatures = rawFeatures.filter(f => Number(f.balance ?? 0) > 0);
    const sortedFeatures = availableFeatures.sort((a, b) => b.price - a.price);

    if (!sortedFeatures.length) return "";

    const productImgPath = `/static/images/${onecId}.png`;
    const defaultImgPath = "/static/images/product.png";

    const featureSelector = `
    <select class="feature-select" data-onec-id="${onecId}">
      ${sortedFeatures.map(f => `
        <option value="${f.id}"
                data-price="${f.price}"
                data-balance="${Number(f.balance ?? 0)}"
                data-feature-img="/static/images/${f.id}.png">
          ${f.name} - ${f.price} ₽
        </option>
      `).join("")}
    </select>
  `;

    return `
    <div class="product-card">
      <a href="/product/${onecId}" class="product-link" data-onec-id="${onecId}">
        <div class="product-image">
          <img src="${productImgPath}"
               data-product-img="${productImgPath}"
               data-default-img="${defaultImgPath}"
               alt="${escapeHtml(p.name)}"
               class="product-img"
               onerror="this.onerror=null; this.src='${defaultImgPath}';">
        </div>
      </a>
      <div class="product-info">
        <span class="product-name">${escapeHtml(p.name)}</span>
        ${featureSelector}
      </div>
      <button class="buy-btn" data-onec-id="${onecId}"></button>
    </div>
  `;
}

/** =========================
 *  BUY COUNTER
 *  ========================= */
function renderBuyCounter(btn, onecId) {
    const card = btn.closest(".product-card");
    const selector = card?.querySelector(".feature-select");
    const selectedFeatureId = selector?.value || null;
    const key = selectedFeatureId ? `${onecId}_${selectedFeatureId}` : onecId;

    const getMaxBalance = () => {
        if (!selector) return Infinity;
        const opt = selector.selectedOptions?.[0];
        if (!opt) return Infinity;
        const bal = Number(opt.dataset.balance ?? Infinity);
        if (!Number.isFinite(bal) || bal <= 0) return Infinity;
        return bal;
    };

    const maxBalance = getMaxBalance();

    const current = state.cart[key] || 0;
    const safeCount = Math.min(current, maxBalance);
    if (safeCount !== current) {
        if (safeCount > 0) state.cart[key] = safeCount;
        else delete state.cart[key];
    }
    const count = state.cart[key] || 0;

    btn.innerHTML = "";

    if (count === 0) {
        const add = document.createElement("button");
        add.textContent = "+ В корзину";
        add.className = "buy-btn-initial";
        add.onclick = () => {
            const max = getMaxBalance();
            if (max <= 0) return;
            state.cart[key] = 1;
            saveCart();
            renderBuyCounter(btn, onecId);
        };
        btn.appendChild(add);
    } else {
        const minus = document.createElement("button");
        minus.textContent = "−";
        minus.onclick = () => {
            const cur = state.cart[key] || 0;
            const next = cur - 1;
            if (next <= 0) delete state.cart[key];
            else state.cart[key] = next;
            saveCart();
            renderBuyCounter(btn, onecId);
        };

        const qty = document.createElement("span");
        qty.textContent = state.cart[key];
        qty.style.margin = "0 4px";

        const plus = document.createElement("button");
        plus.textContent = "+";
        plus.onclick = () => {
            const max = getMaxBalance();
            const cur = state.cart[key] || 0;
            if (cur >= max) return;
            state.cart[key] = cur + 1;
            saveCart();
            renderBuyCounter(btn, onecId);
        };

        btn.append(minus, qty, plus);
    }

    if (selector && !selector.dataset.counterBound) {
        selector.addEventListener("change", () => renderBuyCounter(btn, onecId));
        selector.dataset.counterBound = "1";
    }
}

function attachProductInteractions(container) {
    container.querySelectorAll(".product-link").forEach(link => {
        link.addEventListener("click", e => {
            e.preventDefault();
            const id = link.dataset.onecId;
            navigateTo(`/product/${id}`);
        });
    });

    container.querySelectorAll(".feature-select").forEach(select => {
        if (select.dataset.imageBound) return;
        updateCardImage(select);
        select.addEventListener("change", () => updateCardImage(select));
        select.dataset.imageBound = "1";
    });

    container.querySelectorAll(".buy-btn").forEach(btn => {
        if (btn.dataset.initialized) return;
        renderBuyCounter(btn, btn.dataset.onecId);
        btn.dataset.initialized = "1";
    });
}

/** =========================
 *  CATEGORY FILTER UI
 *  ========================= */
async function getTgCategories() {
    if (tgCategoriesCache) return tgCategoriesCache;
    const data = await apiGet("/tg-categories/"); // should map to /api/v1/tg_categories/
    tgCategoriesCache = Array.isArray(data) ? data : (data?.data || []);
    return tgCategoriesCache;
}

function ensureFilterModal() {
    if (filterModalEl) return filterModalEl;

    // minimal modal (no extra CSS required)
    const el = document.createElement("div");
    el.id = "tg-filter-modal";
    el.style.cssText = `
    position: fixed; inset: 0;
    background: rgba(0,0,0,0.35);
    display: none;
    z-index: 9999;
    padding: 12px;
    box-sizing: border-box;
  `;

    el.innerHTML = `
    <div style="
      max-width: 520px;
      margin: 48px auto 0;
      background: #fff;
      border-radius: 14px;
      overflow: hidden;
      box-shadow: 0 10px 30px rgba(0,0,0,0.15);
    ">
      <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; padding:12px 14px; border-bottom:1px solid #eef2f7;">
        <div style="font-weight:700; color:#111827;">Категории</div>
        <button id="tg-filter-close" type="button" style="border:none; background:transparent; font-size:18px; cursor:pointer;">✕</button>
      </div>

      <div style="padding:10px 14px; border-bottom:1px solid #f3f4f6;">
        <input id="tg-filter-search" type="text" placeholder="Поиск категории..." style="
          width:100%;
          padding:10px 12px;
          border:1px solid #e5e7eb;
          border-radius:10px;
          outline:none;
          font: inherit;
        ">
        <div style="margin-top:8px; font-size:12px; color:#6b7280;">
          Выберите несколько категорий (покажем товары, которые входят хотя бы в одну).
        </div>
      </div>

      <div id="tg-filter-list" style="max-height: 52vh; overflow:auto; padding:10px 14px;"></div>

      <div style="display:flex; gap:10px; padding:12px 14px; border-top:1px solid #eef2f7;">
        <button id="tg-filter-reset" type="button" style="
          flex: 1;
          padding:10px 12px;
          border-radius: 12px;
          border: 1px solid #e5e7eb;
          background: #fff;
          cursor: pointer;
          font-weight: 600;
        ">Сбросить</button>

        <button id="tg-filter-apply" type="button" style="
          flex: 1;
          padding:10px 12px;
          border-radius: 12px;
          border: none;
          background: #111827;
          color: #fff;
          cursor: pointer;
          font-weight: 700;
        ">Применить</button>
      </div>
    </div>
  `;

    document.body.appendChild(el);
    filterModalEl = el;

    // close handlers
    el.addEventListener("click", (e) => {
        if (e.target === el) closeFilterModal();
    });
    el.querySelector("#tg-filter-close").addEventListener("click", closeFilterModal);

    // apply
    el.querySelector("#tg-filter-apply").addEventListener("click", async () => {
        await applyFiltersAndReload();
        closeFilterModal();
    });

    // reset
    el.querySelector("#tg-filter-reset").addEventListener("click", () => {
        filters.tgCategoryIds.clear();
        renderFilterList(); // refresh checks
    });

    // search categories
    el.querySelector("#tg-filter-search").addEventListener("input", () => renderFilterList());

    return el;
}

function openFilterModal() {
    ensureFilterModal();
    filterModalEl.style.display = "block";
    renderFilterList();
}

function closeFilterModal() {
    if (!filterModalEl) return;
    filterModalEl.style.display = "none";
}

async function renderFilterList() {
    const cats = await getTgCategories();
    const list = filterModalEl.querySelector("#tg-filter-list");
    const q = (filterModalEl.querySelector("#tg-filter-search").value || "").trim().toLowerCase();

    const filtered = cats.filter(c => {
        if (!q) return true;
        return String(c.name || "").toLowerCase().includes(q);
    });

    if (!filtered.length) {
        list.innerHTML = `<div style="padding:8px 2px; color:#6b7280;">Ничего не найдено</div>`;
        return;
    }

    list.innerHTML = filtered.map(c => {
        const id = Number(c.id);
        const checked = filters.tgCategoryIds.has(id) ? "checked" : "";
        const count = (c.product_count != null) ? ` <span style="color:#9ca3af;">(${c.product_count})</span>` : "";
        return `
      <label style="display:flex; align-items:center; gap:10px; padding:10px 6px; border-bottom:1px solid #f3f4f6; cursor:pointer;">
        <input type="checkbox" data-cat-id="${id}" ${checked} style="width:16px; height:16px;">
        <div style="flex:1; min-width:0;">
          <div style="font-weight:700; color:#111827; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
            ${escapeHtml(c.name)}${count}
          </div>
          ${c.description ? `<div style="font-size:12px; color:#6b7280; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(c.description)}</div>` : ""}
        </div>
      </label>
    `;
    }).join("");

    list.querySelectorAll("input[type=checkbox][data-cat-id]").forEach(cb => {
        cb.addEventListener("change", () => {
            const id = Number(cb.dataset.catId);
            if (cb.checked) filters.tgCategoryIds.add(id);
            else filters.tgCategoryIds.delete(id);
        });
    });
}

function updateFilterButtonLabel() {
    const btn = document.getElementById("filter-btn");
    if (!btn) return;
    const n = filters.tgCategoryIds.size;
    btn.textContent = n ? `Категории (${n})` : "Категории";
}

/** =========================
 *  LOAD PRODUCTS (with filters)
 *  ========================= */
async function loadMore(container, append = false, useLoader = true) {
    if (loading) return;
    loading = true;

    try {
        const fetchFn = async () => {
            const collected = [];
            let localPage = page;

            const tgIds = Array.from(filters.tgCategoryIds);
            const tgCsv = tgIds.length ? tgIds.join(",") : "";

            while (true) {
                // ✅ IMPORTANT: productService must forward tg_category_ids + tg_category_mode to backend query string
                const data = await searchProducts({
                    q: "",
                    page: localPage,
                    limit: 24,
                    tg_category_ids: tgCsv,
                    tg_category_mode: filters.tgCategoryMode,
                });

                const rawResults = Array.isArray(data?.results) ? data.results : [];
                if (!rawResults.length) break;

                for (const p of rawResults) {
                    const features = Array.isArray(p.features) ? p.features : [];
                    const hasStock = features.some(f => Number(f.balance ?? 0) > 0);
                    if (!hasStock) continue;
                    collected.push(p);
                }

                localPage += 1;
                if (collected.length >= 6) break;
            }

            page = localPage;
            return collected;
        };

        const results = useLoader ? await withLoader(fetchFn) : await fetchFn();
        const html = results.map(productCardHTML).join("");

        if (append) container.insertAdjacentHTML("beforeend", html);
        else container.innerHTML = html;

        attachProductInteractions(container);
    } catch (err) {
        console.error("[Products] load failed:", err);
    } finally {
        loading = false;
    }
}

function setupInfiniteScroll(container) {
    function onScroll() {
        if (mode !== "home") return;
        if (container.style.display === "none") return;

        const st = document.documentElement.scrollTop || document.body.scrollTop;
        const sh = document.documentElement.scrollHeight || document.body.scrollHeight;
        const ch = document.documentElement.clientHeight;
        if (st + ch >= sh - 200) loadMore(container, true);
    }

    window.addEventListener("scroll", onScroll);
}

async function applyFiltersAndReload() {
    updateFilterButtonLabel();
    page = 0;
    await loadMore(listEl, false);
}

/** =========================
 *  AUTH
 *  ========================= */
async function getUser() {
    const initData = state.telegram.initData || "";
    const payload = { initData };
    const result = await apiPost("/auth", payload);
    state.user = result.user;
    return result.user;
}

/** =========================
 *  HOME PAGE
 *  ========================= */
async function openHomePage() {
    mode = "home";
    hideMainButton();
    hideBackButton();

    navBottomEl.style.display = "flex";
    headerTitle.textContent = "Магазин ElixirPeptide";

    tosOverlayEl.style.display = "none";
    listEl.style.display = "grid";
    toolbarEl.style.display = "flex";
    searchBtnEl.style.display = "flex";

    detailEl.style.display = "none";
    cartPageEl.style.display = "none";
    checkoutPageEl.style.display = "none";
    contactPageEl.style.display = "none";
    paymentPageEl.style.display = "none";
    processPaymentEl.style.display = "none";
    profilePageEl.style.display = "none";
    ordersPageEl.style.display = "none";
    orderDetailEl.style.display = "none";

    // bind filter button once
    const filterBtn = document.getElementById("filter-btn");
    if (filterBtn && !filterBtn.dataset.bound) {
        filterBtn.addEventListener("click", openFilterModal);
        filterBtn.dataset.bound = "1";
    }
    updateFilterButtonLabel();

    // preload categories once (so modal opens instantly)
    try { await getTgCategories(); } catch (e) { console.warn("Failed to load tg categories", e); }

    page = 0;
    await loadMore(listEl, false);
    setupInfiniteScroll(listEl);
}

/** =========================
 *  TOS OVERLAY (unchanged logic)
 *  ========================= */
function closeTosOverlay() {
    if (!tosOverlayEl) return;
    tosOverlayEl.classList.add("hidden");
    tosOverlayEl.style.display = "none";
    document.body.style.overflow = "";
    hideMainButton();
}

async function openTosOverlay(user) {
    if (!tosOverlayEl) return;
    const tosBodyEl = document.getElementById("tos-body");

    if (tosBodyEl && !tosBodyEl.dataset.loaded) {
        try {
            const res = await fetch("/static/offer.html", { cache: "no-cache" });
            if (!res.ok) throw new Error("Failed to load offer.html");
            tosBodyEl.innerHTML = await res.text();
            tosBodyEl.dataset.loaded = "1";
        } catch (err) {
            console.error("Не удалось загрузить offer.html:", err);
            tosBodyEl.innerHTML = "<p>Не удалось загрузить текст публичной оферты. Попробуйте позже.</p>";
        }
    }

    tosOverlayEl.classList.remove("hidden");
    tosOverlayEl.style.display = "flex";
    document.body.style.overflow = "hidden";

    let acceptMode = false;

    const setAcceptButton = () => {
        if (acceptMode) return;
        acceptMode = true;

        showMainButton("Прочитал(а) и соглашаюсь", async () => {
            const payload = {
                is_active: true,
                user_id: user.tg_id,
                name: "Начальная",
                sum: 0.0,
                delivery_sum: 0.0,
                delivery_string: "Начальная",
                commentary: "Начальная"
            };
            await apiPost("/cart/create", payload);

            const currentUser = state.user || user;
            if (currentUser) {
                currentUser.accepted_terms = true;
                state.user = currentUser;
            }

            await withLoader(openHomePage);
            closeTosOverlay();
        });
    };

    if (tosBodyEl && !tosBodyEl.dataset.scrollBound) {
        tosBodyEl.addEventListener("scroll", () => {
            const el = tosBodyEl;
            const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 10;
            if (!acceptMode && atBottom) setAcceptButton();
        });
        tosBodyEl.dataset.scrollBound = "1";
    }

    showMainButton("Прокрутить вниз", () => {
        const body = document.getElementById("tos-body");
        if (body) {
            body.scrollTo({ top: body.scrollHeight, behavior: "smooth" });
        }
        setAcceptButton();
    });
}

export async function renderHomePage() {
    showLoader();
    const user = state.user || await getUser();

    if (!user) {
        await openHomePage();
    } else {
        document.getElementById("bottom-nav-avatar").src =
            user.photo_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=user${user.tg_id}`;

        state.user = user;

        if (!user.accepted_terms) openTosOverlay(user);
        else await openHomePage();
    }

    hideLoader();
}

/** =========================
 *  HELPERS
 *  ========================= */
function escapeHtml(s) {
    return String(s ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}