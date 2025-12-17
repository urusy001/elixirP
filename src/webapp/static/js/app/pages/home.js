import {searchProducts} from "../../services/productService.js";
import {hideLoader, showLoader, withLoader} from "../ui/loader.js";
import {navigateTo} from "../router.js";
import {saveCart, state} from "../state.js";
import {hideBackButton, hideMainButton, showBackButton, showMainButton} from "../ui/telegram.js";
import {
    cartPageEl,
    checkoutPageEl,
    contactPageEl,
    detailEl,
    headerTitle,
    listEl,
    navBottomEl, orderDetailEl, ordersPageEl,
    paymentPageEl,
    processPaymentEl, profilePageEl,
    searchBtnEl,
    toolbarEl,
    tosOverlayEl
} from "./constants.js";
import {apiPost, apiGet} from "../../services/api.js";

let page = 0;
let loading = false;
let mode = "home";

/* =========================
   TG CATEGORIES (FILTERS)
   =========================
   Requires backend:
   - GET /tg-categories -> [{id, name, description?}]
   - /search endpoint accepts tg_category_ids (repeatable) or comma string
   This file uses: searchProducts({ q, page, limit, tg_category_ids })
*/
let tgCategoriesCache = null;             // [{id,name,description}]
let selectedTgCategoryIds = new Set();    // Set<number>
let filterUiBound = false;

function getSelectedCategoryIdsArray() {
    return Array.from(selectedTgCategoryIds).map(Number).filter(Number.isFinite);
}

async function fetchTgCategories() {
    // If your route path is different, change here.
    // Expected response: array OR {data:[...]}
    const res = await apiGet("/tg-categories");
    const items = Array.isArray(res) ? res : (res?.data || res?.categories || []);
    return items
        .map(c => ({ id: Number(c.id), name: String(c.name ?? ""), description: c.description ?? null }))
        .filter(c => Number.isFinite(c.id) && c.name.trim().length > 0);
}

