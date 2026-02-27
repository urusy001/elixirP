import { showLoader, hideLoader } from "../ui/loader.js";
import { state, saveCart } from "../state.js";
import {
    isTelegramApp,
    showMainButton,
    showBackButton,
    hideMainButton,
} from "../ui/telegram.js";
import {
    cartPageEl,
    checkoutPageEl,
    contactPageEl,
    detailEl,
    headerTitle,
    listEl,
    navBottomEl,
    orderDetailEl,
    ordersPageEl,
    paymentPageEl,
    processPaymentEl,
    profilePageEl,
    searchBtnEl,
    toolbarEl,
} from "./constants.js";
import { apiGet, apiPost } from "../../services/api.js";
import { renderProcessPaymentPage } from "./process-payment.js";

const form = document.getElementById("contact-form");

export async function renderContactPage() {
    if (!checkoutPageEl || !contactPageEl || !form) return;

    if (!isTelegramApp()) {
        console.warn("[contact] Not in Telegram WebApp.");
        return;
    }

    cartPageEl.style.display = "none";
    detailEl.style.display = "none";
    listEl.style.display = "none";
    toolbarEl.style.display = "none";
    checkoutPageEl.style.display = "none";
    contactPageEl.style.display = "none";
    paymentPageEl && (paymentPageEl.style.display = "none");
    processPaymentEl.style.display = "none";
    profilePageEl.style.display = "none";
    ordersPageEl.style.display = "none";
    orderDetailEl.style.display = "none";

    headerTitle.textContent = "Оформление заказа";
    searchBtnEl.style.display = "none";

    navBottomEl.style.display = "none";

    contactPageEl.style.display = "block";

    form.addEventListener("submit", (e) => e.preventDefault());
    form.addEventListener("keydown", (e) => {
        if (e.key === "Enter") e.preventDefault();
    });

    const tg = state.telegram;
    const user_id = tg?.initDataUnsafe?.user?.id ?? null;

    const nameInput = form.querySelector('[name="name"]');
    const surnameInput = form.querySelector('[name="surname"]');
    const emailInput = form.querySelector('[name="email"]');
    const phoneInput = form.querySelector('[name="phone"]');
    const commentaryInput = form.querySelector("#payment-commentary-input");

    function ensureErrorEl(input) {
        if (!input) return null;
        if (input._errorEl) return input._errorEl;

        const err = document.createElement("div");
        err.className = "field-error";
        input.insertAdjacentElement("afterend", err);
        input._errorEl = err;
        return err;
    }

    const nameErrorEl = ensureErrorEl(nameInput);
    const surnameErrorEl = ensureErrorEl(surnameInput);
    const emailErrorEl = ensureErrorEl(emailInput);
    const phoneErrorEl = ensureErrorEl(phoneInput);

    function clearError(input, errEl) {
        if (!input || !errEl) return;
        input.classList.remove("input-error");
        errEl.textContent = "";
    }

    function setError(input, errEl, message) {
        if (!input || !errEl) return;
        input.classList.add("input-error");
        errEl.textContent = message;
    }

    function hasCompleteProfile(u) {
        return Boolean(u?.name && u?.surname && u?.email && u?.phone);
    }

    function prefillFormFromUser(u) {
        const map = {name: "name", surname: "surname", email: "email", phone: "phone"};
        Object.entries(map).forEach(([k, inputName]) => {
            const el = form.querySelector(`[name="${inputName}"]`);
            if (el && u?.[k]) el.value = u[k];
        });
    }

    async function fetchUserModel(uid) {
        if (!uid) return null;
        try {
            showLoader();
            const url = `/users?column_name=tg_id&value=${encodeURIComponent(String(uid))}`;
            const res = await apiGet(url);
            return res;
        } catch {
            return null;
        } finally {
            hideLoader();
        }
    }

    function saveContactInfo(contact_info) {
        sessionStorage.setItem("contact_info", JSON.stringify(contact_info));
        if (user_id) sessionStorage.setItem("tg_user_id", String(user_id));
    }

    function clearCartAfterOrder() {
        state.cart = {};
        saveCart();
    }

    async function handleSubmit() {
        if (!validateForm()) return;

        const formData = Object.fromEntries(new FormData(form).entries());
        saveContactInfo(formData);

        try {
            showLoader();

            const tg = state.telegram;
            const user_id_from_storage = sessionStorage.getItem("tg_user_id");
            const user_id_final =
                user_id_from_storage ||
                (tg?.initDataUnsafe?.user?.id != null
                    ? String(tg.initDataUnsafe.user.id)
                    : null);

            const contact_info = formData;
            const checkout_data = JSON.parse(sessionStorage.getItem("checkout_data") || "null");
            const promocode = JSON.parse(sessionStorage.getItem("promocode") || "null");
            let selected_delivery = JSON.parse(sessionStorage.getItem("selected_delivery") || "null");
            const selected_delivery_service =
                sessionStorage.getItem("selected_delivery_service") || "Yandex";

            if (String(selected_delivery_service).toLowerCase() === "yandex") {
                let costRub = 0;

                const raw = localStorage.getItem("yandex_delivery_cost_rub") ?? sessionStorage.getItem("yandex_delivery_cost_rub");
                if (raw != null) {
                    const n = Number(raw);
                    if (Number.isFinite(n) && n > 0) costRub = Math.round(n);
                }

                if (!costRub && selected_delivery && typeof selected_delivery === "object") {
                    const pt =
                        selected_delivery?.calc?.price?.pricing_total ??
                        selected_delivery?.calc?.price?.pricing ??
                        selected_delivery?.calc?.pricing_total ??
                        selected_delivery?.calc?.pricing ??
                        null;

                    if (pt != null) {
                        const m = String(pt).trim().match(/(\d+(?:[.,]\d+)?)/);
                        if (m) {
                            const v = Number(m[1].replace(",", "."));
                            if (Number.isFinite(v) && v > 0) costRub = Math.round(v);
                        }
                    }
                }

                if (!selected_delivery || typeof selected_delivery !== "object") selected_delivery = {};
                selected_delivery.delivery_sum = costRub;

                if (costRub > 0) sessionStorage.setItem("delivery_sum", String(costRub));
            }

            const payment_method = "later";
            const payment_commentary = (commentaryInput?.value || "").trim();

            const payload = {
                user_id: user_id_final,
                tg_nick: tg?.initDataUnsafe?.user?.username,
                contact_info,
                checkout_data,
                selected_delivery,
                selected_delivery_service,
                payment_method,
                commentary: payment_commentary,
                promocode,
                source: "telegram",
            };

            const res = await apiPost("/payments/create", payload);

            if (res?.status !== "success") {

                const text = await res?.text?.().catch(() => "");
                throw new Error(`POST /payments/create failed: ${res?.status} ${text}`);
            }

            sessionStorage.removeItem("payment_commentary");
            sessionStorage.removeItem("delivery_sum");
            clearCartAfterOrder();

            if (res?.order_number) {
                await renderProcessPaymentPage(res.order_number);
            }
        } catch (err) {
            console.error("Ошибка при создании платежа:", err);
            alert(err);
        } finally {
            hideLoader();
        }
    }

    hideMainButton();
    showBackButton();

    function validateEmail(v) {
        if (!v) return false;
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim());
    }

    function validatePhone(v) {
        if (!v) return false;
        const digits = v.replace(/[^\d+]/g, "");
        return digits.length >= 7;
    }

    function validateForm() {
        let isValid = true;

        if (!nameInput?.value.trim()) {
            setError(nameInput, nameErrorEl, "Введите имя");
            isValid = false;
        } else {
            clearError(nameInput, nameErrorEl);
        }

        if (!surnameInput?.value.trim()) {
            setError(surnameInput, surnameErrorEl, "Введите фамилию");
            isValid = false;
        } else {
            clearError(surnameInput, surnameErrorEl);
        }

        const emailVal = emailInput?.value.trim() ?? "";
        if (!emailVal) {
            setError(emailInput, emailErrorEl, "Введите email");
            isValid = false;
        } else if (!validateEmail(emailVal)) {
            setError(emailInput, emailErrorEl, "Некорректный email");
            isValid = false;
        } else {
            clearError(emailInput, emailErrorEl);
        }

        const phoneVal = phoneInput?.value.trim() ?? "";
        if (!phoneVal) {
            setError(phoneInput, phoneErrorEl, "Введите телефон");
            isValid = false;
        } else if (!validatePhone(phoneVal)) {
            setError(phoneInput, phoneErrorEl, "Некорректный номер телефона");
            isValid = false;
        } else {
            clearError(phoneInput, phoneErrorEl);
        }

        if (isValid) {
            showMainButton("Оформить заказ", () => {
                handleSubmit();
            });
        } else {
            hideMainButton();
        }

        return isValid;
    }

    if (!form._contactValidationBound) {
        form._contactValidationBound = true;

        [nameInput, surnameInput, emailInput, phoneInput].forEach((input) => {
            input &&
            input.addEventListener("input", () => {
                validateForm();
            });
        });

        if (commentaryInput) {
            commentaryInput.addEventListener("input", () => {
                sessionStorage.setItem("payment_commentary", commentaryInput.value);
            });
        }
    }

    const savedComment = sessionStorage.getItem("payment_commentary");
    if (savedComment && commentaryInput) {
        commentaryInput.value = savedComment;
    }

    let userModel = null;
    if (user_id) {
        userModel = await fetchUserModel(user_id);
    }

    if (userModel && hasCompleteProfile(userModel)) {
        const contact_info = {
            name: userModel.name,
            surname: userModel.surname,
            email: userModel.email,
            phone: userModel.phone,
        };

        saveContactInfo(contact_info);
        prefillFormFromUser(userModel);
        validateForm();
    } else {
        if (userModel) {
            prefillFormFromUser(userModel);
        }
        validateForm();
    }
}
