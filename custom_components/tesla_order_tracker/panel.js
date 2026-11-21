/* Local Home Assistant sidebar panel. All data comes from HA entities. */
const labels = {
  en: {
    title: "Tesla Order Tracker", subtitle: "Your order at a glance", demo: "Demo",
    demoText: "Example order. Use the button to simulate a delivery update.",
    liveText: "Order information from Tesla Fleet API",
    model: "Model", status: "Order status", delivery_window: "Delivery window",
    delivery_center: "Delivery center", appointment: "Delivery appointment",
    production_status: "Production status", vin: "VIN",
    timeline: "Recent changes", empty: "No changes recorded yet.", vinChange: "VIN detected or updated",
    lastSuccess: "Last successful check", refresh: "Refresh order", simulate: "Simulate change",
    waiting: "Waiting for tracker data", ok: "Tracker active",
    problem: "Showing the last known values", auth_required: "Sign in again under Devices & services",
    order_missing: "This order is no longer in the active list",
    rate_limited: "Tesla asked the tracker to wait", failed: "Could not start the update",
  },
  de: {
    title: "Tesla-Bestellung", subtitle: "Deine Bestellung im Überblick", demo: "Demo",
    demoText: "Beispielbestellung. Die Schaltfläche simuliert eine Lieferänderung.",
    liveText: "Bestelldaten aus der Tesla Fleet API",
    model: "Modell", status: "Bestellstatus", delivery_window: "Lieferfenster",
    delivery_center: "Auslieferungszentrum", appointment: "Übergabetermin",
    production_status: "Produktionsstatus", vin: "Fahrgestellnummer",
    timeline: "Letzte Änderungen", empty: "Bisher keine Änderungen erfasst.",
    vinChange: "Fahrgestellnummer erkannt oder geändert",
    lastSuccess: "Letzte erfolgreiche Abfrage", refresh: "Bestellung aktualisieren",
    simulate: "Änderung simulieren", waiting: "Warte auf Bestelldaten", ok: "Überwachung aktiv",
    problem: "Letzte bekannte Werte werden angezeigt",
    auth_required: "Unter Geräte & Dienste erneut anmelden",
    order_missing: "Die Bestellung steht nicht mehr in der Liste aktiver Bestellungen",
    rate_limited: "Tesla hat eine Wartezeit vorgegeben",
    failed: "Aktualisierung konnte nicht gestartet werden",
  },
};
const fields = ["model", "status", "delivery_window", "delivery_center", "appointment", "production_status", "vin"];
const escape = value => String(value ?? "—").replace(/[&<>"']/g, char => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[char]));
const style = `
  :host { display:block; color:var(--primary-text-color); }
  ha-top-app-bar-fixed { --app-header-background-color:var(--primary-background-color);
    --app-header-text-color:var(--primary-text-color); }
  main { max-width:900px; margin:auto; padding:clamp(16px,4vw,40px); }
  article { border:1px solid var(--divider-color); border-radius:20px;
    background:var(--card-background-color); margin-bottom:16px; overflow:hidden; }
  .hero { padding:24px; border-top:4px solid #cf3344; }
  h1 { font-size:clamp(26px,5vw,44px); margin:8px 0; line-height:1.12; }
  h2 { font-size:19px; margin:0 0 16px; }
  p { line-height:1.45; }
  .muted { color:var(--secondary-text-color); }
  .brand { font-size:13px; letter-spacing:.13em; font-weight:700; }
  .pill { display:inline-block; border:1px solid var(--divider-color);
    border-radius:99px; padding:5px 11px; margin-bottom:6px; }
  .body { padding:20px 24px; }
  dl { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,185px),1fr));
    gap:18px; margin:0; }
  dt { color:var(--secondary-text-color); font-size:13px; margin-bottom:5px; }
  dd { margin:0; overflow-wrap:anywhere; font-weight:500; }
  button { border-radius:10px; padding:9px 15px; min-height:44px;
    color:var(--primary-text-color); background:var(--secondary-background-color);
    border:1px solid var(--divider-color); font:inherit; cursor:pointer; }
  button:disabled { opacity:.6; cursor:default; }
  button:focus-visible { outline:2px solid var(--primary-color); outline-offset:3px; }
  ol { list-style:none; margin:0; padding:0; }
  li { border-top:1px solid var(--divider-color); padding:12px 0 0; margin-top:12px; }
  li p { margin:4px 0; overflow-wrap:anywhere; }
`;

class TeslaOrderTrackerPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this.shadowRoot.innerHTML = `<style>${style}</style>
      <ha-top-app-bar-fixed><ha-menu-button slot="navigationIcon"></ha-menu-button>
      <div slot="title">Tesla Order Tracker</div><main></main></ha-top-app-bar-fixed>`;
    this.main = this.shadowRoot.querySelector("main");
    this.menu = this.shadowRoot.querySelector("ha-menu-button");
    this.main.addEventListener("click", async event => {
      const button = event.target.closest("button[data-update]");
      if (!button || button.disabled ||
          !/^button\.[a-z0-9_]+$/.test(button.dataset.update)) return;
      button.disabled = true;
      try {
        await this._hass.callService("button", "press", {entity_id: button.dataset.update});
      } catch {
        const feedback = button.parentElement?.querySelector("[role=status]");
        if (feedback) feedback.textContent = this.words.failed;
      } finally {
        button.disabled = false;
      }
    });
  }

  set narrow(value) {
    this.menu.narrow = value;
  }

  set hass(hass) {
    this._hass = hass;
    this.menu.hass = hass;
    this.words = labels[hass.language?.startsWith("de") ? "de" : "en"];
    const entries = new Map();
    for (const [id, entity] of Object.entries(hass.states)) {
      const key = entity.attributes.tesla_order_tracker_id;
      if (!key) continue;
      if (!entries.has(key)) entries.set(key, {});
      const entry = entries.get(key);
      if (id.startsWith("button.")) entry.button = id;
      else if (entity.attributes.tesla_order_role === "vin") entry.vin = entity.state;
      else if (entity.attributes.tesla_order_role === "health") entry.status = entity;
    }
    const data = [...entries.values()].filter(entry => entry.status);
    const signature = JSON.stringify([hass.language, data]);
    if (signature === this.signature) return;
    const focused = this.shadowRoot.activeElement?.dataset.update;
    this.signature = signature;
    this.main.innerHTML = data.length
      ? data.map(entry => this.renderEntry(entry)).join("")
      : `<p role="status">${escape(this.words.waiting)}</p>`;
    if (focused) {
      [...this.main.querySelectorAll("button")].find(btn => btn.dataset.update === focused)?.focus();
    }
  }

  format(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? "—" : new Intl.DateTimeFormat(this._hass.locale?.language, {
      dateStyle: "medium", timeStyle: "short",
    }).format(date);
  }

  renderEntry(entry) {
    const t = this.words;
    const {attributes, state} = entry.status;
    const order = {...attributes.order};
    if (entry.vin && !["unknown", "unavailable"].includes(entry.vin)) order.vin = entry.vin;
    const history = Array.isArray(attributes.history) ? attributes.history : [];
    const detail = fields.map(key =>
      `<div><dt>${escape(t[key])}</dt><dd>${escape(order[key])}</dd></div>`).join("");
    const events = history.map(event => `<li><time class="muted">${escape(this.format(event.at))}</time>
      ${event.changes.map(change => `<p>${change.field === "vin" ? escape(t.vinChange)
        : `<strong>${escape(t[change.field])}</strong> · ${escape(change.before)} → ${escape(change.after)}`}</p>`).join("")}
      </li>`).join("");
    return `<article><section class="hero">
      <div class="brand">${escape(attributes.is_demo ? t.demo : t.title)}</div>
      <h1>${escape(order.model ?? t.title)}</h1>
      <p class="muted">${escape(attributes.is_demo ? t.demoText : t.liveText)}</p>
      <p class="pill">${escape(t[state] ?? (attributes.is_demo ? t.demo : t.problem))}</p>
      <p class="muted">${escape(t.lastSuccess)} · ${escape(this.format(attributes.last_success))}</p>
      ${entry.button && (!attributes.is_demo || history.length < 2)
        ? `<button data-update="${escape(entry.button)}">${escape(attributes.is_demo ? t.simulate : t.refresh)}</button>` : ""}
      <div role="status" class="muted"></div></section>
      <section class="body"><dl>${detail}</dl></section></article>
      <article class="body"><h2>${escape(t.timeline)}</h2>${events
        ? `<ol>${events}</ol>` : `<p class="muted">${escape(t.empty)}</p>`}</article>`;
  }
}

if (!customElements.get("tesla-order-tracker-panel")) {
  customElements.define("tesla-order-tracker-panel", TeslaOrderTrackerPanel);
}
