import {renderHomePage} from "./pages/home.js";
import {renderProductDetailPage} from "./pages/product-detail.js";
import {renderCartPage} from "./pages/cart.js";
import {renderCheckoutPage} from "./pages/checkout.js";
import {renderContactPage} from "./pages/contact.js";
import {renderPaymentPage} from "./pages/payment.js";
import {renderProcessPaymentPage} from "./pages/process-payment.js";

const routes = [
    {match: p => p === "/" || p === "", action: renderHomePage},
    {
        match: p => p.startsWith("/product/"),
        action: p => {
            const onecId = p.split("/product/")[1];
            return renderProductDetailPage(onecId);
        }
    },
    {match: p => p === "/cart", action: renderCartPage},
    {match: p => p === "/checkout", action: renderCheckoutPage},
    {match: p => p === "/contact", action: renderContactPage},
    {match: p => p === "/payment", action: renderPaymentPage},
    {match: p => p === "/process-payment", action: renderProcessPaymentPage},
];

function getCurrentPath() {
    // URL: https://.../#/cart или https://.../#/product/123
    const raw = window.location.hash || "";
    const path = raw.replace(/^#/, ""); // "#/cart" -> "/cart"
    return path || "/";                 // по умолчанию "/"
}

export async function renderCurrentPath() {
    const path = getCurrentPath();
    for (const r of routes) {
        if (r.match(path)) {
            await r.action(path);
            return;
        }
    }
    await renderHomePage();
}

export function navigateTo(path) {
    const normalized = path.startsWith("/") ? path : `/${path}`;

    // Реальный pathname не трогаем, меняем только hash.
    const targetHash = `#${normalized}`;
    if (window.location.hash === targetHash) return;

    // Меняем hash — это само вызовет hashchange → renderCurrentPath()
    window.location.hash = normalized;
}

export function enablePopstate() {
    // Для hash-роутинга слушаем hashchange
    window.addEventListener("hashchange", () => {
        void renderCurrentPath();
    });
}