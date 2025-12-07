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
import {hideLoader, showLoader} from "../ui/loader.js";
import {hideMainButton, openTgLink, showBackButton} from "../ui/telegram.js";

export function renderProfilePage() {
    showLoader();
    showBackButton();
    hideMainButton();
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
    const user = state.telegram.initDataUnsafe.user;
    const supportButton = document.getElementById("support-button");
    supportButton.addEventListener("click", () => {
        openTgLink("/ShostakovIV")
    })
    profileNameEl.textContent = `${user.first_name} ${user.last_name}`;
    profileAvatarEl.src = user.photo_url;
    hideLoader();
}