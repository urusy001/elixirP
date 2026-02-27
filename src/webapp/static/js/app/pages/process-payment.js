import { launchConfettiBurst, showBackButton, showMainButton } from "../ui/telegram.js";
import {
    cartPageEl,
    checkoutPageEl,
    contactPageEl, detailEl,
    headerTitle, listEl, navBottomEl,
    paymentPageEl,
    processPaymentEl, profilePageEl,
    searchBtnEl,
    toolbarEl
} from "./constants.js";
import { navigateTo } from "../router.js";

export async function renderProcessPaymentPage(order_number) {

    toolbarEl.style.display = "none";
    listEl.style.display = "none";
    detailEl.style.display = "none";
    cartPageEl.style.display = "none";
    checkoutPageEl.style.display = "none";
    contactPageEl.style.display = "none";
    paymentPageEl.style.display = "none";
    processPaymentEl.style.display = "block";
    profilePageEl.style.display = "none";

    headerTitle.textContent = `Номер заказа ${order_number ?? "—"}`;
    searchBtnEl.style.display = "flex";
    navBottomEl.style.display = "none";

    try {
        window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
    } catch (_) {
        window.scrollTo(0, 0);
    }

    const lottieContainer = processPaymentEl.querySelector("#order-lottie");

    if (lottieContainer && typeof window !== "undefined" && window.lottie && !lottieContainer._lottieInited) {
        lottieContainer._lottieInited = true;

        window.lottie.loadAnimation({
            container: lottieContainer,
            renderer: "svg",
            loop: false,
            autoplay: true,
            path: "/static/stickers/cherry-congrats.json",
        });
    }

    try {
        launchConfettiBurst && launchConfettiBurst();
    } catch (e) {
        console.warn("Confetti error:", e);
    }

    showMainButton("В главное меню", () => navigateTo("/"));
    showBackButton(() => navigateTo("/"));
}
