// ============================================================================
// checkout.js — Unified Delivery Checkout (CDEK + Yandex auto-locating PVZ widget)
// ============================================================================
import { showLoader, hideLoader } from "../ui/loader.js";
import { hideCartIcon } from "../ui/cart-icon.js";
import {isTelegramApp, showBackButton, showMainButton} from "../ui/telegram.js";
import { navigateTo } from "../router.js";
import { fetchPVZByCode, getSelectedPVZCode } from "../../services/pvzService.js";
import { YandexPvzWidget } from "./yandex-pvz-widget.js";
import {
    cartPageEl,
    checkoutPageEl,
    contactPageEl, detailEl,
    headerTitle, listEl,
    paymentPageEl,
    processPaymentEl,
    searchBtnEl,
    toolbarEl
} from "./constants.js";

// ---------------------------------------------------------------------------
// DOM references
// ---------------------------------------------------------------------------

// Map container IDs
const CDEK_ID = "cdek-map-container";
const YANDEX_ID = "yandex-map-container";
const YANDEX_LIST_ID = "yandex-list";

let _toggleLock = false;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function ensureMapContainer(id) {
    let el = document.getElementById(id);
    if (!el) {
        el = document.createElement("div");
        el.id = id;
        Object.assign(el.style, {
            width: "100%",
            height: "500px",
            marginTop: "12px",
            display: "none",
            borderRadius: "12px",
            border: "1px solid #ccc",
            overflow: "hidden",
        });
        checkoutPageEl.appendChild(el);
    }
    return el;
}

function ensureListContainer(id, afterEl) {
    let el = document.getElementById(id);
    if (!el) {
        el = document.createElement("div");
        el.id = id;
        Object.assign(el.style, {
            marginTop: "8px",
            border: "1px solid #e5e7eb",
            borderRadius: "12px",
            overflow: "hidden",
            background: "#fff",
        });
        afterEl.insertAdjacentElement("afterend", el);
    }
    return el;
}

// ---------------------------------------------------------------------------
// Yandex Maps API Loader
// ---------------------------------------------------------------------------
let _ymapsReady;
async function ensureYmapsReady() {
    if (window.ymaps?.Map) {
        await new Promise((res) => ymaps.ready(res));
        return;
    }
    if (!_ymapsReady) {
        _ymapsReady = new Promise((resolve, reject) => {
            const existing = document.getElementById("ymaps-api");
            const onLoad = () => ymaps.ready(resolve);
            const onError = () => reject(new Error("Failed to load Yandex Maps"));
            if (existing) {
                existing.addEventListener("load", onLoad, { once: true });
                existing.addEventListener("error", onError, { once: true });
            } else {
                const s = document.createElement("script");
                s.id = "ymaps-api";
                s.src =
                    "https://api-maps.yandex.ru/2.1/?apikey=bb7d36f8-1e64-415c-80d2-12d77317718d&lang=ru_RU";
                s.async = true;
                s.defer = true;
                s.onload = onLoad;
                s.onerror = onError;
                document.head.appendChild(s);
            }
            setTimeout(() => reject(new Error("Yandex Maps load timeout")), 20000);
        });
    }
    await _ymapsReady;
}

// ---------------------------------------------------------------------------
// Delivery service toggle header
// ---------------------------------------------------------------------------
function createDeliveryHeader(currentService = "CDEK") {
    document.querySelector(".delivery-toggle-container")?.remove();

    const header = document.createElement("div");
    header.className = "delivery-toggle-container";
    Object.assign(header.style, {
        display: "flex",
        justifyContent: "space-between",
        alignItems: "stretch",
        width: "100%",
        background: "#1E669E",
        borderRadius: "8px",
        overflow: "hidden",
        marginBottom: "10px",
        userSelect: "none",
        position: "relative",
        whiteSpace: "nowrap",
    });

    const makeButton = (label) => {
        const btn = document.createElement("div");
        btn.textContent = label;
        Object.assign(btn.style, {
            flex: "1 1 50%",
            textAlign: "center",
            color: "#fff",
            fontSize: "14px",
            fontWeight: "500",
            padding: "10px 0",
            cursor: "pointer",
            transition: "background 0.25s ease",
            background: "transparent",
        });
        return btn;
    };

    const cdekBtn = makeButton("CDEK");
    const yandexBtn = makeButton("Yandex");

    const indicator = document.createElement("div");
    Object.assign(indicator.style, {
        position: "absolute",
        bottom: "0",
        left: currentService === "CDEK" ? "0" : "50%",
        width: "50%",
        height: "3px",
        background: "#fff",
        transition: "left 0.3s ease",
    });

    header.append(cdekBtn, yandexBtn, indicator);
    checkoutPageEl.prepend(header);

    const cdekContainer = ensureMapContainer(CDEK_ID);
    const yandexContainer = ensureMapContainer(YANDEX_ID);
    const yandexList = ensureListContainer(YANDEX_LIST_ID, yandexContainer);

    const updateSelection = async (service) => {
        if (_toggleLock) return;
        _toggleLock = true;

        sessionStorage.setItem("selected_delivery_service", service);
        indicator.style.left = service === "CDEK" ? "0" : "50%";
        cdekBtn.style.background = service === "CDEK" ? "#17517D" : "transparent";
        yandexBtn.style.background = service === "Yandex" ? "#17517D" : "transparent";

        cdekContainer.style.display = service === "CDEK" ? "block" : "none";
        yandexContainer.style.display = service === "Yandex" ? "block" : "none";
        yandexList.style.display = service === "Yandex" ? "block" : "none";

        await new Promise((r) => requestAnimationFrame(r));

        try {
            if (service === "CDEK") {
                await initCDEKWidget();
            } else {
                await initYandexWidget();
            }
        } finally {
            _toggleLock = false;
        }
    };

    cdekBtn.onclick = () => updateSelection("CDEK");
    yandexBtn.onclick = () => updateSelection("Yandex");

    updateSelection(currentService);
}

