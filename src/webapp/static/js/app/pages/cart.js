import {withLoader} from "../ui/loader.js";
import {state, saveCart, setCheckoutData} from "../state.js";
import {navigateTo} from "../router.js";
import {apiPost, apiGet} from "../../services/api.js";
import {
    hideMainButton,
    showBackButton,
    isTelegramApp,
    showMainButton, updateMainButton,
} from "../ui/telegram.js";
import {hideCartIcon} from "../ui/cart-icon.js";

const listEl = document.getElementById("product-list");
const detailEl = document.getElementById("product-detail");
const checkoutEl = document.getElementById("checkout-page");
const contactPageEl = document.getElementById("contact-page");
const headerTitle = document.getElementById("header-left");
const toolbarEl = document.getElementById("toolbar");

const cartPageEl = document.getElementById("cart-page");
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

    cartTotalEl.innerHTML = `
    <span class="total-label">Итого:</span>
    <span class="total-amount">${total.toLocaleString("ru-RU")} ₽</span>
  `;
    if (total === 0) showMainButton("К товарам", () => navigateTo("/"));
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

async function renderCart() {
    const keys = Object.keys(state.cart);
    cartItemsEl.innerHTML = "";
    cartRows = {};

    if (!keys.length) {
        cartItemsEl.innerHTML = "<p>Корзина пуста</p>";
        cartTotalEl.textContent = "0 ₽";
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
        cartRows[key] = {row, qtySpan, priceDiv};
    });

    updateTotal();
}

export async function handleCheckout() {
    const checkoutBtn = document.getElementById("checkout-btn");
    updateMainButton("Обработка…", true, true)

    if (checkoutBtn) {
        checkoutBtn.disabled = true;
        checkoutBtn.textContent = "Обработка…";
    }

    try {
        const payload = Object.entries(state.cart).map(([key, qty]) => {
            const [id, featureId] = key.split("_");
            return {id, featureId: featureId || null, qty};
        });

        const data = await apiPost("/cart/json", {items: payload});
        setCheckoutData(data);
        navigateTo("/checkout");
    } catch (err) {
        console.error("Checkout failed:", err);
        alert("Ошибка при оформлении заказа. Попробуйте ещё раз.");
    } finally {
        updateMainButton('x', false, false)
        hideMainButton();
        if (checkoutBtn) {
            checkoutBtn.disabled = false;
            checkoutBtn.textContent = "Оформить заказ";
        }
    }
}

export async function renderCartPage() {
    hideCartIcon();
    toolbarEl.style.display = "none";
    listEl.style.display = "none";
    detailEl.style.display = "none";
    cartPageEl.style.display = "block";
    headerTitle.textContent = "Корзина";
    checkoutEl.style.display = "none";
    contactPageEl.style.display = "none";

    await withLoader(renderCart);

    if (isTelegramApp()) {
        showBackButton(() => {
            navigateTo("/");
        });

        showMainButton('Оформить заказ', () => handleCheckout());
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

    updateTotal();
}
