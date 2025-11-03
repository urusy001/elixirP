import {getProductDetail} from "../../services/productService.js?v=1";
import {withLoader} from "../ui/loader.js?v=1";
import {saveCart, state} from "../state.js?v=1";
import {
    hideMainButton,
    hideBackButton,
    isTelegramApp,
    showBackButton,
    showMainButton,
    updateMainButton,
} from "../ui/telegram.js?v=1";
import {navigateTo} from "../router.js?v=1";
import {hideCartIcon} from "../ui/cart-icon.js";

export async function renderProductDetailPage(onec_id) {
    const toolbarEl = document.querySelector(".toolbar");
    toolbarEl.classList.add("hidden");

    const listEl = document.getElementById("product-list");
    const detailEl = document.getElementById("product-detail");
    const cartPageEl = document.getElementById("cart-page");
    const checkoutEl = document.getElementById("checkout-page");
    hideCartIcon();

    listEl.style.display = "none";
    cartPageEl.style.display = "none";
    checkoutEl.style.display = "none";
    detailEl.style.display = "block";

    const data = await withLoader(() => getProductDetail(onec_id));
    if (data?.error) return;

    const features = data.features || [];

    ensureSheetStyles();

    // Product header
    detailEl.innerHTML = `
    <div class="pd-wrap">
      <div class="pd-card">
        <div class="pd-img">
          <img src="${data.product.image || '/static/images/product.png'}" alt="${data.product.name}">
        </div>
        <div class="pd-info">
          <h1 class="pd-title">${data.product.name}</h1>
          <p class="pd-desc">${data.product.description || "Нет описания"}</p>
        </div>
      </div>
    </div>
  `;

    // Create bottom sheet
    const backdrop = document.createElement("div");
    backdrop.className = "sheet-backdrop";
    backdrop.style.display = "none";

    const sheet = document.createElement("div");
    sheet.className = "sheet";
    sheet.setAttribute("role", "dialog");
    sheet.setAttribute("aria-modal", "true");
    sheet.innerHTML = `
    <div class="sheet-handle" aria-hidden="true">
      <span class="sheet-notch"></span>
    </div>
    <header class="sheet-header">
      <div class="sheet-title">
        <strong>Дозировки</strong>
        <small>Выберите нужное количество</small>
      </div>
    </header>
    <div class="sheet-body">
      <table class="features-table">
        <thead>
          <tr>
            <th>Вид</th>
            <th>Цена</th>
            <th>Склад</th>
            <th class="th-qty">Кол-во</th>
          </tr>
        </thead>
        <tbody>
          ${features.map(f => `
            <tr data-feature-id="${f.onec_id}">
              <td class="td-name">${f.name}</td>
              <td class="td-price">${Number(f.price).toLocaleString("ru-RU")} ₽</td>
              <td class="td-stock">${f.balance}</td>
              <td class="td-qty">
                <button class="qty-btn qty-minus" data-feature-id="${f.onec_id}" aria-label="Минус">−</button>
                <span class="qty-count" data-feature-id="${f.onec_id}">
                  ${state.cart[`${onec_id}_${f.onec_id}`] || 0}
                </span>
                <button class="qty-btn qty-plus" data-feature-id="${f.onec_id}" aria-label="Плюс">+</button>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;

    detailEl.appendChild(backdrop);
    detailEl.appendChild(sheet);

    // Qty logic
    const tbody = sheet.querySelector(".features-table tbody");

    function updateCountDisplay(featureId, count) {
        const span = sheet.querySelector(`.qty-count[data-feature-id="${featureId}"]`);
        if (span) span.textContent = String(count);
    }

    function changeQty(featureId, delta) {
        const key = `${onec_id}_${featureId}`;
        const current = state.cart[key] || 0;
        const next = Math.max(0, current + delta);
        if (next === 0) delete state.cart[key];
        else state.cart[key] = next;
        saveCart();
        updateCountDisplay(featureId, next);
    }

    tbody.addEventListener("click", (e) => {
        const minus = e.target.closest(".qty-minus");
        const plus = e.target.closest(".qty-plus");
        if (minus) {
            e.stopPropagation();
            changeQty(minus.dataset.featureId, -1);
        } else if (plus) {
            e.stopPropagation();
            changeQty(plus.dataset.featureId, +1);
        }
    });

    // Sheet open/close + swipe
    let sheetOpen = false;
    let animating = false;
    let startY = 0;
    let currentY = 0;
    let dragging = false;
    const DRAG_CLOSE_THRESHOLD = 90; // px

    function setSheetTranslateY(y) {
        sheet.style.transform = `translateX(-50%) translateY(${y}px)`;
    }

    // MainButton bindings
    function bindMainOpen() {
        showMainButton("В корзину", () => {
            if (!sheetOpen && !animating) openSheet();
        });
    }
    function bindMainClose() {
        showMainButton("Закрыть", () => {
            if (sheetOpen && !animating) closeSheet();
        });
    }

    function openSheet() {
        hideBackButton();
        if (sheetOpen || animating) return;
        sheetOpen = true;
        animating = true;

        backdrop.style.display = "block";
        requestAnimationFrame(() => {
            backdrop.classList.add("sheet-backdrop--visible");
            sheet.classList.add("sheet--visible");
            sheet.style.transition = "transform .22s ease";
            setSheetTranslateY(0);
        });

        if (isTelegramApp()) {
            // BackButton should ALWAYS navigate to "/", do not change it here
            bindMainClose(); // main temporarily closes the sheet
        }

        setTimeout(() => {
            animating = false;
            sheet.style.transition = "";
        }, 240);
    }

    function closeSheet() {
        if (!sheetOpen || animating) return;
        showBackButton(() => navigateTo("/"))
        sheetOpen = false;
        animating = true;

        sheet.classList.remove("sheet--visible");
        backdrop.classList.remove("sheet-backdrop--visible");

        sheet.style.transition = "transform .18s ease";
        const sheetHeight = sheet.offsetHeight || window.innerHeight;
        setSheetTranslateY(Math.max(sheetHeight, window.innerHeight * 0.6));

        setTimeout(() => {
            backdrop.style.display = "none";
            sheet.style.transition = "";
            sheet.style.transform = "";
            animating = false;

            if (isTelegramApp()) {
                // Keep BackButton logic intact (navigate to "/"), only restore main open behavior
                bindMainOpen();
            }
        }, 200);
    }

    function onDragStart(clientY) {
        if (!sheetOpen) return;
        dragging = true;
        startY = clientY;
        currentY = 0;
        sheet.style.transition = "none";
    }

    function onDragMove(clientY) {
        if (!dragging) return;
        currentY = Math.max(0, clientY - startY);
        const damped = currentY * 0.9;
        setSheetTranslateY(damped);
        const opacity = Math.max(0, Math.min(1, 1 - damped / 300));
        backdrop.style.setProperty("--sheet-backdrop-opacity", String(opacity));
        backdrop.style.background = `rgba(17,17,17,${0.35 * opacity})`;
    }

    function onDragEnd() {
        if (!dragging) return;
        dragging = false;
        sheet.style.transition = "transform .18s ease";
        if (currentY > DRAG_CLOSE_THRESHOLD) {
            closeSheet();
        } else {
            setSheetTranslateY(0);
            requestAnimationFrame(() => {
                sheet.style.transition = "";
            });
            backdrop.style.background = "";
            backdrop.style.removeProperty("--sheet-backdrop-opacity");
        }
    }

    // Touch/Mouse drag on handle and header
    const dragTargets = [sheet.querySelector(".sheet-handle"), sheet.querySelector(".sheet-header")].filter(Boolean);
    dragTargets.forEach((el) => {
        el.addEventListener("touchstart", (e) => onDragStart(e.touches[0].clientY), {passive: true});
        el.addEventListener("touchmove", (e) => {
            if (dragging) e.preventDefault();
            onDragMove(e.touches[0].clientY);
        }, {passive: false});
        el.addEventListener("touchend", onDragEnd);
        el.addEventListener("mousedown", (e) => onDragStart(e.clientY));
    });
    window.addEventListener("mousemove", (e) => { if (dragging) onDragMove(e.clientY); });
    window.addEventListener("mouseup", onDragEnd);

    // Click backdrop closes
    backdrop.addEventListener("click", closeSheet);

    // Telegram buttons initial bindings
    if (isTelegramApp()) {
        // BackButton MUST always navigate to "/"
        showBackButton(() => navigateTo("/"));
        bindMainOpen();

        window.addEventListener("popstate", () => {
            hideMainButton();
        }, {once: true});
    }
}

