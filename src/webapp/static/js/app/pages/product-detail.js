import { getProductDetail } from "../../services/productService.js";
import { withLoader } from "../ui/loader.js";
import { state, saveCart } from "../state.js";
import {
  showBackButton,
  showMainButton,
  updateMainButton,
  hideMainButton,
  hideBackButton,
  isTelegramApp,
} from "../ui/telegram.js";

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
  const featuresTableHtml = `
    <div class="product-features">
      <h2>Вариации</h2>
      <table class="features-table">
        <thead>
          <tr>
            <th data-key="name">Вид</th>
            <th data-key="price">Цена</th>
            <th data-key="balance">Склад</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>
  `;

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
      ${featuresTableHtml}
    </div>
  `;

  const tbody = detailEl.querySelector(".features-table tbody");
  const headers = detailEl.querySelectorAll(".features-table th[data-key]");
  let sortKey = "price";
  let sortAsc = true;

  function renderTableBody() {
    let sorted = [...features];
    if (sortKey) {
      sorted.sort((a, b) => {
        if (typeof a[sortKey] === "string") {
          return sortAsc
            ? a[sortKey].localeCompare(b[sortKey])
            : b[sortKey].localeCompare(a[sortKey]);
        }
        return sortAsc ? a[sortKey] - b[sortKey] : b[sortKey] - a[sortKey];
      });
    }

    tbody.innerHTML = sorted
      .map(
        f => `
      <tr>
        <td>${f.name}</td>
        <td>${Number(f.price).toLocaleString("ru-RU")} ₽</td>
        <td>${f.balance}</td>
      </tr>`
      )
      .join("");

    headers.forEach(h => {
      let label =
        h.dataset.key === "name" ? "Вид" : h.dataset.key === "price" ? "Цена" : "Склад";
      if (h.dataset.key === sortKey) label += sortAsc ? " ▲" : " ▼";
      h.textContent = label;
    });
  }

  headers.forEach(h => {
    h.style.cursor = "pointer";
    h.addEventListener("click", () => {
      const key = h.dataset.key;
      if (sortKey === key) sortAsc = !sortAsc;
      else {
        sortKey = key;
        sortAsc = true;
      }
      renderTableBody();
    });
  });

  renderTableBody();

  if (isTelegramApp()) {
    const off = showBackButton(() => {
      history.back();
      hideBackButton();
    });
    const unsubscribe = showMainButton(
      state.cart[onec_id] ? `В корзине (${state.cart[onec_id]})` : "В корзину",
      () => {
        state.cart[onec_id] = (state.cart[onec_id] || 0) + 1;
        saveCart();
        updateMainButton(`В корзине (${state.cart[onec_id]})`);
      }
    );

    window.addEventListener(
      "popstate",
      () => {
        off?.();
        hideMainButton();
      },
      { once: true }
    );
  } else {
    const fallbackBtn = document.createElement("button");
    fallbackBtn.textContent = state.cart[onec_id]
      ? `(${state.cart[onec_id]})`
      : "В корзину";
    fallbackBtn.className = "buy-btn";
    fallbackBtn.onclick = () => {
      state.cart[onec_id] = (state.cart[onec_id] || 0) + 1;
      saveCart();
      fallbackBtn.textContent = `(${state.cart[onec_id]})`;
    };
    detailEl.appendChild(fallbackBtn);
  }
}