import {getProductDetail} from "../../services/productService.js";
import {withLoader} from "../ui/loader.js";
import {state, saveCart} from "../state.js";
import {
    showBackButton,
    showMainButton,
    updateMainButton,
    hideMainButton,
    hideBackButton,
    isTelegramApp,
} from "../ui/telegram.js";
import {navigateTo} from "../router.js";
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


export async function renderProductDetailPage(onec_id) {
    toolbarEl.style.display = "none";
    listEl.style.display = "none";
    contactPageEl.style.display = "none";
    cartPageEl.style.display = "none";
    checkoutPageEl.style.display = "none";
    paymentPageEl.style.display = "none";
    headerTitle.textContent = "Информация о продукте";
    searchBtnEl.style.display = "flex";
    detailEl.style.display = "block";
    processPaymentEl.style.display = "none";

    const data = await withLoader(() => getProductDetail(onec_id));
    if (data?.error) {
        detailEl.innerHTML = `
      <div class="error-message" style="padding:20px;text-align:center">
        <h2>Ошибка загрузки</h2>
        <p>Не удалось загрузить информацию о товаре. Пожалуйста, попробуйте позже.</p>
      </div>`;
        if (isTelegramApp()) {
            hideMainButton();
            const offBack = showBackButton(() => {
                navigateTo('/');
            });
            window.addEventListener("popstate", () => offBack?.(), {once: true});
        }
        return;
    }

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
            <th>Кол-во</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>`;

    detailEl.innerHTML = `
    <div class="product-detail-container">
      <div class="product-main">
        <div class="product-image">
          <img src="${data.product.image || "/static/images/product.png"}" alt="">
        </div>
        <div class="product-info">
          <h1></h1>
          <div class="product-description"></div>
          <div class="product-meta">
            ${data.product.usage ? `<p><strong>Применение:</strong> <span class="product-usage"></span></p>` : ""}
            ${data.product.expiration ? `<p><strong>Срок годности:</strong> <span class="product-expiration"></span></p>` : ""}
          </div>
        </div>
      </div>
    </div>`;

    // Populate trusted HTML content
    const infoEl = detailEl.querySelector(".product-info");
    infoEl.querySelector("h1").textContent = data.product.name;
    infoEl.querySelector(".product-description").innerHTML = data.product.description || "Нет описания";
    if (data.product.usage) infoEl.querySelector(".product-usage").innerHTML = data.product.usage;
    if (data.product.expiration) infoEl.querySelector(".product-expiration").innerHTML = data.product.expiration;
    detailEl.querySelector(".product-image img").alt = data.product.name;

    // Clamp / expand description
    const descEl = infoEl.querySelector(".product-description");
    setupDescriptionClamp(descEl);

    // Create bottom sheet
    const sheet = createBottomSheet(featuresTableHtml);
    document.body.appendChild(sheet.root);

    const tbody = sheet.root.querySelector(".features-table tbody");
    const headers = sheet.root.querySelectorAll(".features-table th[data-key]");
    let sortKey = "price";
    let sortAsc = true;

    const getCartKey = (f) => `${onec_id}_${f.id ?? f.onec_id ?? f.name}`;
    const getQty = (key) => Number(state.cart?.[key] || 0);
    const setQty = (key, qty) => {
        if (!state.cart) state.cart = {};
        if (qty <= 0) delete state.cart[key];
        else state.cart[key] = qty;
        saveCart();
    };

    const sortVal = (item, key) => {
        if (key === "price" || key === "balance") return Number(item[key]) || 0;
        const v = item[key];
        return typeof v === "string" ? v.toLowerCase() : v ?? "";
    };

    const renderTableBody = () => {
        const sorted = [...features].sort((a, b) => {
            const av = sortVal(a, sortKey);
            const bv = sortVal(b, sortKey);
            if (typeof av === "string" && typeof bv === "string") {
                return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
            }
            return sortAsc ? av - bv : bv - av;
        });

        tbody.innerHTML = "";
        for (const f of sorted) {
            const key = getCartKey(f);
            const tr = document.createElement("tr");

            const balNum = Number(f.balance) || 0;
            const isOOS = balNum <= 0;

            tr.dataset.key = key;
            tr.dataset.balance = String(balNum);
            if (isOOS) tr.classList.add("oos-row");

            const tdName = document.createElement("td");
            tdName.textContent = f.name;

            const tdPrice = document.createElement("td");
            tdPrice.textContent = `${Number(f.price).toLocaleString("ru-RU")} ₽`;

            const tdBal = document.createElement("td");
            tdBal.innerHTML = isOOS
                ? `<span class="oos-badge" title="Ожидается поставка">Нет на складе</span>`
                : String(balNum);

            const tdQty = document.createElement("td");
            if (isOOS) {
                // No controls for out-of-stock items
                tdQty.innerHTML = ``;
            } else {
                tdQty.innerHTML = `
          <div class="cart-qty-ctrl">
            <button class="qty-dec" aria-label="Уменьшить количество">−</button>
            <span class="qty-val">${getQty(key)}</span>
            <button class="qty-inc" aria-label="Увеличить количество">+</button>
          </div>`;
            }

            tr.append(tdName, tdPrice, tdBal, tdQty);
            tbody.appendChild(tr);
        }

        headers.forEach((h) => {
            let label =
                h.dataset.key === "name"
                    ? "Вид"
                    : h.dataset.key === "price"
                        ? "Цена"
                        : "Склад";
            if (h.dataset.key === sortKey) label += sortAsc ? " ▲" : " ▼";
            h.textContent = label;
        });
    };

    // Click sorting
    headers.forEach((h) => {
        h.style.cursor = "pointer";
        h.addEventListener("click", () => {
            const key = h.dataset.key;
            sortAsc = sortKey === key ? !sortAsc : true;
            sortKey = key;
            renderTableBody();
        });
    });

    // Quantity logic (ignore clicks for OOS rows)
    tbody.addEventListener("click", (e) => {
        const dec = e.target.closest(".qty-dec");
        const inc = e.target.closest(".qty-inc");
        if (!dec && !inc) return;

        const tr = e.target.closest("tr");
        const balance = Number(tr.dataset.balance || 0);
        if (balance <= 0) return; // out of stock: ignore

        const key = tr.dataset.key;
        const span = tr.querySelector(".qty-val");

        let qty = getQty(key);
        if (dec) qty = Math.max(0, qty - 1);
        if (inc) qty = Math.min(balance, qty + 1);

        setQty(key, qty);
        span.textContent = qty;
    });

    renderTableBody();

    // Telegram MainButton + BackButton handling
    if (isTelegramApp()) {
        let offBack;

        const setBackForProduct = () => {
            if (offBack) offBack();
            offBack = showBackButton(() => {
                if (sheet.isOpen()) sheet.close(true);
                navigateTo('/');
            });
        };

        // initially show Back for product page
        setBackForProduct();

        const toggleSheet = () => {
            if (sheet.isOpen()) {
                // Close; onClose will restore Back + label
                sheet.close(false);
            } else {
                sheet.open();
                hideBackButton();
                updateMainButton("Скрыть варианты");
            }
        };

        showMainButton("Выбрать дозировку", toggleSheet);

        // Unify close behavior from ALL paths (MainButton, backdrop, drag)
        sheet.onClose(() => {
            updateMainButton("Выбрать дозировку");
            setBackForProduct();
        });

        window.addEventListener(
            "popstate",
            () => {
                offBack?.();
                hideMainButton();
                sheet.close(true);
            },
            {once: true}
        );
    } else {
        const openSheetBtn = document.createElement("button");
        openSheetBtn.textContent = "Выбрать дозировку";
        openSheetBtn.className = "buy-btn";
        openSheetBtn.onclick = () => sheet.open();
        detailEl.querySelector(".product-detail-container").appendChild(openSheetBtn);
    }
}

/* ============================ Helpers ============================ */

function createBottomSheet(innerHTML) {
    const root = document.createElement("div");
    root.className = "sheet-root";
    root.innerHTML = `
    <div class="sheet-backdrop"></div>
    <div class="sheet-panel" role="dialog" aria-modal="true" aria-label="Вариации">
      <div class="sheet-handle"></div>
      <div class="sheet-content">${innerHTML}</div>
    </div>`;

    const backdrop = root.querySelector(".sheet-backdrop");
    const panel = root.querySelector(".sheet-panel");

    const OPEN_CLASS = "open";
    const CLOSE_THRESHOLD_PX = 140;
    let opened = false;
    let dragging = false;
    let startY = 0;
    let currentY = 0;
    const closeCallbacks = new Set();

    const markClosed = () => {
        opened = false;
        closeCallbacks.forEach((fn) => {
            try {
                fn();
            } catch {
            }
        });
    };

    const open = () => {
        root.classList.add(OPEN_CLASS);
        opened = true;
    };

    const close = (instant = false) => {
        if (!root.classList.contains(OPEN_CLASS)) return;
        const finish = () => {
            panel.style.transition = "";
            panel.style.transform = "";
            root.classList.remove(OPEN_CLASS);
            markClosed();
        };
        if (instant) return finish();
        panel.style.transition =
            "transform var(--dur-base,220ms) var(--easing,cubic-bezier(.2,.8,.2,1))";
        panel.style.transform = "translate(-50%, 100%)";
        setTimeout(finish, 220);
    };

    const startDrag = (y) => {
        dragging = true;
        startY = y;
        currentY = y;
        panel.style.transition = "none";
    };
    const moveDrag = (y) => {
        if (!dragging) return;
        currentY = y;
        const dy = Math.max(0, currentY - startY);
        panel.style.transform = `translate(-50%, ${Math.min(100, (dy / window.innerHeight) * 100)}%)`;
    };
    const endDrag = () => {
        if (!dragging) return;
        dragging = false;
        const dy = Math.max(0, currentY - startY);
        panel.style.transition = "";
        panel.style.transform = "";
        if (dy > Math.min(CLOSE_THRESHOLD_PX, window.innerHeight * 0.2)) close();
    };

    // Backdrop click just closes; higher-level onClose handler restores UI
    backdrop.addEventListener("click", () => {
        close();
    });

    const dragMove = (e) => moveDrag(e.touches ? e.touches[0].clientY : e.clientY);
    const dragEnd = () => {
        window.removeEventListener("mousemove", dragMove);
        window.removeEventListener("mouseup", dragEnd);
        window.removeEventListener("touchmove", dragMove);
        window.removeEventListener("touchend", dragEnd);
        endDrag();
    };

    panel.addEventListener(
        "touchstart",
        (e) => {
            startDrag(e.touches[0].clientY);
            window.addEventListener("touchmove", dragMove, {passive: true});
            window.addEventListener("touchend", dragEnd, {passive: true});
        },
        {passive: true}
    );

    panel.addEventListener("mousedown", (e) => {
        startDrag(e.clientY);
        window.addEventListener("mousemove", dragMove);
        window.addEventListener("mouseup", dragEnd);
    });

    const onClose = (fn) => {
        closeCallbacks.add(fn);
        return () => closeCallbacks.delete(fn);
    };
    const isOpen = () => opened;

    return {root, open, close, onClose, isOpen};
}

/**
 * Clamp long product description to first N lines and show TikTok-style "ещё..." toggle.
 */
function setupDescriptionClamp(descEl) {
    if (!descEl) return;

    const MAX_LINES = 4; // how many lines to show when collapsed

    descEl.classList.add("product-description--clamp");
    descEl.style.setProperty("--desc-max-lines", MAX_LINES);

    // Wait for layout so scrollHeight/clientHeight are correct
    requestAnimationFrame(() => {
        // If text fits inside, no "ещё..." needed
        if (descEl.scrollHeight <= descEl.clientHeight + 1) {
            descEl.classList.remove("product-description--clamp");
            return;
        }

        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "product-description-toggle";
        toggle.textContent = "ещё...";

        // Visually like TikTok comments: below the text
        descEl.insertAdjacentElement("afterend", toggle);

        let expanded = false;

        toggle.addEventListener("click", () => {
            expanded = !expanded;
            if (expanded) {
                descEl.classList.add("product-description--expanded");
                toggle.textContent = "скрыть";
            } else {
                descEl.classList.remove("product-description--expanded");
                toggle.textContent = "ещё...";
            }
        });
    });
}