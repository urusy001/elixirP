import {
    cartPageEl, checkoutPageEl, contactPageEl,
    detailEl,
    headerTitle,
    listEl,
    navBottomEl, orderDetailEl, ordersPageEl, paymentPageEl, processPaymentEl, profilePageEl,
    searchBtnEl,
    toolbarEl,
    tosOverlayEl
} from "./constants.js";
import {state} from "../state.js";

export function renderOrdersPage() {
    navBottomEl.style.display = "flex";
    headerTitle.textContent = "Магазин ElixirPeptide";
    tosOverlayEl.style.display = "none";
    listEl.style.display = "none";
    toolbarEl.style.display = "none";
    searchBtnEl.style.display = "none";
    detailEl.style.display = "none";
    cartPageEl.style.display = "none";
    checkoutPageEl.style.display = "none";
    contactPageEl.style.display = "none";
    paymentPageEl.style.display = "none";
    processPaymentEl.style.display = "none";
    profilePageEl.style.display = "none";
    ordersPageEl.style.display = "block";
    orderDetailEl.style.display = "none";
    getUserCarts();

}

function getUserCarts() {
    const user = state.user
    if (user) {
        alert(JSON.stringify(user))
    } else {
        alert('nouser')
    }
}
