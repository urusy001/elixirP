import { getProductDetail } from "../../services/productService.js?v=1";
import { withLoader } from "../ui/loader.js?v=1";
import { saveCart, state } from "../state.js?v=1";
import {
    hideMainButton,
    hideBackButton,
    isTelegramApp,
    showBackButton,
    showMainButton,
    updateMainButton,
} from "../ui/telegram.js";
import { navigateTo } from "../router.js?v=1";

export async function renderProductDetailPage(onec_id) {
    const listEl = document.getElementById("product-list");
    const detailEl = document.getElementById("product-detail");
    const cartPageEl = document.getElementById("cart-page");
    const checkoutEl = document.getElementById("checkout-page");

    listEl.style.display = "none";
    cartPageEl.style.display = "none";
    checkoutEl.style.display = "none";
    detailEl.style.display = "block";

    const data = await withLoader(() => getProductDetail(onec_id));
    if (data?.error) return;

    const features = data.features || [];
    let selectedFeature = null;

    detailEl.innerHTML = `
    <div class="product-detail-container">
      <div class="product-main">
        <div class="product-image">
          <img src="${data.product.image || '/static/images/product.png'}" alt="${data.product.name}">
        </div>
        <div class="product-info">
          <h1>${data.product.name}</h1>
          <p>${data.product.description || "Нет описания"}</p>
        </div>
      </div>
      <div class="product-features">
        <h2>Вариации</h2>
        <table class="features-table">
          <thead>
            <tr>
              <th>Вид</th>
              <th>Цена</th>
              <th>Склад</th>
            </tr>
          </thead>
          <tbody>
            ${features.map(f => `
              <tr data-feature-id="${f.onec_id}">
                <td>${f.name}</td>
                <td>${Number(f.price).toLocaleString("ru-RU")} ₽</td>
                <td>${f.balance}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;

    const tbody = detailEl.querySelector(".features-table tbody");

    // Highlight + selection logic
    tbody.addEventListener("click", e => {
        const row = e.target.closest("tr[data-feature-id]");
        if (!row) return;

        tbody.querySelectorAll("tr.selected").forEach(r => r.classList.remove("selected"));
        row.classList.add("selected");

        const featureId = row.dataset.featureId;
        selectedFeature = features.find(f => f.onec_id === featureId);

        const key = `${onec_id}_${featureId}`;
        const count = state.cart[key] || 0;
        const label = count > 0 ? `В корзине (${count})` : "В корзину";
        updateMainButton(label);
    });

    // Setup Telegram buttons
    if (isTelegramApp()) {
        showBackButton(() => navigateTo("/"));

        // Initial MainButton → scroll to table
        showMainButton("Выбрать дозировку", () => {
            const table = detailEl.querySelector(".features-table");
            if (table) table.scrollIntoView({ behavior: "smooth", block: "start" });
        });

        let selectedFeature = null;
        let key = null;

        const tg = state.telegram;

        function updateSplitButton(count) {
            tg.MainButton.setText(`[-]   ${count}   [+]`);
        }

        tg.MainButton.onClick(async ev => {
            if (!selectedFeature) {
                const table = detailEl.querySelector(".features-table");
                table.scrollIntoView({ behavior: "smooth" });
                return;
            }

            // Determine tap position (approximate split zones)
            const btnWidth = tg.viewportWidth || window.innerWidth;
            const clickX = ev?.clientX || 0;
            const zone = clickX < btnWidth * 0.33 ? "minus" : clickX > btnWidth * 0.66 ? "plus" : "center";

            const count = state.cart[key] || 0;
            if (zone === "minus") {
                if (count > 1) state.cart[key] = count - 1;
                else delete state.cart[key];
                saveCart();
            } else if (zone === "plus") {
                state.cart[key] = count + 1;
                saveCart();
            }
            const newCount = state.cart[key] || 0;
            updateSplitButton(newCount > 0 ? newCount : "+ В корзину");
        });

        // Handle row click for feature selection
        const tbody = detailEl.querySelector(".features-table tbody");
        tbody.addEventListener("click", e => {
            const row = e.target.closest("tr[data-feature-id]");
            if (!row) return;
            tbody.querySelectorAll("tr.selected").forEach(r => r.classList.remove("selected"));
            row.classList.add("selected");
            const featureId = row.dataset.featureId;
            selectedFeature = features.find(f => f.onec_id === featureId);
            key = `${onec_id}_${featureId}`;

            const currentCount = state.cart[key] || 0;
            if (currentCount === 0) {
                tg.MainButton.setText("+ В корзину");
            } else {
                updateSplitButton(currentCount);
            }
        });

        window.addEventListener(
            "popstate",
            () => {
                hideMainButton();
                hideBackButton();
            },
            { once: true }
        );
    }
}