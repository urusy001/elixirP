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
    listEl, navBottomEl,
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

// === TOTAL & QTY HANDLING ===
function updateTotal() {
    const keys = Object.keys(state.cart);

    // если в корзине вообще нет ключей — показываем "К товарам"
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

    cartTotalEl.innerHTML = `
        <span class="total-label">Итого:</span>
        <span class="total-amount">${total.toLocaleString("ru-RU")} ₽</span>
    `;

    if (isTelegramApp()) {
        const promoInput = getPromoInput();
        const hasPromo = promoInput && promoInput.value.trim().length > 0;
        alert(JSON.stringify(hasPromo));

        if (hasPromo) {
            showMainButton("Применить промокод", () => {
                alert("промокоды скоро станут доступны");
            });
        } else {
            // 🔹 Обычное поведение — оформление заказа
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

    // если после изменения корзина стала пустой — перерисуем страницу
    if (!Object.keys(state.cart).length) {
        renderCart();
        return;
    }

    updateTotal();
}

// === RENDER CART (WITH RABBY-SHOP LOTTIE) ===
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

        // лотти-анимация rabby-shop.json
        const animContainer = document.getElementById("cart-empty-lottie");
        if (animContainer && window.lottie && typeof window.lottie.loadAnimation === "function") {
            window.lottie.loadAnimation({
                container: animContainer,
                renderer: "svg",
                loop: true,
                autoplay: true,
                path: "/static/stickers/rabby-shop.json",
                rendererSettings: {
                    preserveAspectRatio: "xMidYMid meet",
                },
            });
        }

        // убираем "Итого" и ставим кнопку "К товарам"
        cartTotalEl.innerHTML = "";
        if (isTelegramApp()) {
            showMainButton("К товарам", () => navigateTo("/"));
        }

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

    // посчитаем сумму и поставим правильную кнопку
    updateTotal();
}

// === PROMO INPUT WATCHER ===
function setupPromoWatcher() {
    const promoInput = getPromoInput();
    if (!promoInput) return;

    if (!promoInput.dataset.boundPromoInput) {
        promoInput.addEventListener("input", () => {
            if (!Object.keys(state.cart).length) return;
            updateTotal();
        });
        promoInput.dataset.boundPromoInput = "1";
    }

    // при первой отрисовке тоже обновим кнопку
    if (Object.keys(state.cart).length) {
        updateTotal();
    }
}

// === CHECKOUT ===
export async function handleCheckout() {
    updateMainButton("Обработка…", true, true);

    // на всякий случай оставляю поддержку checkout-btn
    const checkoutBtn = document.getElementById("checkout-btn");
    if (checkoutBtn) {
        checkoutBtn.disabled = true;
        checkoutBtn.textContent = "Обработка…";
    }

    try {
        const payload = Object.entries(state.cart).map(([key, qty]) => {
            const [id, featureId] = key.split("_");
            const itemName = cartRows[key]?.name || null;
            return {
                id,
                featureId: featureId || null,
                qty,
                name: itemName,
            };
        });

        const data = await apiPost("/cart/json", {items: payload});
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

// === PAGE ENTRYPOINT ===
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

    await withLoader(renderCart);

    // вот тут вешаем реакцию на промокод
    setupPromoWatcher();

    if (isTelegramApp()) showBackButton();
}