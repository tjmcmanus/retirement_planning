// Dashboard page (Alpine.js + Plotly + Tabulator). No build step, no network except /api.

const usd = (n) => (n === null || n === undefined ? "" : "$" + Math.round(n).toLocaleString("en-US"));
const signedPct = (p) => (p >= 0 ? "+" : "") + p.toFixed(1) + "%";

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = (await r.json()).detail || detail; } catch (_) { /* not JSON */ }
    throw new Error(`${r.status}: ${detail}`);
  }
  return r.json();
}

// Plotly/Tabulator measure their container when created. Inside an x-show block that is
// still display:none at that moment, so they come out at default size (or empty). Re-lay-out
// whenever the container's real size changes, which also covers window resizes.
function refitOnResize(el, refit) {
  new ResizeObserver(() => { if (el.offsetWidth > 0) refit(); }).observe(el);
}

const signedUsd = (n) => (n >= 0 ? "+" : "-") + usd(Math.abs(n));
// Accounting style, as the Streamlit statement: always 2 decimals, negatives in parentheses.
const acct = (v) => (v < 0 ? "$(" : "$") + Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + (v < 0 ? ")" : "");
const PASTEL = [[0, "rgb(246,207,113)"], [0.5, "rgb(180,151,231)"], [1, "rgb(139,224,164)"]];