function ensureCategoryFilterOverlay() {
    let overlay = document.getElementById("tgcat-overlay");
    if (overlay) return overlay;

    overlay = document.createElement("div");
    overlay.id = "tgcat-overlay";
    overlay.style.cssText = `
        position: fixed;
        inset: 0;
        display: none;
        align-items: flex-end;
        justify-content: center;
        background: rgba(0,0,0,0.35);
        z-index: 9999;
        padding: 12px;
    `;

    overlay.innerHTML = `
        <div
            id="tgcat-modal"
            style="
                width: 100%;
                max-width: 520px;
                background: #fff;
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 12px 40px rgba(0,0,0,0.18);
                display: flex;
                flex-direction: column;
                max-height: 78vh;
            "
        >
            <div style="padding: 12px 14px; border-bottom: 1px solid #eef2f7; display:flex; align-items:center; justify-content:space-between; gap:10px;">
                <div style="font-weight:700; font-size: 15px; color:#111827;">Категории</div>
                <button id="tgcat-close" type="button" style="border:none; background:transparent; font-size:18px; line-height:1; cursor:pointer;">✕</button>
            </div>

            <div id="tgcat-list" style="padding: 10px 14px; overflow:auto;">
                <div style="color:#6b7280; font-size: 13px;">Загрузка…</div>
            </div>

            <div style="padding: 12px 14px; border-top: 1px solid #eef2f7; display:flex; gap:10px; justify-content:flex-end;">
                <button id="tgcat-reset" type="button" style="border:1px solid #e5e7eb; background:#fff; padding:10px 12px; border-radius: 12px; cursor:pointer; font-weight:600;">
                    Сбросить
                </button>
                <button id="tgcat-apply" type="button" style="border:none; background:#111827; color:#fff; padding:10px 12px; border-radius: 12px; cursor:pointer; font-weight:700;">
                    Применить
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);
    return overlay;
}

function setFilterBtnBadge() {
    const btn = document.getElementById("filter-btn");
    if (!btn) return;
    const n = selectedTgCategoryIds.size;
    btn.textContent = n > 0 ? `Категории (${n})` : "Категории";
}

function renderCategoriesChecklist(categories) {
    const list = document.getElementById("tgcat-list");
    if (!list) return;

    if (!categories.length) {
        list.innerHTML = `<div style="color:#6b7280; font-size: 13px;">Категорий пока нет.</div>`;
        return;
    }

    const rows = categories.map(c => {
        const checked = selectedTgCategoryIds.has(Number(c.id)) ? "checked" : "";
        const desc = c.description ? `<div style="color:#6b7280; font-size:12px; margin-top:2px;">${escapeHtml(c.description)}</div>` : "";
        return `
            <label
                style="
                    display:flex;
                    gap:10px;
                    padding:10px 8px;
                    border:1px solid #eef2f7;
                    border-radius:12px;
                    margin-bottom:8px;
                    cursor:pointer;
                    align-items:flex-start;
                "
            >
                <input
                    type="checkbox"
                    class="tgcat-checkbox"
                    data-id="${c.id}"
                    ${checked}
                    style="margin-top: 2px;"
                />
                <div style="min-width:0;">
                    <div style="font-weight:700; font-size: 14px; color:#111827;">${escapeHtml(c.name)}</div>
                    ${desc}
                </div>
            </label>
        `;
    }).join("");

    list.innerHTML = rows;
}

async function openCategoryFilterOverlay() {
    const overlay = ensureCategoryFilterOverlay();
    overlay.style.display = "flex";
    document.body.style.overflow = "hidden";

    try {
        if (!tgCategoriesCache) {
            tgCategoriesCache = await fetchTgCategories();
        }
        renderCategoriesChecklist(tgCategoriesCache);
    } catch (e) {
        console.error("[TG Categories] load failed:", e);
        const list = document.getElementById("tgcat-list");
        if (list) list.innerHTML = `<div style="color:#ef4444; font-size: 13px;">Не удалось загрузить категории</div>`;
    }
}

function closeCategoryFilterOverlay() {
    const overlay = document.getElementById("tgcat-overlay");
    if (!overlay) return;
    overlay.style.display = "none";
    document.body.style.overflow = "";
}

function bindCategoryFilterUIOnce() {
    if (filterUiBound) return;

    const filterBtn = document.getElementById("filter-btn");
    if (filterBtn) {
        filterBtn.addEventListener("click", async () => {
            await openCategoryFilterOverlay();
        });
    }

    // Overlay events (created lazily)
    document.addEventListener("click", async (e) => {
        const overlay = document.getElementById("tgcat-overlay");
        if (!overlay || overlay.style.display === "none") return;

        const t = e.target;

        // click outside modal closes
        if (t === overlay) {
            closeCategoryFilterOverlay();
            return;
        }

        if (t && t.id === "tgcat-close") {
            closeCategoryFilterOverlay();
            return;
        }

        if (t && t.id === "tgcat-reset") {
            selectedTgCategoryIds.clear();
            // re-render keeping cache
            if (tgCategoriesCache) renderCategoriesChecklist(tgCategoriesCache);
            setFilterBtnBadge();
            return;
        }

        if (t && t.id === "tgcat-apply") {
            // read current checkboxes
            const checkboxes = Array.from(document.querySelectorAll(".tgcat-checkbox"));
            const next = new Set();
            for (const cb of checkboxes) {
                if (cb.checked) next.add(Number(cb.dataset.id));
            }
            selectedTgCategoryIds = next;
            setFilterBtnBadge();
            closeCategoryFilterOverlay();

            // reload products (DO NOT TOUCH OTHER MECHANICS)
            if (mode === "favourites") {
                await withLoader(openFavouritesPage);
            } else {
                page = 0;
                await withLoader(async () => {
                    await loadMore(listEl, false, false);
                });
            }
        }
    }, { passive: true });

    filterUiBound = true;
}

/* =========================
   EXISTING MECHANICS (UNCHANGED)
   ========================= */

// Helper: Handle image switching logic (Feature -> Product -> Default)
function updateCardImage(selectElement) {
    const card = selectElement.closest(".product-card");
    const img = card?.querySelector(".product-img");
    const selectedOption = selectElement.selectedOptions[0];

    if (!img || !selectedOption) return;

    const featureImgSrc = selectedOption.dataset.featureImg; // /static/images/feature_ID.png
    const productImgSrc = img.dataset.productImg;            // /static/images/ONEC_ID.png
    const defaultImgSrc = "/static/images/product.png";      // Fallback

    // Define the error handler chain
    const setFallbackToProduct = () => {
        img.onerror = () => {
            img.onerror = null; // Prevent infinite loop
            img.src = defaultImgSrc;
        };
        img.src = productImgSrc;
    };

    // 1. Try loading the Feature Image
    img.onerror = setFallbackToProduct;
    img.src = featureImgSrc;
}

function productCardHTML(p) {
    const onecId = p.onec_id || (p.url ? p.url.split("/product/")[1] : "0");
    const rawFeatures = Array.isArray(p.features) ? p.features : [];

    const availableFeatures = rawFeatures.filter(f => {
        const bal = Number(f.balance ?? 0);
        return bal > 0;
    });

    const sortedFeatures = availableFeatures.sort((a, b) => b.price - a.price);

    // Если нет ни одной фичи с положительным остатком — вообще НЕ рисуем карточку
    if (!sortedFeatures.length) {
        return "";
    }

    // Prepare paths
    const productImgPath = `/static/images/${onecId}.png`;
    const defaultImgPath = "/static/images/product.png";

    const featureSelector = `
        <select class="feature-select" data-onec-id="${onecId}">
            ${sortedFeatures
        .map(
            f =>
                // Store the specific feature image path in data attribute
                `<option value="${f.id}"
                         data-price="${f.price}"
                         data-balance="${Number(f.balance ?? 0)}"
                         data-feature-img="/static/images/${f.id}.png">
                    ${f.name} - ${f.price} ₽
                 </option>`
        )
        .join("")}
        </select>
    `;

    return `
    <div class="product-card">
      <a href="/product/${onecId}" class="product-link" data-onec-id="${onecId}">
        <div class="product-image">
          <img src="${productImgPath}"
               data-product-img="${productImgPath}"
               data-default-img="${defaultImgPath}"
               alt="${p.name}" 
               class="product-img"
               onerror="this.onerror=null; this.src='${defaultImgPath}';">
        </div>
      </a>
      <div class="product-info">
        <span class="product-name">${p.name}</span>
        ${featureSelector}
      </div>
      <button class="buy-btn" data-onec-id="${onecId}"></button>
    </div>
  `;
}

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
            const current = state.cart[key] || 0;
            const next = current - 1;
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
            const current = state.cart[key] || 0;
            if (current >= max) return;
            state.cart[key] = current + 1;
            saveCart();
            renderBuyCounter(btn, onecId);
        };

        btn.append(minus, qty, plus);
    }

    if (selector && !selector.dataset.counterBound) {
        selector.addEventListener("change", () => {
            renderBuyCounter(btn, onecId);
        });
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

        select.addEventListener("change", () => {
            updateCardImage(select);
        });
        select.dataset.imageBound = "1";
    });

    container.querySelectorAll(".buy-btn").forEach(btn => {
        if (btn.dataset.initialized) return;
        renderBuyCounter(btn, btn.dataset.onecId);
        btn.dataset.initialized = "1";
    });
}

async function loadMore(container, append = false, useLoader = true) {
    if (loading) return;
    loading = true;

    try {
        const fetchFn = async () => {
            const collected = [];
            let localPage = page;

            const tg_category_ids = getSelectedCategoryIdsArray();
            alert(JSON.stringify(tg_category_ids));

            while (true) {
                // ✅ categories applied here (does NOT affect other mechanics)
                const data = await searchProducts({ q: "", page: localPage, tgCategoryIds: tg_category_ids, tgCategoryMode: "all"});

                const rawResults = Array.isArray(data.results) ? data.results : [];
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

async function getUser() {
    const initData = state.telegram.initData || "";
    const payload = {initData};
    const result = await apiPost('/auth', payload);
    state.user = result.user;
    return result.user;
}

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

    // ✅ bind filter UI once, keep everything else intact
    bindCategoryFilterUIOnce();
    setFilterBtnBadge();

    page = 0;
    await loadMore(listEl, false);
    setupInfiniteScroll(listEl);
}

async function openFavouritesPage() {
    mode = "favourites";
    hideMainButton();
    showBackButton();
    navBottomEl.style.display = "flex";
    headerTitle.textContent = "";
    tosOverlayEl.style.display = "none";
    listEl.style.display = "grid";
    toolbarEl.style.display = "none";
    searchBtnEl.style.display = "none";
    detailEl.style.display = "none";
    cartPageEl.style.display = "none";
    checkoutPageEl.style.display = "none";
    contactPageEl.style.display = "none";
    paymentPageEl.style.display = "none";
    processPaymentEl.style.display = "none";
    profilePageEl.style.display = "none";
    ordersPageEl.style.display = "none";
    orderDetailEl.style.display = "none";

    // ✅ keep badge consistent even in favourites mode
    bindCategoryFilterUIOnce();
    setFilterBtnBadge();

    const favIds = state?.user?.favourites || [];
    if (!favIds.length) {
        listEl.innerHTML = `
            <div style="grid-column:1 / -1; text-align:center; padding:24px 12px;">
                <h2 style="margin-bottom:8px; font-size:18px;">У вас пока нет избранных товаров</h2>
                <p style="margin:0; font-size:14px; color:#6b7280;">
                    Нажимайте на сердечко на странице товара, чтобы добавить его в избранное.
                </p>
                <div
                    id="empty-fav-lottie"
                    style="
                        margin-top:16px;
                        max-width:220px;
                        width:100%;
                        height:220px;
                        display:block;
                        margin-left:auto;
                        margin-right:auto;
                        border-radius:12px;
                        overflow:hidden;
                    "
                ></div>
            </div>
        `;

        const animContainer = document.getElementById("empty-fav-lottie");
        if (animContainer && window.lottie) {
            window.lottie.loadAnimation({
                container: animContainer,
                renderer: "svg",
                loop: true,
                autoplay: true,
                path: "/static/stickers/utya-fav.json",
                rendererSettings: {
                    preserveAspectRatio: "xMidYMid meet",
                },
            });
        }

        return;
    }

    const favSet = new Set(favIds.map(String));
    const tg_category_ids = getSelectedCategoryIdsArray();

    const fetchFn = async () => {
        // ✅ categories filter also affects favourites (only if selected)
        const data = await searchProducts({ q: "", page: 0, limit: 500, tgCategoryIds: tg_category_ids, tgCategoryMode: "all" });
        const all = Array.isArray(data?.results) ? data.results : [];

        return all.filter((p) => {
            const onecId = p.onec_id || (p.url ? p.url.split("/product/")[1] : "0");

            const features = Array.isArray(p.features) ? p.features : [];
            const hasStock = features.some(f => Number(f.balance ?? 0) > 0);
            if (!hasStock) return false;

            return favSet.has(String(onecId));
        });
    };

    try {
        const results = await withLoader(fetchFn);
        if (!results.length) {
            listEl.innerHTML = `
                <div style="grid-column:1 / -1; text-align:center; padding:24px 12px;">
                    <h2 style="margin-bottom:8px; font-size:18px;">Не удалось загрузить избранные</h2>
                    <p style="margin:0; font-size:14px; color:#6b7280;">
                        Попробуйте позже.
                    </p>
                </div>
            `;
            return;
        }

        listEl.innerHTML = results.map(productCardHTML).join("");
        attachProductInteractions(listEl);
    } catch (err) {
        console.error("[Favourites] load failed:", err);
        listEl.innerHTML = `
            <div style="grid-column:1 / -1; text-align:center; padding:24px 12px;">
                <h2 style="margin-bottom:8px; font-size:18px;">Ошибка загрузки избранных</h2>
                <p style="margin:0; font-size:14px; color:#6b7280;">
                    Пожалуйста, попробуйте позже.
                </p>
            </div>
        `;
    }
}

// закрытие только после согласия
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
            if (!res.ok) {
                throw new Error("Failed to load offer.html");
            }
            tosBodyEl.innerHTML = await res.text();
            tosBodyEl.dataset.loaded = "1";
        } catch (err) {
            console.error("Не удалось загрузить offer.html:", err);
            tosBodyEl.innerHTML =
                "<p>Не удалось загрузить текст публичной оферты. Попробуйте позже.</p>";
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
                sum: 0.00,
                delivery_sum: 0.00,
                delivery_string: "Начальная",
                commentary: "Начальная"
            };
            await apiPost('/cart/create', payload);

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
            const atBottom =
                el.scrollTop + el.clientHeight >= el.scrollHeight - 10;

            if (!acceptMode && atBottom) {
                setAcceptButton();
            }
        });
        tosBodyEl.dataset.scrollBound = "1";
    }

    showMainButton("Прокрутить вниз", () => {
        const body = document.getElementById("tos-body");
        if (body) {
            body.scrollTo({
                top: body.scrollHeight,
                behavior: "smooth",
            });
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
            user.photo_url ||
            `https://api.dicebear.com/7.x/avataaars/svg?seed=user${user.tg_id}`;
        state.user = user;
        if (!user.accepted_terms) {
            openTosOverlay(user);
        } else await openHomePage();
    }
    hideLoader();
}

export async function renderFavouritesPage() {
    const user = state.user || await getUser();
    if (!user) {
        console.warn("[Favourites] invalid user (auth failed)");
    } else {
        document.getElementById("bottom-nav-avatar").src =
            user.photo_url ||
            `https://api.dicebear.com/7.x/avataaars/svg?seed=user${user.tg_id}`;
        state.user = user;
        if (!user.accepted_terms) {
            openTosOverlay(user);
        } else {
            await openFavouritesPage();
        }
    }
}

/* =========================
   Helpers
   ========================= */

function escapeHtml(s) {
    return String(s ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}