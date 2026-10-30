// Portfolio Hub page (Alpine.js + Plotly + Tabulator). No build step, no network except /api.
// Migrated tabs: Overview, Holdings, Rebalancing, Optimize, Performance & Analytics, Connections.

const usd = (n) => (n === null || n === undefined ? "" : "$" + Math.round(n).toLocaleString("en-US"));
const signedPct = (p) => (p >= 0 ? "+" : "") + p.toFixed(1) + "%";
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const COLORS = { trad: "rgb(139,224,164)", roth: "rgb(180,151,231)", broker: "rgb(254,136,177)", cash: "rgb(246,207,113)" };
const TEXT_COLS = ["account_name", "account_type", "owner", "symbol", "name", "sector", "purchase_date"];
const NUM_COLS = ["qty", "purchase_price"];

async function api(url, { method = "GET", body } = {}) {
  const opts = { method };
  if (body !== undefined) { opts.headers = { "Content-Type": "application/json" }; opts.body = JSON.stringify(body); }
  const r = await fetch(url, opts);
  let data = null;
  try { data = await r.json(); } catch (_) { /* not JSON */ }
  if (!r.ok) {
    const d = data && data.detail;
    const err = new Error(`${r.status}: ${(d && (d.message || (typeof d === "string" && d))) || r.statusText}`);
    err.status = r.status;
    err.errors = (d && d.errors) || [];
    throw err;
  }
  return data;
}

// Plotly measures its container when created; re-lay-out when the size changes (tab switches, resizes).
function refitOnResize(el, refit) {
  new ResizeObserver(() => { if (el.offsetWidth > 0) refit(); }).observe(el);
}
const plotOpts = { responsive: true, displaylogo: false };

// Tabulator and Plotly objects are kept out of Alpine's reactive state (proxying breaks both libraries).
let grid = null;
let nextRid = 1;
const errorRids = new Set();
let indicatorMap = {};
let indicatorsLoading = false;

const withRid = (rows) => rows.map((r) => ({ ...r, rid: nextRid++ }));
const num = (v) => (v === null || v === undefined || v === "" || Number.isNaN(Number(v)) ? null : Number(v));
const text = (v) => (v === null || v === undefined ? "" : String(v).trim());
const normalise = (r) => ({
  account_name: text(r.account_name), account_type: text(r.account_type), owner: text(r.owner) || "Joint",
  symbol: text(r.symbol), name: text(r.name), sector: text(r.sector),
  qty: num(r.qty), purchase_price: num(r.purchase_price), purchase_date: text(r.purchase_date).slice(0, 10),
});
// Order-independent fingerprint of the grid, so "unsaved changes" means "differs from what is stored".
const fingerprint = (rows) => JSON.stringify(rows.map((r) => JSON.stringify(normalise(r))).sort());

