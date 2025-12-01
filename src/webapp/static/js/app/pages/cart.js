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
    listEl,
    paymentPageEl,
    processPaymentEl,
    searchBtnEl,
    toolbarEl,
} from "./constants.js";

const cartTotalEl = document.getElementById("summary-label");
const cartItemsEl = document.getElementById("cart-items");

let cartRows = {};

function updateTotal() {
    let total = 0;

    for (const key in cartRows) {
        const row = cartRows[key];
        const qty = state.cart[key] || 0;
        const price = parseFloat(row.priceDiv.dataset.unitPrice);
        total += price * qty;
    }

    if (total === 0) {
        cartTotalEl.innerHTML = `
            <span class="total-label">Итого:</span>
            <span class="total-amount">0 ₽</span>
        `;
        showMainButton("К товарам", () => navigateTo("/"));
        return;
    }

    cartTotalEl.innerHTML = `
        <span class="total-label">Итого:</span>
        <span class="total-amount">${total.toLocaleString("ru-RU")} ₽</span>
    `;
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
    updateTotal();
}

// 🔽 UPDATED FUNCTION
async function renderCart() {
    const keys = Object.keys(state.cart);
    cartItemsEl.innerHTML = "";
    cartRows = {};

    if (!keys.length) {
        // пустая корзина
        cartItemsEl.innerHTML = `
            <div class="cart-empty" style="text-align:center; padding:24px 12px;">
                <h2 style="margin-bottom:8px; font-size:18px;">Ваша корзина пуста</h2>
                <p style="margin:0; font-size:14px; color:#6b7280;">
                    Добавьте товары в корзину, чтобы оформить заказ.
                </p>
                <img
                    src="/static/stickers/rabby-shop.json"
                    alt="Пустая корзина"
                    style="margin-top:16px; max-width:220px; width:100%; display:block; margin-left:auto; margin-right:auto; border-radius:12px;"
                />
            </div>
        `;

        // убираем блок "Итого"
        cartTotalEl.innerHTML = "";

        // прячем веб-кнопку оформления, если она есть
        const checkoutBtn = document.getElementById("checkout-btn");
        if (checkoutBtn) {
            checkoutBtn.style.display = "none";
        }

        // в Телеграме показываем кнопку "К товарам"
        if (isTelegramApp()) {
            showMainButton("К товарам", () => navigateTo("/"));
        }

        return;
    }

    // есть товары — убедимся, что блок суммы видимый (если ты его где-то скрываешь стилями)
    // cartTotalEl.style.display = "";

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

export async function handleCheckout() {
    const checkoutBtn = document.getElementById("checkout-btn");
    updateMainButton("Обработка…", true, true);

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

export async function renderCartPage() {
    toolbarEl.style.display = "none";
    listEl.style.display = "none";
    detailEl.style.display = "none";
    checkoutPageEl.style.display = "none";
    contactPageEl.style.display = "none";
    paymentPageEl.style.display = "none";
    processPaymentEl.style.display = "none";

    cartPageEl.style.display = "block";
    headerTitle.textContent = "Корзина";
    searchBtnEl.style.display = "flex";

    await withLoader(renderCart);

    if (isTelegramApp()) {
        showBackButton(() => navigateTo("/"));
        showMainButton("Оформить заказ", () => handleCheckout());
    } else {
        let btn = document.getElementById("checkout-btn");
        if (!btn) {
            btn = document.createElement("button");
            btn.id = "checkout-btn";
            btn.textContent = "Оформить заказ";
            btn.className = "checkout-btn";
            cartPageEl.appendChild(btn);
        }
        btn.style.display = "block";
        btn.onclick = handleCheckout;
    }
}