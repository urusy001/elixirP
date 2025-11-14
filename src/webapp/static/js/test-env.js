// test-env.js
import { PvzMapWidget } from "./pvz-widget.js";

function getPinSvg(color = "#1E669E") {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="38" viewBox="0 0 28 38">
    <path fill="${color}" fill-rule="evenodd"
     d="M14 0C6.268 0 0 6.268 0 14c0 10.333 12.25 22.342 13.13 23.51.39.51 1.35.51 1.74 0C15.75 36.342 28 24.333 28 14 28 6.268 21.732 0 14 0zm0 21c-3.866 0-7-3.134-7-7s3.134-7 7-7 7 3.134 7 7-3.134 7-7 7z"/>
  </svg>`;
}
window.defaultPin = `data:image/svg+xml;utf8,${encodeURIComponent(getPinSvg("#6b7280"))}`;
window.selectedPin = `data:image/svg+xml;utf8,${encodeURIComponent(getPinSvg("#D32F2F"))}`;

const CITY_DEFAULTS = {
    "Москва": [55.751, 37.618],
    "Санкт-Петербург": [59.938, 30.314],
    "Казань": [55.796, 49.106],
    "Екатеринбург": [56.838, 60.597],
    "Новосибирск": [55.008, 82.935]
};

let widget = null;

const citySelect = document.getElementById("city-select");
const searchButton = document.getElementById("search-button");
const fabSearchBtn = document.getElementById("fab-search");

function init() {
    widget = new PvzMapWidget("widget-container", {
        onPvzSelected: () => {}
    });

    const coords = CITY_DEFAULTS[citySelect.value] || CITY_DEFAULTS["Москва"];
    widget.initMap(coords, 11);

    citySelect.addEventListener("change", () => {
        const c = CITY_DEFAULTS[citySelect.value] || coords;
        if (widget.map) widget.map.setCenter(c, 11);
    });

    const runSearch = async () => {
        if (!widget?.map) return;
        const center = widget.map.getCenter();

        const setBusy = (busy) => {
            if (searchButton) {
                searchButton.disabled = busy;
                searchButton.textContent = busy ? "Поиск…" : "Искать ПВЗ";
            }
            if (fabSearchBtn) {
                fabSearchBtn.disabled = busy;
                fabSearchBtn.textContent = busy ? "Поиск…" : "Искать ПВЗ";
            }
        };

        setBusy(true);
        try { await widget.search(center); }
        finally { setBusy(false); }
    };

    searchButton.disabled = false;
    searchButton.addEventListener("click", runSearch);
    fabSearchBtn?.addEventListener("click", runSearch);
}

ymaps.ready(init);