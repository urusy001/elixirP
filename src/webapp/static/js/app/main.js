// static/js/app/main.js
import {renderCurrentPath, enablePopstate} from "./router.js";
import {initSearchOverlay} from "./pages/search.js";
import {initCartBadge} from "./ui/cart-badge.js";

document.addEventListener("DOMContentLoaded", async () => {
    initCartBadge();
    initSearchOverlay();
    enablePopstate();
    await renderCurrentPath();
});