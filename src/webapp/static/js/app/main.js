// static/js/app/main.js
import { initCartIcon } from "./ui/cart-icon.js";
import { renderCurrentPath, enablePopstate } from "./router.js";
import { initSearchOverlay } from "./pages/search.js";

document.addEventListener("DOMContentLoaded", async () => {
  initSearchOverlay();
  enablePopstate();
  initCartIcon();
  await renderCurrentPath();
});