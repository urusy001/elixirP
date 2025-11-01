// app/ui/cart-icon.js
import {state} from "../state.js?v=1";
import {navigateTo} from "../router.js?v=1";

let cartIcon = null;
let badge = null;

/**
 * Create or update the floating cart icon
 */
export function createCartIcon() {
    if (cartIcon) return cartIcon; // already exists

    cartIcon = document.createElement("div");
    cartIcon.id = "cart-icon";
    Object.assign(cartIcon.style, {
        position: "fixed",
        bottom: "32px",
        right: "32px",
        width: "60px",
        height: "60px",
        borderRadius: "50%",
        background: "#1E669E",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        cursor: "pointer",
        boxShadow: "0 2px 6px rgba(0,0,0,0.2)",
        zIndex: "9999",
        color: "#fff",
        fontSize: "1.5rem",
    });

    cartIcon.textContent = "🛒";
    cartIcon.addEventListener("click", () => navigateTo("/cart"));
    document.body.appendChild(cartIcon);

    badge = document.createElement("span");
    badge.className = "cart-count";
    Object.assign(badge.style, {
        position: "absolute",
        top: "-4px",
        right: "-4px",
        background: "red",
        color: "white",
        fontSize: "0.7rem",
        width: "18px",
        height: "18px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: "50%",
    });
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