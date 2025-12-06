import {
    cartPageEl,
    checkoutPageEl,
    contactPageEl,
    detailEl,
    headerTitle,
    listEl,
    navBottomEl,
    paymentPageEl,
    processPaymentEl,
    profilePageEl,
    searchBtnEl,
    toolbarEl
} from "./constants.js";
import {state} from "../state.js";
import {showLoader} from "../ui/loader";

export function renderProfilePage() {
    showLoader()
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

    const profileAvatarEl = document.getElementById("profile-avatar");
    const profileNameEl = document.getElementById("profile-name");
    const user = state.telegram.initDataUnsafe.user
    alert(JSON.stringify(user));
    profileNameEl.textContent = `${user.first_name} ${user.last_name}`;
    profileAvatarEl.src = user.photo_url
}