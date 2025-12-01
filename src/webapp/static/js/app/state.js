const persistedCart = JSON.parse(localStorage.getItem("cart") || "{}");

export const state = {
    user: null,
    cart: persistedCart,
    checkout: JSON.parse(sessionStorage.getItem("checkout_data") || "null"),
    delivery: JSON.parse(sessionStorage.getItem("selected_delivery") || "null"),
    deliveryService: sessionStorage.getItem("selected_delivery_service") || null,
    contact: JSON.parse(sessionStorage.getItem("yookassa_contact_info") || "null"),
    telegram: (typeof window !== "undefined" && window.Telegram?.WebApp) || null,
};

export function saveCart() {
    localStorage.setItem("cart", JSON.stringify(state.cart));
    dispatchEvent(new CustomEvent("cart:updated"));
}

export function setCheckoutData(data) {
    state.checkout = data;
    sessionStorage.setItem("checkout_data", JSON.stringify(data));
}

export function setDelivery(data) {
    state.delivery = data;
    sessionStorage.setItem("selected_delivery", JSON.stringify(data));
}

export function setDeliveryService(name) {
    state.deliveryService = name;
    sessionStorage.setItem("selected_delivery_service", name);
}

export function setContactInfo(data) {
    state.contact = data;
    sessionStorage.setItem("yookassa_contact_info", JSON.stringify(data));
}