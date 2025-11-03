import { searchProducts } from "../../services/productService.js?v=1";
import { navigateTo } from "../router.js?v=1";

function debounce(fn, delay) {
    let t;
    return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn(...args), delay);
    };
}

export function initSearchOverlay() {
    const searchBtn = document.getElementById("search-btn");
    const searchOverlay = document.getElementById("search-overlay");
    const searchInput = document.getElementById("search-input");
    const closeSearch = document.getElementById("close-search");
    const historyList = document.getElementById("history-list");

    // --- Open overlay
    searchBtn?.addEventListener("click", () => {
        searchOverlay.classList.add("active");
        searchInput.focus();
    });

    // --- Close overlay (X button)
    closeSearch?.addEventListener("click", () => {
        closeOverlay();
    });

    // --- Helper to close overlay and reset
    function closeOverlay() {
        searchOverlay.classList.remove("active");
        searchInput.value = "";
        historyList.innerHTML = "";
    }

    // --- Click outside (blank area) closes overlay
    searchOverlay?.addEventListener("click", e => {
        // If user clicked directly on the overlay (not on child elements)
        if (e.target === searchOverlay) {
            closeOverlay();
        }
    });

    // --- Perform search
    async function performSearch(query) {
        if (!query) {
            historyList.innerHTML = "";
            return;
        }
        try {
            const data = await searchProducts({ q: query, limit: 50 });
            historyList.innerHTML = (data.results || [])
                .map(
                    p => `
            <li data-onec-id="${p.url.split("/product/")[1]}">
              <div>${p.name}</div>
            </li>`
                )
                .join("");

            historyList.querySelectorAll("li").forEach(li => {
                li.addEventListener("click", () => {
                    const id = li.dataset.onecId;
                    closeOverlay();
                    navigateTo(`/product/${id}`);
                });
            });
        } catch (e) {
            console.error("Search failed:", e);
        }
    }

    // --- Debounced search input
    searchInput?.addEventListener(
        "input",
        debounce(e => performSearch(e.target.value), 300)
    );
}