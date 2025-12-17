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
import {apiPost, apiGet} from "../../services/api.js";

let page = 0;
let loading = false;
let mode = "home";

// =========================
// TG Categories (front filter)
// =========================
let tgCategoriesCache = null;
let activeTgCategoryName = null;
let categoriesUiBound = false;

// Prevent double-binding infinite scroll listener
let infiniteScrollBound = false;

function ensureCategoriesOverlay() {
    let overlay = document.getElementById("categories-overlay");
    if (overlay) return overlay;

    overlay = document.createElement("div");
    overlay.id = "categories-overlay";
    overlay.className = "categories-overlay";
    overlay.innerHTML = `
      <div class="categories-modal" role="dialog" aria-modal="true">
        <div class="categories-header">
          <div class="categories-title">Категории</div>
          <button class="categories-close" id="categories-close" type="button">✕</button>
        </div>
        <div class="categories-list" id="categories-list"></div>
      </div>
    `;

    document.body.appendChild(overlay);

    overlay.addEventListener("click", (e) => {
        if (e.target === overlay) closeCategoriesOverlay();
    });

    overlay.querySelector("#categories-close")?.addEventListener("click", closeCategoriesOverlay);

    return overlay;
}

function openCategoriesOverlay() {
    const overlay = ensureCategoriesOverlay();
    overlay.classList.add("is-open");
    document.body.style.overflow = "hidden";
}

function closeCategoriesOverlay() {
    const overlay = document.getElementById("categories-overlay");
    if (!overlay) return;
    overlay.classList.remove("is-open");
    document.body.style.overflow = "";
}

async function fetchTgCategories() {
    if (Array.isArray(tgCategoriesCache)) return tgCategoriesCache;

    // Adjust these paths if your backend uses different prefix
    const res = await apiGet("/api/v1/public/tg-categories");
    const cats = Array.isArray(res) ? res : (res?.data || res?.categories || []);
    tgCategoriesCache = cats;
    return cats;
}

function renderCategoriesChips(categories) {
    const list = document.getElementById("categories-list");
    if (!list) return;

    list.innerHTML = "";

    // "All" chip
    const allBtn = document.createElement("button");
    allBtn.type = "button";
    allBtn.className = "categories-chip" + (!activeTgCategoryName ? " is-active" : "");
    allBtn.textContent = "Все товары";
    allBtn.addEventListener("click", async () => {
        activeTgCategoryName = null;
        closeCategoriesOverlay();
        await withLoader(openHomePage);
    });
    list.appendChild(allBtn);

    categories.forEach((c) => {
        const name = String(c?.name ?? "").trim();
        if (!name) return;

        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "categories-chip" + (activeTgCategoryName === name ? " is-active" : "");
        btn.textContent = name;

        btn.addEventListener("click", async () => {
            activeTgCategoryName = name;
            closeCategoriesOverlay();
            await withLoader(() => openTgCategoryPage(name));
        });

        list.appendChild(btn);
    });
}

async function openTgCategoryPage(categoryName) {
    mode = "category";

    hideMainButton();
    showBackButton(async () => {
        activeTgCategoryName = null;
        await withLoader(openHomePage);
    });

    navBottomEl.style.display = "flex";
    headerTitle.textContent = categoryName;

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

    // Adjust this path if needed
    const res = await apiGet(`/api/v1/public/tg-categories/products?name=${encodeURIComponent(categoryName)}`);
    const products = Array.isArray(res) ? res : (res?.data || res?.products || []);

    const html = products.map(productCardHTML).join("");
    listEl.innerHTML = html;
    attachProductInteractions(listEl);
}

async function initTgCategoriesUi() {
    if (categoriesUiBound) return;
    categoriesUiBound = true;

    const filterBtn = document.getElementById("filter-btn");
    if (!filterBtn) return;

    filterBtn.addEventListener("click", async () => {
        try {
            openCategoriesOverlay();
            const cats = await withLoader(fetchTgCategories);
            renderCategoriesChips(cats);
        } catch (e) {
            console.error("[TG Categories] failed:", e);
            closeCategoriesOverlay();
        }
    });
}

// Helper: Handle image switching logic (Feature -> Product -> Default)
function updateCardImage(selectElement) {
    const card = selectElement.closest(".product-card");
    const img = card?.querySelector(".product-img");
    const selectedOption = selectElement.selectedOptions[0];

    if (!img || !selectedOption) return;

    const featureImgSrc = selectedOption.dataset.featureImg; // /static/images/feature_ID.png
    const productImgSrc = img.dataset.productImg;            // /static/images/ONEC_ID.png
    const defaultImgSrc = "/static/images/product.png";      // Fallback

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

function productCardHTML(p) {
    const onecId = p.onec_id || (p.url ? p.url.split("/product/")[1] : "0");
    const rawFeatures = Array.isArray(p.features) ? p.features : [];

    const availableFeatures = rawFeatures.filter(f => {
        const bal = Number(f.balance ?? 0);
        return bal > 0;
    });

    const sortedFeatures = availableFeatures.sort((a, b) => b.price - a.price);

    if (!sortedFeatures.length) return "";

    const productImgPath = `/static/images/${onecId}.png`;
    const defaultImgPath = "/static/images/product.png";

    const featureSelector = `
        <select class="feature-select" data-onec-id="${onecId}">
            ${sortedFeatures.map(
        f => `<option value="${f.id}"
                         data-price="${f.price}"
                         data-balance="${Number(f.balance ?? 0)}"
                         data-feature-img="/static/images/${f.id}.png">
                    ${f.name} - ${f.price} ₽
                 </option>`
    ).join("")}
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

            while (true) {
                const data = await searchProducts({q: "", page: localPage});
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
    if (infiniteScrollBound) return;
    infiniteScrollBound = true;

    function onScroll() {
        // infinite scroll only in home mode
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

    page = 0;
    await loadMore(listEl, false);
    setupInfiniteScroll(listEl);
}

/**
 * favourites page
 */
async function openFavouritesPage() {
    mode = "favourites";
    hideMainButton();
    showBackButton(async () => {
        await withLoader(openHomePage);
    });

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
                rendererSettings: { preserveAspectRatio: "xMidYMid meet" },
            });
        }
        return;
    }

    const favSet = new Set(favIds.map(String));

    const fetchFn = async () => {
        const data = await searchProducts({q: "", page: 0, limit: 500});
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

// TOS overlay close only after accept
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

    // bind категории button once
    await initTgCategoriesUi();

    if (!user) {
        await openHomePage();
    } else {
        document.getElementById("bottom-nav-avatar").src =
            user.photo_url ||
            `https://api.dicebear.com/7.x/avataaars/svg?seed=user${user.tg_id}`;
        state.user = user;

        if (!user.accepted_terms) {
            openTosOverlay(user);
        } else {
            await openHomePage();
        }
    }
    hideLoader();
}

export async function renderFavouritesPage() {
    const user = state.user || await getUser();

    // bind категории button once (no harm)
    await initTgCategoriesUi();

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