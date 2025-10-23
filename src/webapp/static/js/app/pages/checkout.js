import { showLoader, hideLoader } from "../ui/loader.js";
import { hideCartIcon } from "../ui/cart-icon.js";
import { isTelegramApp } from "../ui/telegram.js";
import { navigateTo } from "../router.js";
import { handleCheckout } from "./cart.js";

// --- Root container ---
const checkoutPageEl = document.getElementById("checkout-page");

/* -------------------------------------------------------------------------- */
/*                                USER LOCATION                               */
/* -------------------------------------------------------------------------- */
async function getUserLocation() {
  const defaultCoords = [55.7558, 37.6173]; // Москва fallback

  if (!navigator.geolocation) {
    return { city: "Москва", coords: defaultCoords, source: "default" };
  }

  try {
    const pos = await new Promise((resolve, reject) =>
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: false,
        timeout: 5000,
        maximumAge: 60000,
      })
    );

    const { latitude: lat, longitude: lon } = pos.coords;
    const res = await fetch(`/delivery/yandex/reverse-geocode?lat=${lat}&lon=${lon}`);
    if (res.ok) {
      const data = await res.json();
      const city = data?.city || "Москва";
      return { city, coords: [lat, lon], source: "geolocation" };
    }
  } catch (err) {
    console.warn("📍 Geolocation failed:", err.message);
  }

  return { city: "Москва", coords: defaultCoords, source: "fallback" };
}

/* -------------------------------------------------------------------------- */
/*                              HEADER SWITCH UI                              */
/* -------------------------------------------------------------------------- */
function createDeliveryHeader(city, coords, currentService = "CDEK") {
  const oldHeader = document.querySelector(".delivery-toggle-container");
  if (oldHeader) oldHeader.remove();

  const header = document.createElement("div");
  header.className = "delivery-toggle-container";
  Object.assign(header.style, {
    display: "flex",
    flexDirection: "row",
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

  const makeButton = label => {
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

  const cdekContainer = ensureMapContainer("cdek-map-container");
  const yandexContainer = ensureMapContainer("yandex-map-container");

  async function updateSelection(service) {
    sessionStorage.setItem("selected_delivery_service", service);
    indicator.style.left = service === "CDEK" ? "0" : "50%";

    // UI feedback
    cdekBtn.style.background = service === "CDEK" ? "#17517D" : "transparent";
    yandexBtn.style.background = service === "Yandex" ? "#17517D" : "transparent";

    cdekContainer.style.display = service === "CDEK" ? "block" : "none";
    yandexContainer.style.display = service === "Yandex" ? "block" : "none";

    if (service === "CDEK") await initCDEKWidget(coords);
    else await initYandexWidget(city);
  }

  cdekBtn.onclick = () => updateSelection("CDEK");
  yandexBtn.onclick = () => updateSelection("Yandex");

  updateSelection(currentService);
}

/* -------------------------------------------------------------------------- */
/*                             MAP CONTAINER HELPER                           */
/* -------------------------------------------------------------------------- */
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
    });
    checkoutPageEl.appendChild(el);
  }
  return el;
}

/* -------------------------------------------------------------------------- */
/*                                CDEK WIDGET                                 */
/* -------------------------------------------------------------------------- */
async function initCDEKWidget(coords) {
  if (!window.CDEKWidget) {
    console.error("❌ CDEK Widget not loaded!");
    return;
  }

  if (window.cdekWidgetInstance) {
    console.log("♻️ Reusing existing CDEK widget");
    return window.cdekWidgetInstance;
  }

  const id = "cdek-map-container";
  const container = document.getElementById(id);
  container.style.display = "block";

  try {
    window.cdekWidgetInstance = new window.CDEKWidget({
      root: id,
      apiKey: "bb7d36f8-1e64-415c-80d2-12d77317718d",
      servicePath: "/delivery/cdek",
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
        hideLoader();
        container.style.display = "block";
      },

      onChoose: (mode, tariff, address) => {
        sessionStorage.setItem(
          "selected_delivery",
          JSON.stringify({ deliveryMode: mode, tariff, address })
        );
        createProceedButton("Продолжить оформление");
        if (address?.code) fetchPVZByCode(address.code);
      },

      onCalculate: async () => {
        const pvzCode = getSelectedPVZCode();
        if (pvzCode) fetchPVZByCode(pvzCode);
      },
    });
  } catch (err) {
    console.error("❌ Failed to initialize CDEK Widget:", err);
  }

  return window.cdekWidgetInstance;
}

