import {withLoader} from "../ui/loader.js";
import {state, saveCart, setCheckoutData} from "../state.js";
import {navigateTo} from "../router.js";
import {apiPost, apiGet} from "../../services/api.js";
import {
    hideMainButton,
    showBackButton,
    isTelegramApp,
    showMainButton,
    updateMainButton,
} from "../ui/telegram.js";
import {
    cartPageEl,
    checkoutPageEl,
    contactPageEl,
    detailEl,
    headerTitle,
    listEl, navBottomEl, orderDetailEl, ordersPageEl,
    paymentPageEl,
    processPaymentEl, profilePageEl,
    searchBtnEl,
    toolbarEl,
} from "./constants.js";

const cartTotalEl = document.getElementById("summary-label");
const cartItemsEl = document.getElementById("cart-items");

let cartRows = {};

// small helper to read promo input
function getPromoInput() {
    return document.getElementById("promo");
}

/* =========================
   PROMO SESSION STORAGE
   ========================= */
function savePromocodeToSession(code) {
    const v = (code || "").trim();
    sessionStorage.setItem("promocode", JSON.stringify(v || null));
}

function loadPromocodeFromSession() {
    try {
        return JSON.parse(sessionStorage.getItem("promocode") || "null");
    } catch {
        return null;
    }
}

function clearPromocodeFromSession() {
    sessionStorage.removeItem("promocode");
}

function savePromoDataToSession(data) {
    sessionStorage.setItem("promocode_data", JSON.stringify(data || null));
}

function loadPromoDataFromSession() {
    try {
        return JSON.parse(sessionStorage.getItem("promocode_data") || "null");
    } catch {
        return null;
    }
}

function clearPromoDataFromSession() {
    sessionStorage.removeItem("promocode_data");
}

/* =========================
   PROMO APPLY (GET)
   ========================= */
async function applyPromocode() {
    const promoInput = getPromoInput();
    const code = (promoInput?.value || "").trim();

    if (!code) {
        alert("Введите промокод");
        return;
    }

    updateMainButton("Проверка…", true, true);

    try {
        // GET /promocodes/?code=...
        const promo = await apiGet(`/promocodes/?code=${encodeURIComponent(code)}`);

        // expect discount_pct from backend
        const discountPct = promo?.discount_pct ?? promo?.discountPct ?? promo?.discount ?? null;

        // save typed code always
        savePromocodeToSession(code);

        if (discountPct === null || discountPct === undefined) {
            savePromoDataToSession({code, discount_pct: 0});
            alert("Промокод найден ✅ (скидка не указана)");
        } else {
            savePromoDataToSession({code, discount_pct: discountPct});
            alert(`Промокод применён ✅ Скидка: ${discountPct}%`);
        }

        updateTotal();
        if (isTelegramApp()) showMainButton("Оформить заказ", () => handleCheckout());
    } catch (err) {
        console.error(err);
        alert("Промокод не найден ❌");

        // keep input, but remove applied discount
        clearPromoDataFromSession();
        // optional: clear stored code too
        // clearPromocodeFromSession();

        updateTotal();
        if (isTelegramApp()) showMainButton("Оформить заказ", () => handleCheckout());
    }
}

/* =========================
   TOTAL & QTY HANDLING
   ========================= */
