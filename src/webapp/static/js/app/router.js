import { renderProductsPage } from "./pages/products.js";
import { renderProductDetailPage } from "./pages/product-detail.js";
import { renderCartPage } from "./pages/cart.js";
import { renderCheckoutPage } from "./pages/checkout.js";
import { renderContactPage } from "./pages/contact.js";

const routes = [
  { match: p => p === "/" || p === "", action: renderProductsPage },
  { match: p => p.startsWith("/product/"), action: p => renderProductDetailPage(p.split("/product/")[1]) },
  { match: p => p === "/cart", action: renderCartPage },
  { match: p => p === "/checkout", action: renderCheckoutPage },
  { match: p => p === "/contact", action: renderContactPage },
];

export async function renderCurrentPath() {
  const path = location.pathname;
  for (const r of routes) {
    if (r.match(path)) {
      await r.action(path);
      return;
    }
  }
  await renderProductsPage();
}

export function navigateTo(path) {
  history.pushState({}, "", path);
  renderCurrentPath();
}

export function enablePopstate() {
  window.addEventListener("popstate", renderCurrentPath);
}