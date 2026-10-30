/* global Alpine, Plotly */
function monteCarloPage() {
  return {
    tabs: [
      { id: "sim", label: "Run Simulation" },
      { id: "stress", label: "Stress Tests" },
      { id: "longevity", label: "Longevity Risk" },
      { id: "heatmap", label: "Success Heatmap" },
      { id: "compare", label: "Scenario Comparison" },
    ],
    tab: "sim",

    // Simulation inputs
    inputs: {
      portfolio: 1500000,
      withdrawal: 80000,
      start_age: 62,
      end_age: 90,
      ss_annual: 40000,
      ss_start_age: 70,
      inflation_pct: 2.9,
      allocation: "Moderate (70/30)",
      n_simulations: 10000,
      random_seed: 42,
    },

    // Metadata
    meta: {
      portfolio_presets: ["Moderate (70/30)"],
      stress_scenarios: [],
      longevity_scenarios: [],
    },

    // Sub-tab inputs
    selectedStress: [],
    selectedLongevity: [],
    heatmapWithdrawal: 80000,
    heatmapSims: 1000,
    cmpStress: [],
    cmpLongevity: [],

    // Running jobs and status
    job: null,
    jobInterval: null,
    errorMsg: "",

    // Results
    simResult: null,
    stressResult: null,
    longevityResult: null,
    heatmapResult: null,
    compareResult: null,

    async init() {
      try {
        const [metaRes, defRes] = await Promise.all([
          fetch("/api/monte-carlo/meta"),
          fetch("/api/monte-carlo/defaults"),
        ]);
        if (metaRes.ok) {
          this.meta = await metaRes.json();
          this.selectedStress = [...this.meta.stress_scenarios];
          this.selectedLongevity = [...this.meta.longevity_scenarios];
          this.cmpStress = this.meta.stress_scenarios.slice(0, 3);
          this.cmpLongevity = this.meta.longevity_scenarios.slice(0, 3);
        }
        if (defRes.ok) {
          const defs = await defRes.json();
          Object.assign(this.inputs, defs);
          this.heatmapWithdrawal = this.inputs.withdrawal;
        }
      } catch (err) {
        this.errorMsg = "Failed to load initial configuration: " + err.message;
      }

      window.addEventListener("resize", () => this.resizeCharts());
    },

    resizeCharts() {
      const ids = [
        "chart-fan", "chart-success-age", "chart-stress-paths",
        "chart-longevity-bar", "chart-longevity-paths",
        "chart-heatmap", "chart-compare-bar"
      ];
      ids.forEach((id) => {
        const el = document.getElementById(id);
        if (el && el.data && el.data.length && window.Plotly) {
          Plotly.Plots.resize(el);
        }
      });
    },

    formatCurrency(val) {
      if (val === null || val === undefined || isNaN(val)) return "$0";
      return "$" + Number(val).toLocaleString("en-US", { maximumFractionDigits: 0 });
    },

    formatPercent(val) {
      if (val === null || val === undefined || isNaN(val)) return "0.0%";
      return (Number(val) * 100).toFixed(1) + "%";
    },

    getSuccessBadgeClass(prob) {
      if (prob >= 0.90) return "high";
      if (prob >= 0.75) return "med";
      return "low";
    },

    // ──────────────────────────────────────────────────────────────────────────
    // Background Job Poller
    // ──────────────────────────────────────────────────────────────────────────
    pollJob(jobId, onComplete) {
      if (this.jobInterval) clearInterval(this.jobInterval);
      this.errorMsg = "";

      this.jobInterval = setInterval(async () => {
        try {
          const res = await fetch(`/api/jobs/${jobId}`);
          if (!res.ok) {
            clearInterval(this.jobInterval);
            this.job = null;
            this.errorMsg = "Job status check failed";
            return;
          }
          const data = await res.json();
          this.job = data;

          if (data.status === "completed") {
            clearInterval(this.jobInterval);
            this.jobInterval = null;
            this.job = null;
            onComplete(data.result);
          } else if (data.status === "failed") {
            clearInterval(this.jobInterval);
            this.jobInterval = null;
            this.errorMsg = data.error || data.message || "Simulation failed";
            this.job = null;
          }
        } catch (err) {
          clearInterval(this.jobInterval);
          this.jobInterval = null;
          this.job = null;
          this.errorMsg = "Error polling job: " + err.message;
        }
      }, 300);
    },

    // ──────────────────────────────────────────────────────────────────────────
    // Tab 1: Run Simulation
    // ──────────────────────────────────────────────────────────────────────────
    async runSimulation() {
      if (this.job) return;
      this.errorMsg = "";
      try {
        const res = await fetch("/api/monte-carlo/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(this.inputs),
        });
        if (!res.ok) {
          const err = await res.json();
          this.errorMsg = err.detail || "Validation error";
          return;
        }
        const data = await res.json();
        this.job = { id: data.job_id, progress: 0, message: "Queued..." };
        this.pollJob(data.job_id, (result) => {
          this.simResult = result;
          this.$nextTick(() => {
            this.renderFanChart(result.fan_chart);
            this.renderSuccessAgeChart(result.fan_chart);
          });
        });
      } catch (err) {
        this.errorMsg = err.message;
      }
    },

    renderFanChart(fanData) {
      if (!fanData || !fanData.length) return;
      const ages = fanData.map(d => d.age);
      const agesRev = [...ages].reverse();

      const traces = [
        {
          x: [...ages, ...agesRev],
          y: [...fanData.map(d => d.p95), ...fanData.map(d => d.p5).reverse()],
          fill: "toself",
          fillcolor: "rgba(99,110,250,0.08)",
          line: { color: "rgba(0,0,0,0)" },
          name: "P5–P95",
          showlegend: true,
          type: "scatter",
        },
        {
          x: [...ages, ...agesRev],
          y: [...fanData.map(d => d.p90), ...fanData.map(d => d.p10).reverse()],
          fill: "toself",
          fillcolor: "rgba(99,110,250,0.12)",
          line: { color: "rgba(0,0,0,0)" },
          name: "P10–P90",
          showlegend: true,
          type: "scatter",
        },
        {
          x: [...ages, ...agesRev],
          y: [...fanData.map(d => d.p75), ...fanData.map(d => d.p25).reverse()],
          fill: "toself",
          fillcolor: "rgba(99,110,250,0.20)",
          line: { color: "rgba(0,0,0,0)" },
          name: "P25–P75",
          showlegend: true,
          type: "scatter",
        },
        {
          x: ages,
          y: fanData.map(d => d.p50),
          mode: "lines",
          name: "Median (P50)",
          line: { color: "rgb(99,110,250)", width: 2.5 },
          type: "scatter",
        },
        {
          x: ages,
          y: fanData.map(d => d.p10),
          mode: "lines",
          name: "P10 (Pessimistic)",
          line: { color: "rgb(239,85,59)", width: 1.5, dash: "dash" },
          type: "scatter",
        },
      ];

      const layout = {
        title: "Portfolio Value Distribution by Age",
        xaxis: { title: "Age" },
        yaxis: { title: "Portfolio Value ($)", tickformat: "$,.0f" },
        legend: { orientation: "h", yanchor: "bottom", y: 1.02 },
        hovermode: "x unified",
        margin: { l: 60, r: 20, t: 40, b: 40 },
      };

      Plotly.newPlot("chart-fan", traces, layout, { responsive: true, displayModeBar: false });
    },

    renderSuccessAgeChart(fanData) {
      if (!fanData || !fanData.length) return;
      const ages = fanData.map(d => d.age);
      const rates = fanData.map(d => d.success_rate * 100);

      const trace = {
        x: ages,
        y: rates,
        mode: "lines+markers",
        name: "Success Rate",
        line: { color: "rgb(0,204,150)", width: 2 },
        fill: "tozeroy",
        fillcolor: "rgba(0,204,150,0.15)",
        type: "scatter",
      };

      const layout = {
        title: "Probability of Portfolio Survival by Age",
        xaxis: { title: "Age" },
        yaxis: { title: "Success Rate (%)", range: [0, 105] },
        shapes: [
          {
            type: "line",
            x0: ages[0],
            x1: ages[ages.length - 1],
            y0: 90,
            y1: 90,
            line: { color: "orange", width: 1.5, dash: "dash" },
          },
        ],
        margin: { l: 60, r: 20, t: 40, b: 40 },
      };

      Plotly.newPlot("chart-success-age", [trace], layout, { responsive: true, displayModeBar: false });
    },

    // ──────────────────────────────────────────────────────────────────────────
    // Tab 2: Stress Tests
    // ──────────────────────────────────────────────────────────────────────────
    async runStressTests() {
      if (this.job) return;
      this.errorMsg = "";
      try {
        const res = await fetch("/api/monte-carlo/stress-tests", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            inputs: this.inputs,
            scenarios: this.selectedStress,
          }),
        });
        if (!res.ok) {
          const err = await res.json();
          this.errorMsg = err.detail || "Stress tests failed to start";
          return;
        }
        const data = await res.json();
        this.job = { id: data.job_id, progress: 0, message: "Running stress tests..." };
        this.pollJob(data.job_id, (result) => {
          this.stressResult = result;
          this.$nextTick(() => {
            this.renderStressPaths(result);
          });
        });
      } catch (err) {
        this.errorMsg = err.message;
      }
    },

    renderStressPaths(result) {
      if (!result || !result.results) return;
      const ages = result.ages || [];
      const colors = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A", "#19D3F3", "#FF6692", "#B6E880"];

      const traces = result.results
        .filter(r => r.portfolio_path_median && r.portfolio_path_median.length)
        .map((r, i) => ({
          x: ages.slice(0, r.portfolio_path_median.length),
          y: r.portfolio_path_median,
          mode: "lines",
          name: r.scenario_name,
          line: { color: colors[i % colors.length], width: 2 },
          type: "scatter",
        }));

      const layout = {
        title: "Median Portfolio Path — Stress Scenarios",
        xaxis: { title: "Age" },
        yaxis: { title: "Portfolio Value ($)", tickformat: "$,.0f" },
        legend: { orientation: "h", yanchor: "bottom", y: 1.02 },
        margin: { l: 60, r: 20, t: 40, b: 40 },
      };

      Plotly.newPlot("chart-stress-paths", traces, layout, { responsive: true, displayModeBar: false });
    },

    // ──────────────────────────────────────────────────────────────────────────
    // Tab 3: Longevity Risk
    // ──────────────────────────────────────────────────────────────────────────
    async runLongevity() {
      if (this.job) return;
      this.errorMsg = "";
      try {
        const res = await fetch("/api/monte-carlo/longevity", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            inputs: this.inputs,
            scenarios: this.selectedLongevity,
          }),
        });
        if (!res.ok) {
          const err = await res.json();
          this.errorMsg = err.detail || "Longevity analysis failed";
          return;
        }
        const data = await res.json();
        this.job = { id: data.job_id, progress: 0, message: "Evaluating longevity horizons..." };
        this.pollJob(data.job_id, (result) => {
          this.longevityResult = result;
          this.$nextTick(() => {
            this.renderLongevityCharts(result);
          });
        });
      } catch (err) {
        this.errorMsg = err.message;
      }
    },

    renderLongevityCharts(result) {
      if (!result || !result.summary) return;

      const labels = result.summary.map(s => s.scenario);
      const success = result.summary.map(s => s.success_probability * 100);
      const colors = success.map(s => (s >= 90 ? "rgb(0,204,150)" : (s >= 75 ? "rgb(255,165,0)" : "rgb(239,85,59)")));

      const barTrace = {
        x: labels,
        y: success,
        type: "bar",
        marker: { color: colors },
        text: success.map(s => s.toFixed(1) + "%"),
        textposition: "outside",
      };

      const barLayout = {
        title: "Success Probability by Longevity Scenario",
        xaxis: { title: "Longevity Scenario" },
        yaxis: { title: "Success Probability (%)", range: [0, 110] },
        shapes: [
          {
            type: "line",
            x0: -0.5,
            x1: labels.length - 0.5,
            y0: 90,
            y1: 90,
            line: { color: "orange", width: 1.5, dash: "dash" },
          },
        ],
        margin: { l: 50, r: 20, t: 40, b: 40 },
      };

      Plotly.newPlot("chart-longevity-bar", [barTrace], barLayout, { responsive: true, displayModeBar: false });

      // Path traces
      const colorsList = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A"];
      const pathTraces = Object.entries(result.paths || {}).map(([label, path], i) => ({
        x: path.map(p => p.age),
        y: path.map(p => p.p50),
        mode: "lines",
        name: label,
        line: { color: colorsList[i % colorsList.length], width: 2 },
        type: "scatter",
      }));

      const pathLayout = {
        title: "Median Portfolio Path — Longevity Scenarios",
        xaxis: { title: "Age" },
        yaxis: { title: "Portfolio Value ($)", tickformat: "$,.0f" },
        legend: { orientation: "h", yanchor: "bottom", y: 1.02 },
        margin: { l: 60, r: 20, t: 40, b: 40 },
      };

      Plotly.newPlot("chart-longevity-paths", pathTraces, pathLayout, { responsive: true, displayModeBar: false });
    },

    // ──────────────────────────────────────────────────────────────────────────
    // Tab 4: Success Heatmap
    // ──────────────────────────────────────────────────────────────────────────
    async runHeatmap() {
      if (this.job) return;
      this.errorMsg = "";
      try {
        const res = await fetch("/api/monte-carlo/heatmap", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            inputs: this.inputs,
            base_withdrawal: this.heatmapWithdrawal,
            n_sims: this.heatmapSims,
          }),
        });
        if (!res.ok) {
          const err = await res.json();
          this.errorMsg = err.detail || "Heatmap generation failed";
          return;
        }
        const data = await res.json();
        this.job = { id: data.job_id, progress: 0, message: "Building heatmap matrix..." };
        this.pollJob(data.job_id, (result) => {
          this.heatmapResult = result;
          this.$nextTick(() => {
            this.renderHeatmapChart(result);
          });
        });
      } catch (err) {
        this.errorMsg = err.message;
      }
    },

    renderHeatmapChart(result) {
      if (!result || !result.values || !result.values.length) return;

      const trace = {
        z: result.values,
        x: result.columns,
        y: result.index,
        type: "heatmap",
        colorscale: [
          [0.0, "rgb(239,85,59)"],
          [0.75, "rgb(255,165,0)"],
          [0.90, "rgb(0,204,150)"],
          [1.0, "rgb(0,150,100)"],
        ],
        zmin: 0,
        zmax: 100,
        text: result.values.map(row => row.map(v => v.toFixed(0) + "%")),
        texttemplate: "%{text}",
        colorbar: { title: "Success %" },
      };

      const layout = {
        title: "Success Probability Heatmap",
        xaxis: { title: "Portfolio Allocation" },
        yaxis: { title: "Annual Withdrawal" },
        margin: { l: 80, r: 20, t: 40, b: 60 },
      };

      Plotly.newPlot("chart-heatmap", [trace], layout, { responsive: true, displayModeBar: false });
    },

    // ──────────────────────────────────────────────────────────────────────────
    // Tab 5: Scenario Comparison
    // ──────────────────────────────────────────────────────────────────────────
    async runComparison() {
      if (this.job) return;
      this.errorMsg = "";
      try {
        const res = await fetch("/api/monte-carlo/comparison", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            inputs: this.inputs,
            stress_scenarios: this.cmpStress,
            longevity_scenarios: this.cmpLongevity,
          }),
        });
        if (!res.ok) {
          const err = await res.json();
          this.errorMsg = err.detail || "Comparison failed";
          return;
        }
        const data = await res.json();
        this.job = { id: data.job_id, progress: 0, message: "Running full comparison..." };
        this.pollJob(data.job_id, (result) => {
          this.compareResult = result;
          this.$nextTick(() => {
            this.renderCompareChart(result);
          });
        });
      } catch (err) {
        this.errorMsg = err.message;
      }
    },

    renderCompareChart(result) {
      if (!result || !result.bar_data) return;

      const labels = result.bar_data.map(d => d.scenario);
      const vals = result.bar_data.map(d => d.success_rate);
      const colors = vals.map(v => (v >= 90 ? "rgb(0,204,150)" : (v >= 75 ? "rgb(255,165,0)" : "rgb(239,85,59)")));

      const trace = {
        x: labels,
        y: vals,
        type: "bar",
        marker: { color: colors },
        text: vals.map(v => v.toFixed(1) + "%"),
        textposition: "outside",
      };

      const layout = {
        title: "Success Probability — All Scenarios",
        xaxis: { title: "Scenario", tickangle: -25 },
        yaxis: { title: "Success Probability (%)", range: [0, 115] },
        shapes: [
          {
            type: "line",
            x0: -0.5,
            x1: labels.length - 0.5,
            y0: 90,
            y1: 90,
            line: { color: "orange", width: 1.5, dash: "dash" },
          },
        ],
        margin: { l: 50, r: 20, t: 40, b: 80 },
      };

      Plotly.newPlot("chart-compare-bar", [trace], layout, { responsive: true, displayModeBar: false });
    },

    // ──────────────────────────────────────────────────────────────────────────
    // CSV Export
    // ──────────────────────────────────────────────────────────────────────────
    async downloadCsv(includeStress = true, includeLongevity = true) {
      try {
        const res = await fetch("/api/monte-carlo/export-csv", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            inputs: this.inputs,
            include_stress: includeStress,
            include_longevity: includeLongevity,
          }),
        });
        if (!res.ok) {
          this.errorMsg = "CSV export failed";
          return;
        }
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `monte_carlo_report_${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
      } catch (err) {
        this.errorMsg = "Export error: " + err.message;
      }
    },
  };
}