function dashboard() {
  return {
    usd, signedPct, signedUsd, acct,
    networth: { loading: true, error: null, data: null },

    forecastTabs: [
      { key: "longterm", label: "Long-Term" }, { key: "intermediate", label: "Intermediate-Term" },
      { key: "shortterm", label: "Short-Term" }, { key: "stress", label: "Market Stress" },
    ],
    stressRows: [["severe", "Severe"], ["elevated", "Elevated"], ["rising", "Rising"], ["neutral", "Neutral"], ["stable", "Stable"]],
    mf: { tab: "longterm", data: {}, loading: {}, error: {} },

    nwTabs: [
      { key: "trend", label: "Net Worth Trend" }, { key: "statement", label: "Net Worth Statement" },
      { key: "accounts", label: "Account Mix" }, { key: "portfolio", label: "Portfolio Mix" },
    ],
    nw: { tab: "trend", data: { statement: null, accounts: null, portfolio: null }, loading: {}, error: {} },

    ready: { loading: true, error: null, data: null },

    load() {
      this.loadNetworth();
      this.openForecast("longterm");
      this.loadReadiness();
    },

    get fc() { return this.mf.tab === "stress" ? null : this.mf.data[this.mf.tab] || null; },
    get stress() { return this.mf.data.stress || null; },

    slope(v, d) { return (v >= 0 ? "+" : "") + v.toFixed(d.slope_decimals) + "%/" + d.per; },

    // Each tab loads the first time it is opened; forecast and stress calls hit the network.
    async fetchInto(bucket, key, url) {
      if (bucket.data[key] || bucket.loading[key]) return;
      bucket.loading[key] = true;
      bucket.error[key] = null;
      try {
        bucket.data[key] = await getJSON(url);
      } catch (e) {
        bucket.error[key] = "Could not load: " + e.message;
      } finally {
        bucket.loading[key] = false;
      }
    },

    openForecast(key) {
      this.mf.tab = key;
      this.fetchInto(this.mf, key, key === "stress" ? "/api/dashboard/stress" : `/api/dashboard/forecast/${key}`);
    },

    async openNw(key) {
      this.nw.tab = key;
      const url = { statement: "/api/dashboard/statement", accounts: "/api/dashboard/account-mix",
                    portfolio: "/api/dashboard/portfolio-mix" }[key];
      if (!url) return;
      await this.fetchInto(this.nw, key, url);
      const d = this.nw.data[key];
      if (key !== "statement" && d && d.ready) {
        await this.$nextTick();
        this.drawTreemap("chart-" + key, d, key === "accounts"
          ? { value_label: "market_value" }
          : { value_label: "Current value", text_template: "%{label}<br>$%{value:,.2f}" });
      }
    },

    drawTreemap(id, data, opts) {
      const d = { ...data, ...opts };
      const el = document.getElementById(id);
      if (!el || el.dataset.drawn) return;
      el.dataset.drawn = "1";
      Plotly.newPlot(el, [{
        type: "treemap", branchvalues: "total",
        ids: d.nodes.map((n) => n.id), labels: d.nodes.map((n) => n.label),
        parents: d.nodes.map((n) => n.parent), values: d.nodes.map((n) => n.value),
        marker: { colors: d.nodes.map((n) => n.color), colorscale: d.colorscale.map(([p, c]) => [p, c.replace(/\s/g, "")]),
                  cmid: d.midpoint, showscale: true, colorbar: { title: { text: d.value_label } } },
        textinfo: "label+text+value+percent root",
        // PARITY: Streamlit only overrides the text template on Portfolio Mix (2 decimals).
        ...(d.text_template ? { texttemplate: d.text_template } : {}),
        hovertemplate: "%{label}<br>$%{value:,.0f}<extra></extra>",
      }], { title: { text: d.title }, height: 600, margin: { t: 50, l: 25, r: 25, b: 25 } },
      { responsive: true, displaylogo: false });
      refitOnResize(el, () => Plotly.Plots.resize(el));
    },

    async loadReadiness() {
      try {
        this.ready.data = await getJSON("/api/dashboard/readiness");
        if (this.ready.data.ready) { await this.$nextTick(); this.drawGauge(); }
      } catch (e) {
        this.ready.error = "Could not load readiness: " + e.message;
      } finally {
        this.ready.loading = false;
      }
    },

    drawGauge() {
      const r = this.ready.data;
      const el = document.getElementById("chart-gauge");
      Plotly.newPlot(el, [{
        type: "indicator", mode: "gauge+number+delta", value: r.overall,
        title: { text: "Overall Retirement Readiness", font: { size: 16 } },
        number: { suffix: "%", valueformat: ".0f" },
        delta: { reference: 75, valueformat: ".0f" },
        gauge: {
          axis: { range: [0, 100], tickwidth: 1 }, bar: { color: r.colour },
          steps: [{ range: [0, 50], color: "rgba(255,75,75,0.15)" }, { range: [50, 75], color: "rgba(255,165,0,0.15)" },
                  { range: [75, 100], color: "rgba(33,195,84,0.15)" }],
          threshold: { line: { color: "#333", width: 3 }, thickness: 0.75, value: 75 },
        },
      }], { height: 260, margin: { t: 40, l: 20, r: 20, b: 10 } }, { responsive: true, displaylogo: false });
      refitOnResize(el, () => Plotly.Plots.resize(el));
    },

    async loadNetworth() {
      try {
        this.networth.data = await getJSON("/api/dashboard/networth");
        if (this.networth.data.ready) this.drawTrend();
      } catch (e) {
        this.networth.error = "Could not load net worth: " + e.message;
      } finally {
        this.networth.loading = false;
      }
    },

    get kpiCards() {
      const k = this.networth.data && this.networth.data.kpis;
      if (!k) return [];
      const card = (label, m) => ({
        label,
        value: usd(Math.abs(m.amount)),
        delta: (m.amount >= 0 ? "▲ " : "▼ ") + Math.abs(m.percent).toFixed(1) + "%",
        up: m.amount >= 0,
      });
      return [
        { label: "Total Net Worth", value: usd(k.net_worth), delta: null, up: true },
        card("Month-over-Month", k.month_over_month),
        card("Year-to-Date Gain", k.year_to_date),
        card("12-Month Rolling", k.rolling_12_month),
        card("vs 7% Benchmark", k.vs_benchmark),
      ];
    },

    drawTrend() {
      const t = this.networth.data.trend;
      const last = t.values.length - 1;
      const delta = last > 0 ? t.values[last] - t.values[last - 1] : 0;
      const pct = last > 0 && t.values[last - 1] ? (delta / t.values[last - 1]) * 100 : 0;
      const colour = delta >= 0 ? "#21c354" : "#ff4b4b";
      const lo = Math.min(...t.values), hi = Math.max(...t.values), rng = hi - lo;
      const el = document.getElementById("chart-trend");
      Plotly.newPlot(el, [
        { type: "bar", x: t.labels, y: t.values, name: "Net Worth",
          // Same pastel yellow -> purple -> green scale as the Streamlit dashboard.
          marker: { color: t.values, showscale: false,
                    colorscale: [[0, "rgb(246,207,113)"], [0.5, "rgb(180,151,231)"], [1, "rgb(139,224,164)"]] },
          hovertemplate: "%{x}<br>$%{y:,.0f}<extra></extra>" },
        { type: "scatter", mode: "lines+markers", x: t.labels, y: t.values, name: "Trend",
          line: { color: "#4c78a8", width: 3 }, marker: { size: 8, color: "#4c78a8" },
          hovertemplate: "%{x}<br>$%{y:,.0f}<extra></extra>" },
      ], {
        height: 450, margin: { t: 40, l: 70, r: 10, b: 60 },
        xaxis: { type: "category", tickangle: -45 },
        yaxis: { tickformat: "$,.0f", range: [lo - rng * 0.1, hi + rng * 0.15] },
        legend: { orientation: "h", y: 1.1, x: 1, xanchor: "right" },
        annotations: [{
          x: t.labels[last], y: t.values[last], ax: 0, ay: -40, showarrow: true, arrowhead: 2,
          arrowcolor: colour, bordercolor: colour, borderwidth: 2, bgcolor: "white",
          font: { color: colour, size: 12 },
          text: `${delta >= 0 ? "▲" : "▼"} ${usd(Math.abs(delta))} (${signedPct(pct)})`,
        }],
      }, { responsive: true, displaylogo: false });
      refitOnResize(el, () => Plotly.Plots.resize(el));
    },

  };
}
