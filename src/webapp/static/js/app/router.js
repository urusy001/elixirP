import {renderFavouritesPage, renderHomePage} from "./pages/home.js";
import {renderProductDetailPage} from "./pages/product-detail.js";
import {renderCartPage} from "./pages/cart.js";
import {renderCheckoutPage} from "./pages/checkout.js";
import {renderContactPage} from "./pages/contact.js";
import {renderPaymentPage} from "./pages/payment.js";
import {renderProcessPaymentPage} from "./pages/process-payment.js";
import {setupBottomNav, updateBottomNavActive} from "./ui/nav-bottom.js";

const routes = [
    {match: p => p === "/" || p === "", action: renderHomePage},
    {match: p => p.startsWith("/product/"), action: p => {const onecId = p.split("/product/")[1]; return renderProductDetailPage(onecId);}},
    {match: p => p === "/cart", action: renderCartPage},
    {match: p => p === "/checkout", action: renderCheckoutPage},
    {match: p => p === "/contact", action: renderContactPage},
    {match: p => p === "/payment", action: renderPaymentPage},
    {match: p => p === "/process-payment", action: renderProcessPaymentPage},
    {match: p => p === "/favourites", action: renderFavouritesPage},
];

function getCurrentPath() {
    const raw = window.location.hash || "";
    const path = raw.replace(/^#/, "");
    return path || "/";
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
    setupBottomNav();
    const normalized = path.startsWith("/") ? path : `/${path}`;
    updateBottomNavActive(normalized);
    const targetHash = `#${normalized}`;
    if (window.location.hash === targetHash) return;
    window.location.hash = normalized;
}

export function enablePopstate() {
    window.addEventListener("hashchange", () => {
        void renderCurrentPath();
    });
}