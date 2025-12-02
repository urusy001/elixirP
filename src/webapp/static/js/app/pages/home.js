import {searchProducts} from "../../services/productService.js";
import {hideLoader, showLoader, withLoader} from "../ui/loader.js";
import {navigateTo} from "../router.js";
import {state, saveCart} from "../state.js";
import {hideBackButton, hideMainButton, showBackButton, showMainButton} from "../ui/telegram.js";
import {
    cartPageEl,
    checkoutPageEl,
    contactPageEl, detailEl,
    headerTitle, listEl, navBottomEl,
    paymentPageEl,
    processPaymentEl,
    searchBtnEl,
    toolbarEl, tosOverlayEl
} from "./constants.js";
import {apiPost} from "../../services/api.js";

let page = 0;
let loading = false;
// "home" | "favourites" (влияет на бесконечный скролл)
let mode = "home";

// элементы TOS-модалки
const tosBodyEl = document.getElementById("tos-body");
const tosCloseBtn = document.getElementById("tos-close-btn");

function productCardHTML(p) {
    const onecId = p.onec_id || (p.url ? p.url.split("/product/")[1] : "0");
    const sortedFeatures = Array.isArray(p.features)
        ? [...p.features].sort((a, b) => b.price - a.price)
        : [];

    const featureSelector = sortedFeatures.length
        ? `<select class="feature-select" data-onec-id="${onecId}">
         ${sortedFeatures.map(f => `<option value="${f.id}" data-price="${f.price}">${f.name} - ${f.price} ₽</option>`).join("")}
       </select>`
        : "";

    return `
    <div class="product-card">
      <a href="/product/${onecId}" class="product-link" data-onec-id="${onecId}">
        <div class="product-image">
          <img src="/static/images/product.png"
               data-highres="${p.image || '/static/images/product.png'}"
               alt="${p.name}" class="product-img">
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
    const selector = btn.closest(".product-card")?.querySelector(".feature-select");
    const selectedFeatureId = selector?.value || null;
    const key = selectedFeatureId ? `${onecId}_${selectedFeatureId}` : onecId;
    const count = state.cart[key] || 0;

    btn.innerHTML = "";

    if (count === 0) {
        const add = document.createElement("button");
        add.textContent = "+ В корзину";
        add.className = "buy-btn-initial";
        add.onclick = () => {
            state.cart[key] = 1;
            saveCart();
            renderBuyCounter(btn, onecId);
        };
        btn.appendChild(add);
    } else {
        const minus = document.createElement("button");
        minus.textContent = "−";
        minus.onclick = () => {
            state.cart[key] = (state.cart[key] || 0) - 1;
            if (state.cart[key] <= 0) delete state.cart[key];
            saveCart();
            renderBuyCounter(btn, onecId);
        };
        const qty = document.createElement("span");
        qty.textContent = state.cart[key];
        qty.style.margin = "0 4px";
        const plus = document.createElement("button");
        plus.textContent = "+";
        plus.onclick = () => {
            state.cart[key] = (state.cart[key] || 0) + 1;
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
            const data = await searchProducts({q: "", page});
            if (!data.results || !Array.isArray(data.results)) data.results = [];
            return data.results;
        };

        const results = useLoader ? await withLoader(fetchFn) : await fetchFn();
        const html = results.map(productCardHTML).join("");

        if (append) container.insertAdjacentHTML("beforeend", html);
        else container.innerHTML = html;

        attachProductInteractions(container);
        page++;
    } catch (err) {
        console.error("[Products] load failed:", err);
    } finally {
        loading = false;
    }
}

function setupInfiniteScroll(container) {
    function onScroll() {
        // бесконечная прокрутка только в режиме "home"
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
    const tg = window.Telegram?.WebApp;
    if (!tg) return null;

    const initData = tg.initData || "";
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

    page = 1;
    await loadMore(listEl, false);
    setupInfiniteScroll(listEl);
}

/**
 * Открыть страницу избранного.
 * Показывает те же карточки, но только для товаров,
 * onec_id которых лежат в state.user.favourites.
 */
async function openFavouritesPage() {
    mode = "favourites";
    hideMainButton();
    showBackButton();
    navBottomEl.style.display = "flex";
    headerTitle.textContent = "Избранное";
    tosOverlayEl.style.display = "none";
    listEl.style.display = "grid";
    toolbarEl.style.display = "none";
    searchBtnEl.style.display = "flex";
    detailEl.style.display = "none";
    cartPageEl.style.display = "none";
    checkoutPageEl.style.display = "none";
    contactPageEl.style.display = "none";
    paymentPageEl.style.display = "none";
    processPaymentEl.style.display = "none";

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

        // Инициализируем Lottie-анимацию вместо gif
        const animContainer = document.getElementById("empty-fav-lottie");
        if (animContainer && window.lottie) {
            window.lottie.loadAnimation({
                container: animContainer,
                renderer: "svg",
                loop: true,
                autoplay: true,
                path: "/static/stickers/utya-fav.json", // или "static/..." если так раздаёшь
                rendererSettings: {
                    preserveAspectRatio: "xMidYMid meet",
                },
            });
        }

        return;
    }

    const favSet = new Set(favIds.map(String));

    const fetchFn = async () => {
        // Берём побольше товаров и фильтруем по избранным.
        const data = await searchProducts({q: "", page: 0, limit: 500});
        const all = Array.isArray(data?.results) ? data.results : [];
        return all.filter((p) => {
            const onecId = p.onec_id || (p.url ? p.url.split("/product/")[1] : "0");
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

function closeTosOverlay() {
    if (!tosOverlayEl) return;

    tosOverlayEl.classList.add("hidden");
    tosOverlayEl.style.display = "none";
    document.body.style.overflow = "";
    // если нужно, можно прятать MainButton при ручном закрытии
    // hideMainButton();
}

async function openTosOverlay(user) {
    if (!tosOverlayEl) return;

    // 1) Подгружаем текст оферты из /static/offer.html один раз
    if (tosBodyEl && !tosBodyEl.dataset.loaded) {
        try {
            const res = await fetch("/static/offer.html", {cache: "no-cache"});
            if (!res.ok) {
                throw new Error("Failed to load offer.html");
            }
            const html = await res.text();
            tosBodyEl.innerHTML = html;
            tosBodyEl.dataset.loaded = "1";
        } catch (err) {
            console.error("Не удалось загрузить offer.html:", err);
            tosBodyEl.innerHTML =
                "<p>Не удалось загрузить текст публичной оферты. Попробуйте позже.</p>";
        }
    }

    // 2) Показываем оверлей
    tosOverlayEl.classList.remove("hidden");
    tosOverlayEl.style.display = "flex";
    document.body.style.overflow = "hidden";

    // 3) Вешаем обработчик на крестик (если он есть)
    if (tosCloseBtn && !tosCloseBtn.dataset.bound) {
        tosCloseBtn.addEventListener("click", () => {
            closeTosOverlay();
        });
        tosCloseBtn.dataset.bound = "1";
    }

    // 4) Telegram MainButton — подтверждение
    showMainButton("Прочитал(а) и соглашаюсь", async () => {
        const payload = {
            is_active: true,
            user_id: user.tg_id,
        };
        await apiPost('/cart/create', payload);
        await withLoader(openHomePage);
        // прячем оверлей и возвращаем скролл
        closeTosOverlay();
    });
}

export async function renderHomePage() {
    showLoader();
    const user = state.user || await getUser();
    if (!user) {
        console.warn("[Home] invalid user (auth failed)");
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

/**
 * Рендер страницы избранного (аналог renderHomePage,
 * но вместо openHomePage вызывает openFavouritesPage).
 */
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