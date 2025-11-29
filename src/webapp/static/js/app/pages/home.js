import {searchProducts} from "../../services/productService.js";
import {withLoader} from "../ui/loader.js";
import {navigateTo} from "../router.js";
import {state, saveCart} from "../state.js";
import {hideBackButton, hideMainButton} from "../ui/telegram.js";
import {showCartIcon} from "../ui/cart-icon.js";
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
import {apiPost} from "../../services/api";

let page = 0;
let loading = false;

function productCardHTML(p) {
    const onecId = p.onec_id || (p.url ? p.url.split("/product/")[1] : "0");
    const sortedFeatures = Array.isArray(p.features)
        ? [...p.features].sort((a, b) => b.price - a.price)
        : [];

    const featureSelector = sortedFeatures.length
        ? `<select class="feature-select" data-onec-id="${onecId}">
         ${sortedFeatures.map(f => `<option value="${f.id}" data-price="${f.price}">${f.name} - ${f.price} ₽</option>`).join("")}
       </select>`
        : "";

    return `
    <div class="product-card">
      <a href="/product/${onecId}" class="product-link" data-onec-id="${onecId}">
        <div class="product-image">
          <img src="/static/images/product.png"
               data-highres="${p.image || '/static/images/product.png'}"
               alt="${p.name}" class="product-img">
        </div>
      </a>
      <div class="product-info">
        <span class="product-name">${p.name}</span>
        ${featureSelector}
      </div>
      <button class="buy-btn" data-onec-id="${onecId}"></button>
    </div>
  `;
}

function renderBuyCounter(btn, onecId) {
    const selector = btn.closest(".product-card")?.querySelector(".feature-select");
    const selectedFeatureId = selector?.value || null;
    const key = selectedFeatureId ? `${onecId}_${selectedFeatureId}` : onecId;
    const count = state.cart[key] || 0;

    btn.innerHTML = "";

    if (count === 0) {
        const add = document.createElement("button");
        add.textContent = "+ В корзину";
        add.className = "buy-btn-initial";
        add.onclick = () => {
            state.cart[key] = 1;
            saveCart();
            renderBuyCounter(btn, onecId);
        };
        btn.appendChild(add);
    } else {
        const minus = document.createElement("button");
        minus.textContent = "−";
        minus.onclick = () => {
            state.cart[key] = (state.cart[key] || 0) - 1;
            if (state.cart[key] <= 0) delete state.cart[key];
            saveCart();
            renderBuyCounter(btn, onecId);
        };
        const qty = document.createElement("span");
        qty.textContent = state.cart[key];
        qty.style.margin = "0 4px";
        const plus = document.createElement("button");
        plus.textContent = "+";
        plus.onclick = () => {
            state.cart[key] = (state.cart[key] || 0) + 1;
            saveCart();
            renderBuyCounter(btn, onecId);
        };
        btn.append(minus, qty, plus);
    }

    if (selector && !selector.dataset.counterBound) {
        selector.addEventListener("change", () => renderBuyCounter(btn, onecId));
        selector.dataset.counterBound = "1";
    }
}

function attachProductInteractions(container) {
    container.querySelectorAll(".product-link").forEach(link => {
        link.addEventListener("click", e => {
            e.preventDefault();
            const id = link.dataset.onecId;
            navigateTo(`/product/${id}`);
        });
    });

    container.querySelectorAll(".buy-btn").forEach(btn => {
        if (btn.dataset.initialized) return;
        renderBuyCounter(btn, btn.dataset.onecId);
        btn.dataset.initialized = "1";
    });
}

async function loadMore(container, append = false, useLoader = true) {
    if (loading) return;
    loading = true;

    try {
        const fetchFn = async () => {
            const data = await searchProducts({q: "", page});
            if (!data.results || !Array.isArray(data.results)) data.results = [];
            return data.results;
        };

        const results = useLoader ? await withLoader(fetchFn) : await fetchFn();
        const html = results.map(productCardHTML).join("");

        if (append) container.insertAdjacentHTML("beforeend", html);
        else container.innerHTML = html;

        attachProductInteractions(container);
        page++;
    } catch (err) {
        console.error("[Products] load failed:", err);
    } finally {
        loading = false;
    }
}

function setupInfiniteScroll(container) {
    function onScroll() {
        if (container.style.display === "none") return;
        const st = document.documentElement.scrollTop || document.body.scrollTop;
        const sh = document.documentElement.scrollHeight || document.body.scrollHeight;
        const ch = document.documentElement.clientHeight;
        if (st + ch >= sh - 200) loadMore(container, true);
    }

    window.addEventListener("scroll", onScroll);
}

async function getUser() {
    const tg = window.Telegram?.WebApp;
    if (!tg) return null;

    // "сырые" данные, приходящие от Telegram
    const initData = tg.initData || "";
    const initDataUnsafe = tg.initDataUnsafe || {};
    const payload = {
        initData,
        initDataUnsafe,
    }
    alert(JSON.stringify(payload));
    await apiPost('/user/login', payload);
}

export async function renderHomePage() {
    await getUser();
    hideMainButton();
    hideBackButton();
    showCartIcon();
    headerTitle.textContent = "Магазин ElixirPeptide";
    listEl.style.display = "grid";
    toolbarEl.style.display = "flex";
    searchBtnEl.style.display = "flex";
    detailEl.style.display = "none";
    cartPageEl.style.display = "none";
    checkoutPageEl.style.display = "none";
    contactPageEl.style.display = "none";
    paymentPageEl.style.display = "none";
    processPaymentEl.style.display = "none";

    page = 1;
    await loadMore(listEl, false);
    setupInfiniteScroll(listEl);
}