function updateTotal() {
    const keys = Object.keys(state.cart);

    // empty cart
    if (!keys.length) {
        cartTotalEl.innerHTML = "";
        if (isTelegramApp()) {
            showMainButton("К товарам", () => navigateTo("/"));
        }
        return;
    }

    let total = 0;

    for (const key in cartRows) {
        const row = cartRows[key];
        const qty = state.cart[key] || 0;
        const price = parseFloat(row.priceDiv.dataset.unitPrice);
        total += price * qty;
    }

    const promoInput = getPromoInput();
    const typedCode = (promoInput?.value || "").trim();
    const promoData = loadPromoDataFromSession();

    const promoOk = promoData && promoData.code && promoData.code === typedCode;

    let discountPctNum = 0;
    let finalTotal = total;

    if (promoOk) {
        discountPctNum = parseFloat(String(promoData.discount_pct).replace(",", "."));
        if (!Number.isFinite(discountPctNum)) discountPctNum = 0;

        finalTotal = total * (100 - discountPctNum) / 100;
    }

    finalTotal = Math.round(finalTotal * 100) / 100;

    cartTotalEl.innerHTML = promoOk && discountPctNum > 0
        ? `
            <div class="total-line">
                <span class="total-label">Итого:</span>
                <span class="total-amount" style="text-decoration:line-through; opacity:.65;">
                    ${total.toLocaleString("ru-RU")} ₽
                </span>
            </div>
            <div class="total-line">
                <span class="total-label">Скидка:</span>
                <span class="total-amount">${discountPctNum}%</span>
            </div>
            <div class="total-line" style="margin-top:6px;">
                <span class="total-label">К оплате:</span>
                <span class="total-amount">${finalTotal.toLocaleString("ru-RU")} ₽</span>
            </div>
        `
        : `
            <span class="total-label">Итого:</span>
            <span class="total-amount">${total.toLocaleString("ru-RU")} ₽</span>
        `;

    if (isTelegramApp()) {
        const hasPromo = typedCode.length > 0;
        const needsApply = hasPromo && !promoOk;

        if (needsApply) {
            showMainButton("Применить промокод", () => applyPromocode());
        } else {
            showMainButton("Оформить заказ", () => handleCheckout());
        }
    }
}

function updateQuantity(key, delta) {
    state.cart[key] = (state.cart[key] || 0) + delta;

    if (state.cart[key] <= 0) {
        cartRows[key].row.remove();
        delete state.cart[key];
        delete cartRows[key];
    } else {
        const {qtySpan, priceDiv} = cartRows[key];
        qtySpan.textContent = state.cart[key];
        priceDiv.textContent =
            (parseFloat(priceDiv.dataset.unitPrice) * state.cart[key]).toLocaleString("ru-RU") + " ₽";
    }

    saveCart();

    if (!Object.keys(state.cart).length) {
        renderCart();
        return;
    }

    updateTotal();
}

/* =========================
   RENDER CART
   ========================= */
