import {
    cartPageEl,
    checkoutPageEl,
    contactPageEl, detailEl, headerTitle,
    listEl,
    navBottomEl,
    paymentPageEl, processPaymentEl,
    profilePageEl, searchBtnEl,
    toolbarEl
} from "./constants.js";

export function renderProfilePage() {
    profilePageEl.style.display = "block";
    navBottomEl.style.display = "flex";
    toolbarEl.style.display = "none";
    listEl.style.display = "none";
    contactPageEl.style.display = "none";
    cartPageEl.style.display = "none";
    checkoutPageEl.style.display = "none";
    paymentPageEl.style.display = "none";
    headerTitle.textContent = "";
    searchBtnEl.style.display = "none";
    detailEl.style.display = "none";
    processPaymentEl.style.display = "none";
}