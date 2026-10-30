// Advanced Strategy Tools page (Alpine.js + Plotly). No build step, no network except /api and /static/guides.
// Each calculator posts its form to /api/advanced/<tool>; the server owns all the arithmetic.

async function api(url, { method = "GET", body } = {}) {
  const opts = { method };
  if (body !== undefined) { opts.headers = { "Content-Type": "application/json" }; opts.body = JSON.stringify(body); }
  const r = await fetch(url, opts);
  let data = null;
  try { data = await r.json(); } catch (_) { /* not JSON */ }
  if (!r.ok) {
    const d = data && data.detail;
    let msg = r.statusText;
    if (typeof d === "string") msg = d;
    else if (Array.isArray(d)) {
      // FastAPI validation errors: [{loc: ["body", "age"], msg: "..."}]
      msg = d.map((e) => `${(e.loc || []).filter((x) => x !== "body").join(".")}: ${e.msg}`).join("; ");
    }
    throw new Error(msg);
  }
  return data;
}

// Plotly measures its container when created; inside a hidden tab it comes out at the wrong size.
const observed = new WeakSet();
function refitOnResize(el) {
  if (!el || observed.has(el)) return;
  observed.add(el);
  new ResizeObserver(() => { if (el.offsetWidth > 0) Plotly.Plots.resize(el); }).observe(el);
}

const usd0 = (v) => (v == null ? "—" : (v < 0 ? "-$" : "$") + Math.abs(Number(v)).toLocaleString("en-US", { maximumFractionDigits: 0 }));
const usd2 = (v) => (v == null ? "—" : (v < 0 ? "-$" : "$") + Math.abs(Number(v)).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));

const LAYOUT = { margin: { t: 50, r: 20, b: 50, l: 70 }, font: { size: 12 }, paper_bgcolor: "#fff" };
const CONFIG = { displayModeBar: false, responsive: true };

