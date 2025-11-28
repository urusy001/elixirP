import {hideCartIcon} from "../ui/cart-icon.js";
import {showLoader, hideLoader} from "../ui/loader.js";
import {isTelegramApp, showBackButton, showMainButton} from "../ui/telegram.js";
import {navigateTo} from "../router.js";
import { state } from "../state.js";
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
import {apiPost} from "../../services/api.js";

export async function renderPaymentPage() {
    showLoader();
    setupPaymentPage();

    hideCartIcon();
    toolbarEl.style.display = "none";
    listEl.style.display = "none";
    detailEl.style.display = "none";
    cartPageEl.style.display = "none";
    headerTitle.textContent = "Оплата";
    checkoutPageEl.style.display = "none";
    contactPageEl.style.display = "none";
    paymentPageEl.style.display = "block";
    searchBtnEl.style.display = "none";
    processPaymentEl.style.display = "none";

    if (isTelegramApp()) {
        showBackButton(() => {
            navigateTo("/contact");
        });

        // MainButton now sends payment with selected method
        showMainButton("Оформить", handlePaymentSubmit);
    }

    // optional: show totals from sessionStorage
    try {
        const totalEl = document.getElementById("payment-total");
        const deliveryEl = document.getElementById("payment-delivery-amount");
        const deliveryRow = document.getElementById("payment-delivery-row");

        const checkout_data = JSON.parse(sessionStorage.getItem("checkout_data") || "null");
        const selected_delivery = JSON.parse(sessionStorage.getItem("selected_delivery") || "null");

        if (checkout_data?.total && totalEl) {
            totalEl.textContent = checkout_data.total + " ₽";
        }

        if (selected_delivery?.price != null && deliveryEl && deliveryRow) {
            deliveryEl.textContent = selected_delivery.price + " ₽";
            deliveryRow.style.display = "flex";
        }
    } catch (e) {
        console.warn("[payment] cannot restore totals:", e);
    }

    hideLoader();
}

function setupPaymentPage() {
    const methodsContainer = document.getElementById('payment-methods');
    if (!methodsContainer) return;

    const noteEl = document.getElementById('payment-method-note');

    const notes = {
        usdt: 'Способ оплаты: USDT. После оформления мы покажем вам реквизиты и точную сумму.',
        yookassa: 'Способ оплаты: ЮKassa. Вы будете перенаправлены на защищённую платёжную страницу.',
        later: 'Способ оплаты: Оплатить позже. Мы свяжемся с вами для подтверждения заказа и оплаты.'
    };

    // avoid double-binding if renderPaymentPage is called again
    if (!methodsContainer.dataset.boundChange) {
        methodsContainer.addEventListener('change', (e) => {
            if (e.target.name !== 'payment_method') return;

            // toggle active class on cards
            methodsContainer.querySelectorAll('.payment-method').forEach(label => {
                const radio = label.querySelector('input[type="radio"]');
                label.classList.toggle('active', radio.checked);
            });

            const value = e.target.value;
            if (noteEl && notes[value]) {
                noteEl.textContent = notes[value];
            }
        });

        methodsContainer.dataset.boundChange = "1";
    }

    // Helper for other modules:
    window.getSelectedPaymentMethod = function () {
        const checked = document.querySelector('input[name="payment_method"]:checked');
        return checked ? checked.value : null;
    };
}

async function handlePaymentSubmit() {
    try {
        showLoader();

        const tg = state.telegram;
        const user_id =
            sessionStorage.getItem("tg_user_id") ||
            (tg?.initDataUnsafe?.user?.id != null
                ? String(tg.initDataUnsafe.user.id)
                : null);

        const contact_info = JSON.parse(sessionStorage.getItem("contact_info") || "null");
        const checkout_data = JSON.parse(sessionStorage.getItem("checkout_data") || "null");
        const selected_delivery = JSON.parse(sessionStorage.getItem("selected_delivery") || "null");
        const selected_delivery_service =
            sessionStorage.getItem("selected_delivery_service") || "Yandex";

        const payment_method = window.getSelectedPaymentMethod
            ? window.getSelectedPaymentMethod()
            : null;

        if (!payment_method) {
            alert("Выберите способ оплаты.");
            return;
        }

        if (!contact_info) {
            alert("Контактные данные не найдены. Вернитесь назад и заполните форму.");
            navigateTo("/contact");
            return;
        }

        const payload = {
            user_id,
            contact_info,
            checkout_data,
            selected_delivery,
            selected_delivery_service,
            payment_method,   // 👈 HERE we include chosen method
            source: "telegram",
        };

        const res = await apiPost("/payments/create", {
            body: JSON.stringify(payload),
        });

        if (!res.ok) {
            const text = await res.text().catch(() => "");
            throw new Error(`POST /payments/create failed: ${res.status} ${text}`);
        }

        const data = await res.json().catch(() => ({}));

        if (data?.order_id) {
            sessionStorage.setItem("order_id", String(data.order_id));
        }

        // optional: handle method-specific redirects
        if (payment_method === "yookassa" && data?.confirmation_url) {
            // YooKassa: redirect to payment page
            window.location.href = data.confirmation_url;
            return;
        } else if (payment_method === "usdt" && data?.usdt_address) {

        }

        // USDT / later: you may want to show a success screen or instructions
        // For now, just navigate to some local "success" route:
        navigateTo("/process-payment");

    } catch (err) {
        console.error("Ошибка при создании платежа:", err);
        alert("Не удалось создать платеж. Попробуйте снова.");
    } finally {
        hideLoader();
    }
}