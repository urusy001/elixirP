// cart-badge.js
// Отвечает за бейдж на иконке корзины в bottom-nav

import { state } from "../state.js";

/**
 * Считает общее количество товаров в корзине.
 * state.cart имеет структуру: { "onecId_featureId": quantity }
 */
export function getCartItemCount(cart = state.cart) {
    if (!cart) return 0;
    let total = 0;
    if (typeof cart === "object") {
        for (const value of Object.values(cart)) {
            const qty = Number(value);
            if (Number.isFinite(qty) && qty > 0) {
                total += qty;
            }
        }
    }

    return total;
}

/**
 * Обновляет текст и видимость бейджа на иконке корзины.
 * Ожидает элемент с id="cart-badge" в разметке.
 */
export function updateCartBadge() {
    const badge = document.getElementById("cart-badge");
    if (!badge) return;

    const count = getCartItemCount();

    if (!count || count <= 0) {
        badge.classList.add("bottom-nav__badge--hidden");
        return;
    }

    const displayValue = count > 99 ? "99+" : String(count);
    badge.textContent = displayValue;
    badge.classList.remove("bottom-nav__badge--hidden");
}

let cartBadgeInitialized = false;

/**
 * Инициализация бейджа:
 *  - подписывается на событие `cart:updated` (вызывается из saveCart())
 *  - один раз обновляет бейдж при старте
 */
export function initCartBadge() {
    if (cartBadgeInitialized) return;
    cartBadgeInitialized = true;

    // Реакция на изменения корзины
    window.addEventListener("cart:updated", () => {
        updateCartBadge();
    });

    // При инициализации подтягиваем корзину из state.cart
    updateCartBadge();
}