/* ----------------------------- styles ------------------------------ */
function ensureSheetStyles() {
    if (document.getElementById("pretty-bottom-sheet-styles")) return;
    const css = `
  .pd-wrap{padding:12px 12px 0 12px}
  .pd-card{background:#fff;border-radius:16px;box-shadow:var(--shadow-sm,0 1px 3px rgba(0,0,0,.1));overflow:hidden}
  .pd-img{display:flex;justify-content:center;align-items:center;background:linear-gradient(180deg,#fafafa,#f3f3f3)}
  .pd-img img{width:100%;max-height:42vh;object-fit:contain}
  .pd-info{padding:12px 14px 16px}
  .pd-title{margin:0 0 6px 0;font-size:18px;line-height:1.25}
  .pd-desc{margin:0;color:#555;font-size:14px}

  .sheet-backdrop{
    position:fixed;inset:0;background:rgba(17,17,17,.0);
    transition:background .2s ease;z-index:40;backdrop-filter:saturate(140%) blur(2px);
  }
  .sheet-backdrop--visible{background:rgba(17,17,17,.35)}

  .sheet{
    position:fixed;left:50%;bottom:0;transform:translateX(-50%) translateY(100%);
    width:var(--phone-width,390px);max-width:100vw;background:#fff;
    border-top-left-radius:20px;border-top-right-radius:20px;
    box-shadow:0 -8px 30px rgba(0,0,0,.18);z-index:41;
    display:grid;grid-template-rows:auto 1fr;
    max-height:78vh; 
    will-change:transform;
  }
  .sheet--visible{transform:translateX(-50%) translateY(0)}

  .sheet-handle{padding-top:10px;padding-bottom:4px;display:flex;justify-content:center}
  .sheet-notch{width:44px;height:5px;border-radius:5px;background:#DADDE2}

  .sheet-header{
    display:flex;align-items:center;justify-content:space-between;gap:8px;
    padding:8px 14px 10px 14px;position:sticky;top:0;background:#fff;border-bottom:1px solid #f1f1f1;z-index:1;
  }
  .sheet-title{display:flex;flex-direction:column}
  .sheet-title strong{font-size:16px}
  .sheet-title small{color:#777;font-size:12px}

  .sheet-body{overflow:auto;-webkit-overflow-scrolling:touch;padding:6px 8px 12px 8px}
  .features-table{width:100%;border-collapse:separate;border-spacing:0 8px}
  .features-table thead th{
    text-align:left;font-size:12px;
    color: var(--tg-theme-button-text-color, #fff);
    background: var(--tg-theme-button-color, #1E669E);
    font-weight:600;
    padding:4px 8px;
  }
  .features-table thead th:first-child { border-top-left-radius: 10px; }
  .features-table thead th:last-child { border-top-right-radius: 10px; }

  .features-table tbody tr{
    background:#fff;border:1px solid #EEF0F3;border-radius:14px;box-shadow:0 1px 2px rgba(0,0,0,.04);
  }
  .features-table tbody td{
    padding:10px 8px;vertical-align:middle;
  }
  .td-name{font-weight:600}
  .td-price{white-space:nowrap}
  .td-stock{color:#6B7280}
  .th-qty,.td-qty{text-align:center}
  
  .qty-btn{
    width:34px;height:34px;border-radius:10px;border:0;
    background: var(--tg-theme-secondary-bg-color, #F1F3F5);
    color: var(--tg-theme-hint-color, #6B7280);
    font-size:18px;line-height:1;cursor:pointer;transition:transform .05s ease, filter .15s;
  }
  .qty-btn.qty-plus {
    background: var(--tg-theme-button-color, #1E669E);
    color: var(--tg-theme-button-text-color, #fff);
  }
  .qty-btn:active{transform:scale(.98);filter: brightness(0.95);}
  .qty-count{display:inline-block;min-width:2ch;text-align:center;font-weight:600;margin:0 10px}
  `;
    const style = document.createElement("style");
    style.id = "pretty-bottom-sheet-styles";
    style.textContent = css;
    document.head.appendChild(style);
}