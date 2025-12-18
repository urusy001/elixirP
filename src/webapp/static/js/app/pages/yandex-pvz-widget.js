import { withLoader } from "../ui/loader.js";
import { apiGet, apiPost } from "../../services/api.js";

const SUGGEST_ROW_HEIGHT = 36;
const DEFAULT_CENTER = [55.751, 37.618];
const DEFAULT_ZOOM = 4;

export class YandexPvzWidget {
    constructor(containerId, options = {}) {
        this.root = document.getElementById(containerId);
        if (!this.root) {
            console.error(`YandexPvzWidget: #${containerId} not found`);
            return;
        }

        this.options = {
            dataUrl: "/delivery/yandex/get-pvz-all",
            calculateUrl: "/delivery/yandex/calculate",

            // должен вернуть данные заказа ПОД backend CalcRequest:
            // {
            //   total_weight: number,
            //   total_assessed_price: number,
            //   client_price: number,
            //   payment_method: "already_paid" | "card_on_receipt",
            //   places: [ { physical_dims: { dx, dy, dz, weight_gross, predefined_volume? } } ],
            //   is_oversized?: boolean,
            //   send_unix?: boolean
            // }
            getOrderData: null,

            defaultCenter: DEFAULT_CENTER,
            defaultZoom: DEFAULT_ZOOM,
            autoLocate: false,
            onReady: null,
            onChoose: null,
            ...options,
        };

        this.map = null;
        this.manager = null;

        this._pointsById = new Map();
        this._selectedId = null;

        this._doorPlacemark = null;
        this._doorAddress = "";
        this._doorSeq = 0;

        this._geocodeCache = new Map();
        this._geocodeCacheMax = 50;

        this.preset = { default: "islands#blueDotIcon", active: "islands#redDotIcon" };

        this._renderLayout();
        this._bindSearchUI();
    }

