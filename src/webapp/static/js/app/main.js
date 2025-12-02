// static/js/app/main.js
import {renderCurrentPath, enablePopstate} from "./router.js";
import {initSearchOverlay} from "./pages/search.js";
import {initCartBadge} from "./ui/cart-badge.js";
import {setupBottomNav} from "./pages/home.js";

document.addEventListener("DOMContentLoaded", async () => {
    initCartBadge();
    setupBottomNav();
    initSearchOverlay();
    enablePopstate();
    await renderCurrentPath();
});