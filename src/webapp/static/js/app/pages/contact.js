import {showLoader, hideLoader} from "../ui/loader.js";
import {navigateTo} from "../router.js";
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
    headerTitle, listEl,
    paymentPageEl,
    processPaymentEl,
    searchBtnEl,
    toolbarEl
} from "./constants.js";
import {apiGet} from "../../services/api.js";

const form = document.getElementById("contact-form");

export async function renderContactPage() {
    if (!checkoutPageEl || !contactPageEl || !form) return;

    // Only run in Telegram
    if (!isTelegramApp()) {
        console.warn("[contact] Not in Telegram WebApp.");
        return;
    }

    cartPageEl.style.display = "none";
    detailEl.style.display = "none";
    listEl.style.display = "none";
    toolbarEl.style.display = "none";
    contactPageEl.style.display = "none";
    headerTitle.textContent = "Контактная информация";
    checkoutPageEl.style.display = "none";
    searchBtnEl.style.display = "none";
    paymentPageEl.style.display = "none";
    contactPageEl.style.display = "block";
    processPaymentEl.style.display = "none";

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

    // Create / find error containers per input (attach right after input)
    function ensureErrorEl(input) {
        if (!input) return null;
        if (input._errorEl) return input._errorEl;

        const err = document.createElement("div");
        err.className = "field-error";
        err.style.color = "#ef4444";
        err.style.fontSize = "12px";
        err.style.marginTop = "4px";

        input.insertAdjacentElement("afterend", err); // 👈 always unique per input
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

    // 💾 save contact info (called from MainButton)
    function saveContactInfo(contact_info) {
        sessionStorage.setItem("contact_info", JSON.stringify(contact_info));
        if (user_id) sessionStorage.setItem("tg_user_id", String(user_id));
    }

    async function handleSubmit() {
        if (!validateForm()) return; // double check before submit

        const formData = Object.fromEntries(new FormData(form).entries());
        saveContactInfo(formData);
        navigateTo("/payment");
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
            showMainButton("Перейти к оплате", () => handleSubmit());
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
        navigateTo("/payment");
    } else {
        if (userModel) {
            prefillFormFromUser(userModel);
        }
        validateForm();
    }
}