/* -------------------------------------------------------------------------- */
/*                               YANDEX WIDGET                                */
/* -------------------------------------------------------------------------- */
async function initYandexWidget(city = "Москва") {
  const id = "yandex-map-container";
  const container = document.getElementById(id);
  if (!container) return console.error("❌ Yandex container not found!");
  container.style.display = "block";

  if (!window.YaDelivery?.createWidget)
    return console.error("❌ Yandex Delivery widget script not loaded!");

  if (window.yandexWidgetInstance) {
    console.log("♻️ Reusing existing Yandex widget");
    return window.yandexWidgetInstance;
  }

  try {
    window.yandexWidgetInstance = window.YaDelivery.createWidget({
      containerId: id,
      params: {
        city,
        size: { height: "450px", width: "100%" },
        filter: {
          type: ["pickup_point", "terminal"],
          is_yandex_branded: false,
          payment_methods: ["already_paid", "card_on_receipt"],
          payment_methods_filter: "or",
        },
        delivery_options: {
          physical_dims_weight_gross: 1000,
          delivery_term: 3,
          delivery_price: price => `${price} ₽`,
        },
        show_select_button: true,
      },
    });
  } catch (err) {
    console.error("❌ Error initializing Yandex widget:", err);
  }

  return window.yandexWidgetInstance;
}

/* -------------------------------------------------------------------------- */
/*                             PVZ INFO HELPERS                               */
/* -------------------------------------------------------------------------- */
function getSelectedPVZCode() {
  const els = Array.from(document.querySelectorAll(".cdek-1smek3"));
  for (const el of els) {
    const match = el.textContent.trim().match(/- (\S+)$/);
    if (match) return match[1];
  }
  return null;
}

async function fetchPVZByCode(code) {
  try {
    const res = await fetch(`/delivery/cdek?action=offices&code=${encodeURIComponent(code)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data?.length) renderPVZInfo(data[0]);
  } catch (err) {
    console.error("❌ Error fetching PVZ info:", err);
  }
}

function renderPVZInfo(pvz) {
  if (!pvz) return;
  let infoDiv = document.querySelector(".my-pvz-info");
  if (!infoDiv) {
    infoDiv = document.createElement("div");
    infoDiv.className = "my-pvz-info";
    infoDiv.style.marginTop = "10px";
    infoDiv.style.fontSize = "14px";
    infoDiv.style.color = "#333";
    document.querySelector(".cdek-2ew9g8")?.appendChild(infoDiv);
  }
  infoDiv.innerHTML = `
    ${pvz.phones?.length ? `<p><b>Телефон:</b> ${pvz.phones.map(p => p.number).join(", ")}</p>` : ""}
    ${pvz.email ? `<p><b>Email:</b> ${pvz.email}</p>` : ""}
    ${pvz.note ? `<p><b>Примечание:</b> ${pvz.note}</p>` : ""}
  `;
}

/* -------------------------------------------------------------------------- */
/*                           PROCEED TO CONTACT PAGE                           */
/* -------------------------------------------------------------------------- */
export function createProceedButton(label = "Перейти к оплате") {
  const tg = window.Telegram?.WebApp;

  const handleProceedClick = async () => {
    try {
      showLoader();
      navigateTo("/contact");
      // ❌ Removed tg?.MainButton?.hide?.() — keeps button visible
    } finally {
      hideLoader();
    }
  };

  if (isTelegramApp()) {
    tg?.MainButton?.hideProgress?.();
    tg.MainButton.offClick(handleCheckout);
    tg.MainButton.offClick(handleProceedClick);
    tg.MainButton.setText(label);
    tg.MainButton.onClick(handleProceedClick);
    tg.MainButton.show();
  } else {
    let btn = document.querySelector(".checkout-proceed-btn");
    if (!btn) {
      btn = document.createElement("button");
      btn.className = "checkout-proceed-btn";
      btn.textContent = label;
      btn.onclick = handleProceedClick;
      checkoutPageEl.appendChild(btn);
    }
  }
}

/* -------------------------------------------------------------------------- */
/*                                MAIN ENTRY                                  */
/* -------------------------------------------------------------------------- */
export async function renderCheckoutPage() {
  hideCartIcon();
  showLoader();

  const { city, coords } = await getUserLocation();
  checkoutPageEl.style.display = "block";
  createDeliveryHeader(city, coords, "CDEK");

  await initCDEKWidget(coords);
  console.log(`✅ Checkout initialized for ${city}`);
}