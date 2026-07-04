# Quick Start Guide — Retirement Planning Application

Get the application running and loaded with your data in about 10 minutes.

---

## 1. Prerequisites

| Requirement | Version | Check |
|---|---|---|
| Python | 3.9 or higher | `python3 --version` |
| pip | any recent | `pip3 --version` |
| Git | optional | `git --version` |

---

## 2. Download and Install

```bash
# Clone the repository (or download and unzip)
git clone https://github.com/yourusername/retirement_planning.git
cd retirement_planning

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# Install all dependencies
pip install -r requirements.txt
```

---

## 3. Set Up Your Data Files

### 3a. Portfolio data (required)

Copy the sample file and rename it:

```bash
cp portfolio_data_truth.sample.csv portfolio_data_truth.csv
```

Edit the CSV to match your actual accounts, or leave the sample data in place to explore the app first. The format is:

```
Account,Type,Owner,Balance,Basis,Contribution,Annual_Return
401k,401k,Person1,500000,500000,19500,0.07
Roth IRA,Roth IRA,Person1,100000,80000,7000,0.07
Brokerage,Taxable,Joint,250000,200000,0,0.07
```

### 3b. Configuration (required)

The app ships with sensible defaults. The first time you launch, open the **Configuration** page (⚙️ in the sidebar) and fill in:

- Your name(s) and birth dates
- Planned retirement ages
- Annual expenses and filing status
- State of residence
- Social Security benefit estimates

Configuration is saved to `retirement_config.json` automatically.

### 3c. Environment file (optional — brokerage sync only)

```bash
cp .env.example .env
```

Only needed if you want automatic brokerage sync via SnapTrade. See the [Brokerage Connections guide](../guides/brokerage-connections.md) for details.

---

## 4. Run the Application

### macOS / Linux

```bash
./run.sh
```

### Windows

```cmd
run.bat
```

### Manual start

```bash
streamlit run planning_app.py
```

The app opens in your default browser at **http://localhost:8501**.  
Press `Ctrl+C` in the terminal to stop it.

---

## 5. First-Time Walkthrough

Follow this sequence on your first session:

| Step | Where | What to do |
|---|---|---|
| 1 | ⚙️ Configuration | Enter your personal info, expenses, and Social Security estimates |
| 2 | 💼 Portfolio Hub → Holdings | Verify or edit your accounts imported from the CSV |
| 3 | 📊 Dashboard | Check the net-worth projection and market forecast tabs |
| 4 | 🗺️ Strategy | Review the year-by-year withdrawal plan |
| 5 | 🎲 Monte Carlo | Run a simulation to see probability of plan success |
| 6 | 🎯 Advanced Strategies | Explore BETR Roth conversions and bucket strategy |

---

## 6. Checklist

- [ ] Python 3.9+ installed and `python3 --version` confirmed
- [ ] Virtual environment created and activated
- [ ] `pip install -r requirements.txt` completed without errors
- [ ] `portfolio_data_truth.csv` exists (copy of sample or real data)
- [ ] App launches at http://localhost:8501
- [ ] Configuration page shows and saves without errors
- [ ] Dashboard displays a net-worth chart

### Optional — automatic brokerage sync
- [ ] SnapTrade account created at [snaptrade.com](https://snaptrade.com)
- [ ] API credentials (Client ID, Consumer Key) added to `.env`
- [ ] Encryption key generated and added to `.env`
- [ ] At least one brokerage connected via **Portfolio Hub → Connections**
- [ ] Initial sync completed and holdings visible

---

## 7. Common First-Run Problems

### "ModuleNotFoundError"

```bash
# Make sure the virtual environment is active and re-install
source .venv/bin/activate
pip install -r requirements.txt
```

### "FileNotFoundError: portfolio_data_truth.csv"

```bash
cp portfolio_data_truth.sample.csv portfolio_data_truth.csv
```

### Port already in use

```bash
streamlit run planning_app.py --server.port 8502
```

### Virtual environment not activated (Windows)

```cmd
.venv\Scripts\activate
```

### SnapTrade — "Encryption key not found"

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Copy the output and add to .env as:  ENCRYPTION_KEY=<output>
```

---

## 8. Next Steps

Once the app is running:

- Read the **[Full User Guide](../USER_GUIDE.md)** for a deep-dive on every page and feature
- Learn about the **[Market Trend Indicators](MARKET_TREND_GUIDE.md)** and the 9 regime states
- Understand the **[BETR Roth Conversion algorithm](BETR_GUIDE.md)**
- Explore **[Scenario Planning](SCENARIO_PLANNING_USER_GUIDE.md)** to compare strategies

---

*Made with Bob*
