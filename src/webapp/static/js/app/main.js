// static/js/app/main.js
import {renderCurrentPath, enablePopstate} from "./router.js";
import {initSearchOverlay} from "./pages/search.js";

document.addEventListener("DOMContentLoaded", async () => {
    initSearchOverlay();
    enablePopstate();
    await renderCurrentPath();
});