// search-overlay.js
import {renderProductDetailPage} from "./product-detail.js";
import {searchProducts} from "../../services/productService.js";
import {navBottomEl} from "./constants.js";

function debounce(fn, delay) {
    let t;
    return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn(...args), delay);
    };
}

// ---- РЕЖИМЫ КНОПКИ ПОИСКА / ИЗБРАННОЕ ----
let searchMode = "search";          // "search" | "favorite"
let favoriteClickHandler = null;    // callback для сердечка
let searchBtnRef = null;            // кэш ссылки на кнопку

/**
 * Меняет кнопку поиска на "сердечко" (избранное).
 * onClick будет вызываться при нажатии на кнопку в этом режиме.
 */
export function setSearchButtonToFavorite(onClick) {
    searchMode = "favorite";
    favoriteClickHandler = typeof onClick === "function" ? onClick : null;

    const btn = searchBtnRef || document.getElementById("search-btn");
    if (!btn) return;

    // Сохраняем оригинальную разметку и aria-label один раз
    if (!btn.dataset.originalIconHtml) {
        btn.dataset.originalIconHtml = btn.innerHTML;
    }
    if (!btn.dataset.originalAriaLabel && btn.getAttribute("aria-label")) {
        btn.dataset.originalAriaLabel = btn.getAttribute("aria-label");
    }

    // Меняем иконку на сердечко
    btn.innerHTML = `
        <svg class="toolbar-icon toolbar-icon--heart" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5
                     2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09
                     C13.09 3.81 14.76 3 16.5 3
                     19.58 3 22 5.42 22 8.5
                     c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
        </svg>
    `;
    btn.setAttribute("aria-label", "Добавить в избранное");
    btn.classList.add("toolbar-btn--favorite");
}

/**
 * Возвращает кнопке исходную иконку поиска и поведение.
 */
export function restoreSearchButtonToSearch() {
    searchMode = "search";
    favoriteClickHandler = null;

    const btn = searchBtnRef || document.getElementById("search-btn");
    if (!btn) return;

    // Восстанавливаем оригинальный HTML
    if (btn.dataset.originalIconHtml) {
        btn.innerHTML = btn.dataset.originalIconHtml;
    }

    // Восстанавливаем aria-label, если был
    if (btn.dataset.originalAriaLabel) {
        btn.setAttribute("aria-label", btn.dataset.originalAriaLabel);
    } else {
        btn.removeAttribute("aria-label");
    }

    btn.classList.remove("toolbar-btn--favorite");
}

// ---- ОСНОВНАЯ ЛОГИКА ПОИСКОВОГО ОВЕРЛЕЯ ----

export function initSearchOverlay() {
    const searchBtn = document.getElementById("search-btn");
    const searchOverlay = document.getElementById("search-overlay");
    const searchInput = document.getElementById("search-input");
    const closeSearch = document.getElementById("close-search");
    const historyList = document.getElementById("history-list");

    searchBtnRef = searchBtn;

    function openSearchOverlay() {
        if (!searchOverlay || !searchInput) return;
        searchOverlay.classList.add("active");
        navBottomEl.style.display = "none";
        searchInput.focus();
    }

    function closeOverlay() {
        if (!searchOverlay || !searchInput || !historyList) return;
        searchOverlay.classList.remove("active");
        navBottomEl.style.display = "flex";
        searchInput.value = "";
        historyList.innerHTML = "";
    }

    // Клик по кнопке теперь зависит от режима
    searchBtn?.addEventListener("click", () => {
        if (searchMode === "favorite") {
            if (favoriteClickHandler) {
                favoriteClickHandler();
            }
        } else {
            openSearchOverlay();
        }
    });

    closeSearch?.addEventListener("click", closeOverlay);

    // Закрываем при клике по пустому месту
    searchOverlay?.addEventListener("click", (e) => {
        if (e.target === searchOverlay) {
            closeOverlay();
        }
    });

    async function performSearch(query) {
        if (!query) {
            if (historyList) historyList.innerHTML = "";
            return;
        }
        try {
            const data = await searchProducts({q: query, limit: 50});
            if (!historyList) return;

            historyList.innerHTML = (data.results || [])
                .map(
                    (p) =>
                        `<li data-onec-id="${p.url.split("/product/")[1]}">
                            <div>${p.name}</div>
                        </li>`
                )
                .join("");

            historyList.querySelectorAll("li").forEach((li) => {
                li.addEventListener("click", async () => {
                    const id = li.dataset.onecId;
                    history.pushState({productId: id}, "", `/product/${id}`);
                    await renderProductDetailPage(id);
                    closeOverlay();
                });
            });
        } catch (e) {
            console.error("Search failed:", e);
        }
    }

    searchInput?.addEventListener(
        "input",
        debounce((e) => performSearch(e.target.value), 300)
    );
}