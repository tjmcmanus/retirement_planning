/* Reports & PDF Export JavaScript (Alpine.js) */

function reportsPage() {
  return {
    activeTab: 'generate',
    templates: [],
    selectedTemplateId: 'comprehensive_retirement_plan',
    currentTemplate: null,
    sectionSelections: {},

    reportOptions: {
      title: 'Comprehensive Retirement Plan',
      prepared_for: '',
      filename: '',
    },

    // Generation State
    generating: false,
    generationProgress: 0,
    generationMessage: '',
    activeJobId: null,
    lastGeneratedFile: null,

    // History State
    historyList: [],

    // Expense & Healthcare State
    expenseHcData: null,

    // Feedback
    statusMsg: '',
    errorMsg: '',

    async init() {
      await this.loadTemplates();
      await this.loadDefaultNames();
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

    get enabledSectionsCount() {
      if (!this.currentTemplate || !this.currentTemplate.sections) return 0;
      return this.currentTemplate.sections.filter(s => this.sectionSelections[s.section_id] !== false).length;
    },

    async loadTemplates() {
      try {
        const res = await fetch('/api/reports/templates');
        if (!res.ok) throw new Error('Failed to load templates');
        this.templates = await res.json();

        if (this.templates.length > 0) {
          if (!this.templates.some(t => t.template_id === this.selectedTemplateId)) {
            this.selectedTemplateId = this.templates[0].template_id;
          }
          await this.loadTemplateDetails(this.selectedTemplateId);
        }
      } catch (e) {
        this.showError(e.message || 'Error loading templates');
      }
    },

    async loadDefaultNames() {
      try {
        const res = await fetch('/api/config');
        if (res.ok) {
          const cfg = await res.json();
          const p1 = cfg.personal_info?.person1_name || '';
          const p2 = cfg.personal_info?.person2_name || '';
          const single = cfg.personal_info?.is_single_person || false;

          if (single && p1) {
            this.reportOptions.prepared_for = p1;
          } else if (p1 && p2) {
            this.reportOptions.prepared_for = `${p1} & ${p2}`;
          } else if (p1) {
            this.reportOptions.prepared_for = p1;
          }
        }
      } catch (_) {}
    },

    async onTemplateChange() {
      await this.loadTemplateDetails(this.selectedTemplateId);
    },

    async loadTemplateDetails(templateId) {
      try {
        const res = await fetch(`/api/reports/templates/${templateId}`);
        if (!res.ok) throw new Error('Failed to load template details');
        this.currentTemplate = await res.json();

        // Update default title & sections
        this.reportOptions.title = this.currentTemplate.name;
        const slug = this.currentTemplate.name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
        const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
        this.reportOptions.filename = `${slug}_${dateStr}.pdf`;

        // Initialize section selections
        this.sectionSelections = {};
        (this.currentTemplate.sections || []).forEach(s => {
          this.sectionSelections[s.section_id] = s.enabled !== false;
        });
      } catch (e) {
        this.showError(e.message || 'Error loading template details');
      }
    },

    async generateReport() {
      if (!this.selectedTemplateId) return;

      this.generating = true;
      this.generationProgress = 5;
      this.generationMessage = 'Starting report generation...';
      this.lastGeneratedFile = null;

      try {
        const payload = {
          template_id: this.selectedTemplateId,
          title: this.reportOptions.title,
          prepared_for: this.reportOptions.prepared_for,
          filename: this.reportOptions.filename,
          sections: this.sectionSelections,
        };

        const res = await fetch('/api/reports/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        if (!res.ok) throw new Error('Failed to submit report job');
        const data = await res.json();
        this.activeJobId = data.job_id;

        // Poll job progress
        await this.pollJob(this.activeJobId);
      } catch (e) {
        this.generating = false;
        this.showError(e.message || 'Error generating report');
      }
    },

    async pollJob(jobId) {
      const interval = 1000;
      const check = async () => {
        try {
          const res = await fetch(`/api/jobs/${jobId}`);
          if (!res.ok) throw new Error('Failed to poll report job');
          const job = await res.json();

          this.generationProgress = job.progress || 0;
          this.generationMessage = job.message || 'Processing...';

          if (job.status === 'completed') {
            this.generating = false;
            this.generationProgress = 100;
            this.lastGeneratedFile = job.result;
            this.showStatus('Report generated successfully!');
          } else if (job.status === 'failed') {
            this.generating = false;
            this.showError(job.error || 'Report generation failed');
          } else {
            setTimeout(check, interval);
          }
        } catch (e) {
          this.generating = false;
          this.showError(e.message || 'Polling error');
        }
      };
      setTimeout(check, interval);
    },

    async loadHistory() {
      try {
        const res = await fetch('/api/reports/history');
        if (res.ok) {
          this.historyList = await res.json();
        }
      } catch (e) {
        this.showError('Failed to load report history');
      }
    },

    async deleteReportFile(filename) {
      if (!confirm(`Delete report '${filename}'?`)) return;
      try {
        const res = await fetch(`/api/reports/history/${encodeURIComponent(filename)}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Failed to delete report');
        this.showStatus('Report deleted');
        await this.loadHistory();
      } catch (e) {
        this.showError(e.message || 'Error deleting report');
      }
    },

    async clearAllHistory() {
      if (!confirm('Are you sure you want to delete ALL generated reports?')) return;
      try {
        const res = await fetch('/api/reports/history', { method: 'DELETE' });
        if (!res.ok) throw new Error('Failed to clear reports');
        this.showStatus('All reports cleared');
        await this.loadHistory();
      } catch (e) {
        this.showError(e.message || 'Error clearing reports');
      }
    },

    async loadExpenseHcData() {
      try {
        const res = await fetch('/api/reports/expense-healthcare-data');
        if (res.ok) {
          this.expenseHcData = await res.json();
        }
      } catch (e) {
        this.showError('Failed to load expense & healthcare data');
      }
    },
  };
}
