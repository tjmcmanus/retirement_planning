---
layout: default
title: Home
---

# Financial Planner

A comprehensive retirement and financial planning application with advanced tax optimization, portfolio management, and Monte Carlo simulation capabilities.

## 🚀 Quick Links

- [Getting Started](getting-started.md) - Installation and setup guide
- [Features Overview](features.md) - Complete feature list
- [User Guides](guides.md) - Step-by-step tutorials
- [API Reference](api-reference.md) - Technical documentation
- [User Documentation Folder](user/README.md) - User-facing markdown guides
- [Implementation Documentation Folder](implementation/README.md) - Technical and implementation notes

## ✨ Key Features

### 💼 Portfolio Hub (Redesigned March 2026)
Professional-grade portfolio management with:
- **Brokerage Connections** - Automatic sync via SnapTrade API ⭐ NEW
- Real-time holdings tracking and management
- Performance analytics with risk metrics
- Tax-efficient rebalancing suggestions
- Market indicators and trend analysis

### 🎯 Advanced Tax Optimization
- **BETR Algorithm**: Bracket-Efficient Tax-Aware Roth Conversion
- Mega Backdoor Roth strategies
- Tax-loss harvesting
- Capital gains optimization
- IRMAA threshold management

### 📊 Withdrawal Strategy Engine
6-stage life-cycle strategy with:
- Pre-retirement accumulation
- Early retirement optimization
- Social Security timing
- RMD management
- Estate planning integration

### 🎲 Monte Carlo Simulation
- 10,000+ scenario analysis
- Market volatility modeling
- Success probability calculations
- Risk assessment tools

### 🏥 Healthcare Planning
- Long-Term Care (LTC) cost modeling
- HSA integration and optimization
- Medicare IRMAA planning
- Healthcare expense projections

### 📈 Social Security Optimization
- Claiming strategy analysis
- Spousal benefit coordination
- Tax-efficient timing
- Survivor benefit planning

## 🆕 Recent Updates (March 2026)

### SnapTrade Brokerage Integration ⭐ NEW
Automatic portfolio synchronization with secure brokerage connections:
- **12,000+ Institutions** - Schwab, Fidelity, Vanguard, and more
- **OAuth 2.0 Security** - Bank-level authentication
- **One-Click Sync** - Automatic portfolio updates
- **Encrypted Storage** - AES-256 credential encryption
- **Read-Only Access** - View-only permissions for safety
- **Free Tier Available** - Up to 5 connections at no cost

[Setup Guide](user/SNAPTRADE_QUICKSTART.md) | [Implementation Details](implementation/SNAPTRADE_IMPLEMENTATION_SUMMARY.md)

### Portfolio Hub Redesign
Complete overhaul with professional analytics dashboard featuring:
- **Brokerage Connections Tab** - Automatic sync via SnapTrade ⭐ NEW
- Interactive holdings editor with real-time validation
- Performance metrics (Sharpe ratio, max drawdown, volatility)
- Asset allocation visualization
- Tax-efficient rebalancing recommendations

### Single Person Mode
Streamlined interface for individual planning with:
- Age-based expense adjustments
- Simplified configuration
- Medicare enrollment guidance

### Enhanced Healthcare Planning
- Long-term care cost modeling
- HSA contribution optimization
- Medicare premium calculations
- Healthcare expense forecasting

## 📚 Documentation Sections

### Getting Started
- [Installation Guide](getting-started.md#installation)
- [Quick Start](getting-started.md#quick-start)
- [Configuration](getting-started.md#configuration)
- [Data Files Setup](getting-started.md#data-files)

### User Guides
- [User Documentation Index](user/README.md)
- [Brokerage Connections](guides/brokerage-connections.md)
- [BETR Roth Conversion](advanced/betr-guide.md)

### Technical Reference
- [Implementation Documentation Index](implementation/README.md)
- [API Documentation](api-reference.md)

## 🎯 Use Cases

### Pre-Retirement Planning
- Optimize contribution strategies
- Plan Roth conversions
- Build tax-efficient portfolios
- Project retirement readiness

### Early Retirement
- Calculate safe withdrawal rates
- Optimize healthcare coverage
- Manage tax brackets
- Bridge to Social Security

### Traditional Retirement
- Coordinate Social Security claiming
- Manage RMDs efficiently
- Minimize Medicare premiums
- Optimize estate planning

### High Net Worth
- Advanced Roth strategies
- Tax-loss harvesting
- Charitable giving optimization
- Multi-generational planning

## 🛠️ Technology Stack

- **Frontend**: Streamlit (Python web framework)
- **Data Processing**: Pandas, NumPy
- **Visualization**: Plotly, Matplotlib
- **Financial Data**: yfinance, SnapTrade API ⭐ NEW
- **Security**: Cryptography (Fernet/AES-256) ⭐ NEW
- **Testing**: pytest
- **Configuration**: YAML, JSON

## 📊 Example Scenarios

The application includes several pre-configured scenarios:
- Standard retirement planning
- Early retirement (FIRE)
- High-income optimization
- Custom strategy templates

## ⚠️ Disclaimer

This tool is for educational and planning purposes only. It does not constitute financial, tax, or legal advice. Always consult with qualified professionals before making financial decisions.

## 📞 Support & Contributing

- [GitHub Repository](https://github.com/yourusername/retirement_planning)
- [Issue Tracker](https://github.com/yourusername/retirement_planning/issues)
- [Contributing Guidelines](CONTRIBUTING.md)

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**Version**: March 2026  
**Last Updated**: {{ site.time | date: '%B %d, %Y' }}