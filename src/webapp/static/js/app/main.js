// static/js/app/main.js
import {renderCurrentPath, enablePopstate} from "./router.js";
import {initSearchOverlay} from "./pages/search.js";
import {initCartBadge} from "./ui/cart-badge.js";
import {setupBottomNav} from "./ui/nav-bottom.js";

document.addEventListener("DOMContentLoaded", async () => {
    setupBottomNav();
    initCartBadge();
    initSearchOverlay();
    enablePopstate();
    await renderCurrentPath();
});

(function initTelegramTheme() {
    const tg = window.Telegram && window.Telegram.WebApp;
    if (!tg) {
        // не в Telegram — можно оставить светлую тему или сделать свою логику
        return;
    }

    tg.ready();

    function hexToRgb(hex) {
        if (!hex || typeof hex !== "string") return null;
        const h = hex.replace("#", "").trim();
        if (![3, 6].includes(h.length)) return null;
        const full = h.length === 3 ? h.split("").map(ch => ch + ch).join("") : h;
        const n = parseInt(full, 16);
        if (Number.isNaN(n)) return null;
        return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
    }

    function applyTheme() {
        const tp = tg.themeParams || {};
        const root = document.documentElement;

        // 1) Прокидываем TG themeParams в CSS vars (чтобы можно было использовать var(--tg-...))
        // Список популярных ключей: bg_color, text_color, hint_color, link_color,
        // button_color, button_text_color, secondary_bg_color, header_bg_color, accent_text_color и др.
        Object.entries(tp).forEach(([k, v]) => {
            if (typeof v === "string" && v.trim()) {
                root.style.setProperty(`--tg-${k.replace(/_/g, "-")}`, v.trim());
            }
        });

        // 2) Определяем dark/light
        // В новых клиентах есть tg.colorScheme = "dark" | "light"
        const scheme = (tg.colorScheme || "").toLowerCase();
        const isDark = scheme === "dark";

        // 3) Если хочешь свой dark-mode токенами — включаем data-theme
        // (Если тебе не нужен свой dark-mode, этот блок можно удалить)
        if (isDark) root.setAttribute("data-theme", "dark");
        else root.removeAttribute("data-theme");

        // 4) Мелочь: подстрой фон документа под Telegram (если нужно)
        // Обычно достаточно var(--tg-bg-color) или своей переменной
        // document.body.style.background = tp.bg_color || "";
    }

    applyTheme();

    // Событие смены темы
    tg.onEvent("themeChanged", applyTheme);

    // Если хочешь потом отписаться:
    // tg.offEvent("themeChanged", applyTheme);
})();