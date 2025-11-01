import {showLoader, hideLoader} from "../ui/loader.js?v=1";
import {hideMainButton, showBackButton} from "../ui/telegram.js?v=1";
import {navigateTo} from "../router.js?v=1";

export async function renderContactPage() {
    const checkout = document.getElementById("checkout-page");
    const contactPage = document.getElementById("contact-page");
    const form = document.getElementById("contact-form");
    const button = document.getElementById("submit-contact");
    if (!checkout || !contactPage || !form) return;

    checkout.style.display = "none";
    contactPage.style.display = "block";

    form.addEventListener("submit", e => e.preventDefault());
    form.addEventListener("keydown", e => {
        if (e.key === "Enter") e.preventDefault();
    });

    // Replace old button (browser mode only)
    if (button) {
        const newButton = button.cloneNode(true);
        button.replaceWith(newButton);
    }

    const tg = window.Telegram?.WebApp;
    const isTg = Boolean(tg && tg.initDataUnsafe?.user);

    async function handleSubmit() {
        const formData = Object.fromEntries(new FormData(form).entries());

        try {
            showLoader();

            if (isTg) {
                tg.MainButton.setText("Обработка…");
                tg.MainButton.showProgress();
            } else {
                const btn = document.getElementById("submit-contact");
                if (btn) {
                    btn.disabled = true;
                    btn.textContent = "Обработка…";
                }
            }

            // --- Prepare payload ---
            sessionStorage.setItem("yookassa_contact_info", JSON.stringify(formData));
            const checkout_data = JSON.parse(sessionStorage.getItem("checkout_data") || "null");
            const selected_delivery = JSON.parse(sessionStorage.getItem("selected_delivery") || "null");
            const selected_delivery_service =
                sessionStorage.getItem("selected_delivery_service") || "Yandex";
            const user_id = tg?.initDataUnsafe?.user?.id || null;

            const payload = {
                contact_info: formData,
                checkout_data,
                selected_delivery,
                selected_delivery_service,
                user_id,
            };

            // --- API request ---
            const res = await fetch("/payments/create", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify(payload),
            });

            if (!res.ok) throw new Error(`Ошибка (${res.status})`);
            const data = await res.json();

            if (data.confirmation_url) {
                if (isTg) tg.openLink(data.confirmation_url);
                else window.location.href = data.confirmation_url;
            } else {
                navigateTo("/");
            }
        } catch (err) {
            console.error("Ошибка при создании платежа:", err);
            alert(error);
        } finally {
            hideLoader();

            if (isTg) {
                tg.MainButton.hideProgress();
                tg.MainButton.enable();
                tg.MainButton.setText("Продолжить");
                tg.MainButton.show(); // 🔥 make sure it reappears
            } else {
                const btn = document.getElementById("submit-contact");
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = "Продолжить";
                }
            }
        }
    }

    // --- Telegram vs browser handling ---
    if (isTg) {
        showBackButton(() => {
            contactPage.style.display = "none";
            tg.MainButton.offClick(handleSubmit);
            hideMainButton();
            navigateTo("/");
        })
        tg.MainButton.offClick(handleSubmit);
        tg.MainButton.setText("Продолжить");
        tg.MainButton.onClick(handleSubmit);
        tg.MainButton.show(); // 🔥 ensure it’s visible right away
    } else {
        const btn = document.getElementById("submit-contact");
        if (btn) {
            btn.style.display = "block";
            btn.addEventListener("click", handleSubmit);
        }
    }
}