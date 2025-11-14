import { showLoader, hideLoader } from "../ui/loader.js";
import { hideCartIcon } from "../ui/cart-icon.js";
import { navigateTo } from "../router.js";
import { state } from "../state.js";
import { isTelegramApp, showMainButton, updateMainButton, showBackButton } from "../ui/telegram.js";

const checkoutPageEl = document.getElementById("checkout-page");
const listEl = document.getElementById("product-list");
const detailEl = document.getElementById("product-detail");
const cartPageEl = document.getElementById("cart-page");
const contactPageEl = document.getElementById("contact-page");
const headerTitle = document.getElementById("header-left");
const toolbarEl = document.getElementById("toolbar");
const searchBtnEl = document.getElementById("search-btn");
const paymentPageEl = document.getElementById("payment-page");
const contactPage = document.getElementById("contact-page");
const form = document.getElementById("contact-form");

export async function renderContactPage() {
    if (!checkoutPageEl || !contactPage || !form) return;

    // Only run in Telegram
    if (!isTelegramApp()) {
        console.warn("[contact] Not in Telegram WebApp.");
        return;
    }

    hideCartIcon();
    cartPageEl && (cartPageEl.style.display = "none");
    detailEl && (detailEl.style.display = "none");
    listEl && (listEl.style.display = "none");
    toolbarEl && (toolbarEl.style.display = "none");
    contactPageEl && (contactPageEl.style.display = "none");
    headerTitle && (headerTitle.textContent = "Контактная информация");
    checkoutPageEl && (checkoutPageEl.style.display = "none");
    searchBtnEl && (searchBtnEl.style.display = "none");
    paymentPageEl && (paymentPageEl.style.display = "none");
    contactPage.style.display = "block";

    // Prevent default submit/enter
    form.addEventListener("submit", (e) => e.preventDefault());
    form.addEventListener("keydown", (e) => { if (e.key === "Enter") e.preventDefault(); });

    const tg = state.telegram;
    const user_id = tg?.initDataUnsafe?.user?.id ?? null;

    // ---------- Helpers ----------
    function hasCompleteProfile(u) {
        return Boolean(u?.name && u?.surname && u?.email && u?.phone);
    }

    function prefillFormFromUser(u) {
        const map = { name: "name", surname: "surname", email: "email", phone: "phone" };
        Object.entries(map).forEach(([k, input]) => {
            const el = form.querySelector(`[name="${input}"]`);
            if (el && u?.[k]) el.value = u[k];
        });
    }

    async function fetchUserModel(uid) {
        if (!uid) return null;
        try {
            showLoader();
            const url = `/users?column_name=tg_id&value=${encodeURIComponent(String(uid))}`;
            const res = await fetch(url, { method: "GET", headers: { Accept: "application/json" } });
            if (!res.ok) return null;
            const arr = await res.json(); // List[UserRead]
            return Array.isArray(arr) && arr.length ? arr[0] : null;
        } catch {
            return null;
        } finally {
            hideLoader();
        }
    }

    // 💾 save contact info (called from MainButton)
    function saveContactInfo(contact_info) {
        sessionStorage.setItem("contact_info", JSON.stringify(contact_info));
        // also nice to keep user_id here if you want it later
        if (user_id) sessionStorage.setItem("tg_user_id", String(user_id));
    }

    async function handleSubmit() {
        const formData = Object.fromEntries(new FormData(form).entries());
        saveContactInfo(formData);
        navigateTo("/payment"); // 👉 go to payment page, no POST yet
    }

    showMainButton("Продолжить", handleSubmit);
    showBackButton(() => navigateTo("/checkout"));

    // ---------- Prefill / auto-skip ----------
    let userModel = null;
    if (user_id) {
        userModel = await fetchUserModel(user_id);
    }

    if (userModel && hasCompleteProfile(userModel)) {
        // If we already know everything – save & jump straight to payment page
        const contact_info = {
            name: userModel.name,
            surname: userModel.surname,
            email: userModel.email,
            phone: userModel.phone,
        };

        saveContactInfo(contact_info);
        navigateTo("/payment");
    } else if (userModel) {
        prefillFormFromUser(userModel);
    }
}