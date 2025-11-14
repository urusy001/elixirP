// pvz-widget.js
export class PvzMapWidget {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) return;

        this.options = options;
        this.map = null;
        this.clusterer = null;
        this.placemarks = new Map();
        this.selectedPvzId = null;

        this.renderLayout();
    }

    renderLayout() {
        this.container.innerHTML = `
      <div class="pvz-widget-layout">
        <div class="pvz-widget-map" id="widget-map-instance"></div>
        <div class="pvz-widget-list" id="widget-list-instance">
          <div class="pvz-list-status">Нажмите «Искать ПВЗ».</div>
        </div>
      </div>
    `;
        this.mapEl = this.container.querySelector("#widget-map-instance");
        this.listEl = this.container.querySelector("#widget-list-instance");
    }

    initMap(centerCoords = [55.75, 37.61], zoom = 10) {
        this.map = new ymaps.Map(this.mapEl, {
            center: centerCoords,
            zoom,
            controls: ["zoomControl", "fullscreenControl"]
        }, {
            suppressMapOpenBlock: true,
            yandexMapDisablePoiInteractivity: true
        });

        this.clusterer = new ymaps.Clusterer({
            preset: "islands#invertedBlueClusterIcons",
            groupByCoordinates: false
        });

        this.map.geoObjects.add(this.clusterer);
    }

    _formatSchedule(scheduleData) {
        const dayNames = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"];
        const pad2 = n => String(n ?? 0).padStart(2,"0");
        const fmtTime = t => {
            if (!t) return "??:??";
            if (typeof t === "string") return t;
            if (typeof t.value === "string") return t.value;
            const h = ("hours" in t) ? t.hours : t.h ?? t.hour;
            const m = ("minutes" in t) ? t.minutes : t.m ?? t.min ?? 0;
            return `${pad2(h)}:${pad2(m)}`;
        };

        const restrictions = Array.isArray(scheduleData)
            ? scheduleData
            : Array.isArray(scheduleData?.restrictions)
                ? scheduleData.restrictions
                : [];

        if (!restrictions.length) return "Часы работы не указаны";

        const byTime = new Map();
        for (const item of restrictions) {
            const daysArr = Array.isArray(item.days) ? item.days : (item.day != null ? [item.day] : []);
            const time = `${fmtTime(item.time_from)}-${fmtTime(item.time_to)}`;
            if (!byTime.has(time)) byTime.set(time, new Set());
            const set = byTime.get(time);
            for (const d of daysArr) {
                const dn = Number(d);
                if (dn >= 1 && dn <= 7) set.add(dn);
            }
        }

        const segments = [];
        for (const [time, daysSet] of byTime.entries()) {
            const days = Array.from(daysSet).sort((a,b)=>a-b).map(d=>dayNames[d-1]);
            segments.push(`${days.join(", ")}: ${time}`);
        }
        return segments.join("; ");
    }

    clear() {
        this.clusterer.removeAll();
        this.placemarks.clear();
        this.listEl.innerHTML = '<div class="pvz-list-status">Нажмите «Искать ПВЗ».</div>';
        this.selectedPvzId = null;
    }

    async search(centerCoords) {
        this.clear();
        this.listEl.innerHTML = '<div class="pvz-list-status">Поиск…</div>';
        try {
            const response = await fetch('/delivery/yandex/get-pvz', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    latitude: centerCoords[0],
                    longitude: centerCoords[1],
                    radius: 10000
                })
            });
            if (!response.ok) throw new Error('HTTP ' + response.status);
            const data = await response.json();
            const points = (data.points ?? []).map(point => ({
                id: point.ID,
                lat: point.position.latitude,
                lon: point.position.longitude,
                name: point.name,
                address: point.address.full_address,
                phone: point.contact?.phone || null,
                schedule: this._formatSchedule(point.schedule)
            }));
            this.renderResults(points);
            return points.length;
        } catch (e) {
            this.listEl.innerHTML = `<div class="pvz-list-status">Ошибка поиска.</div>`;
            return 0;
        }
    }

    renderResults(points) {
        if (!points.length) {
            this.listEl.innerHTML = '<div class="pvz-list-status">Ничего не найдено.</div>';
            return;
        }
        this.listEl.innerHTML = '';
        const placemarkObjects = [];

        points.forEach(pvz => {
            const itemEl = document.createElement('div');
            itemEl.className = 'pvz-list-item';
            itemEl.dataset.id = pvz.id;
            itemEl.innerHTML = `
        <div class="pvz-item-name">${pvz.name}</div>
        <div class="pvz-item-addr">${pvz.address}</div>
        <div class="pvz-item-hours">🕒 ${pvz.schedule}</div>
      `;
            itemEl.addEventListener('click', () => this.selectPvz(pvz.id, 'list'));
            this.listEl.appendChild(itemEl);

            const placemark = new ymaps.Placemark([pvz.lat, pvz.lon], { hintContent: pvz.name }, {
                iconLayout: "default#image",
                iconImageHref: window.defaultPin,
                iconImageSize: [28, 38],
                iconImageOffset: [-14, -38]
            });
            placemark.events.add('click', () => this.selectPvz(pvz.id, 'map'));

            placemarkObjects.push(placemark);
            this.placemarks.set(pvz.id, { placemark, pvz });
        });

        this.clusterer.add(placemarkObjects);
        if (this.clusterer.getBounds()) {
            this.map.setBounds(this.clusterer.getBounds(), { checkZoomRange: true, zoomMargin: 32 });
        }
    }

    selectPvz(pvzId, source) {
        if (this.selectedPvzId === pvzId) return;

        if (this.selectedPvzId) {
            const old = this.placemarks.get(this.selectedPvzId);
            if (old) old.placemark.options.set('iconImageHref', window.defaultPin);
            const oldItem = this.listEl.querySelector(`[data-id="${this.selectedPvzId}"]`);
            if (oldItem) oldItem.classList.remove('selected');
        }

        this.selectedPvzId = pvzId;
        const { placemark, pvz } = this.placemarks.get(pvzId);
        placemark.options.set('iconImageHref', window.selectedPin);

        const listItem = this.listEl.querySelector(`[data-id="${pvzId}"]`);
        if (listItem) {
            listItem.classList.add('selected');
            if (source === 'map') listItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        this.map.panTo([pvz.lat, pvz.lon], { duration: 300 });
        this.options.onPvzSelected?.(pvz);
    }
}