function hub() {
  return {
    usd, signedPct,
    tabs: [
      { key: "overview", label: "Overview" },
      { key: "holdings", label: "Holdings" },
      { key: "rebalancing", label: "Rebalancing" },
      { key: "harvest", label: "Optimize" },
      { key: "performance", label: "Performance & Analytics" },
      { key: "connections", label: "Connections" },
      { key: "tax_records", label: "Tax Records" },
    ],
    tab: "overview",
    meta: null, metaError: null,
    legacyUrl: `${location.protocol}//${location.hostname}:8501/portfolio_hub`,

    ov: { loading: false, error: null, data: null },
    tm: { loading: false, error: null, data: null },

    periodKey: "", busy: false,
    hold: { loading: false, loaded: false, error: null },
    gridReady: false, dirty: false, baseline: "",
    summary: { rows: 0, accounts: 0, symbols: 0, byType: [], byIndicator: [] },
    msg: { kind: "", text: "" },
    report: { errors: [], warnings: [], ok: "" },
    ind: { loading: false, error: null, loadedFor: "" },
    indRows: [],
    lookup: { symbol: "", loading: false, result: null, error: null },

    // rebalancing state
    rb: { cash: 10, bonds: 10, stocks: 80, threshold: 5, busy: false, error: null,
          result: null, saved: null, savedMsg: "" },

    // optimize (tax harvest) state
    opt: { agi: 80000, marginalRate: 22, lossThreshold: 500, gainThreshold: 500,
           dropTrigger: 10, busy: false, error: null, result: null },
    optSubTab: "harvest",

    // DAF bundling state
    daf: { agi: 150000, annualGiving: 5000, yearsToBunde: 3, marginalRate: 22,
           stdDeduction: 29200, busy: false, error: null, result: null },

    // factor analysis state
    fac: { busy: false, error: null, result: null },
    perfSubTab: "metrics",

    // performance state
    perf: { period: "all", benchmarkPreset: "^GSPC", benchmark: "^GSPC",
            customTicker: "", busy: false, error: null, result: null,
            updateBenchmark() {
              this.benchmark = this.benchmarkPreset === "custom" ? this.customTicker : this.benchmarkPreset;
            } },

    // harvest savings (DI) state
    harvSav: { year: new Date().getFullYear(), loading: false, error: null, data: null },

    // tax records state
    txr: {
      subTab: "transactions",
      loaded: false, loading: false, error: null,
      data: { rows: [], total: 0, truncated: false, totals: {}, choices: { accounts: [], types: [] } },
      f: { account: "", symbol: "", types: [], start: "", end: "" },
      cb: { loaded: false, loading: false, error: null, method: "FIFO", account: "", symbol: "",
            data: { lots: [], total_basis: 0, choices: { accounts: [] } } },
      cg: { loaded: false, loading: false, error: null, method: "FIFO", year: "", taxableOnly: true,
            data: { years: [], rows: [], unmatched: [] } },
    },

    // connections (SnapTrade) state
    conn: {
      state: "idle",   // idle | loading | ready | error | unconfigured
      error: null,
      data: { connected: false, account_count: 0, accounts: [], last_sync: null },
      linking: false,
      authLink: null,
      syncing: false,
      syncMonth: new Date().getMonth() + 1,
      syncYear: new Date().getFullYear(),
      syncMsg: { kind: "", text: "" },
      confirmDisconnect: false,
    },

    // Schwab Direct API state
    sw: {
      loaded: false,
      loading: false,
      configured: true,
      detail: "",
      connected: false,
      accounts: [],
      authUrl: null,
      callbackUrl: "",
      busy: false,
      syncing: false,
      confirmDisconnect: false,
      msg: { kind: "", text: "" },
    },

    // ------------------------------------------------------------------ startup
    async init() {
      try {
        this.meta = await api("/api/portfolio/meta");
      } catch (e) {
        this.metaError = "Could not load portfolio periods: " + e.message;
        return;
      }
      const eff = this.meta.effective;
      this.periodKey = this.key(eff.month, eff.year);
      const wanted = location.hash.replace("#", "");
      this.openTab(this.tabs.some((t) => t.key === wanted) ? wanted : "overview");
    },

    key: (m, y) => `${y}-${String(m).padStart(2, "0")}`,
    get period() {
      const [y, m] = this.periodKey.split("-").map(Number);
      return { month: m, year: y };
    },
    get periodOptions() {
      if (!this.meta) return [];
      const rows = new Map(this.meta.periods.map((p) => [this.key(p.month, p.year), p.rows]));
      for (const p of [this.meta.current, this.meta.effective]) if (!rows.has(this.key(p.month, p.year))) rows.set(this.key(p.month, p.year), 0);
      return [...rows.entries()].sort((a, b) => (a[0] < b[0] ? 1 : -1)).map(([k, n]) => {
        const [y, m] = k.split("-").map(Number);
        return { key: k, label: `${MONTHS[m - 1]} ${y} (${n} rows)` };
      });
    },

    openTab(key) {
      this.tab = key;
      history.replaceState(null, "", "#" + key);
      if (key === "overview" && !this.ov.data && !this.ov.loading) this.loadOverview();
      if (key === "holdings" && !this.hold.loaded && !this.hold.loading) this.loadHoldings();
      if (key === "rebalancing" && !this.rb.saved && !this.rb.busy) this.rbLoadDefaults();
      if (key === "harvest" && !this.opt.result && !this.opt.busy) this.optPrefillAgi();
      if (key === "harvest") this.dafMaybeInit();
      if (key === "performance" && !this.perf.result && !this.perf.busy) this.perfLoad();
      if (key === "connections" && this.conn.state === "idle") this.connLoadStatus();
      if (key === "connections" && !this.sw.loaded && !this.sw.loading) this.swLoadStatus();
      if (key === "tax_records" && !this.txr.loaded && !this.txr.loading) this.txrLoad();
    },

    // ------------------------------------------------------------------ Overview
    async loadOverview() {
      this.ov.loading = true; this.ov.error = null;
      try {
        this.ov.data = await api("/api/portfolio/overview");
        await this.$nextTick();
        this.drawOverview();
      } catch (e) {
        this.ov.error = "Could not load overview: " + e.message;
      } finally {
        this.ov.loading = false;
      }
      if (this.ov.data) this.loadTreemap();
    },

    drawOverview() {
      const d = this.ov.data;
      if (d.history) {
        const h = d.history;
        const max = Math.max(...h.labels.map((_, i) => h.cash[i] + h.taxable[i] + h.traditional[i] + h.roth[i]));
        const el = document.getElementById("chart-stacked");
        Plotly.newPlot(el, [
          { type: "bar", x: h.labels, y: h.traditional, name: "Traditional", marker: { color: COLORS.trad } },
          { type: "bar", x: h.labels, y: h.roth, name: "Roth", marker: { color: COLORS.roth } },
          { type: "bar", x: h.labels, y: h.taxable, name: "Broker", marker: { color: COLORS.broker } },
          { type: "bar", x: h.labels, y: h.cash, name: "Cash", marker: { color: COLORS.cash } },
        ], {
          barmode: "stack", height: 400, margin: { t: 40, l: 70, r: 10, b: 50 },
          xaxis: { title: "Date", tickformat: "%b %Y" }, yaxis: { title: "Amount", tickformat: "$,.0f", range: [0, max * 1.1] },
          legend: { title: { text: "Account Type" }, orientation: "h", y: 1.12 },
        }, plotOpts);
        refitOnResize(el, () => Plotly.Plots.resize(el));

        const pie = document.getElementById("chart-pie");
        Plotly.newPlot(pie, [{
          type: "pie", labels: d.mix.labels, values: d.mix.values,
          marker: { colors: [COLORS.cash, COLORS.broker, COLORS.trad, COLORS.roth] },
          textinfo: "label+percent+value", hoverinfo: "label+percent+value", texttemplate: "%{label}<br>%{percent}<br>$%{value:,.0f}",
        }], { height: 400, margin: { t: 40, l: 1, r: 1, b: 1 }, legend: { orientation: "h", y: 1.12 } }, plotOpts);
        refitOnResize(pie, () => Plotly.Plots.resize(pie));
      }
      if (d.performance) {
        const p = d.performance, last = p.labels.length - 1;
        const up = p.vs_amount >= 0, colour = up ? "#21c354" : "#ff4b4b";
        const el = document.getElementById("chart-perf");
        Plotly.newPlot(el, [
          { type: "scatter", mode: "lines+markers", x: p.labels, y: p.portfolio, name: "Your Portfolio",
            line: { color: "#4c78a8", width: 2 }, marker: { size: 5 }, hovertemplate: "%{x|%b %Y}<br>Portfolio: $%{y:,.0f}<extra></extra>" },
          { type: "scatter", mode: "lines", x: p.labels, y: p.benchmark, name: `Benchmark (${(p.benchmark_rate * 100).toFixed(0)}% p.a.)`,
            line: { color: "#f58518", width: 2, dash: "dash" }, hovertemplate: "%{x|%b %Y}<br>Benchmark: $%{y:,.0f}<extra></extra>" },
          { type: "scatter", x: [...p.labels, ...[...p.labels].reverse()], y: [...p.portfolio, ...[...p.benchmark].reverse()],
            fill: "toself", fillcolor: "rgba(76,120,168,0.10)", line: { color: "rgba(255,255,255,0)" }, showlegend: false, hoverinfo: "skip" },
        ], {
          height: 420, margin: { t: 40, l: 70, r: 10, b: 40 }, xaxis: { title: "Month", tickformat: "%b %Y" },
          yaxis: { title: "Portfolio Value ($)", tickformat: "$,.0f" }, legend: { orientation: "h", y: 1.1, x: 1, xanchor: "right" },
          annotations: [{
            x: p.labels[last], y: p.portfolio[last], ax: 0, ay: -40, showarrow: true, arrowhead: 2, arrowcolor: colour,
            bordercolor: colour, borderwidth: 1, bgcolor: "white", font: { color: colour, size: 11 },
            text: `${up ? "▲" : "▼"} ${usd(Math.abs(p.vs_amount))} (${signedPct(p.vs_percent)}) vs benchmark`,
          }],
        }, plotOpts);
        refitOnResize(el, () => Plotly.Plots.resize(el));
      }
    },

    async loadTreemap() {
      this.tm.loading = true; this.tm.error = null; this.tm.data = null;
      try {
        this.tm.data = await api("/api/portfolio/treemap");
        if (this.tm.data.ready) { await this.$nextTick(); this.drawTreemap(); }
      } catch (e) {
        this.tm.error = "Could not load holdings breakdown: " + e.message;
      } finally {
        this.tm.loading = false;
      }
    },

    drawTreemap() {
      const d = this.tm.data, el = document.getElementById("chart-treemap");
      Plotly.newPlot(el, [{
        type: "treemap", branchvalues: "total",
        ids: d.nodes.map((n) => n.id), labels: d.nodes.map((n) => n.label),
        parents: d.nodes.map((n) => n.parent), values: d.nodes.map((n) => n.value),
        marker: { colors: d.nodes.map((n) => n.color), colorscale: d.colorscale.map(([p, c]) => [p, c.replace(/\s/g, "")]),
                  cmid: d.midpoint, showscale: true, colorbar: { title: { text: "Current value" } } },
        textinfo: "label+text+value+percent root", texttemplate: "%{label}<br>$%{value:,.2f}",
        hovertemplate: "%{label}<br>$%{value:,.0f}<extra></extra>",
      }], { height: 600, margin: { t: 50, l: 25, r: 25, b: 25 } }, plotOpts);
      refitOnResize(el, () => Plotly.Plots.resize(el));
    },

    // ------------------------------------------------------------------ Holdings: loading
    say(kind, textMsg) { this.msg = { kind, text: textMsg }; },
    clearReport() { this.report = { errors: [], warnings: [], ok: "" }; this.setErrorRows([]); },

    async run(fn) {
      this.busy = true;
      try { return await fn(); } catch (e) { this.say("error", e.message); } finally { this.busy = false; }
    },

    async loadHoldings() {
      this.hold.loading = true; this.hold.error = null;
      try {
        const { month, year } = this.period;
        const data = await api(`/api/portfolio/holdings?month=${month}&year=${year}`);
        await this.showRows(data.rows);
        this.baseline = fingerprint(data.rows);
        this.refresh();
        this.loadIndicators();
      } catch (e) {
        this.hold.error = "Could not load holdings: " + e.message;
      } finally {
        this.hold.loading = false;
      }
    },

    async showRows(rows) {
      const data = withRid(rows);
      if (!grid) {
        this.hold.loaded = true;
        await this.$nextTick();
        this.buildGrid(data);
      } else {
        const editing = grid.modules.edit && grid.modules.edit.currentCell;     // an open editor breaks setData()
        if (editing) { try { editing.getComponent().cancelEdit(); } catch (_e) { /* the editor's cell is already gone */ } }
        await grid.setData(data);
      }
      this.gridReady = true;
    },

    async reload() {
      if (this.dirty && !confirm("Discard unsaved changes and reload from the database?")) return;
      this.clearReport(); this.say("", "");
      await this.run(() => this.loadHoldings());
      this.say("ok", "Reloaded from the database.");
    },

    async changePeriod() {
      if (this.dirty && !confirm("Discard unsaved changes and switch period?")) {
        this.periodKey = this.lastPeriodKey; return;
      }
      this.lastPeriodKey = this.periodKey;
      this.clearReport(); this.say("", "");
      indicatorMap = {}; this.ind.loadedFor = "";
      await this.run(() => this.loadHoldings());
    },

    // ------------------------------------------------------------------ Holdings: grid
    buildGrid(data) {
      const m = this.meta;
      const edit = (title, field, extra = {}) => ({ title, field, editor: "input", headerSort: true, ...extra });
      const money = (c) => { const v = c.getValue(); return v === null || v === undefined || v === "" ? "" : "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 4 }); };
      const qty = (c) => { const v = c.getValue(); return v === null || v === undefined || v === "" ? "" : Number(v).toLocaleString("en-US", { maximumFractionDigits: 4 }); };
      this.lastPeriodKey = this.periodKey;

      grid = new Tabulator("#grid-holdings", {
        data, index: "rid", layout: "fitColumns", height: 640, placeholder: "No holdings",
        rowFormatter: (row) => row.getElement().classList.toggle("row-error", errorRids.has(row.getData().rid)),
        columns: [
          edit("Account", "account_name", { minWidth: 130 }),
          { title: "Type", field: "account_type", editor: "list", editorParams: { values: m.account_types, clearable: false }, width: 105 },
          { title: "Owner", field: "owner", editor: "list", editorParams: { values: m.owners, clearable: false }, width: 95 },
          edit("Symbol", "symbol", { width: 120 }),
          edit("Name", "name", { minWidth: 160 }),
          { title: "Sector", field: "sector", minWidth: 150, editor: "list",
            editorParams: { values: m.sectors, autocomplete: true, freetext: true, allowEmpty: true, listOnEmpty: true, clearable: true } },
          { title: "Quantity", field: "qty", editor: "number", editorParams: { step: "any" }, hozAlign: "right", width: 105, formatter: qty },
          { title: "Purchase Price", field: "purchase_price", editor: "number", editorParams: { step: "any", min: 0 }, hozAlign: "right", width: 120, formatter: money },
          { title: "Purchase Date", field: "purchase_date", editor: "input", editorParams: { elementAttributes: { type: "date" } }, width: 135 },
          { title: "Market Indicator", field: "_ind", headerSort: false, width: 150,
            formatter: (c) => this.indicatorCell(c.getRow().getData().symbol) },
          { title: "", field: "_del", headerSort: false, width: 44, hozAlign: "center",
            formatter: () => "✕", cellClick: (_e, c) => c.getRow().delete() },
        ],
      });
      // A grid built or shown while its tab is hidden renders no rows; lay them out when it becomes visible.
      const host = document.getElementById("grid-holdings");
      new ResizeObserver(() => {
        if (host.offsetWidth > 0 && grid && grid.getDataCount() > 0 && !host.querySelector(".tabulator-row")) grid.redraw(true);
      }).observe(host);
      grid.on("cellEdited", (cell) => { this.onCellEdited(cell); });
      grid.on("rowDeleted", () => this.refresh());
      grid.on("rowAdded", () => this.refresh());
      grid.on("cellEdited", () => this.refresh());
    },

    indicatorCell(symbol) {
      const i = indicatorMap[text(symbol)];
      if (i) return `<span class="ind ind-${i.condition}" title="${i.recommendation.replace(/"/g, "&quot;")}">${i.label}</span>`;
      if (indicatorsLoading) return '<span class="muted">…</span>';
      return '<span class="muted">—</span>';
    },

    refresh() {
      const rows = grid ? grid.getData() : [];
      this.dirty = fingerprint(rows) !== this.baseline;
      const byType = {}, byInd = {};
      rows.forEach((r) => {
        byType[r.account_type] = (byType[r.account_type] || 0) + 1;
      });
      new Set(rows.map((r) => text(r.symbol))).forEach((s) => {
        const i = indicatorMap[s];
        if (i) byInd[i.label] = (byInd[i.label] || 0) + 1;
      });
      this.summary = {
        rows: rows.length,
        accounts: new Set(rows.map((r) => r.account_name)).size,
        symbols: new Set(rows.map((r) => text(r.symbol))).size,
        byType: Object.entries(byType).map(([k, n]) => ({ k, n })),
        byIndicator: Object.entries(byInd).map(([k, n]) => ({ k, n })),
      };
    },

    // When a symbol changes, fill a blank name and a blank/stale sector from Yahoo Finance (as the Streamlit editor does).
    async onCellEdited(cell) {
      if (cell.getField() !== "symbol") return;
      const row = cell.getRow(), sym = text(cell.getValue());
      if (!sym) return;
      const stale = new Set(this.meta.stale_sectors);
      if (/^\d/.test(sym)) { row.update({ sector: "MF:Cash" }); this.refresh(); return; }
      try {
        const r = await api("/api/portfolio/lookup?symbol=" + encodeURIComponent(sym));
        if (text(row.getData().symbol) !== sym) return;           // edited again while waiting
        if (!r.valid) { this.say("warn", `Symbol '${sym}' was not found in Yahoo Finance (${r.error || "no data"}).`); return; }
        const d = row.getData(), patch = {};
        if (!text(d.name) && r.name) patch.name = r.name;
        if (stale.has(text(d.sector)) && r.sector) patch.sector = r.sector;
        if (Object.keys(patch).length) row.update(patch);
        this.refresh();
      } catch (_) { /* lookup is a convenience; validation reports real problems */ }
    },

    addRow() {
      const today = new Date().toISOString().slice(0, 10);
      const [first] = this.meta.owners;
      grid.addRow({ rid: nextRid++, account_name: "", account_type: "Brokerage", owner: first || "Joint", symbol: "", name: "",
                    sector: "", qty: null, purchase_price: null, purchase_date: today }, true)
        .then((row) => { grid.scrollToRow(row, "top", false); row.getCell("account_name").edit(); });
    },

    // ------------------------------------------------------------------ Holdings: toolbar
    async copyPrevious() {
      if (grid && grid.getDataCount() > 0 && !confirm("Replace the rows in the grid with the previous month's holdings?")) return;
      await this.run(async () => {
        const data = await api("/api/portfolio/holdings/copy-previous", { method: "POST", body: this.period });
        await this.showRows(data.rows);
        this.clearReport(); this.refresh();
        this.say("ok", `Copied ${data.rows.length} holdings from ${data.from.month}/${data.from.year}. Not saved yet.`);
      });
    },

    importCsv(ev) {
      const file = ev.target.files[0];
      ev.target.value = "";
      if (!file) return;
      if (file.size > 1_500_000) { this.say("error", "That file is larger than 1.5 MB."); return; }
      if (grid && grid.getDataCount() > 0 && !confirm("Replace the rows in the grid with the contents of this CSV?")) return;
      const reader = new FileReader();
      reader.onload = () => this.run(async () => {
        const data = await api("/api/portfolio/holdings/import", { method: "POST", body: { ...this.period, csv: String(reader.result) } });
        await this.showRows(data.rows);
        this.clearReport(); this.refresh();
        this.say(data.warnings.length ? "warn" : "ok", `Imported ${data.rows.length} rows. Not saved yet.` + (data.warnings.length ? " " + data.warnings.join(" ") : ""));
      });
      reader.onerror = () => this.say("error", "Could not read that file.");
      reader.readAsText(file);
    },

    downloadCsv() {
      const { month, year } = this.period;
      const cols = ["month", "year", ...TEXT_COLS.slice(0, 6), ...NUM_COLS, "purchase_date"];
      const quote = (v) => { const s = v === null || v === undefined ? "" : String(v); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
      const lines = [cols.join(",")];
      grid.getData().forEach((r) => lines.push(cols.map((c) => quote(c === "month" ? month : c === "year" ? year : r[c])).join(",")));
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([lines.join("\n") + "\n"], { type: "text/csv" }));
      a.download = `portfolio_holdings_${month}_${year}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
    },

    backupAll() {
      return this.run(async () => {
        const r = await api("/api/portfolio/holdings/backup", { method: "POST", body: {} });
        this.say("ok", `Backup created: ${r.file} (${r.rows} rows).`);
      });
    },

    enrich() {
      if (this.dirty) { this.say("warn", "Save or reload first: enrichment writes to the database directly."); return; }
      return this.run(async () => {
        this.say("", "Fetching names and sectors from Yahoo Finance...");
        const r = await api("/api/portfolio/holdings/enrich", { method: "POST", body: this.period });
        if (r.enriched === 0 && r.failed === 0) this.say("ok", "All holdings already complete. Nothing to update.");
        else if (r.enriched > 0) {
          this.say("ok", `Updated ${r.enriched} holding(s). ${r.unchanged} already complete. ${r.failed} symbol(s) had no data.`);
          await this.loadHoldings();
          this.ov.data = null;
        } else this.say("warn", `Enrichment finished: ${r.failed} symbol(s) returned no data from Yahoo Finance.`);
      });
    },

    // ------------------------------------------------------------------ Holdings: validate and save
    payload() {
      return { ...this.period, rows: grid.getData().map((r) => ({ rid: r.rid, ...normalise(r) })) };
    },

    setErrorRows(rids) {
      errorRids.clear();
      rids.forEach((r) => r != null && errorRids.add(r));
      if (grid) grid.getRows().forEach((r) => r.reformat());
    },

    showProblems(errors, warnings) {
      this.report = { errors, warnings, ok: "" };
      this.setErrorRows(errors.map((e) => e.rid));
    },

    focusRow(rid) {
      const row = grid && grid.getRow(rid);
      if (!row) return;
      grid.scrollToRow(row, "center", false).catch(() => {});
      const el = row.getElement();
      el.classList.add("row-hl");
      setTimeout(() => el.classList.remove("row-hl"), 2000);
    },

    validateRows() {
      return this.run(async () => {
        this.say("", "Checking rows and looking up symbols in Yahoo Finance...");
        const r = await api("/api/portfolio/holdings/validate", { method: "POST", body: this.payload() });
        this.say("", "");
        this.showProblems(r.errors, r.warnings);
        if (!r.errors.length && !r.warnings.length) this.report.ok = "All validations passed. Ready to save.";
      });
    },

    save() {
      return this.run(async () => {
        this.clearReport();
        try {
          const r = await api("/api/portfolio/holdings", { method: "PUT", body: this.payload() });
          await this.showRows(r.rows);
          this.baseline = fingerprint(r.rows);
          this.refresh();
          this.ov.data = null; this.tm.data = null;      // the Overview must re-read the new holdings
          indicatorMap = {}; this.ind.loadedFor = ""; this.loadIndicators();
          this.say("ok", `Saved ${r.saved} holdings for ${r.month}/${r.year}: ${r.added} added, ${r.updated} changed, ${r.removed} removed.` +
                         (r.backup ? ` Previous version backed up to .backups/${r.backup}.` : ""));
        } catch (e) {
          if (e.status === 422 && e.errors.length) {
            this.showProblems(e.errors, []);
            this.say("error", `Cannot save: ${e.errors.length} problem(s) found. Nothing was saved.`);
          } else throw e;
        }
      });
    },

    // ------------------------------------------------------------------ Holdings: market indicators
    get indicatorsReady() { return this.ind.loadedFor !== ""; },

    async loadIndicators() {
      const { month, year } = this.period, k = this.periodKey;
      if (indicatorsLoading || this.ind.loadedFor === k) return;
      indicatorsLoading = true; this.ind.loading = true; this.ind.error = null;
      if (grid) grid.getRows().forEach((r) => r.reformat());
      try {
        const r = await api(`/api/portfolio/holdings/indicators?month=${month}&year=${year}`);
        if (k !== this.periodKey) return;
        indicatorMap = Object.fromEntries(Object.entries(r.indicators).filter(([, v]) => v));
        this.ind.loadedFor = k;
        this.indRows = Object.entries(indicatorMap).map(([symbol, v]) => ({ symbol, ...v })).sort((a, b) => (a.symbol < b.symbol ? -1 : 1));
      } catch (e) {
        this.ind.error = "Could not calculate market indicators: " + e.message;
      } finally {
        indicatorsLoading = false; this.ind.loading = false;
        if (grid) grid.getRows().forEach((r) => r.reformat());
        this.refresh();
      }
    },

    // ------------------------------------------------------------------ Holdings: ticker lookup
    async doLookup() {
      const symbol = this.lookup.symbol.trim();
      if (!symbol) { this.lookup.error = "Enter a ticker symbol."; return; }
      this.lookup.loading = true; this.lookup.error = null; this.lookup.result = null;
      try {
        this.lookup.result = await api("/api/portfolio/lookup?symbol=" + encodeURIComponent(symbol));
      } catch (e) {
        this.lookup.error = e.message;
      } finally {
        this.lookup.loading = false;
      }
    },

    // ------------------------------------------------------------------ Rebalancing
    async rbLoadDefaults() {
      try {
        const d = await api("/api/portfolio/rebalancing/defaults");
        this.rb.saved = d.saved || null;
        if (d.saved) {
          // Pre-fill inputs from saved targets
          this.rb.cash      = d.saved.cash_pct;
          this.rb.bonds     = d.saved.bonds_pct;
          this.rb.stocks    = d.saved.stocks_pct;
          this.rb.threshold = d.saved.drift_threshold_pct;
        } else {
          // Fall back to bucket-strategy-derived defaults
          this.rb.cash      = d.defaults.cash_pct;
          this.rb.bonds     = d.defaults.bonds_pct;
          this.rb.stocks    = d.defaults.stocks_pct;
          this.rb.threshold = d.defaults.drift_threshold_pct;
        }
      } catch (e) {
        // Non-fatal — user can still enter values manually
      }
    },

    async rbCalculate(saveTargets) {
      const total = this.rb.cash + this.rb.bonds + this.rb.stocks;
      if (Math.abs(total - 100) > 0.01) return;
      this.rb.busy = true; this.rb.error = null; this.rb.result = null; this.rb.savedMsg = "";
      try {
        const res = await api("/api/portfolio/rebalancing/calculate", {
          method: "POST",
          body: {
            cash_pct: this.rb.cash,
            bonds_pct: this.rb.bonds,
            stocks_pct: this.rb.stocks,
            drift_threshold_pct: this.rb.threshold,
            save_targets: saveTargets,
          },
        });
        this.rb.result = res;
        if (saveTargets) {
          this.rb.saved = { cash_pct: this.rb.cash, bonds_pct: this.rb.bonds,
                            stocks_pct: this.rb.stocks, drift_threshold_pct: this.rb.threshold,
                            last_updated: new Date().toISOString() };
          this.rb.savedMsg = "Targets saved — will be used in Portfolio Review reports.";
          setTimeout(() => { this.rb.savedMsg = ""; }, 4000);
        }
        this.$nextTick(() => this.rbDrawChart());
      } catch (e) {
        this.rb.error = "Could not calculate rebalancing plan: " + e.message;
      } finally {
        this.rb.busy = false;
      }
    },

    rbPeriodLabel() {
      if (!this.rb.result) return "";
      const { month, year } = this.rb.result.period;
      return `${MONTHS[month - 1]} ${year}`;
    },

    rbActionClass(a) {
      const v = a.action.toLowerCase();
      if (v === "sell" && a.account_type === "Brokerage") return "rb-sell-taxable";
      if (v === "sell") return "rb-sell";
      if (v === "buy") return "rb-buy";
      if (v === "redirect") return "rb-redirect";
      return "rb-transfer";
    },

    rbDrawChart() {
      const el = document.getElementById("chart-rebalancing");
      if (!el || !this.rb.result || !window.Plotly) return;
      const s = this.rb.result.summary;
      const classes = s.map((x) => x.asset_class);
      const current = s.map((x) => x.current_pct);
      const target  = s.map((x) => x.target_pct);
      Plotly.newPlot(el, [
        { type: "bar", name: "Current %", x: classes, y: current,
          marker: { color: s.map((x) => x.is_drifted ? "#ef4444" : "#3b82d4") },
          text: current.map((v) => v.toFixed(1) + "%"), textposition: "auto" },
        { type: "bar", name: "Target %",  x: classes, y: target,
          marker: { color: "#9ca3af" },
          text: target.map((v) => v.toFixed(1) + "%"), textposition: "auto" },
      ], {
        barmode: "group",
        height: 260,
        margin: { t: 20, b: 40, l: 40, r: 20 },
        legend: { orientation: "h", y: -0.2 },
        plot_bgcolor: "#f7f8fa", paper_bgcolor: "#ffffff",
        yaxis: { title: "Allocation %", range: [0, 100] },
      }, { responsive: true, displaylogo: false });
    },

    // ------------------------------------------------------------------ Optimize (Tax Harvest)
    async optPrefillAgi() {
      // Try to pre-fill AGI from config (best-effort — non-fatal if unavailable)
      try {
        const cfg = await api("/api/config");
        const wages = (cfg?.income?.person1_annual_wages || 0) + (cfg?.income?.person2_annual_wages || 0);
        if (wages > 0) this.opt.agi = wages;
        const rate = cfg?.tax_strategy?.max_roth_conversion_tax_rate;
        if (rate > 0) this.opt.marginalRate = Math.round(rate * 100);
      } catch (_) { /* non-fatal */ }
    },

    async optScan() {
      this.opt.busy = true; this.opt.error = null; this.opt.result = null;
      try {
        this.opt.result = await api("/api/portfolio/optimize", {
          method: "POST",
          body: {
            agi: this.opt.agi,
            marginal_rate_pct: this.opt.marginalRate,
            loss_threshold: this.opt.lossThreshold,
            gain_threshold: this.opt.gainThreshold,
            drop_trigger_pct: this.opt.dropTrigger,
          },
        });
      } catch (e) {
        this.opt.error = "Scan failed: " + e.message;
      } finally {
        this.opt.busy = false;
      }
    },

    optRowClass(h) {
      const r = h.recommendation || "";
      if (r.startsWith("🔴")) return "opt-harvest-loss";
      if (r.startsWith("🟢")) return "opt-harvest-gain";
      if (r.startsWith("🟡")) return "opt-monitor";
      return "";
    },

    // ------------------------------------------------------------------ Performance
    async perfLoad() {
      this.perf.busy = true; this.perf.error = null; this.perf.result = null;
      const bm = this.perf.benchmarkPreset === "custom" ? this.perf.customTicker : this.perf.benchmarkPreset;
      try {
        this.perf.result = await api(
          `/api/portfolio/performance?period=${encodeURIComponent(this.perf.period)}&benchmark=${encodeURIComponent(bm || "^GSPC")}`
        );
        this.$nextTick(() => this.perfDrawCharts());
      } catch (e) {
        this.perf.error = "Could not load performance data: " + e.message;
      } finally {
        this.perf.busy = false;
      }
    },

    perfRatingLabel(metric, val) {
      if (metric === "sharpe") {
        if (val > 1.5) return "Excellent (>1.5)";
        if (val > 1.0) return "Good (>1.0)";
        if (val > 0.5) return "Fair (>0.5)";
        return "Poor (<0.5)";
      }
      if (metric === "sortino") {
        if (val > 2.0) return "Excellent (>2.0)";
        if (val > 1.5) return "Good (>1.5)";
        if (val > 1.0) return "Fair (>1.0)";
        return "Poor (<1.0)";
      }
      if (metric === "beta") {
        if (val < 0.8) return "Defensive (<0.8)";
        if (val < 1.2) return "Neutral (~1.0)";
        return "Aggressive (>1.2)";
      }
      return "";
    },

    perfDrawCharts() {
      if (!this.perf.result || !this.perf.result.available || !window.Plotly) return;
      const r = this.perf.result;

      // ── Line chart: portfolio vs benchmark ──────────────────────────────
      const el = document.getElementById("chart-perf-line");
      if (el) {
        const traces = [{
          type: "scatter", mode: "lines", name: "Portfolio",
          x: r.chart.labels, y: r.chart.portfolio,
          line: { color: "#3b82d4", width: 2 },
          hovertemplate: "%{x}<br>Portfolio: $%{y:,.0f}<extra></extra>",
        }];
        if (r.chart.benchmark.length) {
          traces.push({
            type: "scatter", mode: "lines", name: `Benchmark (${r.benchmark})`,
            x: r.chart.labels, y: r.chart.benchmark,
            line: { color: "#f58518", width: 2, dash: "dash" },
            hovertemplate: "%{x}<br>Benchmark: $%{y:,.0f}<extra></extra>",
          });
        }
        Plotly.newPlot(el, traces, {
          height: 320, margin: { t: 20, b: 50, l: 60, r: 20 },
          xaxis: { title: "Date" }, yaxis: { title: "Value ($)", tickformat: "$,.0f" },
          legend: { orientation: "h", y: -0.25 },
          hovermode: "x unified",
          plot_bgcolor: "#f7f8fa", paper_bgcolor: "#ffffff",
        }, plotOpts);
      }

      // ── Pie: attribution ────────────────────────────────────────────────
      const elA = document.getElementById("chart-perf-attr");
      if (elA) {
        const { estimated_growth, estimated_contrib } = r.attribution;
        Plotly.newPlot(elA, [{
          type: "pie",
          labels: ["Investment Growth", "Contributions"],
          values: [Math.max(0, estimated_growth), Math.max(0, estimated_contrib)],
          marker: { colors: ["#3b82d4", "#72b7b2"] },
          texttemplate: "%{label}<br>$%{value:,.0f}<br>(%{percent})",
          hovertemplate: "%{label}<br>$%{value:,.0f}<br>%{percent}<extra></extra>",
        }], { height: 280, margin: { t: 10, b: 10, l: 10, r: 10 },
              plot_bgcolor: "#f7f8fa", paper_bgcolor: "#ffffff" }, plotOpts);
      }

      // ── Scatter: risk-return ─────────────────────────────────────────────
      const elR = document.getElementById("chart-perf-rr");
      if (elR) {
        const rr = r.risk_return;
        const traces2 = [{
          type: "scatter", mode: "markers+text",
          name: "Portfolio",
          x: [rr.portfolio_vol], y: [rr.portfolio_ret],
          marker: { size: 14, color: "#3b82d4" },
          text: ["Portfolio"], textposition: "top center",
          hovertemplate: "Vol: %{x:.2f}%<br>Return: %{y:.2f}%<extra></extra>",
        }];
        if (rr.benchmark_vol !== null) {
          traces2.push({
            type: "scatter", mode: "markers+text",
            name: "Benchmark",
            x: [rr.benchmark_vol], y: [rr.benchmark_ret],
            marker: { size: 14, color: "#f58518", symbol: "diamond" },
            text: ["Benchmark"], textposition: "top center",
            hovertemplate: "Vol: %{x:.2f}%<br>Return: %{y:.2f}%<extra></extra>",
          });
        }
        Plotly.newPlot(elR, traces2, {
          height: 280, margin: { t: 20, b: 50, l: 50, r: 20 },
          xaxis: { title: "Volatility (%)", zeroline: false },
          yaxis: { title: "Return (%)", zeroline: true },
          legend: { orientation: "h", y: -0.25 },
          plot_bgcolor: "#f7f8fa", paper_bgcolor: "#ffffff",
        }, plotOpts);
      }
    },

    // ------------------------------------------------------------------ DAF Bundling
    dafMaybeInit() {
      // Pre-fill AGI from config if not already set
      if (this.daf.agi === 150000) {
        api("/api/config").then((cfg) => {
          const wages = (cfg?.income?.person1_annual_wages || 0) + (cfg?.income?.person2_annual_wages || 0);
          if (wages > 0) this.daf.agi = wages;
          const rate = cfg?.tax_strategy?.max_roth_conversion_tax_rate;
          if (rate > 0) this.daf.marginalRate = Math.round(rate * 100);
        }).catch(() => {});
      }
    },

    async dafAnalyze() {
      this.daf.busy = true; this.daf.error = null; this.daf.result = null;
      try {
        this.daf.result = await api("/api/portfolio/daf", {
          method: "POST",
          body: {
            agi:                this.daf.agi,
            annual_giving:      this.daf.annualGiving,
            years_to_bundle:    this.daf.yearsToBunde,
            marginal_rate_pct:  this.daf.marginalRate,
            standard_deduction: this.daf.stdDeduction,
          },
        });
      } catch (e) {
        this.daf.error = "DAF analysis failed: " + e.message;
      } finally {
        this.daf.busy = false;
      }
    },

    // ------------------------------------------------------------------ Factor Analysis
    factorsMaybeLoad() {
      if (!this.fac.result && !this.fac.busy) this.factorsLoad();
    },

    async factorsLoad() {
      this.fac.busy = true; this.fac.error = null; this.fac.result = null;
      try {
        this.fac.result = await api("/api/portfolio/factors");
        this.$nextTick(() => this.factorsDrawRadar());
      } catch (e) {
        this.fac.error = "Factor analysis failed: " + e.message;
      } finally {
        this.fac.busy = false;
      }
    },

    factorColor(tilt) {
      if (tilt > 5) return "#21c354";
      if (tilt < -5) return "#ef4444";
      return "#3b82d4";
    },

    factorsDrawRadar() {
      const el = document.getElementById("chart-factors-radar");
      if (!el || !this.fac.result || !this.fac.result.available || !window.Plotly) return;
      const exp = this.fac.result.exposure;
      const categories = ["Value", "Growth", "Momentum", "Quality"];
      const scores     = [exp.value, exp.growth, exp.momentum, exp.quality];
      // Close the polygon
      const theta  = [...categories, categories[0]];
      const values = [...scores, scores[0]];
      const bench  = [50, 50, 50, 50, 50];
      Plotly.newPlot(el, [
        { type: "scatterpolar", mode: "lines+markers",
          name: "Portfolio", r: values, theta,
          fill: "toself", fillcolor: "rgba(59,130,212,0.15)",
          line: { color: "#3b82d4", width: 2 },
          marker: { size: 6 } },
        { type: "scatterpolar", mode: "lines",
          name: "Benchmark (S&P 500)", r: bench, theta,
          line: { color: "#9ca3af", width: 1, dash: "dash" } },
      ], {
        polar: { radialaxis: { visible: true, range: [0, 100], tickfont: { size: 11 } } },
        showlegend: true,
        height: 320,
        margin: { t: 30, b: 30, l: 40, r: 40 },
        paper_bgcolor: "#ffffff",
        legend: { orientation: "h", y: -0.12 },
      }, plotOpts);
    },

    // ------------------------------------------------------------------ Connections
    async connLoadStatus() {
      this.conn.state = "loading";
      this.conn.error = null;
      try {
        this.conn.data = await api("/api/portfolio/connections/status");
        this.conn.state = "ready";
      } catch (e) {
        if (e.status === 503) {
          this.conn.state = "unconfigured";
        } else {
          this.conn.state = "error";
          this.conn.error = e.message;
        }
      }
    },

    async connRefreshStatus() {
      this.conn.state = "idle";
      this.conn.authLink = null;
      await this.connLoadStatus();
    },

    async connGetLink() {
      this.conn.linking = true;
      this.conn.authLink = null;
      try {
        const r = await api("/api/portfolio/connections/auth", { method: "POST", body: {} });
        this.conn.authLink = r.auth_link;
      } catch (e) {
        this.conn.error = "Could not generate auth link: " + e.message;
        this.conn.state = "error";
      } finally {
        this.conn.linking = false;
      }
    },

    async connSync() {
      this.conn.syncing = true;
      this.conn.syncMsg = { kind: "", text: "" };
      try {
        const r = await api("/api/portfolio/connections/sync", {
          method: "POST",
          body: { month: this.conn.syncMonth, year: this.conn.syncYear },
        });
        this.conn.syncMsg = {
          kind: "ok",
          text: `Synced ${r.synced} holdings → ${r.merged} saved, ${r.enriched} enriched.${this.txnNote(r.transactions)} Navigate to Holdings to review.`,
        };
        this.txr.loaded = this.txr.cb.loaded = this.txr.cg.loaded = false;
        // Refresh the status block (last_sync timestamp)
        await this.connRefreshStatus();
        // Invalidate any loaded holdings so they reload fresh
        this.hold.loaded = false;
      } catch (e) {
        this.conn.syncMsg = { kind: "error", text: "Sync failed: " + e.message };
      } finally {
        this.conn.syncing = false;
      }
    },

    async connDisconnect() {
      try {
        await api("/api/portfolio/connections", { method: "DELETE" });
        this.conn.confirmDisconnect = false;
        this.conn.state = "idle";
        await this.connLoadStatus();
      } catch (e) {
        this.conn.error = "Disconnect failed: " + e.message;
        this.conn.state = "error";
        this.conn.confirmDisconnect = false;
      }
    },

    txnNote(t) {
      if (!t) return "";
      if (t.error) return ` Transactions: import failed (${t.error}).`;
      return ` Transactions: ${t.stored} stored.`;
    },

    // ------------------------------------------------------------------ Tax Records: Transactions
    async txrLoad() {
      this.txr.loading = true; this.txr.error = null;
      const f = this.txr.f, q = new URLSearchParams();
      if (f.account) q.set("account", f.account);
      if (f.symbol.trim()) q.set("symbol", f.symbol.trim());
      f.types.forEach((t) => q.append("types", t));
      if (f.start) q.set("start", f.start);
      if (f.end) q.set("end", f.end);
      try {
        this.txr.data = await api("/api/portfolio/transactions?" + q.toString());
        this.txr.loaded = true;
      } catch (e) {
        this.txr.error = "Could not load transactions: " + e.message;
      } finally {
        this.txr.loading = false;
      }
    },

    txrClear() {
      this.txr.f = { account: "", symbol: "", types: [], start: "", end: "" };
      this.txrLoad();
    },

    txrToggleType(t) {
      const i = this.txr.f.types.indexOf(t);
      if (i >= 0) this.txr.f.types.splice(i, 1); else this.txr.f.types.push(t);
      this.txrLoad();
    },

    txrMoney(v) {
      if (v === null || v === undefined || v === 0) return "";
      return (v < 0 ? "-$" : "$") + Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    },

    txrQty(v) {
      return v ? Number(v).toLocaleString("en-US", { maximumFractionDigits: 4 }) : "";
    },

    txrPrice(v) {
      return v ? "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 4 }) : "";
    },

    txrTotalsList() {
      return Object.entries(this.txr.data.totals).map(([type, t]) => ({ type, ...t }));
    },

    txrSub(name) {
      this.txr.subTab = name;
      if (name === "costbasis" && !this.txr.cb.loaded && !this.txr.cb.loading) this.cbLoad();
      if (name === "capgains" && !this.txr.cg.loaded && !this.txr.cg.loading) this.cgLoad();
    },

    // ------------------------------------------------------------------ Tax Records: Cost Basis
    async cbLoad() {
      const cb = this.txr.cb, q = new URLSearchParams({ method: cb.method });
      if (cb.account) q.set("account", cb.account);
      if (cb.symbol.trim()) q.set("symbol", cb.symbol.trim());
      cb.loading = true; cb.error = null;
      try {
        cb.data = await api("/api/portfolio/cost-basis?" + q.toString());
        cb.loaded = true;
      } catch (e) {
        cb.error = "Could not load cost basis: " + e.message;
      } finally {
        cb.loading = false;
      }
    },

    // ------------------------------------------------------------------ Tax Records: Capital Gains
    async cgLoad() {
      const cg = this.txr.cg, q = new URLSearchParams({ method: cg.method, taxable_only: cg.taxableOnly });
      if (cg.year) q.set("year", cg.year);
      cg.loading = true; cg.error = null;
      try {
        cg.data = await api("/api/portfolio/capital-gains?" + q.toString());
        cg.loaded = true;
      } catch (e) {
        cg.error = "Could not load capital gains: " + e.message;
      } finally {
        cg.loading = false;
      }
    },

    cgExportCsv() {
      const cols = ["account", "symbol", "quantity", "acquired", "sold", "proceeds", "basis", "gain", "term"];
      this.downloadCsv("capital-gains.csv", cols, this.txr.cg.data.rows);
    },

    cbExportCsv() {
      const cols = ["account", "symbol", "acquired", "quantity", "unit_cost", "basis", "term"];
      this.downloadCsv("cost-basis-lots.csv", cols, this.txr.cb.data.lots);
    },

    downloadCsv(filename, cols, rows) {
      const esc = (v) => '"' + String(v ?? "").replace(/"/g, '""') + '"';
      const csv = [cols.join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
    },

    txrExportCsv() {
      const cols = ["date", "account", "type", "symbol", "description", "quantity", "price", "amount", "fee"];
      const esc = (v) => '"' + String(v ?? "").replace(/"/g, '""') + '"';
      const csv = [cols.join(","), ...this.txr.data.rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
      a.download = "transactions.csv";
      a.click();
      URL.revokeObjectURL(a.href);
    },

    // ------------------------------------------------------------------ Schwab Direct
    async swLoadStatus() {
      this.sw.loading = true;
      try {
        const r = await api("/api/portfolio/connections/schwab/status");
        Object.assign(this.sw, {
          configured: r.configured, detail: r.detail || "",
          connected: r.connected, accounts: r.accounts || [], loaded: true,
        });
      } catch (e) {
        this.sw.msg = { kind: "error", text: "Could not load Schwab status: " + e.message };
        this.sw.loaded = true;
      } finally {
        this.sw.loading = false;
      }
    },

    async swAuthorize() {
      this.sw.busy = true;
      this.sw.msg = { kind: "", text: "" };
      try {
        const r = await api("/api/portfolio/connections/schwab/auth", { method: "POST", body: {} });
        this.sw.authUrl = r.auth_url;
      } catch (e) {
        this.sw.msg = { kind: "error", text: "Could not start authorization: " + e.message };
      } finally {
        this.sw.busy = false;
      }
    },

    async swComplete() {
      if (!this.sw.callbackUrl.trim()) return;
      this.sw.busy = true;
      this.sw.msg = { kind: "", text: "" };
      try {
        await api("/api/portfolio/connections/schwab/complete", {
          method: "POST", body: { callback_url: this.sw.callbackUrl },
        });
        this.sw.authUrl = null;
        this.sw.callbackUrl = "";
        await this.swLoadStatus();
      } catch (e) {
        this.sw.msg = { kind: "error", text: "Authorization failed: " + e.message };
      } finally {
        this.sw.busy = false;
      }
    },

    async swSync() {
      this.sw.syncing = true;
      this.sw.msg = { kind: "", text: "" };
      try {
        const r = await api("/api/portfolio/connections/schwab/sync", {
          method: "POST",
          body: { month: this.conn.syncMonth, year: this.conn.syncYear },
        });
        this.sw.msg = {
          kind: "ok",
          text: `Synced ${r.synced} holdings → ${r.merged} saved, ${r.enriched} enriched. Navigate to Holdings to review.`,
        };
        this.txr.loaded = this.txr.cb.loaded = this.txr.cg.loaded = false;
        this.hold.loaded = false;
      } catch (e) {
        this.sw.msg = { kind: "error", text: "Sync failed: " + e.message };
      } finally {
        this.sw.syncing = false;
      }
    },

    async swDisconnect() {
      try {
        await api("/api/portfolio/connections/schwab", { method: "DELETE" });
        this.sw.confirmDisconnect = false;
        await this.swLoadStatus();
      } catch (e) {
        this.sw.msg = { kind: "error", text: "Disconnect failed: " + e.message };
        this.sw.confirmDisconnect = false;
      }
    },

    // ------------------------------------------------------------------ Harvest Savings (DI)
    async harvSavLoad() {
      if (this.harvSav.loading) return;
      this.harvSav.loading = true;
      this.harvSav.error = null;
      try {
        this.harvSav.data = await api(`/api/portfolio/harvest-savings?year=${this.harvSav.year}`);
      } catch (e) {
        if (e.status === 503) {
          this.harvSav.error = null; // not configured — show setup prompt instead
          this.harvSav.data = null;
        } else {
          this.harvSav.error = e.message;
        }
      } finally {
        this.harvSav.loading = false;
      }
    },
  };
}