    _renderLayout() {
        this.root.innerHTML = `
      <div class="ydw-toolbar" style="display:flex;flex-direction:column;gap:8px;margin-bottom:.5rem;">
        <div style="display:flex;align-items:center;gap:8px;">
          <input id="ydw-query" type="text" inputmode="search" placeholder="Введите населённый пункт"
                 style="flex:1;padding:.5rem .6rem;border:1px solid #ddd;border-radius:8px;">
        </div>

        <div id="ydw-suggest"
             style="display:none;height:${SUGGEST_ROW_HEIGHT * 5}px;overflow-y:auto;border:1px solid #e5e7eb;border-radius:8px;background:#fff;"></div>

        <div id="ydw-delivery"
             style="display:none;border:1px solid #e5e7eb;background:#fff;border-radius:10px;padding:10px 12px;">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;">
            <div style="font-weight:600;font-size:13px;">Доставка</div>
            <button id="ydw-delivery-close"
                    style="border:0;background:transparent;cursor:pointer;font-size:16px;line-height:1;">✕</button>
          </div>
          <div id="ydw-delivery-body" style="margin-top:6px;font-size:13px;line-height:1.35;"></div>
        </div>
      </div>

      <div id="ydw-map" style="width:100%;height:100%;min-height:400px;border-radius:8px;"></div>
    `;

        this.mapEl = this.root.querySelector("#ydw-map");
        this.queryEl = this.root.querySelector("#ydw-query");
        this.suggestEl = this.root.querySelector("#ydw-suggest");

        this.deliveryEl = this.root.querySelector("#ydw-delivery");
        this.deliveryBodyEl = this.root.querySelector("#ydw-delivery-body");
        this.deliveryCloseEl = this.root.querySelector("#ydw-delivery-close");

        this.deliveryCloseEl?.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            this._hideDelivery();
        });

        // Handle "Выбрать" clicks inside PVZ balloons
        this.root.addEventListener("click", (e) => {
            const btn = e.target.closest(".ydw-choose-btn");
            if (!btn) return;

            const id = btn.getAttribute("data-id");
            if (!id) return;

            (async () => {
                btn.textContent = "⏳ Считаю доставку...";
                btn.disabled = true;
                btn.style.opacity = "0.8";
                btn.style.cursor = "default";

                this._select(id, false);
                await this._emitChoosePVZ();

                btn.textContent = "✅ Выбрано";
            })();
        });
    }

    async init(center = this.options.defaultCenter, zoom = this.options.defaultZoom) {
        this.map = new ymaps.Map(
            this.mapEl,
            { center, zoom, controls: ["zoomControl", "fullscreenControl"] },
            { suppressMapOpenBlock: true, yandexMapDisablePoiInteractivity: true }
        );

        this.manager = new ymaps.ObjectManager({ clusterize: true, gridSize: 64, clusterDisableClickZoom: false });
        this.manager.objects.options.set("preset", this.preset.default);
        this.manager.clusters.options.set("preset", "islands#invertedBlueClusterIcons");
        this.map.geoObjects.add(this.manager);

        this.manager.objects.events.add("click", (e) => {
            const id = e.get("objectId");
            this._removeDoorPlacemark();
            this._select(id, true);
        });

        this.map.events.add("click", (e) => {
            if (e.get("target") !== this.map) return;
            const coords = e.get("coords");
            this._clearSelection();
            this._setDoorPlacemark(coords);
        });

        const all = await withLoader(async () => {
            try {
                const data = await apiGet(this.options.dataUrl);
                return data ?? { points: [] };
            } catch {
                return { points: [] };
            }
        });

        const src = Array.isArray(all?.points) ? all.points : Array.isArray(all) ? all : [];
        const points = src.map((p) => this._normalizePoint(p));
        this._drawPoints(points);

        if (points.length) {
            try {
                const coords = points.map((p) => p.coords);
                const bounds = ymaps.util.bounds.fromPoints(coords);
                this.map.setBounds(bounds, { checkZoomRange: true, zoomMargin: 32 });
            } catch {}
        } else {
            this._toast("Нет пунктов выдачи для отображения");
        }

        if (this.options.autoLocate && navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    const coords = [pos.coords.latitude, pos.coords.longitude];
                    this.map?.panTo(coords, { duration: 300 });
                },
                () => {},
                { enableHighAccuracy: true, maximumAge: 60_000, timeout: 5_000 }
            );
        }

        this.options.onReady?.();
    }

    /* ------------------------ Search (locality suggest) ----------------------- */

    _bindSearchUI() {
        const debounce = (fn, delay = 300) => {
            let t;
            return (...a) => {
                clearTimeout(t);
                t = setTimeout(() => fn(...a), delay);
            };
        };

        this._searchVariants = [];
        this._suggestActive = -1;

        this.queryEl?.addEventListener(
            "input",
            debounce(async (e) => {
                const q = e.target.value.trim();
                if (!q) {
                    this._searchVariants = [];
                    this._renderSuggest([]);
                    return;
                }
                const variants = await this._geocodeLocality(q);
                this._searchVariants = Array.isArray(variants) ? variants : [];
                this._renderSuggest(this._searchVariants);
                this._suggestActive = -1;
            }, 250)
        );

        this.suggestEl?.addEventListener("click", (e) => {
            const row = e.target.closest(".ydw-suggest-row");
            this.queryEl.value = "";
            if (!row) return;
            const idx = Number(row.getAttribute("data-index") || "-1");
            const item = this._searchVariants?.[idx];
            if (!item?.coords) return;
            this._goToVariant(item);
        });

        this.queryEl?.addEventListener("keydown", (e) => {
            if (!this._searchVariants.length) return;

            if (e.key === "ArrowDown" || e.key === "ArrowUp") {
                e.preventDefault();
                const max = this._searchVariants.length - 1;
                if (e.key === "ArrowDown") this._suggestActive = Math.min(max, this._suggestActive + 1);
                else this._suggestActive = Math.max(0, this._suggestActive < 0 ? 0 : this._suggestActive - 1);
                this._highlightSuggest(this._suggestActive);
            } else if (e.key === "Enter") {
                e.preventDefault();
                const idx = this._suggestActive >= 0 ? this._suggestActive : 0;
                const item = this._searchVariants[idx];
                if (item) this._goToVariant(item);
            } else if (e.key === "Escape") {
                this._renderSuggest([]);
            }
        });
    }

    _goToVariant(item) {
        if (item.bounds) this.map?.setBounds(item.bounds, { checkZoomRange: true, zoomMargin: 32 });
        else this.map?.panTo(item.coords, { duration: 300 });
        this._renderSuggest([]);
    }

    _highlightSuggest(activeIdx) {
        if (!this.suggestEl) return;
        [...this.suggestEl.children].forEach((el, i) => (el.style.background = i === activeIdx ? "#eef2ff" : ""));
        const target = this.suggestEl.children[activeIdx];
        if (target) target.scrollIntoView({ block: "nearest" });
    }

    _renderSuggest(variants) {
        if (!this.suggestEl) return;
        if (!Array.isArray(variants) || variants.length === 0) {
            this.suggestEl.style.display = "none";
            this.suggestEl.innerHTML = "";
            return;
        }

        const frag = document.createDocumentFragment();
        variants.forEach((v, i) => {
            const row = document.createElement("div");
            row.className = "ydw-suggest-row";
            row.setAttribute("data-index", String(i));
            row.style.cssText = `
        display:flex;align-items:center;height:${SUGGEST_ROW_HEIGHT}px;padding:0 10px;
        cursor:pointer;border-bottom:1px solid #f0f0f0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;user-select:none;
      `;
            row.addEventListener("mouseenter", () => (row.style.background = "#f8fafc"));
            row.addEventListener("mouseleave", () => (row.style.background = ""));

            const name = (v.name || "").toString();
            const kind = (v.kind || "").toString();

            row.innerHTML = `
        <div style="font-size:13px;flex:1;min-width:0;">
          ${this._escape(name)}
          ${kind ? `<span style="opacity:.65;font-size:12px;margin-left:6px;">(${this._escape(kind)})</span>` : ""}
        </div>
      `;
            frag.appendChild(row);
        });

        this.suggestEl.innerHTML = "";
        this.suggestEl.appendChild(frag);
        this.suggestEl.style.height = `${SUGGEST_ROW_HEIGHT * 5}px`;
        this.suggestEl.style.display = "block";
    }

    async _geocodeLocality(query) {
        if (this._geocodeCache.has(query)) return this._geocodeCache.get(query);
        try {
            const res = await ymaps.geocode(query, { results: 50 });
            const gos = res.geoObjects;
            if (!gos || gos.getLength() === 0) {
                this._rememberGeocode(query, []);
                return [];
            }
            const variants = [];
            for (let i = 0; i < gos.getLength(); i++) {
                const g = gos.get(i);
                const meta = g.properties.get("metaDataProperty")?.GeocoderMetaData;
                variants.push({
                    name: g.getAddressLine(),
                    kind: meta?.kind,
                    coords: g.geometry.getCoordinates(),
                    bounds: g.properties.get("boundedBy"),
                });
            }
            this._rememberGeocode(query, variants);
            return variants;
        } catch {
            this._rememberGeocode(query, []);
            return [];
        }
    }

    _rememberGeocode(q, val) {
        this._geocodeCache.set(q, val);
        if (this._geocodeCache.size > this._geocodeCacheMax) {
            const firstKey = this._geocodeCache.keys().next().value;
            this._geocodeCache.delete(firstKey);
        }
    }

    /* --------------------------- Courier pin logic --------------------------- */

    async _setDoorPlacemark(coords) {
        const mySeq = ++this._doorSeq;

        const prev = this._doorPlacemark || null;
        const address = (await this._resolveAddress(coords)) || "Адрес не определён";
        if (mySeq !== this._doorSeq) return;

        this._doorAddress = address;
        const html = this._doorBalloonHtml(address);

        const fresh = new ymaps.Placemark(
            coords,
            { hintContent: address, balloonContent: html },
            { preset: "islands#redIcon", draggable: true }
        );
        try {
            fresh.properties.set("ydwDoor", true);
        } catch {}

        fresh.events.add("dragend", async () => {
            const newCoords = fresh.geometry.getCoordinates();
            await this._setDoorPlacemark(newCoords);
        });

        this.map.geoObjects.add(fresh);
        this._doorPlacemark = fresh;
        try {
            fresh.balloon.open();
        } catch {}
        this._wireDoorChooseOnce(coords);

        if (prev && prev !== fresh) {
            try {
                prev.balloon?.close?.();
            } catch {}
            try {
                this.map.geoObjects.remove(prev);
            } catch {}
        }

        this._purgeOldDoorPlacemarks(fresh);
        this.map?.panTo(coords, { duration: 300 });
    }

    _wireDoorChooseOnce(coords) {
        const onceHandler = (e) => {
            const btn = e.target.closest(".ydw-choose-door");
            if (!btn) return;
            e.stopPropagation();

            (async () => {
                btn.textContent = "⏳ Считаю доставку...";
                btn.disabled = true;
                btn.style.opacity = "0.8";
                btn.style.cursor = "default";

                const basePayload = { deliveryMode: "time_interval", coords, address: this._doorAddress || "" };
                const enriched = await this._calcDelivery(basePayload);

                btn.textContent = "✅ Выбрано";
                this.options.onChoose?.(null, enriched);
            })();
        };

        this.root.addEventListener("click", onceHandler, { once: true });
    }

    async _resolveAddress(coords) {
        const [lat, lon] = coords;

        // apiGet у тебя возвращает JSON, поэтому читаем как JSON.
        try {
            const info = await apiGet(`/delivery/yandex/reverse-geocode?lat=${lat}&lon=${lon}`);
            if (info?.formatted) return info.formatted;
        } catch {}

        // fallback geocode from ymaps
        try {
            const g = await ymaps.geocode(coords, { results: 1 });
            const first = g.geoObjects.get(0);
            return first?.getAddressLine?.() || "";
        } catch {}

        return "";
    }

    _doorBalloonHtml(address) {
        return `
      <div style="font-size:13px;line-height:1.35;max-width:260px">
        <div style="font-weight:600;margin-bottom:4px">Доставка курьером</div>
        <div style="margin-bottom:6px">${this._escape(address)}</div>
        <div style="margin-top:8px;display:flex;gap:8px;justify-content:flex-end">
          <button class="ydw-choose-door"
                  style="padding:6px 10px;border:0;border-radius:8px;background:#ef4444;color:#fff;cursor:pointer;">
            Выбрать этот адрес
          </button>
        </div>
      </div>
    `;
    }

    _removeDoorPlacemark() {
        if (this._doorPlacemark) {
            try {
                this.map.geoObjects.remove(this._doorPlacemark);
            } catch {}
            this._doorPlacemark = null;
            this._doorAddress = "";
        }
        this._hideDelivery();
    }

    _purgeOldDoorPlacemarks(keep) {
        if (!this.map) return;
        try {
            this.map.geoObjects.each((obj) => {
                if (obj && obj.properties && obj.properties.get("ydwDoor") && obj !== keep) {
                    try {
                        obj.balloon?.close?.();
                    } catch {}
                    try {
                        this.map.geoObjects.remove(obj);
                    } catch {}
                }
            });
        } catch {}
    }

    /* ------------------------------- PVZ logic ------------------------------- */

    _normalizePoint(p) {
        const safeId = `pvz_${p.id}`;
        const addr = p.address ?? {};
        return {
            id: safeId,
            rawId: p.id,
            coords: [p.position.latitude, p.position.longitude],
            name: p.name ?? "Пункт выдачи заказов",
            phone: p.contact?.phone ?? "",
            schedule: this._formatSchedule(p.schedule),
            dayoffs: this._formatDayoffs(p.dayoffs),
            address: addr.full_address || [addr.region, addr.locality, addr.street, addr.house].filter(Boolean).join(", "),
        };
    }

    _drawPoints(points) {
        this._pointsById.clear();
        this.manager.removeAll();
        if (!Array.isArray(points) || !points.length) return;

        const features = points.map((p) => {
            this._pointsById.set(p.id, p);
            return {
                type: "Feature",
                id: p.id,
                geometry: { type: "Point", coordinates: p.coords },
                properties: { hintContent: p.name, balloonContent: this._balloonHtml(p) },
            };
        });

        this.manager.add({ type: "FeatureCollection", features });
    }

    _balloonHtml(p) {
        return `
      <div style="font-size:13px;line-height:1.35;max-width:260px">
        <div style="font-weight:600;margin-bottom:4px">${this._escape(p.name)}</div>
        <div style="margin-bottom:6px">${this._escape(p.address)}</div>

        ${p.phone ? `<div style="margin-bottom:4px">☎ ${this._escape(p.phone)}</div>` : ""}
        ${p.schedule ? `<div style="margin-bottom:4px">🕒 ${this._escape(p.schedule)}</div>` : ""}
        ${p.dayoffs ? `<div style="margin-bottom:4px">❌ ${this._escape(p.dayoffs)}</div>` : ""}

        <div style="margin-top:8px;display:flex;justify-content:flex-end">
          <button class="ydw-choose-btn" data-id="${this._escape(p.id)}"
                  style="padding:6px 10px;border:0;border-radius:8px;background:#10b981;color:#fff;cursor:pointer;">
            Выбрать
          </button>
        </div>
      </div>
    `;
    }

    _select(id, openBalloon = false) {
        if (id && !String(id).startsWith("pvz_")) id = `pvz_${id}`;
        if (!this._pointsById.has(id)) return;

        const prev = this._selectedId;
        if (prev === id) return;

        this._removeDoorPlacemark();

        if (this.manager) {
            if (prev) this.manager.objects.setObjectOptions(prev, { preset: this.preset.default });
            this.manager.objects.setObjectOptions(id, { preset: this.preset.active });
        }

        const p = this._pointsById.get(id);
        this.map?.panTo(p.coords, { duration: 300 });
        this._selectedId = id;

        if (openBalloon) {
            try {
                this.manager.objects.balloon.close();
            } catch {}
            setTimeout(() => this.manager.objects.balloon.open(id), 0);
        }
    }

    _clearSelection() {
        this._hideDelivery();
        const prev = this._selectedId;
        if (prev && this.manager) this.manager.objects.setObjectOptions(prev, { preset: this.preset.default });
        this._selectedId = null;
        try {
            this.manager?.objects?.balloon?.close();
        } catch {}
    }

    async _emitChoosePVZ() {
        const p = this._pointsById.get(this._selectedId);
        if (!p) return;

        const basePayload = {
            deliveryMode: "self_pickup",
            code: p.rawId,
            name: p.name,
            coords: p.coords,
            address: p.address,
            phone: p.phone,
            schedule: p.schedule,
            dayoffs: p.dayoffs,
        };

        const enriched = await this._calcDelivery(basePayload);
        this.options.onChoose?.(p, enriched);
    }

    /* -------------------------- CALCULATE интеграция -------------------------- */

    async _calcDelivery(destinationPayload) {
        const order = (typeof this.options.getOrderData === "function" ? this.options.getOrderData() : null) || null;

        const body = {
            delivery_mode: destinationPayload.deliveryMode,

            destination:
                destinationPayload.deliveryMode === "self_pickup"
                    ? { platform_station_id: String(destinationPayload.code ?? "") }
                    : { address: String(destinationPayload.address ?? "") },

            total_weight: Math.max(1, Number(order?.total_weight ?? 0) | 0),
            total_assessed_price: Math.max(0, Number(order?.total_assessed_price ?? 0) | 0),
            client_price: Math.max(0, Number(order?.client_price ?? 0) | 0),

            payment_method: order?.payment_method === "card_on_receipt" ? "card_on_receipt" : "already_paid",

            places: Array.isArray(order?.places)
                ? order.places.map((p) => ({
                    physical_dims: {
                        dx: Math.max(1, Number(p?.physical_dims?.dx ?? 0) | 0),
                        dy: Math.max(1, Number(p?.physical_dims?.dy ?? 0) | 0),
                        dz: Math.max(1, Number(p?.physical_dims?.dz ?? 0) | 0),
                        weight_gross: Math.max(1, Number(p?.physical_dims?.weight_gross ?? 0) | 0),
                        ...(p?.physical_dims?.predefined_volume
                            ? { predefined_volume: Math.max(1, Number(p.physical_dims.predefined_volume) | 0) }
                            : {}),
                    },
                }))
                : [],

            is_oversized: Boolean(order?.is_oversized),
            send_unix: order?.send_unix === undefined ? true : Boolean(order.send_unix),
        };

        const calc = await withLoader(async () => {
            try {
                const res = await apiPost(this.options.calculateUrl, body);

                // apiPost может возвращать либо JSON, либо fetch Response — поддержим оба.
                if (res && typeof res === "object" && typeof res.json === "function") {
                    const data = await res.json().catch(() => ({}));
                    if (!res.ok) throw new Error(data?.detail || "calculate failed");
                    if (!data?.ok) throw new Error(data?.detail || "calculate failed");
                    return data;
                }

                // JSON already
                const data = res ?? {};
                if (!data?.ok) throw new Error(data?.detail || "calculate failed");
                return data;
            } catch (e) {
                return { ok: false, error: String(e?.message || e) };
            }
        });

        const enriched = { ...destinationPayload, calc };
        this._showDelivery(enriched);
        return enriched;
    }

    /* ------------------------------ Formatting ------------------------------- */

    _formatSchedule(schedule) {
        if (!schedule?.restrictions?.length) return "";
        const dayNames = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
        const pad = (n) => String(n).padStart(2, "0");
        const fmt = (t) => `${pad(t?.hours ?? 0)}:${pad(t?.minutes ?? 0)}`;
        return schedule.restrictions
            .map((r) => {
                const days = (r.days ?? []).map((d) => dayNames[d - 1]).join(", ");
                return `${days || "—"}: ${fmt(r.time_from)}–${fmt(r.time_to)}`;
            })
            .join(" · ");
    }

    _formatDayoffs(dayoffs) {
        if (!Array.isArray(dayoffs) || !dayoffs.length) return "";
        const opts = { day: "2-digit", month: "2-digit" };
        const formatted = dayoffs
            .map((d) => {
                const dt = d.date_utc ? new Date(d.date_utc) : new Date((d.date ?? 0) * 1000);
                return isNaN(dt) ? "" : dt.toLocaleDateString("ru-RU", opts);
            })
            .filter(Boolean);
        return formatted.length ? `Выходные: ${formatted.join(", ")}` : "";
    }

    _escape(s) {
        return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    _toast(msg) {
        console.info(msg);
    }

    /* ----------------------- Delivery panel UI helpers ----------------------- */

    _parsePriceRub(pricingTotal) {
        // backend может вернуть "240 RUB" (строка) или число/копейки в будущем
        if (pricingTotal == null) return 0;

        if (typeof pricingTotal === "number") {
            // если вдруг это копейки — будет слишком большое; но у тебя сейчас строка, так что ок.
            // считаем, что это уже RUB.
            return Math.round(pricingTotal);
        }

        const s = String(pricingTotal).trim();
        // "240 RUB", "240", "240.5 RUB"
        const m = s.match(/(\d+(?:[.,]\d+)?)/);
        if (!m) return 0;
        const v = Number(m[1].replace(",", "."));
        return Number.isFinite(v) ? Math.round(v) : 0;
    }

    _showDelivery(enriched) {
        if (!this.deliveryEl || !this.deliveryBodyEl) return;

        const calc = enriched?.calc;

        if (!calc?.ok) {
            const err = calc?.error || calc?.detail || "Не удалось рассчитать доставку";
            this.deliveryBodyEl.innerHTML = `❌ ${this._escape(err)}`;
            this.deliveryEl.style.display = "block";
            return;
        }

        const priceRub = this._parsePriceRub(calc?.price?.pricing_total);
        const days = calc?.delivery_days;

        const daysText =
            Array.isArray(days) && days.length === 2
                ? `${days[0]}–${days[1]} дн.`
                : typeof days === "number"
                    ? `~${days} дн.`
                    : "";


        const modeTitle = enriched?.deliveryMode === "self_pickup" ? "Самовывоз (ПВЗ)" : "Курьер";
        const pointLine =
            enriched?.deliveryMode === "self_pickup" && enriched?.name
                ? `<div style="opacity:.85">${this._escape(enriched.name)}</div>`
                : "";

        this.deliveryBodyEl.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:4px;">
        <div><b>${this._escape(modeTitle)}</b></div>
        ${pointLine}
        <div>💰 Цена: <b>${priceRub} ₽</b></div>
        ${daysText ? `<div>📦 Срок: ${this._escape(daysText)}</div>` : ""}
      </div>
    `;
        this.deliveryEl.style.display = "block";
    }

    _hideDelivery() {
        if (!this.deliveryEl) return;
        this.deliveryEl.style.display = "none";
        if (this.deliveryBodyEl) this.deliveryBodyEl.innerHTML = "";
    }

    destroy() {
        this._removeDoorPlacemark();
        try {
            this.manager?.removeAll();
        } catch {}
        try {
            this.map?.destroy?.();
        } catch {}
        this.map = null;
        this.manager = null;
        this.root.innerHTML = "";
    }
}