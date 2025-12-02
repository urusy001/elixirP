import {navigateTo} from "../router.js";

export function setupBottomNav() {
    const items = document.querySelectorAll(".bottom-nav__item");
    items.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            const route = item.dataset.route;
            navigateTo(route);
        });
    });
}