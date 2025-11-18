import {renderHomePage} from "./pages/home.js";
import {renderProductDetailPage} from "./pages/product-detail.js";
import {renderCartPage} from "./pages/cart.js";
import {renderCheckoutPage} from "./pages/checkout.js";
import {renderContactPage} from "./pages/contact.js";
import {renderPaymentPage} from "./pages/payment.js";
import {renderProcessPaymentPage} from "./pages/process-payment.js";

const routes = [
    {match: p => p === "/" || p === "", action: renderHomePage},
    {match: p => p.startsWith("/product/"), action: p => renderProductDetailPage(p.split("/product/")[1])},
    {match: p => p === "/cart", action: renderCartPage},
    {match: p => p === "/checkout", action: renderCheckoutPage},
    {match: p => p === "/contact", action: renderContactPage},
    {match: p => p === "/payment", action: renderPaymentPage},
    {match: p => p === "/process-payment", action: renderProcessPaymentPage},
];

export async function renderCurrentPath() {
    const path = location.pathname;
    for (const r of routes) {
        if (r.match(path)) {
            await r.action(path);
            return;
        }
    }
    await renderHomePage();
}

export function navigateTo(path) {
    history.pushState({}, "", path);
    renderCurrentPath();
}

export function enablePopstate() {
    window.addEventListener("popstate", renderCurrentPath);
}