// app/ui/cart-icon.js
import { state } from "../state.js";
import { navigateTo } from "../router.js";

let cartIcon = null;
let badge = null;

/**
 * Create or update the floating cart icon
 */
export function createCartIcon() {
  if (cartIcon) return cartIcon; // already exists

  cartIcon = document.createElement("div");
  cartIcon.id = "cart-icon";
  cartIcon.textContent = "🛒";
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