function advancedPage() {
  const year = new Date().getFullYear();
  return {
    tab: "planner",
    tabs: [
      { id: "planner", label: "Tax Planner" },
      { id: "multi", label: "Multi-Year Tax Planning" },
      { id: "backdoor", label: "Backdoor & Mega Backdoor Roth" },
      { id: "nua", label: "NUA Analysis" },
      { id: "qcd", label: "QCD Optimizer" },
      { id: "sepp", label: "72(t) SEPP Calculator" },
      { id: "harvest", label: "Capital Loss Harvesting" },
    ],
    filings: ["married_filing_jointly", "single"],
    meta: null, metaError: null,
    guides: {},
    busy: {}, err: {}, res: {},   // keyed by tool name; read with !! because keys appear on first use

    // Form state. Defaults are the Streamlit page's defaults.
    planner: { wages: 0, trad_dist: 0, interest: 0, ltcg: 0, stcg: 0, medicare: 0, year, maxdaf: "N",
               charitable: 0, headroom_pct: 24, daf_type: "securities", roth_amount: 0, prepaid: 0 },
    multi: { start_year: year, filing_status: "married_filing_jointly", income: 150000, cg_lt: 0,
             conversion: 0, qbi: 0, loss_cf: 0, window: 5 },
    qbi: { qbi_income: 100000, total_taxable_income: 200000, filing_status: "married_filing_jointly",
           w2_wages: 0, ubia: 0, is_sstb: false },
    backdoor: { year, age: 45, magi: 250000, trad_balance: 0, basis: 0, filing_status: "married_filing_jointly" },
    betr: { conversion_amount: 50000, trad_balance: 500000, basis: 0, current_rate: 24, future_rate: 22,
            annual_return: 7, years: 20, pay_from_taxable: true, taxable_balance: 200000 },
    mega: { year, age: 45, employee_deferral: 23500, employer_match: 5000,
            plan_allows_after_tax: true, plan_allows_in_plan_conversion: true },
    nua: { cost_basis: 50000, current_value: 200000, ordinary_rate: 24, ltcg_rate: 15, years: 5 },
    qcd: { year, age: 73, ira_balance: 500000, rmd: 20000, agi: 100000, charitable: 10000,
           marginal_rate: 22, filing_status: "married_filing_jointly" },
    sepp: { balance: 500000, age: 50, rate: 5.0, method: "Fixed Amortization", marginal_rate: 22 },
    harvest: { start_year: year, window: 5, filing_status: "married_filing_jointly", income: 150000, unrealized_losses: 50000 },

    async init() {
      try {
        this.meta = await api("/api/advanced/meta");
        this.planner.year = this.meta.default_planner_year;
        // The Tax Planner reads the filing status from Settings server-side; the other forms default to MFJ, as in Streamlit.
      } catch (e) {
        this.metaError = `Could not load page settings: ${e.message}`;
      }
    },

    yearRange(n) { return Array.from({ length: n }, (_, i) => new Date().getFullYear() + i); },

    // ── formatting ────────────────────────────────────────────
    fmt0: usd0,
    pct0(v) { return v == null ? "—" : (v * 100).toFixed(0) + "%"; },
    pct1(v) { return v == null ? "—" : (v * 100).toFixed(1) + "%"; },
    fmtMetric(m) {
      switch (m.kind) {
        case "percent1": return m.value.toFixed(1) + "%";
        case "percent0": return m.value.toFixed(0) + "%";
        case "money0": return usd0(m.value);
        default: return usd2(m.value);
      }
    },
    fmtDelta(d) { return (d < 0 ? "-" : "") + Math.abs(d).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); },

    // ── guides ────────────────────────────────────────────────
    async loadGuide(key, ev) {
      if (!ev.target.open || this.guides[key]) return;
      try {
        const r = await fetch(`/static/guides/${key}.html`);
        if (!r.ok) throw new Error(r.statusText);
        this.guides[key] = await r.text();
      } catch (e) {
        this.guides[key] = `<p class="error">Could not load the guide: ${e.message}</p>`;
      }
    },

    // ── running a calculator ──────────────────────────────────
    payload(tool) {
      const f = this[tool];
      switch (tool) {
        case "betr":
          return { ...f, current_rate: f.current_rate / 100, future_rate: f.future_rate / 100, annual_return: f.annual_return / 100 };
        case "nua":
          return { ...f, ordinary_rate: f.ordinary_rate / 100, ltcg_rate: f.ltcg_rate / 100 };
        case "qcd":
          return { ...f, marginal_rate: f.marginal_rate / 100 };
        case "sepp":
          return { ...f, rate: f.rate / 100, marginal_rate: f.marginal_rate / 100 };
        default:
          return { ...f };
      }
    },
    ENDPOINT: { planner: "tax-planner", multi: "multi-year", qbi: "qbi", backdoor: "backdoor",
                betr: "betr", mega: "mega-backdoor", nua: "nua", qcd: "qcd", sepp: "sepp", harvest: "harvest" },

    async run(tool) {
      this.busy[tool] = true; this.err[tool] = null;
      try {
        // Plain data in Alpine state is fine; Plotly figures are not stored.
        this.res[tool] = await api(`/api/advanced/${this.ENDPOINT[tool]}`, { method: "POST", body: this.payload(tool) });
        await this.$nextTick();
        this.draw(tool);
      } catch (e) {
        this.res[tool] = null;
        this.err[tool] = e.message;
      } finally {
        this.busy[tool] = false;
      }
    },

    // ── charts ────────────────────────────────────────────────
    draw(tool) {
      const r = this.res[tool];
      if (!r) return;
      if (tool === "multi") {
        const el = document.getElementById("chart-multi");
        if (!el) return;
        const yrs = r.years.map((p) => p.year);
        Plotly.react(el, [
          { type: "bar", x: yrs, y: r.years.map((p) => p.federal_tax), name: "Federal Tax", marker: { color: "rgb(239,85,59)" } },
          { type: "bar", x: yrs, y: r.years.map((p) => p.bracket_headroom), name: "Bracket Headroom", marker: { color: "rgb(99,110,250)" } },
        ], { ...LAYOUT, barmode: "group", title: "Federal Tax vs. Bracket Headroom",
             xaxis: { title: "Year", type: "category" }, yaxis: { title: "Amount ($)", tickformat: "$,.0f" },
             legend: { orientation: "h", y: 1.12 } }, CONFIG);
        refitOnResize(el);
      } else if (tool === "betr") {
        const el = document.getElementById("chart-betr");
        if (!el) return;
        const roth = r.roth_future_value > r.traditional_future_value;
        Plotly.react(el, [{
          type: "bar", x: ["Traditional IRA", "Roth IRA"], y: [r.traditional_future_value, r.roth_future_value],
          marker: { color: [roth ? "rgb(239,85,59)" : "rgb(99,110,250)", roth ? "rgb(0,204,150)" : "rgb(239,85,59)"] },
          text: [usd0(r.traditional_future_value), usd0(r.roth_future_value)], textposition: "outside",
        }], { ...LAYOUT, title: `After-Tax Future Value (${r.years}-Year Horizon)`,
              yaxis: { title: "After-Tax Future Value ($)", tickformat: "$,.0f" } }, CONFIG);
        refitOnResize(el);
      } else if (tool === "nua") {
        const el = document.getElementById("chart-nua");
        if (!el) return;
        const rec = r.strategy_recommended;
        Plotly.react(el, [{
          type: "bar", x: ["NUA Strategy Tax", "IRA Rollover Tax"], y: [r.total_nua_tax, r.tax_if_distributed_as_cash],
          marker: { color: [rec ? "rgb(0,204,150)" : "rgb(239,85,59)", rec ? "rgb(239,85,59)" : "rgb(0,204,150)"] },
          text: [usd0(r.total_nua_tax), usd0(r.tax_if_distributed_as_cash)], textposition: "outside",
        }], { ...LAYOUT, title: "Tax Cost: NUA Strategy vs. IRA Rollover",
              yaxis: { title: "Tax Cost ($)", tickformat: "$,.0f" } }, CONFIG);
        refitOnResize(el);
      } else if (tool === "harvest") {
        const el = document.getElementById("chart-harvest");
        if (!el) return;
        Plotly.react(el, [{
          type: "bar", x: r.rows.map((x) => x.year), y: r.rows.map((x) => x.tax_savings),
          name: "Tax Savings", marker: { color: "rgb(0,204,150)" },
        }], { ...LAYOUT, title: "Annual Tax Savings from Loss Harvesting",
              xaxis: { title: "Year", type: "category" }, yaxis: { title: "Tax Savings ($)", tickformat: "$,.0f" } }, CONFIG);
        refitOnResize(el);
      }
    },

    resizeCharts() {
      document.querySelectorAll(".chart").forEach((el) => {
        if (el.offsetWidth > 0 && el.data) Plotly.Plots.resize(el);
      });
    },
  };
}
