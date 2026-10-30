/* Scenario Planning JavaScript (Alpine.js + Plotly.js) */

function scenarioPage() {
  return {
    availableScenarios: [],
    selectedScenarioIds: [],
    selectedScenarios: [],
    results: {},
    eventTemplates: [],
    activeTab: 'trajectories',

    loading: false,
    loadingMsg: '',
    statusMsg: '',
    errorMsg: '',

    // Editing
    editingScenario: null,

    // Modals
    showNewModal: false,
    newScenarioName: '',
    newScenarioDesc: '',

    showEventModal: false,
    eventTargetScenarioId: null,
    selectedTemplateName: '',
    newEvent: {
      name: '',
      event_type: 'custom',
      start_age: 62,
      end_age: 0,
      income_change: 0,
      expense_change: 0,
      one_time_amount: 0,
      notes: '',
      color: '#3B82F6',
    },

    async init() {
      await this.loadTemplates();
      await this.loadScenarios();
    },

    showStatus(msg) {
      this.statusMsg = msg;
      this.errorMsg = '';
      setTimeout(() => { if (this.statusMsg === msg) this.statusMsg = ''; }, 5000);
    },

    showError(msg) {
      this.errorMsg = msg;
      this.statusMsg = '';
      setTimeout(() => { if (this.errorMsg === msg) this.errorMsg = ''; }, 8000);
    },

    formatCurrency(val) {
      if (val === null || val === undefined || isNaN(val)) return '$0';
      return '$' + Math.round(Number(val)).toLocaleString();
    },

    formatPct(val) {
      if (val === null || val === undefined || isNaN(val)) return '0.0%';
      return (Number(val) * 100).toFixed(1) + '%';
    },

    async loadTemplates() {
      try {
        const res = await fetch('/api/scenarios/templates');
        if (res.ok) {
          this.eventTemplates = await res.json();
        }
      } catch (e) {
        console.error('Failed to load event templates:', e);
      }
    },

    async loadScenarios() {
      try {
        this.loading = true;
        this.loadingMsg = 'Loading scenarios...';
        const res = await fetch('/api/scenarios');
        if (!res.ok) throw new Error('Failed to fetch scenarios');
        this.availableScenarios = await res.json();

        // Default selection: up to first 2 scenarios
        if (this.selectedScenarioIds.length === 0 && this.availableScenarios.length > 0) {
          this.selectedScenarioIds = this.availableScenarios.slice(0, Math.min(2, this.availableScenarios.length)).map(s => s.id);
        }

        await this.syncSelectedScenarios();
      } catch (e) {
        this.showError(e.message || 'Error loading scenarios');
      } finally {
        this.loading = false;
        this.loadingMsg = '';
      }
    },

    async syncSelectedScenarios() {
      this.selectedScenarios = [];
      for (const id of this.selectedScenarioIds) {
        try {
          const res = await fetch(`/api/scenarios/${id}`);
          if (res.ok) {
            const sc = await res.json();
            this.selectedScenarios.push(sc);
          }
        } catch (e) {
          console.error(`Error loading scenario ${id}:`, e);
        }
      }

      // Update editing scenario if 1 selected
      if (this.selectedScenarios.length === 1) {
        this.editingScenario = JSON.parse(JSON.stringify(this.selectedScenarios[0]));
      } else if (this.selectedScenarios.length > 0) {
        this.editingScenario = JSON.parse(JSON.stringify(this.selectedScenarios[0]));
      } else {
        this.editingScenario = null;
      }

      await this.runAnalysisForSelected();
    },

    async toggleScenario(id) {
      const idx = this.selectedScenarioIds.indexOf(id);
      if (idx >= 0) {
        this.selectedScenarioIds.splice(idx, 1);
      } else {
        if (this.selectedScenarioIds.length >= 4) {
          this.showError('You can compare a maximum of 4 scenarios at once.');
          return;
        }
        this.selectedScenarioIds.push(id);
      }
      await this.syncSelectedScenarios();
    },

    async runAnalysisForSelected() {
      if (this.selectedScenarios.length === 0) return;

      this.loading = true;
      this.loadingMsg = 'Running Monte Carlo simulations & timeline analysis...';

      for (const sc of this.selectedScenarios) {
        try {
          const res = await fetch(`/api/scenarios/${sc.id}/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ n_simulations: 5000 }),
          });
          if (res.ok) {
            this.results[sc.id] = await res.json();
          }
        } catch (e) {
          console.error(`Analysis failed for ${sc.name}:`, e);
        }
      }

      this.loading = false;
      this.loadingMsg = '';
      this.$nextTick(() => {
        this.renderAllCharts();
      });
    },

    renderAllCharts() {
      this.renderTrajectoryChart();
      this.renderSuccessChart();
      this.renderCashflowCharts();
      this.renderEventTimelineCharts();
    },

    resizeCharts() {
      this.$nextTick(() => {
        const ids = ['chart-trajectories', 'chart-success'];
        for (const sc of this.selectedScenarios) {
          ids.push(`chart-cashflow-${sc.id}`);
          ids.push(`chart-events-${sc.id}`);
        }
        ids.forEach(id => {
          const el = document.getElementById(id);
          if (el && window.Plotly) {
            try { Plotly.Plots.resize(el); } catch (_) {}
          }
        });
      });
    },

    renderTrajectoryChart() {
      const el = document.getElementById('chart-trajectories');
      if (!el || !window.Plotly) return;

      const colors = ['#3b82d4', '#10b981', '#f59e0b', '#8b5cf6'];
      const data = [];

      this.selectedScenarios.forEach((sc, idx) => {
        const res = this.results[sc.id];
        if (res && res.median_path && res.ages) {
          data.push({
            x: res.ages,
            y: res.median_path,
            type: 'scatter',
            mode: 'lines',
            name: sc.name,
            line: { color: colors[idx % colors.length], width: 3 },
            hovertemplate: `<b>${sc.name}</b><br>Age: %{x}<br>Portfolio: $%{y:,.0f}<extra></extra>`,
          });
        }
      });

      const layout = {
        title: 'Portfolio Value Over Time (Median Projection)',
        xaxis: { title: 'Age' },
        yaxis: { title: 'Portfolio Value ($)', tickformat: '$,.0f' },
        hovermode: 'x unified',
        legend: { orientation: 'h', yanchor: 'bottom', y: 1.02, xanchor: 'left', x: 0 },
        margin: { t: 40, r: 20, l: 70, b: 40 },
        autosize: true,
      };

      Plotly.react(el, data, layout, { responsive: true, displayModeBar: false });
    },

    renderSuccessChart() {
      const el = document.getElementById('chart-success');
      if (!el || !window.Plotly) return;

      const names = [];
      const rates = [];
      const barColors = [];

      this.selectedScenarios.forEach(sc => {
        const res = this.results[sc.id];
        if (res) {
          const pct = (res.success_probability || 0) * 100;
          names.push(sc.name);
          rates.push(pct);
          barColors.push(pct >= 90 ? '#10b981' : (pct >= 75 ? '#f59e0b' : '#ef4444'));
        }
      });

      const data = [{
        x: names,
        y: rates,
        type: 'bar',
        marker: { color: barColors },
        text: rates.map(r => r.toFixed(1) + '%'),
        textposition: 'outside',
      }];

      const layout = {
        title: 'Success Probability by Scenario',
        yaxis: { title: 'Success Probability (%)', range: [0, 115] },
        shapes: [{
          type: 'line',
          y0: 90,
          y1: 90,
          x0: -0.5,
          x1: names.length - 0.5,
          line: { color: '#f59e0b', dash: 'dash', width: 2 },
        }],
        annotations: [{
          x: names.length - 1,
          y: 92,
          text: '90% Target',
          showarrow: false,
          font: { color: '#f59e0b' },
        }],
        margin: { t: 40, r: 20, l: 60, b: 40 },
        autosize: true,
      };

      Plotly.react(el, data, layout, { responsive: true, displayModeBar: false });
    },

    renderCashflowCharts() {
      this.selectedScenarios.forEach(sc => {
        const el = document.getElementById(`chart-cashflow-${sc.id}`);
        if (!el || !window.Plotly) return;

        const res = this.results[sc.id];
        if (!res || !res.cash_flows) return;

        const ages = res.cash_flows.map(cf => cf.age);
        const income = res.cash_flows.map(cf => cf.income);
        const expenses = res.cash_flows.map(cf => cf.expenses);
        const net = res.cash_flows.map(cf => cf.net_cash_flow);

        const data = [
          {
            x: ages,
            y: income,
            type: 'scatter',
            mode: 'lines',
            name: 'Income',
            line: { color: '#10b981', width: 2 },
            fill: 'tozeroy',
            fillcolor: 'rgba(16, 185, 129, 0.2)',
          },
          {
            x: ages,
            y: expenses,
            type: 'scatter',
            mode: 'lines',
            name: 'Expenses',
            line: { color: '#ef4444', width: 2 },
            fill: 'tozeroy',
            fillcolor: 'rgba(239, 68, 68, 0.2)',
          },
          {
            x: ages,
            y: net,
            type: 'scatter',
            mode: 'lines',
            name: 'Net Cash Flow',
            line: { color: '#3b82d4', width: 3, dash: 'dash' },
          }
        ];

        const layout = {
          xaxis: { title: 'Age' },
          yaxis: { title: 'Annual Amount ($)', tickformat: '$,.0f' },
          hovermode: 'x unified',
          margin: { t: 20, r: 20, l: 70, b: 40 },
          autosize: true,
        };

        Plotly.react(el, data, layout, { responsive: true, displayModeBar: false });
      });
    },

    renderEventTimelineCharts() {
      this.selectedScenarios.forEach(sc => {
        const el = document.getElementById(`chart-events-${sc.id}`);
        if (!el || !window.Plotly) return;

        const events = sc.life_events || [];
        if (events.length === 0) return;

        const data = events.map((ev, idx) => {
          const end = ev.end_age || ev.start_age;
          return {
            x: [ev.start_age, end],
            y: [idx, idx],
            type: 'scatter',
            mode: 'lines+markers',
            name: ev.name,
            line: { color: ev.color || '#3b82f6', width: 8 },
            marker: { size: 10, color: ev.color || '#3b82f6' },
            hovertemplate: `<b>${ev.name}</b><br>Ages: ${ev.start_age}-${end}<extra></extra>`,
          };
        });

        const layout = {
          xaxis: { title: 'Age' },
          yaxis: { showticklabels: false, zeroline: false },
          showlegend: true,
          margin: { t: 20, r: 20, l: 30, b: 40 },
          height: Math.max(200, events.length * 45),
          autosize: true,
        };

        Plotly.react(el, data, layout, { responsive: true, displayModeBar: false });
      });
    },

    openNewScenarioModal() {
      this.newScenarioName = '';
      this.newScenarioDesc = '';
      this.showNewModal = true;
    },

    async createNewScenario() {
      if (!this.newScenarioName.trim()) {
        this.showError('Scenario name is required.');
        return;
      }

      try {
        const res = await fetch('/api/scenarios', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: this.newScenarioName.trim(),
            description: this.newScenarioDesc.trim(),
          }),
        });

        if (!res.ok) throw new Error('Failed to create scenario');
        const sc = await res.json();
        this.showNewModal = false;
        this.showStatus(`Scenario '${sc.name}' created!`);
        this.selectedScenarioIds = [sc.id];
        await this.loadScenarios();
      } catch (e) {
        this.showError(e.message || 'Error creating scenario');
      }
    },

    async cloneSelectedScenario() {
      if (this.selectedScenarioIds.length !== 1) return;
      const id = this.selectedScenarioIds[0];
      try {
        const res = await fetch(`/api/scenarios/${id}/clone`, { method: 'POST' });
        if (!res.ok) throw new Error('Failed to clone scenario');
        const cloned = await res.json();
        this.showStatus(`Cloned as '${cloned.name}'!`);
        this.selectedScenarioIds = [cloned.id];
        await this.loadScenarios();
      } catch (e) {
        this.showError(e.message || 'Error cloning scenario');
      }
    },

    async deleteSelectedScenario() {
      if (this.selectedScenarioIds.length !== 1) return;
      const id = this.selectedScenarioIds[0];
      if (!confirm('Are you sure you want to delete this scenario?')) return;

      try {
        const res = await fetch(`/api/scenarios/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Cannot delete baseline or scenario not found');
        this.showStatus('Scenario deleted');
        this.selectedScenarioIds = [];
        await this.loadScenarios();
      } catch (e) {
        this.showError(e.message || 'Error deleting scenario');
      }
    },

    async saveScenarioChanges() {
      if (!this.editingScenario) return;
      try {
        const id = this.editingScenario.id;
        const res = await fetch(`/api/scenarios/${id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.editingScenario),
        });

        if (!res.ok) throw new Error('Failed to save scenario');
        this.showStatus('Scenario updated successfully!');
        await this.loadScenarios();
      } catch (e) {
        this.showError(e.message || 'Error saving scenario');
      }
    },

    openAddEventModal(scenarioId) {
      this.eventTargetScenarioId = scenarioId;
      this.selectedTemplateName = '';
      this.newEvent = {
        name: 'Custom Event',
        event_type: 'custom',
        start_age: 62,
        end_age: 0,
        income_change: 0,
        expense_change: 0,
        one_time_amount: 0,
        notes: '',
        color: '#3B82F6',
      };
      this.showEventModal = true;
    },

    applyTemplate() {
      const t = this.eventTemplates.find(x => x.name === this.selectedTemplateName);
      if (t) {
        this.newEvent.name = t.name;
        this.newEvent.event_type = t.type;
        this.newEvent.income_change = t.default_income_change || 0;
        this.newEvent.expense_change = t.default_expense_change || 0;
        this.newEvent.one_time_amount = t.default_one_time || 0;
        this.newEvent.color = t.color || '#3B82F6';
      }
    },

    async submitAddLifeEvent() {
      if (!this.eventTargetScenarioId) return;
      try {
        const res = await fetch(`/api/scenarios/${this.eventTargetScenarioId}/events`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.newEvent),
        });

        if (!res.ok) throw new Error('Failed to add life event');
        this.showEventModal = false;
        this.showStatus('Life event added!');
        await this.loadScenarios();
      } catch (e) {
        this.showError(e.message || 'Error adding life event');
      }
    },

    async deleteLifeEvent(scenarioId, eventId) {
      if (!confirm('Are you sure you want to remove this life event?')) return;
      try {
        const res = await fetch(`/api/scenarios/${scenarioId}/events/${eventId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Failed to delete event');
        this.showStatus('Life event removed');
        await this.loadScenarios();
      } catch (e) {
        this.showError(e.message || 'Error removing life event');
      }
    },

    downloadComparisonCsv() {
      if (this.selectedScenarios.length === 0) return;
      const headers = ['Parameter', ...this.selectedScenarios.map(s => `"${s.name}"`)];
      const rows = [
        ['Starting Portfolio', ...this.selectedScenarios.map(s => s.initial_portfolio)],
        ['Annual Expenses', ...this.selectedScenarios.map(s => s.annual_expenses)],
        ['Retirement Age', ...this.selectedScenarios.map(s => s.retirement_age)],
        ['Plan End Age', ...this.selectedScenarios.map(s => s.plan_to_age)],
        ['Inflation Rate', ...this.selectedScenarios.map(s => (s.inflation_rate * 100).toFixed(1) + '%')],
        ['Social Security (Person 1)', ...this.selectedScenarios.map(s => s.social_security?.person1_amount || 0)],
        ['Life Events Count', ...this.selectedScenarios.map(s => (s.life_events || []).length)],
        ['Success Rate', ...this.selectedScenarios.map(s => this.results[s.id] ? (this.results[s.id].success_probability * 100).toFixed(1) + '%' : 'N/A')],
        ['Median Final Portfolio', ...this.selectedScenarios.map(s => this.results[s.id] ? Math.round(this.results[s.id].median_final) : 'N/A')],
      ];

      const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.setAttribute('href', url);
      link.setAttribute('download', `scenario_comparison_${new Date().toISOString().slice(0, 10)}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    },
  };
}
