// Settings page (Alpine.js). The form is generated from GET /api/config/schema.
// State is a flat map {"section.key": value}; only changed paths are sent on save.

const usd = (n) => (n === null || n === undefined || n === "" || Number.isNaN(n) ? "" : "$" + Math.round(n).toLocaleString("en-US"));
const num0 = (v) => (typeof v === "number" && Number.isFinite(v) ? v : 0);
const clone = (v) => (v === undefined ? undefined : JSON.parse(JSON.stringify(v)));
const getPath = (tree, path) => path.split(".").reduce((o, k) => (o !== null && typeof o === "object" ? o[k] : undefined), tree);
const ISO = /^\d{4}-\d{2}-\d{2}$/;

function validDate(s) {
  if (typeof s !== "string" || !ISO.test(s)) return false;
  const d = new Date(s + "T00:00:00Z");
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s;
}

// Defaults for new table rows (the Streamlit editors use the same ones).
function newRow(spec) {
  const year = new Date().getFullYear();
  const byKey = { frequency_years: 10, start_year: year, end_year: year + 30, amount: 0, purchase_price: 0, year: year + 1 };
  const row = {};
  for (const c of spec.columns) {
    row[c.key] = c.key in byKey ? byKey[c.key] : c.type === "bool" ? false : c.type === "number" ? 0 : "";
  }
  return row;
}