async function renderCart() {
    const keys = Object.keys(state.cart);
    cartItemsEl.innerHTML = "";
    cartRows = {};

    if (!keys.length) {
        cartItemsEl.innerHTML = `
            <div style="grid-column:1 / -1; text-align:center; padding:24px 12px;">
                <h2 style="margin-bottom:8px; font-size:18px;">Ваша корзина пуста</h2>
                <p style="margin:0; font-size:14px; color:#6b7280;">
                    Добавьте товары в корзину, чтобы оформить заказ.
                </p>
                <div
                    id="cart-empty-lottie"
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

        const animContainer = document.getElementById("cart-empty-lottie");
        if (animContainer && window.lottie && typeof window.lottie.loadAnimation === "function") {
            window.lottie.loadAnimation({
                container: animContainer,
                renderer: "svg",
                loop: true,
                autoplay: true,
                path: "/static/stickers/rabby-shop.json",
                rendererSettings: {preserveAspectRatio: "xMidYMid meet"},
            });
        }

        cartTotalEl.innerHTML = "";
        if (isTelegramApp()) showMainButton("К товарам", () => navigateTo("/"));
        return;
    }

    const products = await Promise.all(
        keys.map(async key => {
            const [onecId, featureId] = key.split("_");
            try {
                return await apiGet(`/cart/product/${onecId}?feature_id=${featureId || ""}`);
            } catch {
                return null;
            }
        }),
    );

    products.forEach((p, i) => {
        if (!p) return;

        const key = keys[i];
        const qty = state.cart[key] || 0;
        if (qty <= 0) return;

        const name = p.feature ? `${p.product.name} (${p.feature.name})` : p.product.name;
        const unitPrice = p.feature ? p.feature.price : p.product.price;

        const row = document.createElement("div");
        row.className = "cart-item";
        row.innerHTML = `
            <div class="cart-item-name">
                ${name}:
                <span class="cart-item-price" data-unit-price="${unitPrice}">
                    ${(unitPrice * qty).toLocaleString("ru-RU")} ₽
                </span>
            </div>
            <div class="cart-item-controls">
                <button class="minus">−</button>
                <span class="qty">${qty}</span>
                <button class="plus">+</button>
            </div>
        `;

        const minus = row.querySelector(".minus");
        const plus = row.querySelector(".plus");
        const qtySpan = row.querySelector(".qty");
        const priceDiv = row.querySelector(".cart-item-price");

        minus.onclick = () => updateQuantity(key, -1);
        plus.onclick = () => updateQuantity(key, 1);

        cartItemsEl.appendChild(row);
        cartRows[key] = {row, qtySpan, priceDiv, name};
    });

    updateTotal();
}

/* =========================
   PROMO INPUT WATCHER
   ========================= */
function setupPromoWatcher() {
    const promoInput = getPromoInput();
    if (!promoInput) return;

    // restore typed code
    const savedCode = loadPromocodeFromSession();
    if (savedCode && !promoInput.value) promoInput.value = savedCode;

    if (!promoInput.dataset.boundPromoInput) {
        promoInput.addEventListener("input", () => {
            savePromocodeToSession(promoInput.value);

            // if user edits code after applying, remove applied discount
            const data = loadPromoDataFromSession();
            const now = promoInput.value.trim();
            if (data && data.code && data.code !== now) {
                clearPromoDataFromSession();
            }

            if (!Object.keys(state.cart).length) return;
            updateTotal();
        });
        promoInput.dataset.boundPromoInput = "1";
    }

    if (Object.keys(state.cart).length) updateTotal();
}

/* =========================
   CHECKOUT
   ========================= */
export async function handleCheckout() {
    updateMainButton("Обработка…", true, true);

    const checkoutBtn = document.getElementById("checkout-btn");
    if (checkoutBtn) {
        checkoutBtn.disabled = true;
        checkoutBtn.textContent = "Обработка…";
    }

    try {
        const payload = Object.entries(state.cart).map(([key, qty]) => {
            const [id, featureId] = key.split("_");
            const itemName = cartRows[key]?.name || null;
            return {id, featureId: featureId || null, qty, name: itemName};
        });

        const promoCode = (loadPromocodeFromSession() || "").trim() || null;

        const data = await apiPost("/cart/json", {
            items: payload,
            promo_code: promoCode, // ✅ send to backend (ignore if backend doesn't use)
        });

        setCheckoutData(data);
        navigateTo("/checkout");
    } catch (err) {
        console.error(err);
    } finally {
        hideMainButton();
        if (checkoutBtn) {
            checkoutBtn.disabled = false;
            checkoutBtn.textContent = "Оформить заказ";
        }
    }
}

/* =========================
   PAGE ENTRYPOINT
   ========================= */
export async function renderCartPage() {
    toolbarEl.style.display = "none";
    listEl.style.display = "none";
    detailEl.style.display = "none";
    checkoutPageEl.style.display = "none";
    contactPageEl.style.display = "none";
    paymentPageEl.style.display = "none";
    processPaymentEl.style.display = "none";
    navBottomEl.style.display = "flex";
    profilePageEl.style.display = "none";
    cartPageEl.style.display = "block";
    headerTitle.textContent = "";
    searchBtnEl.style.display = "none";
    ordersPageEl.style.display = "none";
    orderDetailEl.style.display = "none";

    await withLoader(renderCart);
    setupPromoWatcher();

    if (isTelegramApp()) showBackButton();
}