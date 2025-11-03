import { withLoader } from "../ui/loader.js?v=1";
import { saveCart, setCheckoutData, state } from "../state.js?v=1";
import { navigateTo } from "../router.js?v=1";
import { apiGet, apiPost } from "../../services/api.js?v=1";
import {
    hideBackButton,
    hideMainButton,
    isTelegramApp,
    showBackButton,
    showMainButton,
    updateMainButton,
} from "../ui/telegram.js?v=1";
import { hideCartIcon, showCartIcon } from "../ui/cart-icon.js?v=1";

const productListEl = document.getElementById("product-list");
const productDetailEl = document.getElementById("product-detail");
const cartPageEl = document.getElementById("cart-page");
const cartItemsEl = document.getElementById("cart-items");
const cartTotalEl = document.getElementById("summary-label");
const toolbarEl = document.querySelector(".toolbar");

let cartRows = {};

/* -------------------------------------------------------------------------- */
/*                               UTIL FUNCTIONS                               */
/* -------------------------------------------------------------------------- */

function updateTotal() {
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
}

function updateQuantity(key, delta) {
    state.cart[key] = (state.cart[key] || 0) + delta;

    if (state.cart[key] <= 0) {
        cartRows[key].row.remove();
        delete state.cart[key];
        delete cartRows[key];
    } else {
        const { qtySpan, priceDiv } = cartRows[key];
        qtySpan.textContent = state.cart[key];
        priceDiv.textContent =
            (parseFloat(priceDiv.dataset.unitPrice) * state.cart[key]).toLocaleString("ru-RU") + " ₽";
    }

    saveCart();
    updateTotal();
    window.dispatchEvent(new CustomEvent("cart:updated"));
}

/* -------------------------------------------------------------------------- */
/*                              RENDER CART ITEMS                             */
/* -------------------------------------------------------------------------- */

async function renderCart() {
    const keys = Object.keys(state.cart);
    cartItemsEl.innerHTML = "";
    cartRows = {};

    if (!keys.length) {
        cartItemsEl.innerHTML = "<p>Корзина пуста</p>";
        cartTotalEl.innerHTML = `
      <span class="total-label">Итого:</span>
      <span class="total-amount">0 ₽</span>`;
        updateMainButton("Пустая корзина", false, true);
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
        })
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
        cartRows[key] = { row, qtySpan, priceDiv };
    });

    updateTotal();
}

/* -------------------------------------------------------------------------- */
/*                                CHECKOUT FLOW                               */
/* -------------------------------------------------------------------------- */

export async function handleCheckout() {
    const tg = state.telegram;
    if (!tg?.MainButton) return;

    updateMainButton("Обработка…", true, true);

    try {
        const payload = Object.entries(state.cart).map(([key, qty]) => {
            const [id, featureId] = key.split("_");
            return { id, featureId: featureId || null, qty };
        });

        const data = await apiPost("/cart/json", { items: payload });
        setCheckoutData(data);

        cartPageEl.style.display = "none";
        navigateTo("/checkout");
    } catch (err) {
        console.error("Checkout failed:", err);
        alert("Ошибка при оформлении заказа. Попробуйте ещё раз.");
    } finally {
        updateMainButton("Оформить заказ", false, false);
    }
}

/* -------------------------------------------------------------------------- */
/*                                  CART PAGE                                 */
/* -------------------------------------------------------------------------- */

export async function renderCartPage() {
    if (!isTelegramApp()) {
        console.error("Cart page is Telegram-only now.");
        return;
    }

    // Hide all others
    hideCartIcon();
    toolbarEl.classList.add("hidden");
    productListEl.style.display = "none";
    productDetailEl.style.display = "none";
    cartPageEl.style.display = "block";

    await withLoader(renderCart);

    const tg = state.telegram;

    showBackButton(() => {
        navigateTo("/");
        hideMainButton();
        showCartIcon();
        hideBackButton();
    });

    showMainButton("Оформить заказ", handleCheckout);

    updateTotal();
}