// ---------------------------------------------------------------------------
// CDEK Widget initialization
// ---------------------------------------------------------------------------
async function initCDEKWidget(coords = [55.75, 37.61]) {
    if (!window.CDEKWidget) {
        hideLoader();
        return;
    }

    if (window.cdekWidgetInstance) {
        hideLoader();
        return window.cdekWidgetInstance;
    }

    const container = document.getElementById(CDEK_ID);
    if (!container) return;

    container.style.display = "block";
    if (!container.style.height) container.style.height = "500px";
    await new Promise((r) => requestAnimationFrame(r));

    try {
        window.cdekWidgetInstance = new window.CDEKWidget({
            root: CDEK_ID,
            apiKey: "bb7d36f8-1e64-415c-80d2-12d77317718d",
            servicePath: "api/v1/delivery/cdek",
            from: {
                city: "Уфа",
                code: 256,
                address: "ул. Революционная, 98/1 блок А",
                country_code: "RU",
                postal_code: "450078",
                coords: [55.986566, 54.729366],
            },
            defaultLocation: coords,
            canChoose: true,
            hideFilters: { have_cashless: false, have_cash: false, is_dressing_room: false },
            hideDeliveryOptions: { office: false, door: false },
            goods: [{ width: 10, height: 10, length: 10, weight: 10 }],
            onReady: () => {
                container.style.display = "block";
                hideLoader();
            },
            onChoose: (mode, tariff, address) => {
                sessionStorage.setItem(
                    "selected_delivery",
                    JSON.stringify({ deliveryMode: mode, tariff, address }),
                );
                if (address?.code) fetchPVZByCode(address.code);
                createProceedButton("Продолжить оформление");
            },
            onCalculate: async () => {
                const pvzCode = getSelectedPVZCode();
                if (pvzCode) fetchPVZByCode(pvzCode);
            },
        });
    } catch (err) {
        console.error("CDEK widget init failed:", err);
    }
    return window.cdekWidgetInstance;
}

// ---------------------------------------------------------------------------
// Yandex PVZ Widget initialization (auto-locating)
// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// Yandex PVZ Widget initialization (show/reopen without re-init on toggle)
// ---------------------------------------------------------------------------
let ydwInstance = null;

async function initYandexWidget() {
    const container = document.getElementById(YANDEX_ID);
    if (!container) return;

    // make visible & ensure height
    container.style.display = "block";
    if (!container.style.height) container.style.height = "500px";
    await new Promise((r) => requestAnimationFrame(r));

    if (!ydwInstance) {
        // first time only: load API + init widget
        await ensureYmapsReady();

        ydwInstance = new YandexPvzWidget(YANDEX_ID, {
            listContainerId: YANDEX_LIST_ID,
            radiusMeters: 12000,
            autoLocate: true,
            autoSearch: true,
            onReady: () => {},
            onChoose: (_pvz, payload) => {
                sessionStorage.setItem(
                    "selected_delivery",
                    JSON.stringify({
                        deliveryMode: payload.deliveryMode,
                        tariff: null,
                        address: {
                            code: payload.code,
                            address: payload.address,
                            coords: payload.coords,
                            name: payload.name,
                            phone: payload.phone,
                            schedule: payload.schedule,
                        },
                    }),
                );
                createProceedButton("Продолжить оформление");
            },
        });

        await ydwInstance.init(); // first load only
    } else {
        // subsequent toggles: DO NOT re-init — just reopen/refresh
        try {
            // if the map exists, refresh sizing after container became visible
            ydwInstance.map?.container.fitToViewport?.();

            // reopen last UI state (door placemark balloon > selected PVZ balloon)
            if (ydwInstance._doorPlacemark) {
                ydwInstance._doorPlacemark.balloon?.open?.();
            } else if (ydwInstance._selectedId) {
                try { ydwInstance.manager?.objects.balloon.close(); } catch {}
                ydwInstance.manager?.objects.balloon.open(ydwInstance._selectedId);
            }
        } catch (e) {
            console.warn("Yandex widget reopen failed, falling back to init:", e);
            // fallback: if something went wrong (e.g., map was destroyed), re-init once
            try { await ydwInstance.init(); } catch {}
        }
    }

    hideLoader();
}

// ---------------------------------------------------------------------------
// Proceed button
// ---------------------------------------------------------------------------
export function createProceedButton(
    label = "Продолжить оформление",
    onClick = () => navigateTo("/contact"),
) {
    if (isTelegramApp()) {
        showMainButton(label, onClick);
    } else {
        let btn = document.querySelector(".checkout-proceed-btn");
        if (!btn) {
            btn = document.createElement("button");
            btn.className = "checkout-proceed-btn";
            checkoutPageEl.appendChild(btn);
        }
        btn.textContent = label;
        btn.onclick = onClick;
    }
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------
export async function renderCheckoutPage() {
    showLoader();
    showBackButton(() => navigateTo("/cart"));
    cartPageEl.style.display = "none";
    detailEl.style.display = "none";
    listEl.style.display = "none";
    toolbarEl.style.display = "none";
    contactPageEl.style.display = "none";
    searchBtnEl.style.display = "none";
    headerTitle.textContent = "Доставка";
    paymentPageEl.style.display = "none";
    processPaymentEl.style.display = "none";

    hideCartIcon();

    checkoutPageEl.style.display = "block";
    await new Promise((r) => requestAnimationFrame(r));

    createDeliveryHeader("CDEK");
    console.log("✅ Checkout initialized");
}