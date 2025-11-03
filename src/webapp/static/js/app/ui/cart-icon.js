import { navigateTo } from "../router.js";

let cartIcon = null;
let badge = null;

/* -----------------------------------------------------------
   Smooth FAB animations (injected once)
----------------------------------------------------------- */
function ensureCartIconStyles() {
    if (document.getElementById("cart-fab-anim-styles")) return;
    const style = document.createElement("style");
    style.id = "cart-fab-anim-styles";
    style.textContent = `
    /* Smooth show/hide for the cart FAB */
    #cart-icon{
      opacity: 0;
      transform: translateY(8px) scale(.98);
      visibility: hidden;
      transition:
        opacity .18s ease,
        transform .18s ease,
        visibility 0s linear .18s; /* delay visibility toggle so fade-out can play */
    }
    #cart-icon.is-visible{
      opacity: 1;
      transform: translateY(0) scale(1);
      visibility: visible;
      transition:
        opacity .18s ease,
        transform .18s ease,
        visibility 0s; /* immediate once visible */
    }
  `;
    document.head.appendChild(style);
}

/* -----------------------------------------------------------
   Create (once) the floating cart icon
----------------------------------------------------------- */
export function createCartIcon() {
    ensureCartIconStyles();

    cartIcon = document.getElementById("cart-icon");
    if (!cartIcon) {
        cartIcon = document.createElement("div");
        cartIcon.id = "cart-icon";
        cartIcon.setAttribute("aria-label", "Open cart");
        cartIcon.textContent = "🛒";
        document.body.appendChild(cartIcon);
    }

    // Ensure badge exists
    badge = cartIcon.querySelector(".cart-count");
    if (!badge) {
        badge = document.createElement("span");
        badge.className = "cart-count";
        cartIcon.appendChild(badge);
    }

    updateCartIconCount();
    return cartIcon;
}

/* -----------------------------------------------------------
   Helpers to read cart totals
----------------------------------------------------------- */
function getCartTotal() {
    const s = (window.state && window.state.cart) || null;
    const cart = s ?? JSON.parse(localStorage.getItem("cart") || "{}");
    return Object.values(cart).reduce((a, n) => a + Number(n || 0), 0);
}
function hasItems() {
    return getCartTotal() > 0;
}

/* -----------------------------------------------------------
   Update badge + enabled/disabled visual state
----------------------------------------------------------- */
export function updateCartIconCount(e) {
    if (!cartIcon) cartIcon = document.getElementById("cart-icon");
    if (!badge && cartIcon) badge = cartIcon.querySelector(".cart-count");
    if (!badge || !cartIcon) return;

    const total = getCartTotal();

    // Badge content/visibility
    if (total > 0) {
        badge.textContent = String(total);
        badge.classList.add("show");
    } else {
        badge.textContent = "";
        badge.classList.remove("show");
    }

    // Interactivity & subtle dim when empty (but keep visible if shown)
    const enabled = total > 0;
    cartIcon.setAttribute("aria-disabled", String(!enabled));
    cartIcon.dataset.disabled = String(!enabled);
    cartIcon.style.pointerEvents = enabled ? "auto" : "none";
    cartIcon.style.cursor = enabled ? "pointer" : "default";
    // Keep a slight dim when empty (do not hide completely)
    cartIcon.style.opacity = cartIcon.classList.contains("is-visible")
        ? (enabled ? "1" : "0")
        : cartIcon.style.opacity;
    cartIcon.title = enabled ? "Открыть корзину" : "Корзина пуста";
}

/* -----------------------------------------------------------
   Smooth show/hide API
----------------------------------------------------------- */
export function showCartIcon() {
    cartIcon = document.getElementById("cart-icon") || createCartIcon();
    // Add visible class to trigger CSS transition
    cartIcon.classList.add("is-visible");
    // Set interactivity/opacity according to items
    const enabled = hasItems();
    cartIcon.style.pointerEvents = enabled ? "auto" : "none";
    cartIcon.style.cursor = enabled ? "pointer" : "default";
    cartIcon.style.opacity = enabled ? "1" : "0";
}

export function hideCartIcon() {
    cartIcon = document.getElementById("cart-icon");
    if (!cartIcon) return;
    // Remove visible class to fade/slide out
    cartIcon.classList.remove("is-visible");
    // Also prevent clicks during the fade-out
    cartIcon.style.pointerEvents = "none";
}

/* -----------------------------------------------------------
   Init
----------------------------------------------------------- */
export function initCartIcon() {
    // Ensure the icon & badge exist before binding
    createCartIcon();

    // Prevent duplicate listeners, then bind
    window.removeEventListener("cart:updated", updateCartIconCount);
    window.addEventListener("cart:updated", updateCartIconCount);

    // Click only works when cart has items
    cartIcon.onclick = (e) => {
        if (!hasItems()) {
            e.preventDefault();
            e.stopPropagation();
            return;
        }
        navigateTo("/cart");
    };

    // Initial render from current state
    updateCartIconCount();
}