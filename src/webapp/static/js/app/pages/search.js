import { renderProductDetailPage } from "./product-detail.js";
import { searchProducts } from "../../services/productService.js";

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

    searchBtn?.addEventListener("click", () => {
        searchOverlay.classList.add("active");
        searchInput.focus();
    });

    function closeOverlay() {
        searchOverlay.classList.remove("active");
        searchInput.value = "";
        historyList.innerHTML = "";
    }

    closeSearch?.addEventListener("click", closeOverlay);

    // 🔹 Close when clicking on empty space inside overlay
    searchOverlay?.addEventListener("click", (e) => {
        // if click target *is the overlay itself* (not input or list or child)
        if (e.target === searchOverlay) {
            closeOverlay();
        }
    });

    async function performSearch(query) {
        if (!query) {
            historyList.innerHTML = "";
            return;
        }
        try {
            const data = await searchProducts({ q: query, limit: 50 });
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
                    history.pushState({ productId: id }, "", `/product/${id}`);
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