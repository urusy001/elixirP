import { showLoader, hideLoader } from "../ui/loader.js";
import { isTelegramApp, showBackButton, showMainButton } from "../ui/telegram.js";
import { navigateTo } from "../router.js";
import { state } from "../state.js";
import {
    cartPageEl,
    checkoutPageEl,
    contactPageEl, detailEl,
    headerTitle, listEl, navBottomEl, orderDetailEl, ordersPageEl,
    paymentPageEl,
    processPaymentEl, profilePageEl,
    searchBtnEl,
    toolbarEl
} from "./constants.js";
import { apiPost } from "../../services/api.js";

export async function renderPaymentPage() {
    showLoader();
    setupPaymentPage();
    setupPaymentCommentary();

    toolbarEl.style.display = "none";
    listEl.style.display = "none";
    detailEl.style.display = "none";
    cartPageEl.style.display = "none";
    headerTitle.textContent = "  Выберите способ оплаты";
    checkoutPageEl.style.display = "none";
    contactPageEl.style.display = "none";
    paymentPageEl.style.display = "block";
    searchBtnEl.style.display = "none";
    processPaymentEl.style.display = "none";
    navBottomEl.style.display = "flex";
    profilePageEl.style.display = "none";
    ordersPageEl.style.display = "none";
    orderDetailEl.style.display = "none";

    if (isTelegramApp()) {
        showBackButton();

        showMainButton("Оформить", handlePaymentSubmit);
    }

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
        later: 'Способ оплаты: Оплатить позже, через менеджера. Мы свяжемся с вами для подтверждения заказа и оплаты.'
    };

    if (!methodsContainer.dataset.boundChange) {
        methodsContainer.addEventListener('change', (e) => {
            if (e.target.name !== 'payment_method') return;

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

    window.getSelectedPaymentMethod = function () {
        const checked = document.querySelector('input[name="payment_method"]:checked');
        return checked ? checked.value : null;
    };

    if (!methodsContainer.dataset.defaultSet) {
        const defaultRadio = methodsContainer.querySelector('input[name="payment_method"][value="later"]');
        if (defaultRadio) {
            defaultRadio.checked = true;

            methodsContainer.querySelectorAll('.payment-method').forEach(label => {
                const radio = label.querySelector('input[type="radio"]');
                label.classList.toggle('active', radio === defaultRadio);
            });

            if (noteEl && notes.later) {
                noteEl.textContent = notes.later;
            }

            methodsContainer.dataset.defaultSet = "1";
        }
    }
}

function setupPaymentCommentary() {
    const commentaryEl = document.getElementById("payment-commentary-input");
    if (!commentaryEl) return;

    const saved = sessionStorage.getItem("payment_commentary");
    if (saved) {
        commentaryEl.value = saved;
    }

    if (!commentaryEl.dataset.boundInput) {
        commentaryEl.addEventListener("input", () => {
            sessionStorage.setItem("payment_commentary", commentaryEl.value);
        });
        commentaryEl.dataset.boundInput = "1";
    }
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
        const promocode = JSON.parse(sessionStorage.getItem("promocode") || "null");
        const selected_delivery = JSON.parse(sessionStorage.getItem("selected_delivery") || "null");
        const selected_delivery_service =
            sessionStorage.getItem("selected_delivery_service") || "Yandex";

        const payment_method = window.getSelectedPaymentMethod
            ? window.getSelectedPaymentMethod()
            : null;

        const commentaryEl = document.getElementById("payment-commentary-input");
        const payment_commentary = commentaryEl
            ? commentaryEl.value.trim()
            : (sessionStorage.getItem("payment_commentary") || "").trim();

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
            payment_method,
            "commentary": payment_commentary,
            promocode,
            source: "telegram",
        };

    } catch (err) {
        console.error("Ошибка при создании платежа:", err);
        alert("Не удалось создать платеж. Попробуйте снова.");
    } finally {
        hideLoader();
    }
}