function settings() {
  return {
    schema: null,
    config: null,
    form: {},
    saved: {},
    tab: "personal",
    loading: true,
    saving: false,
    message: null,       // {kind: "ok"|"error"|"warn", text}
    errors: {},          // path -> [messages]
    ss: { 1: null, 2: null },
    _ssTimers: {},

    // Direct Indexing config (separate YAML, not the main retirement_config.json)
    di: { loading: false, error: null, saved: null, saving: false, cfg: null },

    async init() {
      window.addEventListener("beforeunload", (e) => {
        if (this.dirtyPaths.length) { e.preventDefault(); e.returnValue = ""; }
      });
      try {
        const [schema, config] = await Promise.all([this.fetchJSON("/api/config/schema"), this.fetchJSON("/api/config")]);
        this.schema = schema;
        this.applyConfig(config);
      } catch (e) {
        this.message = { kind: "error", text: "Could not load settings: " + e.message };
      } finally {
        this.loading = false;
      }
    },

    async fetchJSON(url, opts) {
      const r = await fetch(url, opts);
      let body = null;
      try { body = await r.json(); } catch (_) { /* not JSON */ }
      if (!r.ok) {
        const err = new Error(`${r.status}: ${(body && body.detail && (body.detail.message || body.detail)) || r.statusText}`);
        err.status = r.status;
        err.errors = (body && body.detail && body.detail.errors) || [];
        throw err;
      }
      return body;
    },

    // ---- form state ----------------------------------------------------------------------
    *fields() {
      for (const sec of this.schema.sections) for (const g of sec.groups) for (const f of g.fields) yield f;
    },

    initialValue(f) {
      const v = getPath(this.config, f.path);
      if (v !== undefined) return clone(v);
      // Not saved yet: use the same fallbacks the Streamlit page uses.
      if (f.path === "tax_strategy.savings_safety_reserve") {
        return Math.round(num0(getPath(this.config, "financial_assumptions.expected_annual_expenses")) / 12 * 5);
      }
      if (f.type === "bool") return !!f.default;
      if (f.type === "multi" || f.type === "table") return [];
      if (f.type === "number") return f.default ?? null;
      return f.type === "select" ? (f.nullable ? null : "") : "";
    },

    applyConfig(config) {
      this.config = config;
      const form = {};
      for (const f of this.fields()) if (f.path) form[f.path] = this.initialValue(f);
      this.form = form;
      this.saved = clone(form);
      this.errors = {};
    },

    get dirtyPaths() {
      return Object.keys(this.form).filter((p) => JSON.stringify(this.form[p]) !== JSON.stringify(this.saved[p]));
    },

    sectionDirty(sec) {
      const dirty = new Set(this.dirtyPaths);
      return sec.groups.some((g) => g.fields.some((f) => f.path && dirty.has(f.path)));
    },

    // ---- display helpers -----------------------------------------------------------------
    name(n) { return (this.form[`personal_info.person${n}_name`] || (n === 1 ? "Primary" : "Spouse")).trim(); },
    lbl(s) { return (s || "").replace(/\{p1\}/g, this.name(1)).replace(/\{p2\}/g, this.name(2)); },
    optVal(o) { return Array.isArray(o) ? o[0] : o; },
    optLabel(o) { return Array.isArray(o) ? o[1] : o; },
    visible(f) {
      return (f.show_if || []).every(([path, op, val]) => {
        const v = this.form[path];
        if (op === "falsy") return !v;
        if (op === "truthy") return !!v;
        if (op === "ne") return v !== val;
        return true;
      });
    },
    groupVisible(g) { return g.fields.some((f) => this.visible(f)); },
    fieldErrors(f) { return this.errors[f.path] || []; },

    toggleMulti(path, value) {
      const cur = this.form[path];
      this.form[path] = cur.includes(value) ? cur.filter((x) => x !== value) : [...cur, value];
    },
    addRow(f) { this.form[f.path].push(newRow(f)); },
    removeRow(f, i) { this.form[f.path].splice(i, 1); },

    // ---- computed read-outs --------------------------------------------------------------
    computedView(f) {
      const F = (p) => this.form[p];
      const sum = (prefix, keys) => keys.reduce((t, k) => t + num0(F(`${prefix}.${k}`)), 0);
      const living = () => sum("expenses.living_expenses", this.livingKeys());
      const ent = () => sum("expenses.entertainment_expenses", this.entKeys());
      const id = f.id;
      let m;
      if ((m = /^ages_(\d)$/.exec(id))) {
        const n = m[1];
        const b = F(`personal_info.person${n}_birth_date`), r = F(`personal_info.person${n}_retirement_date`);
        if (!validDate(b) || !validDate(r)) return { items: [] };
        const now = new Date();
        const bd = new Date(b + "T00:00:00");
        let age = now.getFullYear() - bd.getFullYear();
        if (now.getMonth() < bd.getMonth() || (now.getMonth() === bd.getMonth() && now.getDate() < bd.getDate())) age--;
        const retYear = +r.slice(0, 4), retAge = retYear - +b.slice(0, 4);
        return { items: [
          { label: "Current age", value: String(age) },
          { label: "Retirement age", value: String(retAge) },
          { label: "Retirement year", value: String(retYear) },
          { label: "Years until retirement", value: String(Math.max(0, retYear - now.getFullYear())) },
        ] };
      }
      if (id === "living_total") return { items: [{ label: "Total living expenses", value: usd(living()) }] };
      if (id === "expense_totals") {
        const total = living() + ent();
        const saved = getPath(this.config, "financial_assumptions.expected_annual_expenses");
        const items = [
          { label: "Living expenses", value: usd(living()) },
          { label: "Entertainment & lifestyle", value: usd(ent()) },
          { label: "Total from the expense breakdown", value: usd(total) },
          { label: "Saved 'expected annual expenses'", value: usd(saved) },
        ];
        if (total <= 0) items.push({ label: "Note", value: "Breakdown is empty, so the saved value is kept." });
        else if (saved !== undefined && Math.round(saved) !== Math.round(total)) {
          items.push({ label: "Note", value: "Saving replaces the saved value with the breakdown total." });
        }
        return { items };
      }
      if ((m = /^health_cost_(\d)$/.exec(id))) {
        const n = m[1];
        const monthly = num0(F(`healthcare.person${n}_aca_insurance_monthly`));
        if (monthly <= 0) return { items: [] };
        const years = Math.max(0, num0(F(`healthcare.person${n}_aca_end_age`)) - num0(F(`healthcare.person${n}_aca_start_age`)));
        return { items: [
          { label: "Annual retirement healthcare cost", value: usd(monthly * 12) },
          { label: `Total over ${years} years`, value: usd(monthly * 12 * years) },
        ] };
      }
      if ((m = /^ss_preview_(\d)$/.exec(id))) {
        const s = this.ss[m[1]];
        return { items: s ? [
          { label: "Monthly benefit at claiming age", value: usd(s.monthly) },
          { label: "Annual", value: usd(s.annual) },
          { label: "Share of the age-67 benefit", value: s.pct_of_fra === null ? "" : s.pct_of_fra + "%" },
        ] : [] };
      }
      if (id === "bucket_progression") {
        const years = num0(F("bucket_strategy.bucket_2_years")), a = num0(F("bucket_strategy.bucket_2_start_stock_pct"));
        const b = num0(F("bucket_strategy.bucket_2_end_stock_pct"));
        if (years < 2) return { items: [] };
        const rows = [];
        for (let y = 1; y <= years; y++) {
          const stock = a + ((b - a) * (y - 1)) / (years - 1);
          rows.push([`Year ${y}`, stock.toFixed(0) + "%", (100 - stock).toFixed(0) + "%"]);
        }
        return { items: [], table: { head: ["Year", "Stocks %", "Bonds %"], rows } };
      }
      if (id === "daf_bundle_suggestion") {
        // Same rule as the Streamlit page: bundle enough years of giving to exceed the standard deduction.
        const giving = num0(F("charitable_giving.annual_charitable_giving"));
        if (giving <= 0) return { items: [] };
        const stdDed = 30000; // 2025 MFJ standard deduction reference
        const interval = Math.max(2, Math.min(Math.floor(stdDed / giving) + 1, 5));
        return { items: [
          { label: "Suggested bundle interval", value: `Every ${interval} years` },
          { label: "Suggested bundled contribution", value: usd(giving * interval) },
          { label: "Currently set", value: usd(num0(F("charitable_giving.daf_annual_contribution"))) },
        ] };
      }
      if (id === "re_total") {
        const rows = F("real_estate.properties") || [];
        return { items: [
          { label: "Properties", value: String(rows.length) },
          { label: "Total purchase price", value: usd(rows.reduce((t, r) => t + num0(r.purchase_price), 0)) },
        ] };
      }
      return { items: [] };
    },
    livingKeys() { return this.keysUnder("expenses.living_expenses."); },
    entKeys() { return this.keysUnder("expenses.entertainment_expenses.").filter((k) => !k.startsWith("retirement_decline")); },
    keysUnder(prefix) {
      return Object.keys(this.form).filter((p) => p.startsWith(prefix)).map((p) => p.slice(prefix.length))
        .filter((k) => typeof this.form[prefix + k] === "number" || this.form[prefix + k] === null);
    },

    // Social Security benefit preview comes from the server so it uses the same SSA rules as the engine.
    refreshSS(n) {
      const amount = this.form[`social_security.person${n}_ssi_amount`], age = this.form[`social_security.person${n}_ssi_age`];
      clearTimeout(this._ssTimers[n]);
      if (typeof amount !== "number" || typeof age !== "number") { return; }
      this._ssTimers[n] = setTimeout(async () => {
        try { this.ss[n] = await this.fetchJSON(`/api/social-security/preview?amount=${amount}&age=${age}`); }
        catch (_) { this.ss[n] = null; }
      }, 250);
    },

    // ---- validation + save ---------------------------------------------------------------
    validateField(f, v) {
      if (f.type === "number") {
        if (v === "" || v === null || typeof v !== "number" || !Number.isFinite(v)) return "Enter a number";
        if (f.int && !Number.isInteger(v)) return "Must be a whole number";
        if (v < f.min || v > f.max) return `Must be between ${f.min} and ${f.max}`;
      } else if (f.type === "date") {
        if ((v === null || v === "") && f.nullable) return null;
        if (!validDate(v)) return "Enter a valid date";
      } else if (f.type === "text") {
        if (typeof v === "string" && v.length > (f.max_len || 120)) return `At most ${f.max_len || 120} characters`;
      }
      return null;
    },

    buildChanges() {
      const changes = {};
      const specs = {};
      for (const f of this.fields()) if (f.path) specs[f.path] = f;
      const errors = {};
      for (const p of this.dirtyPaths) {
        const f = specs[p];
        let v = clone(this.form[p]);
        if (f.type !== "table") {
          const msg = this.validateField(f, v);
          if (msg) { errors[p] = [msg]; continue; }
          if (v === "" && f.nullable) v = null;
        }
        const parts = p.split(".");
        let cur = changes;
        parts.slice(0, -1).forEach((k) => { cur = cur[k] = cur[k] || {}; });
        cur[parts[parts.length - 1]] = v;
      }
      return { changes, errors };
    },

    async save() {
      this.message = null;
      const { changes, errors } = this.buildChanges();
      this.errors = errors;
      if (Object.keys(errors).length) {
        this.message = { kind: "error", text: `Fix ${Object.keys(errors).length} field(s) marked in red before saving.` };
        this.jumpToFirstError();
        return;
      }
      if (!Object.keys(changes).length) { this.message = { kind: "ok", text: "No changes to save." }; return; }
      this.saving = true;
      try {
        const res = await this.fetchJSON("/api/config", {
          method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ changes }),
        });
        this.applyConfig(res.config);
        const notes = Object.entries(res.derived || {}).map(([p, v]) => `${p.split(".").pop()} = ${v}`);
        const warn = (res.warnings || []).join(" ");
        this.message = {
          kind: warn ? "warn" : "ok",
          text: "Saved." + (notes.length ? " Derived: " + notes.join(", ") + "." : "") + (warn ? " " + warn : ""),
        };
      } catch (e) {
        const errs = {};
        for (const er of e.errors || []) (errs[er.path] = errs[er.path] || []).push(er.message);
        this.errors = errs;
        this.message = { kind: "error", text: Object.keys(errs).length ? "The server rejected some values (marked in red)." : "Save failed: " + e.message };
        this.jumpToFirstError();
      } finally {
        this.saving = false;
      }
    },

    jumpToFirstError() {
      const first = Object.keys(this.errors)[0];
      if (!first) return;
      for (const sec of this.schema.sections) {
        if (sec.groups.some((g) => g.fields.some((f) => f.path === first))) { this.tab = sec.id; return; }
      }
    },

    discard() {
      if (this.dirtyPaths.length && !confirm("Discard all unsaved changes?")) return;
      this.form = clone(this.saved);
      this.errors = {};
      this.message = null;
    },

    async resetDefaults() {
      if (!confirm("Reset ALL settings to the built-in defaults? The current file is backed up first, but this replaces every value.")) return;
      this.saving = true;
      try {
        const res = await this.fetchJSON("/api/config/reset", { method: "POST" });
        this.applyConfig(res.config);
        this.message = { kind: "ok", text: "Settings reset to defaults (previous file backed up)." };
      } catch (e) {
        this.message = { kind: "error", text: "Reset failed: " + e.message };
      } finally {
        this.saving = false;
      }
    },

    // ------------------------------------------------------------------ Direct Indexing
    async diOpen() {
      this.tab = "di";
      if (!this.di.cfg && !this.di.loading) await this.diLoad();
    },

    async diLoad() {
      this.di.loading = true;
      this.di.error = null;
      try {
        const raw = await this.fetchJSON("/api/di/config");
        // Expose the direct_indexing sub-key for the form
        this.di.cfg = raw.direct_indexing || {};
        // Ensure all expected sub-sections exist so x-model doesn't throw
        this.di.cfg.thresholds   = this.di.cfg.thresholds   || {};
        this.di.cfg.replacement  = this.di.cfg.replacement  || {};
        this.di.cfg.wash_sale    = this.di.cfg.wash_sale    || {};
        this.di.cfg.data         = this.di.cfg.data         || {};
        this.di.cfg.initial_setup = this.di.cfg.initial_setup || {};
      } catch (e) {
        this.di.error = "Could not load DI config: " + e.message;
      } finally {
        this.di.loading = false;
      }
    },

    async diSave() {
      this.di.saving = true;
      this.di.saved = null;
      this.di.error = null;
      try {
        await this.fetchJSON("/api/di/config", {
          method: "PUT",
          body: JSON.stringify({ changes: this.di.cfg }),
        });
        this.di.saved = "Direct Indexing config saved.";
        setTimeout(() => { this.di.saved = null; }, 4000);
      } catch (e) {
        this.di.error = "Save failed: " + e.message;
      } finally {
        this.di.saving = false;
      }
    },
  };
}
