/* global Alpine, Plotly */
function estatePage() {
  return {
    tabs: [
      { id: "assess", label: "Assessment" },
      { id: "tax", label: "Estate Tax" },
      { id: "beneficiary", label: "Beneficiaries" },
      { id: "charitable", label: "Charitable Giving" },
      { id: "legal", label: "Legal Documents" },
      { id: "financial", label: "Financial Accounts" },
      { id: "property", label: "Property & Legacy" },
      { id: "docs", label: "Document Locations" },
      { id: "schedule", label: "Review Schedule" },
      { id: "progress", label: "Progress Summary" },
    ],
    tab: "assess",

    data: {
      assessment: {},
      legal: { core_docs: {}, incapacity_docs: {}, advanced_docs: {} },
      financial: { beneficiaries: {}, trust_accounts: {}, housekeeping: {} },
      property: { real_estate_trust: {}, personal_items: {}, family_items: {} },
      document_locations: { legal_documents: {}, financial_documents: {}, real_estate_documents: {}, personal_documents: {} },
      review_schedule: { last_reviewed: "", reviews: {} },
    },

    meta: {
      person1_name: "Person 1",
      person2_name: "Person 2",
      account_names: [],
      property_names: [],
      children: [],
      has_minor_children: false,
      has_adult_children: false,
      has_special_needs: false,
      state_estate_tax_states: [],
      state_inheritance_tax_states: [],
      exemption_years: [2024, 2025, 2026, 2027, 2028, 2029, 2030],
    },

    recommendations: [],
    progress: { categories: [], total_done: 0, total_items: 0, overall_percent: 0, pending_items: [] },

    // Calculators state
    taxCalc: {
      year: 2026,
      estate_value: 10000000,
      prior_taxable_gifts: 0,
      marital_status: "married",
      state: "None",
      surviving_spouse: false,
      deceased_spousal_unused_exemption: 0,
      gift_recipients: 2,
      gift_years: 10,
      estate_growth_rate: 0.05,
    },
    taxResult: null,

    benCalc: {
      type: "ten_year_rule",
      ira_balance: 500000,
      tax_rate: 0.24,
      growth_rate: 0.06,
      strategy: "equal_annual",
      spouse_age: 60,
      deceased_age: 68,
      trust_type: "conduit",
    },
    benResult: null,

    charCalc: {
      tool: "crut",
      asset_value: 1000000,
      cost_basis: 200000,
      payout_rate: 0.06,
      term_years: 20,
      discount_rate: 0.04,
      growth_rate: 0.07,
      annual_grant: 50000,
      qcd_amount: 25000,
      taxable_dist: 50000,
      marginal_rate: 0.24,
    },
    charResult: null,

    statusMsg: "",
    errorMsg: "",
    isSaving: false,

    async init() {
      try {
        const res = await fetch("/api/estate");
        if (res.ok) {
          const overview = await res.json();
          this.data = overview.data || this.data;
          this.meta = overview.meta || this.meta;
          this.recommendations = overview.recommendations || [];
          this.progress = overview.progress || this.progress;
        }
      } catch (err) {
        this.errorMsg = "Failed to load estate data: " + err.message;
      }

      window.addEventListener("resize", () => this.resizeCharts());
    },

    resizeCharts() {
      const ids = ["chart-estate-tax", "chart-ben-schedule", "chart-crt-payouts"];
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

    async saveSection(sectionName) {
      this.isSaving = true;
      this.statusMsg = "";
      this.errorMsg = "";
      try {
        const patch = this.data[sectionName] || {};
        const res = await fetch(`/api/estate/${sectionName}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ patch }),
        });
        if (!res.ok) {
          const err = await res.json();
          this.errorMsg = err.detail || "Save failed";
          this.isSaving = false;
          return;
        }
        const overview = await res.json();
        this.data = overview.data;
        this.recommendations = overview.recommendations;
        this.progress = overview.progress;
        this.statusMsg = "Saved successfully";
        setTimeout(() => { if (this.statusMsg === "Saved successfully") this.statusMsg = ""; }, 2500);
      } catch (err) {
        this.errorMsg = "Save error: " + err.message;
      } finally {
        this.isSaving = false;
      }
    },

    // ──────────────────────────────────────────────────────────────────────────
    // Tax Calculator
    // ──────────────────────────────────────────────────────────────────────────
    async runTaxCalculation() {
      this.errorMsg = "";
      try {
        const res = await fetch("/api/estate/calculate-tax", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(this.taxCalc),
        });
        if (!res.ok) {
          const err = await res.json();
          this.errorMsg = err.detail || "Tax calculation failed";
          return;
        }
        this.taxResult = await res.json();
        this.$nextTick(() => this.renderTaxChart());
      } catch (err) {
        this.errorMsg = err.message;
      }
    },

    renderTaxChart() {
      if (!this.taxResult || !this.taxResult.comprehensive) return;
      const comp = this.taxResult.comprehensive;
      const tcja = this.taxResult.tcja_comparison;

      const labels = ["Current Plan", "Post-2026 Sunset"];
      const federalTaxes = [tcja.current_federal_tax, tcja.post_sunset_federal_tax];
      const netHeirs = [
        this.taxCalc.estate_value - tcja.current_federal_tax,
        this.taxCalc.estate_value - tcja.post_sunset_federal_tax,
      ];

      const traces = [
        {
          x: labels,
          y: federalTaxes,
          name: "Federal Estate Tax",
          type: "bar",
          marker: { color: "rgb(239,85,59)" },
          text: federalTaxes.map(v => this.formatCurrency(v)),
          textposition: "auto",
        },
        {
          x: labels,
          y: netHeirs,
          name: "Net to Heirs",
          type: "bar",
          marker: { color: "rgb(0,204,150)" },
          text: netHeirs.map(v => this.formatCurrency(v)),
          textposition: "auto",
        },
      ];

      const layout = {
        title: "Estate Distribution & TCJA Sunset Impact",
        barmode: "stack",
        xaxis: { title: "Scenario" },
        yaxis: { title: "Amount ($)", tickformat: "$,.0f" },
        legend: { orientation: "h", yanchor: "bottom", y: 1.02 },
        margin: { l: 70, r: 20, t: 40, b: 40 },
      };

      Plotly.newPlot("chart-estate-tax", traces, layout, { responsive: true, displayModeBar: false });
    },

    // ──────────────────────────────────────────────────────────────────────────
    // Beneficiary Calculator
    // ──────────────────────────────────────────────────────────────────────────
    async runBeneficiaryCalculation() {
      this.errorMsg = "";
      try {
        let params = {};
        if (this.benCalc.type === "ten_year_rule") {
          params = {
            ira_balance: this.benCalc.ira_balance,
            beneficiary_tax_rate: this.benCalc.tax_rate,
            growth_rate: this.benCalc.growth_rate,
            strategy: this.benCalc.strategy,
          };
        } else if (this.benCalc.type === "spousal_options") {
          params = {
            ira_balance: this.benCalc.ira_balance,
            spouse_age: this.benCalc.spouse_age,
            deceased_age: this.benCalc.deceased_age,
            growth_rate: this.benCalc.growth_rate,
            tax_rate: this.benCalc.tax_rate,
          };
        } else if (this.benCalc.type === "trust_beneficiary") {
          params = {
            ira_balance: this.benCalc.ira_balance,
            trust_type: this.benCalc.trust_type,
            beneficiary_tax_rate: this.benCalc.tax_rate,
            growth_rate: this.benCalc.growth_rate,
          };
        } else {
          params = {
            ira_balance: this.benCalc.ira_balance,
            beneficiary_tax_rate: this.benCalc.tax_rate,
            growth_rate: this.benCalc.growth_rate,
          };
        }

        const res = await fetch("/api/estate/calculate-beneficiary", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ strategy_type: this.benCalc.type, params }),
        });
        if (!res.ok) {
          const err = await res.json();
          this.errorMsg = err.detail || "Beneficiary calculation failed";
          return;
        }
        this.benResult = await res.json();
      } catch (err) {
        this.errorMsg = err.message;
      }
    },

    // ──────────────────────────────────────────────────────────────────────────
    // Charitable Calculator
    // ──────────────────────────────────────────────────────────────────────────
    async runCharitableCalculation() {
      this.errorMsg = "";
      try {
        const res = await fetch("/api/estate/calculate-charitable", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tool_type: this.charCalc.tool,
            params: this.charCalc,
          }),
        });
        if (!res.ok) {
          const err = await res.json();
          this.errorMsg = err.detail || "Charitable calculation failed";
          return;
        }
        this.charResult = await res.json();
      } catch (err) {
        this.errorMsg = err.message;
      }
    },
  };
}
