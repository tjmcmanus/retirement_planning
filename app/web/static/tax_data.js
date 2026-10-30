// Tax Data Admin page (Alpine.js + Tabulator). No build step, no network except /api.
// One table and one year are edited at a time; the server validates and backs up on every save.

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

// Tabulator is kept out of Alpine's reactive state (proxying breaks it).
let grid = null;
let nextRid = 1;
let baseline = "";
let sentRids = [];
const errorRids = new Set();

const withRid = (rows) => rows.map((r) => ({ ...r, rid: nextRid++ }));
const strip = (rows, cols) => rows.map((r) => Object.fromEntries(cols.map((c) => [c, r[c] === undefined ? null : r[c]])));
// Order-independent, so reverting an edit makes the page clean again.
const fingerprint = (rows, cols) => JSON.stringify(strip(rows, cols).map((r) => JSON.stringify(r)).sort());

function taxAdmin() {
  return {
    tables: [], current: null, data: null, year: null,
    loading: true, busy: false, dirty: false, rowCount: 0,
    message: null, errorLines: [],
    up: { open: false, text: "", report: null, error: null },

    async init() {
      try {
        this.tables = await api("/api/tax-data");
      } catch (e) {
        this.say("error", "Could not load tax tables: " + e.message);
        this.loading = false;
        return;
      }
      this.loading = false;
      const wanted = location.hash.replace("#", "");
      const first = this.tables.find((t) => t.key === wanted && t.exists) || this.tables.find((t) => t.exists);
      if (first) await this.load(first.key, null);
    },

    say(kind, text) { this.message = text ? { kind, text } : null; },
    get cols() { return this.data ? this.data.columns.map((c) => c.name) : []; },

    async openTable(key) {
      if (key === this.current) return;
      if (this.dirty && !confirm("Discard unsaved changes and switch table?")) return;
      history.replaceState(null, "", "#" + key);
      await this.load(key, null);
    },

    async changeYear() {
      const wanted = this.year;
      if (this.dirty && !confirm("Discard unsaved changes and switch year?")) { this.year = this.data.year; return; }
      await this.load(this.current, wanted);
    },

    async load(key, year) {
      this.busy = true; this.say("", ""); this.errorLines = []; errorRids.clear();
      this.up = { open: false, text: "", report: null, error: null };
      try {
        const data = await api(`/api/tax-data/${key}` + (year ? `?year=${year}` : ""));
        this.current = key;
        await this.show(data);
      } catch (e) {
        this.say("error", "Could not load the table: " + e.message);
      } finally {
        this.busy = false;
      }
    },

    async show(data) {
      this.data = data;
      this.year = data.year;
      await this.$nextTick();
      this.buildGrid(withRid(data.rows));
    },

    // ---- grid -----------------------------------------------------------------------------
    buildGrid(rows) {
      if (grid) { try { grid.destroy(); } catch (_e) { /* already gone */ } grid = null; }
      const numeric = (c) => c.kind === "int" || c.kind === "float";
      const columns = this.data.columns.map((c) => {
        const col = { title: c.name, field: c.name, headerSort: true, minWidth: 90 };
        if (c.choices) {
          col.editor = "list"; col.editorParams = { values: c.choices, clearable: false }; col.minWidth = 170;
        } else if (numeric(c)) {
          col.editor = "number"; col.editorParams = { step: c.kind === "int" ? 1 : "any" }; col.hozAlign = "right";
        } else {
          col.editor = "input";
        }
        return col;
      });
      columns.push({ title: "", field: "_del", headerSort: false, width: 44, hozAlign: "center", formatter: () => "✕", cellClick: (_e, cell) => cell.getRow().delete() });
      grid = new Tabulator("#grid-tax", {
        data: rows, index: "rid", layout: "fitColumns", height: Math.min(80 + rows.length * 36, 560), placeholder: "No rows",
        columns,
        rowFormatter: (row) => row.getElement().classList.toggle("row-error", errorRids.has(row.getData().rid)),
      });
      // getData() is empty until Tabulator has finished building, so start from the rows we passed in.
      baseline = fingerprint(rows, this.cols);
      this.rowCount = rows.length;
      this.dirty = false;
      grid.on("cellEdited", () => this.sync());
      grid.on("rowAdded", () => this.sync());
      grid.on("rowDeleted", () => this.sync());
    },

    sync() {
      const rows = grid ? grid.getData() : [];
      this.rowCount = rows.length;
      this.dirty = fingerprint(rows, this.cols) !== baseline;
    },

    addRow() {
      const row = { rid: nextRid++ };
      for (const c of this.data.columns) {
        row[c.name] = c.name === "year" && this.data.year ? this.data.year : c.choices ? c.choices[0] : c.kind === "text" ? "" : null;
      }
      grid.addRow(row, false);                  // at the bottom; the grid scrolls to it
      grid.scrollToRow(row.rid, "bottom", false);
    },

    discard() {
      const editing = grid.modules.edit && grid.modules.edit.currentCell;     // an open editor breaks setData()
      if (editing) { try { editing.getComponent().cancelEdit(); } catch (_e) { /* the editor's cell is already gone */ } }
      errorRids.clear(); this.errorLines = [];
      grid.setData(withRid(this.data.rows)).then(() => { baseline = fingerprint(grid.getData(), this.cols); this.sync(); });
    },

    // ---- save -----------------------------------------------------------------------------
    async save() {
      this.busy = true; this.say("", ""); this.errorLines = []; errorRids.clear();
      const editing = grid.modules.edit && grid.modules.edit.currentCell;
      if (editing) { try { editing.getComponent().cancelEdit(); } catch (_e) { /* ignore */ } }
      const rows = grid.getData();
      sentRids = rows.map((r) => r.rid);
      try {
        const out = await api(`/api/tax-data/${this.current}`, { method: "PUT", body: { year: this.data.year, rows: strip(rows, this.cols) } });
        await this.show(out);
        this.tables = await api("/api/tax-data");
        this.say("ok", `Saved ${this.data.filename}.` + (out.backup ? ` Previous file backed up to ${out.backup}.` : ""));
      } catch (e) {
        if (e.status === 422 && e.errors.length) {
          this.errorLines = e.errors.map((x) => (x.row === null || x.row === undefined ? "" : `Row ${x.row + 1}` + (x.column ? `, ${x.column}` : "") + ": ") + x.message);
          e.errors.forEach((x) => { if (x.row !== null && x.row !== undefined && sentRids[x.row] !== undefined) errorRids.add(sentRids[x.row]); });
          grid.redraw(true);
          this.say("error", e.message);
        } else {
          this.say("error", "Save failed: " + e.message);
        }
      } finally {
        this.busy = false;
      }
    },

    // ---- upload ---------------------------------------------------------------------------
    async pickFile(ev) {
      const file = ev.target.files[0];
      this.up.report = null; this.up.error = null; this.up.text = "";
      if (!file) return;
      if (file.size > 1_500_000) { this.up.error = "File is too large (limit 1.5 MB)."; return; }
      this.up.text = await file.text();
      this.busy = true;
      try {
        this.up.report = await api(`/api/tax-data/${this.current}/validate-upload`, { method: "POST", body: { csv: this.up.text } });
      } catch (e) {
        this.up.error = e.errors && e.errors.length ? e.errors.map((x) => x.message).join(" ") : "Could not read the file: " + e.message;
      } finally {
        this.busy = false;
      }
    },

    async confirmUpload() {
      if (this.dirty && !confirm("Unsaved grid edits will be lost. Replace the file anyway?")) return;
      this.busy = true;
      try {
        const out = await api(`/api/tax-data/${this.current}/upload`, { method: "PUT", body: { csv: this.up.text } });
        this.up = { open: false, text: "", report: null, error: null };
        document.getElementById("upload-file").value = "";
        await this.show(out);
        this.tables = await api("/api/tax-data");
        this.say("ok", `${this.data.filename} has been replaced.` + (out.backup ? ` Previous file backed up to ${out.backup}.` : ""));
      } catch (e) {
        this.up.error = "Upload failed: " + e.message;
      } finally {
        this.busy = false;
      }
    },
  };
}
