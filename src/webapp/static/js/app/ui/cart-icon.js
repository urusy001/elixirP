// app/ui/cart-icon.js
import { state } from "../state.js";
import { navigateTo } from "../router.js";

// Simple outline cart icon (white / currentColor)
const CART_SVG = `
<svg
  class="cart-icon"
  xmlns="http://www.w3.org/2000/svg"
  viewBox="0 0 24 24"
  aria-hidden="true"
  fill="currentColor"
>
  <path
    d="M7 18c-1.1 0-1.99.9-1.99 2S5.9 22 7 22s2-.9 2-2-.9-2-2-2zM1 2v2h2l3.6 7.59-1.35 2.45c-.16.28-.25.61-.25.96 0 1.1.9 2 2 2h12v-2H7.42c-.14 0-.25-.11-.25-.25l.03-.12.9-1.63h7.45c.75 0 1.41-.41 1.75-1.03l3.58-6.49c.08-.14.12-.31.12-.48 0-.55-.45-1-1-1H5.21l-.94-2H1zm16 16c-1.1 0-1.99.9-1.99 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"
  />
</svg>`;
let cartIcon = null;
let badge = null;

/**
 * Create or update the floating cart icon
 */
export function createCartIcon() {
    if (cartIcon) return cartIcon; // already exists

    cartIcon = document.createElement("div");
    cartIcon.id = "cart-icon";
    cartIcon.innerHTML = CART_SVG;             // ⬅️ use SVG instead of emoji
    cartIcon.addEventListener("click", () => navigateTo("/cart"));
    document.body.appendChild(cartIcon);

    badge = document.createElement("span");
    badge.className = "cart-count";
    cartIcon.appendChild(badge);

    updateCartIconCount();
    return cartIcon;
}

/**
 * Update badge count based on state.cart
 */
export function updateCartIconCount() {
    if (!badge) return;
    const total = Object.values(state.cart).reduce((a, b) => a + b, 0);
    badge.textContent = total > 0 ? total : "";
}

/**
 * Show / hide control
 */
export function showCartIcon() {
    if (!cartIcon) createCartIcon();
    cartIcon.style.opacity = "1";
    cartIcon.style.pointerEvents = "auto";
    cartIcon.style.display = "flex";
}

export function hideCartIcon() {
    if (!cartIcon) return;
    cartIcon.style.opacity = "0";
    cartIcon.style.pointerEvents = "none";
    cartIcon.style.display = "none";
}

/**
 * Listen for cart updates
 */
export function initCartIcon() {
    createCartIcon();
    window.addEventListener("cart:updated", updateCartIconCount);
    updateCartIconCount();
}