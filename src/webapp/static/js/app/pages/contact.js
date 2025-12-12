import {showLoader, hideLoader} from "../ui/loader.js";
import navigateTo from "../router.js";
import {state} from "../state.js";
import {
    isTelegramApp,
    showMainButton,
    showBackButton,
    hideMainButton,
} from "../ui/telegram.js";
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
import {apiGet, apiPost} from "../../services/api.js";

const form = document.getElementById("contact-form");

export async function renderContactPage() {
    if (!checkoutPageEl || !contactPageEl || !form) return;

    // Only run in Telegram
    if (!isTelegramApp()) {
        console.warn("[contact] Not in Telegram WebApp.");
        return;
    }

    // Hide everything except contact page
    cartPageEl.style.display = "none";
    detailEl.style.display = "none";
    listEl.style.display = "none";
    toolbarEl.style.display = "none";
    checkoutPageEl.style.display = "none";
    contactPageEl.style.display = "none";
    paymentPageEl && (paymentPageEl.style.display = "none");
    processPaymentEl.style.display = "none";
    profilePageEl.style.display = "none";

    headerTitle.textContent = "Оформление заказа";
    searchBtnEl.style.display = "none";

    // You can choose: show or hide bottom nav here. Let's keep it visible like on your screenshot.
    navBottomEl.style.display = "flex";

    contactPageEl.style.display = "block";

    // Prevent default submit/enter
    form.addEventListener("submit", (e) => e.preventDefault());
    form.addEventListener("keydown", (e) => {
        if (e.key === "Enter") e.preventDefault();
    });

    const tg = state.telegram;
    const user_id = tg?.initDataUnsafe?.user?.id ?? null;

    // --- Input refs ---
    const nameInput = form.querySelector('[name="name"]');
    const surnameInput = form.querySelector('[name="surname"]');
    const emailInput = form.querySelector('[name="email"]');
    const phoneInput = form.querySelector('[name="phone"]');
    const commentaryInput = form.querySelector('#payment-commentary-input');

    // Create / find error containers per input (attach right after input)
    function ensureErrorEl(input) {
        if (!input) return null;
        if (input._errorEl) return input._errorEl;

        const err = document.createElement("div");
        err.className = "field-error"; // styles in contact.css
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

    // ---------- Helpers ----------
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

    // 💾 save contact info (used in order payload)
    function saveContactInfo(contact_info) {
        sessionStorage.setItem("contact_info", JSON.stringify(contact_info));
        if (user_id) sessionStorage.setItem("tg_user_id", String(user_id));
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
            const selected_delivery = JSON.parse(sessionStorage.getItem("selected_delivery") || "null");
            const selected_delivery_service =
                sessionStorage.getItem("selected_delivery_service") || "Yandex";

            const payment_method = "later"; // only option now
            const payment_commentary =
                (commentaryInput?.value || "").trim();

            const payload = {
                user_id: user_id_final,
                contact_info,
                checkout_data,
                selected_delivery,
                selected_delivery_service,
                payment_method,            // fixed: "later"
                commentary: payment_commentary,
                promocode,
                source: "telegram",
            };

            const res = await apiPost("/payments/create", payload);

            if (!res.ok) {
                const text = await res.text().catch(() => "");
                throw new Error(`POST /payments/create failed: ${res.status} ${text}`);
            }
            const data = await res.json().catch(() => ({}));
            if (data?.order_number)

            sessionStorage.removeItem("payment_commentary");
            navigateTo("/process-payment");
        } catch (err) {
            console.error("Ошибка при создании платежа:", err);
            alert("Не удалось создать заказ. Попробуйте снова.");
        } finally {
            hideLoader();

        }
    }

    hideMainButton();
    showBackButton();

    // ---------- Validation ----------
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

        // name
        if (!nameInput?.value.trim()) {
            setError(nameInput, nameErrorEl, "Введите имя");
            isValid = false;
        } else {
            clearError(nameInput, nameErrorEl);
        }

        // surname
        if (!surnameInput?.value.trim()) {
            setError(surnameInput, surnameErrorEl, "Введите фамилию");
            isValid = false;
        } else {
            clearError(surnameInput, surnameErrorEl);
        }

        // email
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

        // phone
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

        // MainButton logic
        if (isValid) {
            showMainButton("Оформить заказ", () => {
                // allow async
                handleSubmit();
            });
        } else {
            hideMainButton();
        }

        return isValid;
    }

    // Attach listeners only once per page lifetime
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
                // optional: if you ever want to auto-save comment:
                sessionStorage.setItem("payment_commentary", commentaryInput.value);
            });
        }
    }

    // Restore saved commentary if exists
    const savedComment = sessionStorage.getItem("payment_commentary");
    if (savedComment && commentaryInput) {
        commentaryInput.value = savedComment;
    }

    // ---------- Prefill / auto-skip ----------
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
        // With merged page we DON'T go to /payment anymore,
        // we just prefill the form and validate.
        prefillFormFromUser(userModel);
        validateForm();
    } else {
        if (userModel) {
            prefillFormFromUser(userModel);
        }
        validateForm();
    }
}