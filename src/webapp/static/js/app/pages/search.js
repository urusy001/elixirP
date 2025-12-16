// search.js
import { renderProductDetailPage } from "./product-detail.js";
import { searchProducts } from "../../services/productService.js";
import { navBottomEl } from "./constants.js";

function debounce(fn, delay) {
    let t;
    return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn(...args), delay);
    };
}

// ---- STATES ----
let searchMode = "search";          // "search" | "favorite"
let favoriteClickHandler = null;    // callback for heart click
let searchBtnRef = null;            // cache for the button element
let isFavoriteActive = false;       // local boolean tracking state

function getBtn() {
    return searchBtnRef || document.getElementById("search-btn");
}

/**
 * Updates the visual classes/attributes based on isFavoriteActive
 */
function updateVisuals() {
    const btn = getBtn();
    if (!btn) return;

    if (isFavoriteActive) {
        btn.classList.add("toolbar-btn--favorite-active");
        btn.setAttribute("aria-pressed", "true");
        btn.setAttribute("aria-label", "В избранном");
    } else {
        btn.classList.remove("toolbar-btn--favorite-active");
        btn.setAttribute("aria-pressed", "false");
        btn.setAttribute("aria-label", "Добавить в избранное");
    }
}

/**
 * Public function to set the state (e.g. from API or optimistic update)
 */
export function setFavoriteButtonActive(active) {
    isFavoriteActive = !!active;
    updateVisuals();
}

/**
 * Switches the Search button to a Favorite (Heart) button.
 */
export function setSearchButtonToFavorite(onClick, initialActive = false) {
    searchMode = "favorite";
    favoriteClickHandler = typeof onClick === "function" ? onClick : null;
    isFavoriteActive = !!initialActive;

    const btn = getBtn();
    if (!btn) return;
    searchBtnRef = btn; // ensure cache

    // Save original HTML/Label if not already saved
    if (!btn.dataset.originalIconHtml) {
        btn.dataset.originalIconHtml = btn.innerHTML;
    }
    if (!btn.dataset.originalAriaLabel && btn.getAttribute("aria-label")) {
        btn.dataset.originalAriaLabel = btn.getAttribute("aria-label");
    }

    // Render Heart Icon
    btn.innerHTML = `
        <svg class="toolbar-icon toolbar-icon--heart" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5
                     2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09
                     C13.09 3.81 14.76 3 16.5 3
                     19.58 3 22 5.42 22 8.5
                     c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
        </svg>
    `;
    btn.classList.add("toolbar-btn--favorite");

    // Apply initial state
    updateVisuals();
}

/**
 * Restores the button back to the Search (Magnifying glass).
 */
export function restoreSearchButtonToSearch() {
    searchMode = "search";
    favoriteClickHandler = null;
    isFavoriteActive = false;

    const btn = getBtn();
    if (!btn) return;

    // Restore original HTML
    if (btn.dataset.originalIconHtml) {
        btn.innerHTML = btn.dataset.originalIconHtml;
    }

    // Restore label
    if (btn.dataset.originalAriaLabel) {
        btn.setAttribute("aria-label", btn.dataset.originalAriaLabel);
    } else {
        btn.removeAttribute("aria-label");
        btn.removeAttribute("aria-pressed");
    }

    btn.classList.remove("toolbar-btn--favorite", "toolbar-btn--favorite-active");
}

// ---- INIT ----

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
        if (navBottomEl) {
            navBottomEl.style.display = "none";
        }
        searchInput.focus();
    }

    function closeOverlay() {
        if (!searchOverlay || !searchInput || !historyList) return;
        searchOverlay.classList.remove("active");
        if (navBottomEl) {
            navBottomEl.style.display = "flex";
        }
        searchInput.value = "";
        historyList.innerHTML = "";
    }

    // MAIN CLICK HANDLER
    searchBtn?.addEventListener("click", async (e) => {
        // Stop propagation just in case
        e.stopPropagation();

        if (searchMode === "favorite") {
            // Logic for Heart
            if (favoriteClickHandler) {
                // Pass the CURRENT state so handler knows what to do
                favoriteClickHandler(isFavoriteActive);
            }
        } else {
            // Logic for Search
            openSearchOverlay();
        }
    });

    closeSearch?.addEventListener("click", closeOverlay);

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
            const data = await searchProducts({ q: query, limit: 50 });
            if (!historyList) return;

            const results = Array.isArray(data?.results) ? data.results : [];

            historyList.innerHTML = results
                .map((p) => {
                    const id = p.url?.split("/product/")[1] || "";
                    return `
                        <li data-onec-id="${id}">
                            <div>${p.name}</div>
                        </li>
                    `;
                })
                .join("");

            historyList.querySelectorAll("li").forEach((li) => {
                li.addEventListener("click", async () => {
                    const id = li.dataset.onecId;
                    if (!id) return;
                    history.pushState({ productId: id }, "", `/product/${id}`);
                    await renderProductDetailPage(id);
                    closeOverlay();
                    navBottomEl.style.display = "none";
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