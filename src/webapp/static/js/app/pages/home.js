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
    paymentPageEl,
    processPaymentEl, profilePageEl,
    searchBtnEl,
    toolbarEl,
    tosOverlayEl
} from "./constants.js";
import {apiPost} from "../../services/api.js";

let page = 0;
let loading = false;
let mode = "home";

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

    // Initial image load logic:
    // We try to load the Product Image first. If it fails, standard HTML onerror switches to default.
    // (Dynamic feature switching happens via JS listeners later)
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
        if (!Number.isFinite(bal) || bal <= 0) return Infinity; // на всякий случай
        return bal;
    };

    const maxBalance = getMaxBalance();

    // Приводим текущее количество к допустимому (не больше баланса)
    const current = state.cart[key] || 0;
    const safeCount = Math.min(current, maxBalance);
    if (safeCount !== current) {
        if (safeCount > 0) {
            state.cart[key] = safeCount;
        } else {
            delete state.cart[key];
        }
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
            if (next <= 0) {
                delete state.cart[key];
            } else {
                state.cart[key] = next;
            }
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
            if (current >= max) {
                // Можно добавить какое-то уведомление/вибрацию, если захочешь
                return;
            }
            state.cart[key] = current + 1;
            saveCart();
            renderBuyCounter(btn, onecId);
        };

        btn.append(minus, qty, plus);
    }

    // Note: The 'change' listener for the counter is handled here,
    // but we moved the 'change' listener for images to attachProductInteractions
    // to keep logic clean, or we can chain them.
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

    // Initialize Selectors for Image Switching
    container.querySelectorAll(".feature-select").forEach(select => {
        if (select.dataset.imageBound) return;

        // 1. Immediately set the image to the "active" feature (selected option)
        updateCardImage(select);

        // 2. Listen for future changes
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

                if (!rawResults.length) {
                    // Ничего больше нет — выходим
                    break;
                }

                // Отфильтруем тут те продукты, у которых вообще нет фич с balance > 0
                for (const p of rawResults) {
                    const features = Array.isArray(p.features) ? p.features : [];
                    const hasStock = features.some(f => Number(f.balance ?? 0) > 0);
                    if (!hasStock) continue;
                    collected.push(p);
                }

                localPage += 1;

                // Если набрали хотя бы 4 товара — достаточно
                if (collected.length >= 4) {
                    break;
                }
            }

            // Обновляем глобальный page на следующую страницу после последней взятой
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

    // начинаем с 0-й страницы, а loadMore сам будет дотягивать, если < 4
    page = 0;
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
    profilePageEl.style.display = "none";

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

            // тут тоже можем отсечь товары без остатка
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

    // 1) Подгружаем текст оферты из /static/offer.html один раз
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

    // 2) Показываем оверлей
    tosOverlayEl.classList.remove("hidden");
    tosOverlayEl.style.display = "flex";
    document.body.style.overflow = "hidden";

    // локальный флаг: уже ли мы переключили кнопку на "соглашаюсь"
    let acceptMode = false;

    const setAcceptButton = () => {
        if (acceptMode) return;
        acceptMode = true;

        // второй шаг — реальное согласие
        showMainButton("Прочитал(а) и соглашаюсь", async () => {
            const payload = {
                is_active: true,
                user_id: user.tg_id,
            };

            await apiPost("/cart/create", payload);

            // помечаем в фронте, что пользователь уже принял условия
            const currentUser = state.user || user;
            if (currentUser) {
                currentUser.accepted_terms = true;
                state.user = currentUser;
            }

            await withLoader(openHomePage);

            // прячем оверлей и возвращаем скролл
            closeTosOverlay();
        });
    };

    // 3) Листенер: если юзер сам докрутил до низа — сразу включаем acceptMode
    if (tosBodyEl && !tosBodyEl.dataset.scrollBound) {
        tosBodyEl.addEventListener("scroll", () => {
            const el = tosBodyEl;
            const atBottom =
                el.scrollTop + el.clientHeight >= el.scrollHeight - 10; // небольшой зазор

            if (!acceptMode && atBottom) {
                setAcceptButton();
            }
        });
        tosBodyEl.dataset.scrollBound = "1";
    }

    // 4) Первый шаг: MainButton скроллит оферту до низа и потом включает acceptMode
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