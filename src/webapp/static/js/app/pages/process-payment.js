import {hideCartIcon} from "../ui/cart-icon.js";
import {showLoader} from "../ui/loader.js";
import {
    cartPageEl,
    checkoutPageEl,
    contactPageEl, detailEl,
    headerTitle, listEl,
    paymentPageEl,
    processPaymentEl,
    searchBtnEl,
    toolbarEl
} from "./constants.js";

export async function renderProcessPaymentPage() {
    showLoader();
    hideCartIcon();
    toolbarEl.style.display = "none";
    listEl.style.display = "none";
    detailEl.style.display = "none";
    cartPageEl.style.display = "none";
    headerTitle.textContent = "Оплата";
    checkoutPageEl.style.display = "none";
    contactPageEl.style.display = "none";
    paymentPageEl.style.display = "none";
    searchBtnEl.style.display = "none";
    processPaymentEl.style.display = "block";

}