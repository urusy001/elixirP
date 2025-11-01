// static/js/app/main.js
import {initCartIcon} from "./ui/cart-icon.js?v=1";
import {enablePopstate, renderCurrentPath} from "./router.js?v=1";
import {initSearchOverlay} from "./pages/search.js?v=1";

document.addEventListener("DOMContentLoaded", async () => {
    initSearchOverlay();
    enablePopstate();
    initCartIcon();
    await renderCurrentPath();
});