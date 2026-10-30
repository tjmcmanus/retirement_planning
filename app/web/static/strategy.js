// Strategy page (Alpine.js + Plotly + Tabulator). No build step, no network except /api.

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = (await r.json()).detail || detail; } catch (_) { /* not JSON */ }
    throw new Error(`${r.status}: ${detail}`);
  }
  return r.json();
}

// Plotly/Tabulator measure their container when created. Inside a hidden panel
// it comes out at default size. Re-lay-out whenever the container's real size changes.
function refitOnResize(el, refit) {
  if (!el) return;
  new ResizeObserver(() => { if (el.offsetWidth > 0) refit(); }).observe(el);
}

function fmt$(v) {
  if (v == null) return "—";
  return "$" + Number(v).toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function strategyPage() {
  return {
    // ── top-level state ───────────────────────────────────────────
    loading: true,
    err: null,
    activeTab: "plan",
    tabs: [
      { id: "plan",    label: "📋 Long-Term Plan" },
      { id: "monthly", label: "📅 Monthly Plan" },
      { id: "buckets", label: "🪣 Bucket Strategy" },
      { id: "tax",     label: "💰 Tax Analytics" },
      { id: "incexp",  label: "📊 Income & Expenses" },
    ],

    // ── per-section state ─────────────────────────────────────────
    strategy: null,   // main /api/strategy response
    timeline: { loading: false, error: null, events: null },
    timelineCategories: [
      { id: "ss",       label: "Social Security",  color: "#3b82d4" },
      { id: "medicare", label: "Medicare",         color: "#4ecdc4" },
      { id: "rmd",      label: "RMDs",             color: "#f38181" },
      { id: "roth",     label: "Roth Conversions", color: "#aa96da" },
    ],
    timelineFilter: ["ss", "medicare", "rmd"],  // Roth conversions off by default
    flow:     { loading: false, error: null, data: null },
    monthly:  { loading: false, error: null, data: null },
    buckets:  { loading: false, error: null, data: null },
    tax:      { loading: false, error: null, data: null },
    incexp:   { loading: false, error: null, data: null },

    decisions: { loading: false, error: null, data: null },
    decisionYear: null,

    flowYear: null,
    flowYears: [],
    monthlyYear: null,
    monthlyYears: [],

    activeTaxTab: "overview",
    taxTabs: [
      { id: "overview",  label: "Tax Burden" },
      { id: "income",    label: "Income Sources" },
      { id: "rates",     label: "Effective Rates" },
      { id: "insights",  label: "Insights" },
    ],

    // ── entry point ───────────────────────────────────────────────
    async load() {
      try {
        this.strategy = await getJSON("/api/strategy");

        // Set initial year selectors before revealing the UI
        const years = this.strategy.strategy.map(r => r["Year"]);
        this.flowYears = years;
        this.monthlyYears = years;
        this.flowYear = years[0];
        this.monthlyYear = years[0];

        this.err = null;
      } catch (e) {
        this.err = "Could not load strategy: " + e.message;
      } finally {
        this.loading = false;
      }

      // x-if="!loading" stamps the DOM on the next tick — wait for it before
      // calling getElementById, otherwise the containers don't exist yet.
      await this.$nextTick();
      this.drawStrategyTable();

      // Kick off all secondary sections in parallel — errors are scoped per-section
      this.loadTimeline();
      this.loadMoneyFlow();
      this.loadMonthly();
      this.loadBuckets();
      this.loadTax();
      this.loadIncExp();
    },

    // ── Projected balances chart (used on both Long-Term Plan and Income Sources) ──
    drawBalancesChart() {
      // Prefer tax.data.balances (flat arrays), fall back to strategy.balances (records)
      let years, vals;
      const el = document.getElementById("chart-balances");
      if (!el) return;

      if (this.tax.data && this.tax.data.balances) {
        const b = this.tax.data.balances;
        years = b.years;
        vals = [
          { name: "Cash",        data: b.cash,        color: "#64b5f6" },
          { name: "Taxable",     data: b.taxable,     color: "#ffb74d" },
          { name: "Traditional", data: b.traditional, color: "#ef9a9a" },
          { name: "Roth",        data: b.roth,        color: "#a5d6a7" },
          { name: "DAF",         data: b.daf,         color: "#ce93d8" },
        ];
      } else {
        const s = this.strategy;
        years = s.balances.map(r => r["Year"]);
        vals = [
          { name: "Cash",        data: s.balances.map(r => r["Cash Balance"]        || 0), color: "#64b5f6" },
          { name: "Taxable",     data: s.balances.map(r => r["Taxable Balance"]     || 0), color: "#ffb74d" },
          { name: "Traditional", data: s.balances.map(r => r["Traditional Balance"] || 0), color: "#ef9a9a" },
          { name: "Roth",        data: s.balances.map(r => r["Roth Balance"]        || 0), color: "#a5d6a7" },
          { name: "DAF",         data: s.balances.map(r => r["DAF Balance"]         || 0), color: "#ce93d8" },
        ];
      }

      Plotly.newPlot(el,
        vals.map(v => ({
          type: "scatter", mode: "lines", stackgroup: "one", name: v.name,
          x: years, y: v.data,
          line: { color: v.color },
          hovertemplate: "%{x}<br>" + v.name + ": $%{y:,.0f}<extra></extra>",
        })), {
          title: "Projected Account Balances", height: 380,
          margin: { t: 50, l: 70, r: 10, b: 40 },
          yaxis: { tickformat: "$,.0f" },
          legend: { orientation: "h", y: -0.18 },
        }, { responsive: true, displaylogo: false });
      refitOnResize(el, () => Plotly.Plots.resize(el));
    },

    // ── Year-by-year detail table ─────────────────────────────────
    drawStrategyTable() {
      const el = document.getElementById("table-strategy");
      if (!el) return;
      // Display titles; the field names stay as the engine emits them.
      const COLUMN_TITLES = {
        "Trad→\nCash": "Traditional Distribution",
        "Trad→\nRoth": "Roth Conversion",
        "DAF Contribution": "DAF",
      };
      // Narrow columns whose headers wrap onto two lines.
      const COLUMN_WIDTHS = {
        "Trad→\nCash": 110, "Trad→\nRoth": 110, "Healthcare Cost": 100,
      };
      const s = this.strategy;
      // Show a curated subset of columns to keep the table manageable
      const show = ["Year","Age","Stage","Wages","SS Benefits","Trad→\nCash","Trad→\nRoth",
                    "RMD","Expenses","Healthcare Cost","DAF Contribution","Federal Tax","State Tax",
                    "AGI","Total Portfolio"];
      const cols = show.filter(c => s.columns.includes(c));
      const table = new Tabulator(el, {
        data: s.strategy, layout: "fitDataStretch", height: 380, frozenColumns: 1,
        headerWordWrap: true,
        columns: cols.map(c => ({
          title: COLUMN_TITLES[c] || c.replace(/\n/g, " "), field: c,
          ...(COLUMN_WIDTHS[c] ? { width: COLUMN_WIDTHS[c] } : {}),
          hozAlign: (c === "Year" || c === "Age" || c === "Stage") ? "left" : "right",
          formatter: cell => {
            const v = cell.getValue();
            if (v == null) return "—";
            if (c === "Year" || c === "Age" || c === "Stage") return String(v);
            if (typeof v === "number")
              return v.toLocaleString("en-US", { maximumFractionDigits: 0 });
            return v;
          },
        })),
      });
      table.on("rowClick", (_e, row) => {
        this.decisionYear = row.getData()["Year"];
        this.loadDecisions();
      });
      refitOnResize(el, () => table.redraw(true));
    },

    // ── Why these numbers (engine decision log) ───────────────────
    async loadDecisions() {
      if (!this.decisionYear) { this.decisions.data = null; return; }
      this.decisions.loading = true;
      this.decisions.error = null;
      try {
        this.decisions.data = await getJSON(`/api/strategy/decisions?year=${this.decisionYear}`);
      } catch (e) {
        this.decisions.data = null;
        this.decisions.error = "Decisions: " + e.message;
      } finally {
        this.decisions.loading = false;
      }
    },

    decisionCategoryLabel(cat) {
      const labels = {
        stage_info: "Stage", tax_strategy: "Tax strategy", roth_conversion: "Roth conversion",
        aca_decisions: "ACA / healthcare", irmaa_decisions: "IRMAA", cash_replenishment: "Cash",
        brokerage_replenishment: "Brokerage", contribution_decisions: "Contributions",
        rmd_decisions: "RMDs", ltcg_decisions: "Capital gains", ss_decisions: "Social Security",
        daf_decisions: "Donor Advised Fund",
      };
      return labels[cat] || cat;
    },

    decisionValues(values) {
      return Object.entries(values).map(([k, v]) => {
        let shown = v;
        if (typeof v === "number") {
          // Rates are stored as fractions; show them as percentages. Everything else is a dollar/count figure.
          shown = /rate|betr|ratio|pct|bracket/i.test(k) && Math.abs(v) <= 1
            ? (v * 100).toFixed(2) + "%"
            : v.toLocaleString("en-US", { maximumFractionDigits: Number.isInteger(v) ? 0 : 2 });
        } else if (v !== null && typeof v === "object") {
          shown = JSON.stringify(v);
        }
        return `${k.replace(/_/g, " ")}: ${shown}`;
      }).join("  ·  ");
    },

    // ── Timeline ──────────────────────────────────────────────────
    async loadTimeline() {
      this.timeline.loading = true;
      try {
        const d = await getJSON("/api/strategy/timeline");
        this.timeline.events = d.events;
        this.$nextTick(() => this.drawTimeline(d.events));
      } catch (e) {
        this.timeline.error = "Timeline: " + e.message;
      } finally {
        this.timeline.loading = false;
      }
    },

    toggleTimelineCategory(id) {
      const i = this.timelineFilter.indexOf(id);
      if (i >= 0) this.timelineFilter.splice(i, 1);
      else this.timelineFilter.push(id);
      this.drawTimeline(this.timeline.events);
    },

    drawTimeline(allEvents) {
      const wrap = document.getElementById("timeline-container");
      if (!wrap) return;
      wrap.innerHTML = "";
      const events = (allEvents || []).filter(e => this.timelineFilter.includes(e.category));
      if (!events.length) return;

      const years = events.map(e => e.year);
      const minY = Math.min(...years) - 1;
      const maxY = Math.max(...years) + 1;
      const span = maxY - minY || 1;

      // Horizontal position (2.5 % – 97.5 %)
      const pos = y => 2.5 + ((y - minY) / span) * 95;

      const catColor = {
        ss:       "#3b82d4",
        medicare: "#4ecdc4",
        rmd:      "#f38181",
        roth:     "#aa96da",
      };

      // Add baseline
      const line = document.createElement("div");
      line.className = "timeline-line";
      wrap.appendChild(line);

      // Add year tick marks
      for (let y = minY + 1; y <= maxY; y++) {
        const tick = document.createElement("div");
        tick.style.cssText =
          `position:absolute;left:${pos(y)}%;top:50%;transform:translate(-50%,0);` +
          `font-size:.65rem;color:#999;text-align:center;`;
        tick.innerHTML = `<div style="width:1px;height:10px;background:#ccc;margin:0 auto"></div>${y}`;
        wrap.appendChild(tick);
      }

      // Group events by year so we can alternate above/below
      const byYear = {};
      events.forEach(e => { (byYear[e.year] = byYear[e.year] || []).push(e); });

      let globalIdx = 0;
      Object.entries(byYear).forEach(([yr, evts]) => {
        evts.forEach((evt, i) => {
          const above = (globalIdx % 2 === 0);
          globalIdx++;

          const el = document.createElement("div");
          el.className = "timeline-event";
          el.style.left = pos(parseInt(yr)) + "%";

          const color = catColor[evt.category] || "#888";
          el.innerHTML =
            `<div class="dot" style="background:${color}"></div>` +
            `<div class="evt-label ${above ? "evt-above" : "evt-below"}">` +
            `<div class="title">${evt.event}</div>` +
            `<div class="year">${evt.year}</div>` +
            `<div class="detail">${evt.details}</div>` +
            `</div>`;
          wrap.appendChild(el);
        });
      });
    },

    // ── Money Flow (Sankey) ───────────────────────────────────────
    async loadMoneyFlow() {
      if (!this.flowYear) return;
      this.flow.loading = true;
      this.flow.error = null;
      try {
        const d = await getJSON(`/api/strategy/money-flow?year=${this.flowYear}`);
        this.flow.data = d;
        this.$nextTick(() => this.drawSankey(d));
      } catch (e) {
        this.flow.error = "Money flow: " + e.message;
      } finally {
        this.flow.loading = false;
      }
    },

    drawSankey(d) {
      const el = document.getElementById("chart-sankey");
      if (!el || !d.labels.length) return;

      // Node base colors (rgb only — opacity applied separately for links)
      const _nodeRGB = {
        "Wages/Salary":           "31,119,180",
        "Social Security":        "23,190,207",
        "Traditional IRA/401(k)": "214,39,40",
        "Roth IRA/401(k)":        "148,103,189",
        "Brokerage":              "255,187,120",
        "Cash/Spending":          "152,223,138",
        "Living Expenses":        "31,119,180",
        "Healthcare":             "255,127,14",
        "Federal Tax":            "188,189,34",
        "State Tax":              "23,190,207",
        "Payroll Taxes":          "227,119,194",
        "Roth Conversion":        "148,103,189",
        "DAF (Charitable)":       "140,86,75",
      };
      const _rgb = l => _nodeRGB[l] || "180,180,180";
      const nodeColors = d.labels.map(l => `rgba(${_rgb(l)},.85)`);
      // Each link inherits its source node's color at reduced opacity
      const linkColors = d.sources.map(si => `rgba(${_rgb(d.labels[si])},.35)`);

      Plotly.react(el, [{
        type: "sankey",
        node: {
          pad: 20, thickness: 25,
          line: { color: "black", width: .5 },
          label: d.labels, color: nodeColors,
          hovertemplate: "%{label}<br>Total: $%{value:,.0f}<extra></extra>",
        },
        link: {
          source: d.sources, target: d.targets, value: d.values,
          color: linkColors,
          hovertemplate: "%{source.label} → %{target.label}<br>$%{value:,.0f}<extra></extra>",
        },
      }], {
        title: `Money Flow — ${d.year}`,
        height: 420, margin: { t: 50, l: 10, r: 10, b: 20 },
      }, { responsive: true, displaylogo: false });
      refitOnResize(el, () => Plotly.Plots.resize(el));
    },

    // ── Monthly plan ──────────────────────────────────────────────
    async loadMonthly() {
      if (!this.monthlyYear) return;
      this.monthly.loading = true;
      this.monthly.error = null;
      try {
        this.monthly.data = await getJSON(`/api/strategy/monthly-plan?year=${this.monthlyYear}`);
      } catch (e) {
        this.monthly.error = "Monthly plan: " + e.message;
      } finally {
        this.monthly.loading = false;
      }
    },

    // ── Bucket Strategy ───────────────────────────────────────────
    async loadBuckets() {
      this.buckets.loading = true;
      try {
        this.buckets.data = await getJSON("/api/strategy/buckets");
        if (this.buckets.data.enabled) {
          this.$nextTick(() => {
            this.drawBucketsChart();
            this.drawBucketsTable();
          });
        }
      } catch (e) {
        this.buckets.error = "Buckets: " + e.message;
      } finally {
        this.buckets.loading = false;
      }
    },

    bucketCards() {
      const d = this.buckets.data;
      if (!d || !d.enabled) return [];
      return [
        { label: "🛡️ Bucket 1 — Safety",     value: d.bucket1.value, target: d.bucket1.target, pct: d.bucket1.pct, drift: d.bucket1.drift },
        { label: "🔄 Bucket 2 — Transition",  value: d.bucket2.value, target: d.bucket2.target, pct: d.bucket2.pct, drift: d.bucket2.drift },
        { label: "🚀 Bucket 3 — Growth",      value: d.bucket3.value, target: d.bucket3.target, pct: d.bucket3.pct, drift: d.bucket3.drift },
      ];
    },

    driftClass(drift) {
      const abs = Math.abs(drift);
      return abs < 5 ? "drift-ok" : abs < 15 ? "drift-warn" : "drift-bad";
    },

    drawBucketsChart() {
      const d = this.buckets.data;
      const el = document.getElementById("chart-buckets");
      if (!el || !d.enabled) return;
      const labels = ["Bucket 1<br>Safety", "Bucket 2<br>Transition", "Bucket 3<br>Growth"];
      Plotly.newPlot(el, [
        { type: "bar", name: "Current", x: labels,
          y: [d.bucket1.value, d.bucket2.value, d.bucket3.value],
          marker: { color: "#3b82d4" } },
        { type: "bar", name: "Target", x: labels,
          y: [d.bucket1.target, d.bucket2.target, d.bucket3.target],
          marker: { color: "#e5e7eb" } },
      ], {
        barmode: "group", title: "Current vs Target Allocation",
        height: 320, yaxis: { tickformat: "$,.0f" },
        margin: { t: 50, l: 70, r: 10, b: 60 }, legend: { orientation: "h", y: -0.2 },
      }, { responsive: true, displaylogo: false });
      refitOnResize(el, () => Plotly.Plots.resize(el));
    },

    drawBucketsTable() {
      const el = document.getElementById("table-buckets");
      if (!el) return;
      const d = this.buckets.data;
      if (!d.enabled || !d.holdings.length) return;
      const bucketLabel = {
        bucket_1_safety:     "Bucket 1 — Safety",
        bucket_2_transition: "Bucket 2 — Transition",
        bucket_3_growth:     "Bucket 3 — Growth",
      };
      new Tabulator(el, {
        data: d.holdings.map(h => ({
          ...h,
          bucket_label: bucketLabel[h.bucket] || h.bucket,
          value_fmt: fmt$(h.value),
        })),
        layout: "fitDataStretch", height: 280,
        columns: [
          { title: "Symbol",     field: "symbol",       width: 100 },
          { title: "Name",       field: "name",         minWidth: 160 },
          { title: "Bucket",     field: "bucket_label", minWidth: 160 },
          { title: "Asset Class",field: "asset_class",  width: 120 },
          { title: "Value",      field: "value_fmt",    hozAlign: "right", width: 130 },
        ],
      });
    },

    // ── Tax Analytics ─────────────────────────────────────────────
    async loadTax() {
      this.tax.loading = true;
      try {
        this.tax.data = await getJSON("/api/strategy/tax-analytics");
        this.$nextTick(() => this.drawTaxCharts());
      } catch (e) {
        this.tax.error = "Tax analytics: " + e.message;
      } finally {
        this.tax.loading = false;
      }
    },

    drawTaxCharts() {
      const d = this.tax.data;
      if (!d) return;
      const years = d.years.map(r => r.year);

      // ── Tax Burden sub-tab ──────────────────────────────────────
      const burdenEl = document.getElementById("chart-tax-burden");
      if (burdenEl) {
        Plotly.newPlot(burdenEl, [
          { type: "bar", name: "Federal Tax",  x: years, y: d.years.map(r => r.federal_tax),  marker: { color: "#ef4444" } },
          { type: "bar", name: "State Tax",    x: years, y: d.years.map(r => r.state_tax),    marker: { color: "#f97316" } },
          { type: "bar", name: "IRMAA",        x: years, y: d.years.map(r => r.irmaa),        marker: { color: "#a855f7" } },
          { type: "bar", name: "Payroll FICA", x: years, y: d.years.map(r => r.payroll),      marker: { color: "#3b82f6" } },
        ], {
          barmode: "stack", title: "Annual Tax Burden by Type",
          height: 380, yaxis: { tickformat: "$,.0f" }, xaxis: { title: "Year" },
          margin: { t: 50, l: 80, r: 10, b: 50 }, legend: { orientation: "h", y: -0.2 },
        }, { responsive: true, displaylogo: false });
        refitOnResize(burdenEl, () => Plotly.Plots.resize(burdenEl));
      }

      // ── Income Sources sub-tab ──────────────────────────────────
      // Chart 1: stacked bar — Annual Income by Source
      const incBarEl = document.getElementById("chart-income-by-source");
      if (incBarEl) {
        const incSeries = [
          { key: "wages",       name: "Wages",                   color: "#22c55e" },
          { key: "ss_benefits", name: "Social Security",         color: "#2dd4bf" },
          { key: "trad_cash",   name: "Traditional Withdrawals", color: "#ef4444" },
          { key: "roth_cash",   name: "Roth Withdrawals",        color: "#a855f7" },
          { key: "brok_cash",   name: "Brokerage Withdrawals",   color: "#f59e0b" },
          { key: "rmd",         name: "RMDs",                    color: "#ec4899" },
        ].filter(s => d.years.some(r => r[s.key] > 0));
        Plotly.newPlot(incBarEl,
          incSeries.map(s => ({
            type: "bar", name: s.name,
            x: years, y: d.years.map(r => r[s.key] || 0),
            marker: { color: s.color },
            hovertemplate: "%{x}<br>" + s.name + ": $%{y:,.0f}<extra></extra>",
          })), {
            barmode: "stack", title: "Annual Income by Source",
            height: 380, yaxis: { title: "Income Amount ($)", tickformat: "$,.0f" }, xaxis: { title: "Year" },
            margin: { t: 50, l: 90, r: 10, b: 50 }, legend: { orientation: "h", y: -0.22 },
          }, { responsive: true, displaylogo: false });
        refitOnResize(incBarEl, () => Plotly.Plots.resize(incBarEl));
      }

      // Chart 2: donut — Income Source Distribution (average composition)
      const incDonutEl = document.getElementById("chart-income-donut");
      if (incDonutEl) {
        const src = d.income_sources;
        const filtered = Object.entries(src).filter(([, v]) => v > 0);
        const donutColors = {
          "Wages":                   "#22c55e",
          "Social Security":         "#2dd4bf",
          "Traditional Withdrawals": "#ef4444",
          "Roth Conversions":        "#a855f7",
          "Roth Withdrawals":        "#8b5cf6",
          "Brokerage Withdrawals":   "#f59e0b",
          "RMDs":                    "#ec4899",
        };
        Plotly.newPlot(incDonutEl, [{
          type: "pie",
          labels: filtered.map(([k]) => k),
          values: filtered.map(([, v]) => v),
          hole: .38,
          marker: { colors: filtered.map(([k]) => donutColors[k] || "#aaa") },
          textinfo: "label+percent",
          hovertemplate: "%{label}<br>$%{value:,.0f}<br>%{percent}<extra></extra>",
        }], {
          title: "Income Source Distribution",
          height: 360,
          margin: { t: 50, l: 20, r: 20, b: 60 },
          showlegend: true, legend: { orientation: "h", y: -0.18 },
        }, { responsive: true, displaylogo: false });
        refitOnResize(incDonutEl, () => Plotly.Plots.resize(incDonutEl));
      }

      // Chart 3: projected balances (moved here from Long-Term Plan)
      this.drawBalancesChart();

      // ── Effective Rates sub-tab ─────────────────────────────────
      const rateEl = document.getElementById("chart-tax-rates");
      if (rateEl) {
        Plotly.newPlot(rateEl, [{
          type: "scatter", mode: "lines+markers", name: "Effective Rate",
          x: years, y: d.years.map(r => r.effective_rate),
          line: { color: "#3b82d4", width: 2 },
          hovertemplate: "Year %{x}<br>Rate: %{y:.1f}%<extra></extra>",
        }], {
          title: "Effective Tax Rate by Year", height: 320,
          xaxis: { title: "Year" }, yaxis: { title: "Rate (%)", ticksuffix: "%" },
          margin: { t: 50, l: 60, r: 10, b: 50 },
        }, { responsive: true, displaylogo: false });
        refitOnResize(rateEl, () => Plotly.Plots.resize(rateEl));
      }
    },

    taxInsights() {
      const d = this.tax.data;
      if (!d) return [];
      const ins = [];
      const s = d.summary;
      if (s.total_irmaa > 0)
        ins.push(`💊 IRMAA Impact: ${fmt$(s.total_irmaa)} in Medicare surcharges. Consider managing MAGI to avoid IRMAA brackets.`);
      if (s.avg_effective_rate > 20)
        ins.push(`⚠️ High average effective tax rate (${s.avg_effective_rate.toFixed(1)}%). Review Roth conversion timing to spread tax burden.`);
      const lowIRMAA = d.years.filter(r => r.irmaa === 0 && r.roth_conversion < 10_000 && r.agi < 120_000);
      if (lowIRMAA.length > 0)
        ins.push(`💡 ${lowIRMAA.length} years with AGI < $120k and no IRMAA. Consider larger Roth conversions in these years.`);
      if (!ins.length)
        ins.push("✅ No major tax optimisation opportunities flagged — the plan looks well-structured.");
      return ins;
    },

    // ── Income & Expenses ─────────────────────────────────────────
    async loadIncExp() {
      this.incexp.loading = true;
      try {
        this.incexp.data = await getJSON("/api/strategy/income-expense");
        this.$nextTick(() => this.drawIncExpCharts());
      } catch (e) {
        this.incexp.error = "Income/expense: " + e.message;
      } finally {
        this.incexp.loading = false;
      }
    },

    drawIncExpCharts() {
      const d = this.incexp.data;
      if (!d) return;
      const { income, expenses } = d;
      const years = income.years;

      const incEl = document.getElementById("chart-income");
      if (incEl) {
        const incSeries = [
          { key: "wages",       name: "Wages",                  color: "#2ecc71" },
          { key: "ss_benefits", name: "Social Security",        color: "#3498db" },
          { key: "trad_cash",   name: "Traditional Withdrawal", color: "#e74c3c" },
          { key: "roth_cash",   name: "Roth Withdrawal",        color: "#9b59b6" },
          { key: "brok_cash",   name: "Brokerage Withdrawal",   color: "#f39c12" },
          { key: "rmd",         name: "RMDs",                   color: "#e67e22" },
          { key: "interest",    name: "Interest",               color: "#1abc9c" },
          { key: "dividends",   name: "Dividends",              color: "#f1c40f" },
        ].filter(s => income[s.key] && income[s.key].some(v => v > 0));

        Plotly.newPlot(incEl,
          incSeries.map(s => ({
            type: "scatter", mode: "lines", stackgroup: "one", name: s.name,
            x: years, y: income[s.key],
            line: { color: s.color },
            hovertemplate: "%{x}<br>" + s.name + ": $%{y:,.0f}<extra></extra>",
          })), {
            title: "Income Sources by Year", height: 380,
            yaxis: { tickformat: "$,.0f" }, xaxis: { title: "Year" },
            margin: { t: 50, l: 80, r: 10, b: 50 },
            legend: { orientation: "h", y: -0.22 },
          }, { responsive: true, displaylogo: false });
        refitOnResize(incEl, () => Plotly.Plots.resize(incEl));
      }

      const expEl = document.getElementById("chart-expenses");
      if (expEl) {
        const expSeries = [
          { key: "living",      name: "Living Expenses", color: "#3b82d4" },
          { key: "healthcare",  name: "Healthcare",      color: "#f97316" },
          { key: "federal_tax", name: "Federal Tax",     color: "#ef4444" },
          { key: "state_tax",   name: "State Tax",       color: "#f59e0b" },
          { key: "irmaa",       name: "IRMAA",           color: "#a855f7" },
          { key: "daf",         name: "DAF",             color: "#8b5cf6" },
        ].filter(s => expenses[s.key] && expenses[s.key].some(v => v > 0));

        Plotly.newPlot(expEl,
          expSeries.map(s => ({
            type: "scatter", mode: "lines", stackgroup: "one", name: s.name,
            x: expenses.years, y: expenses[s.key],
            line: { color: s.color },
            hovertemplate: "%{x}<br>" + s.name + ": $%{y:,.0f}<extra></extra>",
          })), {
            title: "Expenses by Year", height: 360,
            yaxis: { tickformat: "$,.0f" }, xaxis: { title: "Year" },
            margin: { t: 50, l: 80, r: 10, b: 50 },
            legend: { orientation: "h", y: -0.22 },
          }, { responsive: true, displaylogo: false });
        refitOnResize(expEl, () => Plotly.Plots.resize(expEl));
      }
    },

    // ── Resize helpers (fix charts drawn while tab was hidden) ────
    resizeTabCharts(tabId) {
      const ids = {
        plan:    ["chart-sankey"],
        buckets: ["chart-buckets"],
        tax:     ["chart-tax-burden", "chart-income-by-source", "chart-income-donut", "chart-balances", "chart-tax-rates"],
        incexp:  ["chart-income", "chart-expenses"],
      }[tabId] || [];
      ids.forEach(id => {
        const el = document.getElementById(id);
        if (el && el.offsetWidth > 0) Plotly.Plots.resize(el);
      });
    },

    resizeTaxChart(subtabId) {
      const chartIds = {
        overview: ["chart-tax-burden"],
        income:   ["chart-income-by-source", "chart-income-donut", "chart-balances"],
        rates:    ["chart-tax-rates"],
      }[subtabId] || [];
      chartIds.forEach(id => {
        const el = document.getElementById(id);
        if (el && el.offsetWidth > 0) Plotly.Plots.resize(el);
      });
    },
  };
}
