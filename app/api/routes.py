"""Dashboard, strategy and configuration endpoints."""
from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.services import advanced, config_schema, config_service, dashboard, estate, jobs, monte_carlo_service, networth, portfolio_hub, reports_service, scenario_service, strategy_service, tax_data

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/config")
def get_config() -> dict[str, Any]:
    return config_service.read_config()


class ConfigUpdate(BaseModel):
    """Partial update: ``{"section": {"key": value}}``. Unlisted keys are untouched."""

    changes: dict[str, dict[str, Any]] = Field(min_length=1)


@router.get("/config/schema")
def get_config_schema() -> dict[str, Any]:
    return config_schema.schema_payload()


@router.put("/config")
def put_config(body: ConfigUpdate) -> dict[str, Any]:
    """Returns ``{"config", "derived", "warnings"}``. Invalid values give 422 with ``detail.errors``."""
    try:
        return config_service.update_config(body.changes)
    except config_service.ValidationError as exc:
        raise HTTPException(status_code=422, detail={"message": "Invalid settings", "errors": exc.errors}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"message": str(exc), "errors": []}) from exc
    except OSError as exc:
        logger.exception("Config save failed")
        raise HTTPException(status_code=500, detail={"message": str(exc), "errors": []}) from exc


@router.post("/config/reset")
def reset_config() -> dict[str, Any]:
    try:
        return config_service.reset_config()
    except OSError as exc:
        logger.exception("Config reset failed")
        raise HTTPException(status_code=500, detail={"message": str(exc), "errors": []}) from exc


@router.get("/config/export")
def export_config() -> Response:
    filename, data = config_service.export_bundle()
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/social-security/preview")
def social_security_preview(amount: float = Query(ge=0, le=10000), age: int = Query(ge=62, le=70)) -> dict[str, Any]:
    return config_service.ss_preview(amount, age)


@router.get("/dashboard/networth")
async def dashboard_networth() -> dict[str, Any]:
    # Blocking pandas/yfinance work: keep it off the event loop.
    return await run_in_threadpool(networth.dashboard_networth)


async def _dashboard_call(label: str, fn, *args) -> dict[str, Any]:
    try:
        return await run_in_threadpool(fn, *args)
    except Exception as exc:
        logger.exception("Dashboard %s failed", label)
        raise HTTPException(status_code=500, detail=f"{label} failed: {exc}") from exc


@router.get("/dashboard/forecast/{timeframe}")
async def dashboard_forecast(timeframe: str) -> dict[str, Any]:
    if timeframe not in dashboard.FORECAST_TIMEFRAMES:
        raise HTTPException(status_code=422, detail=f"timeframe must be one of {list(dashboard.FORECAST_TIMEFRAMES)}")
    return await _dashboard_call("Market forecast", dashboard.market_forecast, timeframe)


@router.get("/dashboard/stress")
async def dashboard_stress() -> dict[str, Any]:
    return await _dashboard_call("Market stress", dashboard.market_stress)


@router.get("/dashboard/statement")
async def dashboard_statement() -> dict[str, Any]:
    return await _dashboard_call("Net worth statement", dashboard.net_worth_statement)


@router.get("/dashboard/account-mix")
async def dashboard_account_mix() -> dict[str, Any]:
    return await _dashboard_call("Account mix", dashboard.account_mix)


@router.get("/dashboard/portfolio-mix")
async def dashboard_portfolio_mix() -> dict[str, Any]:
    return await _dashboard_call("Portfolio mix", dashboard.portfolio_mix)


@router.get("/dashboard/readiness")
async def dashboard_readiness() -> dict[str, Any]:
    return await _dashboard_call("Readiness", dashboard.readiness)


@router.get("/strategy")
async def get_strategy(start_year: int | None = None, end_year: int = 2050) -> dict[str, Any]:
    if start_year is not None and end_year < start_year:
        raise HTTPException(status_code=422, detail="end_year must be >= start_year")
    try:
        return await run_in_threadpool(strategy_service.withdrawal_strategy, start_year, end_year)
    except Exception as exc:
        logger.exception("Strategy calculation failed")
        raise HTTPException(status_code=500, detail=f"Strategy calculation failed: {exc}") from exc


async def _strategy_call(label: str, fn, *args) -> dict[str, Any]:
    try:
        return await run_in_threadpool(fn, *args)
    except Exception as exc:
        logger.exception("Strategy %s failed", label)
        raise HTTPException(status_code=500, detail=f"{label} failed: {exc}") from exc


@router.get("/strategy/timeline")
async def get_strategy_timeline(start_year: int | None = None, end_year: int = 2050) -> dict[str, Any]:
    return await _strategy_call("timeline", strategy_service.timeline_events, start_year, end_year)


@router.get("/strategy/decisions")
async def get_decisions(year: int, start_year: int | None = None, end_year: int = 2050) -> dict[str, Any]:
    try:
        return await run_in_threadpool(strategy_service.decision_log, year, start_year, end_year)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception:
        logger.exception("Strategy decisions failed")
        raise HTTPException(status_code=500, detail="Could not load the strategy decisions")


@router.get("/strategy/money-flow")
async def get_money_flow(year: int, start_year: int | None = None, end_year: int = 2050) -> dict[str, Any]:
    return await _strategy_call("money_flow", strategy_service.money_flow, year, start_year, end_year)


@router.get("/strategy/monthly-plan")
async def get_monthly_plan(year: int, start_year: int | None = None, end_year: int = 2050) -> dict[str, Any]:
    return await _strategy_call("monthly_plan", strategy_service.monthly_plan, year, start_year, end_year)


@router.get("/strategy/buckets")
async def get_buckets() -> dict[str, Any]:
    return await _strategy_call("buckets", strategy_service.bucket_analysis)


@router.get("/strategy/tax-analytics")
async def get_tax_analytics(start_year: int | None = None, end_year: int = 2050) -> dict[str, Any]:
    return await _strategy_call("tax_analytics", strategy_service.tax_analytics, start_year, end_year)


@router.get("/strategy/income-expense")
async def get_income_expense(start_year: int | None = None, end_year: int = 2050) -> dict[str, Any]:
    return await _strategy_call("income_expense", strategy_service.income_expense, start_year, end_year)


# ---------------------------------------------------------------------------
# Portfolio Hub
# ---------------------------------------------------------------------------

MonthQ = Query(ge=1, le=12)
YearQ = Query(ge=2000, le=2100)


class HoldingsBody(BaseModel):
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)
    rows: list[dict[str, Any]] = Field(max_length=5000)


class PeriodBody(BaseModel):
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)


class CsvBody(PeriodBody):
    csv: str = Field(max_length=2_000_000)


async def _portfolio_call(label: str, fn, *args) -> dict[str, Any]:
    try:
        return await run_in_threadpool(fn, *args)
    except HTTPException:
        raise
    except portfolio_hub.HoldingsValidationError as exc:
        raise HTTPException(status_code=422, detail={"message": exc.message, "errors": exc.errors}) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Portfolio %s failed", label)
        raise HTTPException(status_code=500, detail=f"{label} failed: {exc}") from exc


@router.get("/portfolio/meta")
async def portfolio_meta() -> dict[str, Any]:
    return await _portfolio_call("Portfolio periods", portfolio_hub.meta)


@router.get("/portfolio/overview")
async def portfolio_overview() -> dict[str, Any]:
    return await _portfolio_call("Portfolio overview", portfolio_hub.overview)


@router.get("/portfolio/treemap")
async def portfolio_treemap() -> dict[str, Any]:
    return await _portfolio_call("Portfolio treemap", portfolio_hub.treemap)


@router.get("/portfolio/holdings")
async def portfolio_holdings(month: int = MonthQ, year: int = YearQ) -> dict[str, Any]:
    return await _portfolio_call("Holdings", portfolio_hub.list_holdings, month, year)


@router.put("/portfolio/holdings")
async def portfolio_save_holdings(body: HoldingsBody) -> dict[str, Any]:
    """Replace the month with exactly these rows. 422 with ``detail.errors`` (per row) writes nothing."""
    return await _portfolio_call("Save holdings", portfolio_hub.save_holdings, body.rows, body.month, body.year)


@router.post("/portfolio/holdings/validate")
async def portfolio_validate_holdings(body: HoldingsBody) -> dict[str, Any]:
    return await _portfolio_call("Validate holdings", portfolio_hub.validate, body.rows, body.month, body.year)


@router.post("/portfolio/holdings/copy-previous")
async def portfolio_copy_previous(body: PeriodBody) -> dict[str, Any]:
    return await _portfolio_call("Copy previous month", portfolio_hub.copy_previous, body.month, body.year)


@router.post("/portfolio/holdings/import")
async def portfolio_import_csv(body: CsvBody) -> dict[str, Any]:
    return await _portfolio_call("CSV import", portfolio_hub.import_csv, body.csv, body.month, body.year)


@router.post("/portfolio/holdings/backup")
async def portfolio_backup() -> dict[str, Any]:
    return await _portfolio_call("Backup", portfolio_hub.backup_all)


@router.post("/portfolio/holdings/enrich")
async def portfolio_enrich(body: PeriodBody) -> dict[str, Any]:
    return await _portfolio_call("Enrich names and sectors", portfolio_hub.enrich, body.month, body.year)


@router.get("/portfolio/holdings/indicators")
async def portfolio_indicators(month: int = MonthQ, year: int = YearQ) -> dict[str, Any]:
    return await _portfolio_call("Market indicators", portfolio_hub.indicators, month, year)


@router.get("/portfolio/lookup")
async def portfolio_lookup(symbol: str = Query(min_length=1, max_length=40)) -> dict[str, Any]:
    return await _portfolio_call("Ticker lookup", portfolio_hub.lookup, symbol)


# ---------------------------------------------------------------------------
# Rebalancing
# ---------------------------------------------------------------------------

class RebalanceBody(BaseModel):
    cash_pct: float = Field(ge=0, le=100)
    bonds_pct: float = Field(ge=0, le=100)
    stocks_pct: float = Field(ge=0, le=100)
    drift_threshold_pct: float = Field(ge=1, le=20, default=5.0)
    save_targets: bool = False


@router.get("/portfolio/rebalancing/defaults")
async def rebalancing_defaults() -> dict[str, Any]:
    """Return saved target allocation and smart bucket-strategy defaults."""
    return await _portfolio_call("Rebalancing defaults", portfolio_hub.rebalancing_defaults)


@router.post("/portfolio/rebalancing/calculate")
async def rebalancing_calculate(body: RebalanceBody) -> dict[str, Any]:
    """Calculate a rebalancing plan for the given targets. Pass save_targets=true to persist."""
    total = body.cash_pct + body.bonds_pct + body.stocks_pct
    if abs(total - 100.0) > 0.01:
        raise HTTPException(status_code=422, detail=f"cash_pct + bonds_pct + stocks_pct must equal 100; got {total:.2f}")
    return await _portfolio_call(
        "Rebalancing calculate",
        portfolio_hub.rebalance,
        body.cash_pct, body.bonds_pct, body.stocks_pct,
        body.drift_threshold_pct, body.save_targets,
    )


# ---------------------------------------------------------------------------
# Optimize (Tax Harvesting + Direct Indexing)
# ---------------------------------------------------------------------------

class OptimizeBody(BaseModel):
    agi: float = Field(ge=0, le=2_000_000, default=80_000)
    marginal_rate_pct: float = Field(ge=0, le=50, default=22)
    loss_threshold: float = Field(ge=0, le=100_000, default=500)
    gain_threshold: float = Field(ge=0, le=100_000, default=500)
    drop_trigger_pct: float = Field(ge=1, le=50, default=10)


@router.post("/portfolio/optimize")
async def portfolio_optimize(body: OptimizeBody) -> dict[str, Any]:
    """Scan brokerage holdings for tax-loss/gain harvest opportunities."""
    return await _portfolio_call(
        "Optimize",
        portfolio_hub.optimize,
        body.agi, body.marginal_rate_pct,
        body.loss_threshold, body.gain_threshold,
        body.drop_trigger_pct,
    )


# ---------------------------------------------------------------------------
# Performance & Analytics
# ---------------------------------------------------------------------------

VALID_PERIODS = {"1y", "3y", "5y", "all"}


@router.get("/portfolio/performance")
async def portfolio_performance(
    period: str = Query(default="all", pattern="^(1y|3y|5y|all)$"),
    benchmark: str = Query(default="^GSPC", min_length=1, max_length=20),
) -> dict[str, Any]:
    """Calculate performance metrics (TWR, MWR, Sharpe, Sortino, drawdown, alpha/beta)."""
    return await _portfolio_call("Performance", portfolio_hub.performance, period, benchmark)


# ---------------------------------------------------------------------------
# Factor Analysis & DAF Bundling
# ---------------------------------------------------------------------------

@router.get("/portfolio/factors")
async def portfolio_factors() -> dict[str, Any]:
    """Portfolio factor exposure: Value / Growth / Momentum / Quality scores (slow — fetches Yahoo Finance)."""
    return await _portfolio_call("Factor analysis", portfolio_hub.factor_analysis)


class DAFBody(BaseModel):
    agi: float = Field(ge=0, le=2_000_000, default=150_000)
    annual_giving: float = Field(ge=0, le=500_000, default=5_000)
    years_to_bundle: int = Field(ge=1, le=5, default=3)
    marginal_rate_pct: float = Field(ge=0, le=50, default=22)
    standard_deduction: float = Field(ge=0, le=100_000, default=29_200)


@router.post("/portfolio/daf")
async def portfolio_daf(body: DAFBody) -> dict[str, Any]:
    """DAF bundling analysis: appreciated securities to donate + estimated tax savings."""
    return await _portfolio_call(
        "DAF bundling",
        portfolio_hub.daf_bundling,
        body.agi, body.annual_giving, body.years_to_bundle,
        body.marginal_rate_pct, body.standard_deduction,
    )


# ---------------------------------------------------------------------------
# Connections (SnapTrade)
# ---------------------------------------------------------------------------

@router.get("/portfolio/connections/status")
async def connections_status() -> dict[str, Any]:
    """Check SnapTrade credentials & return connected accounts.
    Returns 503 if env vars are not configured, 502 if SnapTrade API is unreachable."""
    try:
        return await run_in_threadpool(portfolio_hub.connections_status)
    except (ImportError, ValueError, TypeError) as exc:
        # Missing package, missing env vars, or SDK version mismatch — show setup panel
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Connections status failed")
        raise HTTPException(status_code=502, detail=f"SnapTrade error: {exc}") from exc


class AuthLinkBody(BaseModel):
    redirect_uri: str | None = None


@router.post("/portfolio/connections/auth")
async def connections_auth(body: AuthLinkBody = AuthLinkBody()) -> dict[str, Any]:
    """Generate a SnapTrade OAuth link for the user to open in their browser."""
    try:
        return await run_in_threadpool(portfolio_hub.connections_auth_link, body.redirect_uri)
    except (ImportError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Auth link failed")
        raise HTTPException(status_code=502, detail=f"SnapTrade error: {exc}") from exc


@router.post("/portfolio/connections/sync")
async def connections_sync(body: PeriodBody) -> dict[str, Any]:
    """Sync all brokerage holdings into portfolio.db for month/year."""
    try:
        return await run_in_threadpool(portfolio_hub.connections_sync, body.month, body.year)
    except (ImportError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Connections sync failed")
        raise HTTPException(status_code=502, detail=f"Sync error: {exc}") from exc


@router.delete("/portfolio/connections")
async def connections_disconnect() -> dict[str, Any]:
    """Disconnect SnapTrade (revoke + delete user). Irreversible — will require re-auth."""
    try:
        return await run_in_threadpool(portfolio_hub.connections_disconnect)
    except (ImportError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Connections disconnect failed")
        raise HTTPException(status_code=502, detail=f"Disconnect error: {exc}") from exc


# ---------------------------------------------------------------------------
# Transactions (Tax Records)
# ---------------------------------------------------------------------------

@router.get("/portfolio/transactions")
async def transactions_list(
    account: str | None = None,
    symbol: str | None = None,
    types: list[str] | None = Query(default=None),
    start: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    limit: int = Query(default=2000, ge=1, le=20000),
) -> dict[str, Any]:
    """Brokerage transactions stored by the Connections syncs (newest first)."""
    try:
        return await run_in_threadpool(portfolio_hub.transactions_list, account, symbol, types, start, end, limit)
    except Exception as exc:
        logger.exception("Transactions list failed")
        raise HTTPException(status_code=500, detail=f"Transactions error: {exc}") from exc


@router.get("/portfolio/cost-basis")
async def cost_basis(
    method: str = Query(default="FIFO", pattern="^(?i:FIFO|LIFO|HIFO|LOFO)$"),
    account: str | None = None,
    symbol: str | None = None,
) -> dict[str, Any]:
    """Open tax lots rebuilt from stored trades."""
    try:
        return await run_in_threadpool(portfolio_hub.cost_basis_lots, method, account, symbol)
    except Exception as exc:
        logger.exception("Cost basis failed")
        raise HTTPException(status_code=500, detail=f"Cost basis error: {exc}") from exc


@router.get("/portfolio/capital-gains")
async def capital_gains(
    method: str = Query(default="FIFO", pattern="^(?i:FIFO|LIFO|HIFO|LOFO)$"),
    year: int | None = Query(default=None, ge=1990, le=2100),
    taxable_only: bool = True,
) -> dict[str, Any]:
    """Realized gains by tax year, matched to lots."""
    try:
        return await run_in_threadpool(portfolio_hub.capital_gains, method, year, taxable_only)
    except Exception as exc:
        logger.exception("Capital gains failed")
        raise HTTPException(status_code=500, detail=f"Capital gains error: {exc}") from exc


# ---------------------------------------------------------------------------
# Connections (Schwab Direct API)
# ---------------------------------------------------------------------------

class SchwabCallbackBody(BaseModel):
    callback_url: str


@router.get("/portfolio/connections/schwab/status")
async def schwab_status() -> dict[str, Any]:
    """Schwab Direct status; ``configured: false`` when credentials are missing."""
    try:
        return await run_in_threadpool(portfolio_hub.schwab_status)
    except Exception as exc:
        logger.exception("Schwab status failed")
        raise HTTPException(status_code=502, detail=f"Schwab error: {exc}") from exc


@router.post("/portfolio/connections/schwab/auth")
async def schwab_auth() -> dict[str, Any]:
    """Generate the Schwab OAuth authorization URL."""
    try:
        return await run_in_threadpool(portfolio_hub.schwab_auth_url)
    except (ImportError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Schwab auth failed")
        raise HTTPException(status_code=502, detail=f"Schwab error: {exc}") from exc


@router.post("/portfolio/connections/schwab/complete")
async def schwab_complete(body: SchwabCallbackBody) -> dict[str, Any]:
    """Exchange the pasted callback URL for tokens."""
    try:
        return await run_in_threadpool(portfolio_hub.schwab_complete, body.callback_url)
    except (ImportError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Schwab authorization failed")
        raise HTTPException(status_code=502, detail=f"Schwab error: {exc}") from exc


@router.post("/portfolio/connections/schwab/sync")
async def schwab_sync(body: PeriodBody) -> dict[str, Any]:
    """Sync Schwab positions into portfolio.db for month/year."""
    try:
        return await run_in_threadpool(portfolio_hub.schwab_sync, body.month, body.year)
    except (ImportError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Schwab sync failed")
        raise HTTPException(status_code=502, detail=f"Sync error: {exc}") from exc


@router.delete("/portfolio/connections/schwab")
async def schwab_disconnect() -> dict[str, Any]:
    """Clear Schwab tokens and deactivate the stored connection."""
    try:
        return await run_in_threadpool(portfolio_hub.schwab_disconnect)
    except (ImportError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Schwab disconnect failed")
        raise HTTPException(status_code=502, detail=f"Disconnect error: {exc}") from exc


# ---------------------------------------------------------------------------
# Harvest Savings (Direct Indexing)
# ---------------------------------------------------------------------------

@router.get("/portfolio/harvest-savings")
async def harvest_savings(year: int = Query(default=0, ge=0, le=2100)) -> dict[str, Any]:
    """YTD direct-index harvest savings tracker for the given year (default: current year)."""
    import datetime as _dt
    if year == 0:
        year = _dt.date.today().year
    try:
        return await run_in_threadpool(portfolio_hub.harvest_savings, year)
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Harvest savings failed")
        raise HTTPException(status_code=500, detail=f"Harvest savings error: {exc}") from exc


# ---------------------------------------------------------------------------
# Direct Indexing YAML config
# ---------------------------------------------------------------------------

@router.get("/di/config")
async def di_config_get() -> dict[str, Any]:
    """Read direct_indexing_config.yaml."""
    try:
        return await run_in_threadpool(portfolio_hub.di_config_read)
    except Exception as exc:
        logger.exception("DI config read failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class DIConfigBody(BaseModel):
    """Partial update — only the sections provided are updated."""
    changes: dict[str, Any] = Field(min_length=1)


@router.put("/di/config")
async def di_config_put(body: DIConfigBody) -> dict[str, Any]:
    """Deep-merge *changes* into direct_indexing_config.yaml and return the saved config."""
    try:
        return await run_in_threadpool(portfolio_hub.di_config_write, body.changes)
    except Exception as exc:
        logger.exception("DI config write failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Tax data administration (IRS lookup tables)
# ---------------------------------------------------------------------------

class TaxRowsBody(BaseModel):
    year: int | None = Field(default=None, ge=2000, le=2100)
    rows: list[dict[str, Any]] = Field(max_length=5000)


class TaxCsvBody(BaseModel):
    csv: str = Field(max_length=2_000_000)


async def _tax_call(label: str, fn, *args) -> Any:
    try:
        return await run_in_threadpool(fn, *args)
    except tax_data.TableValidationError as exc:
        raise HTTPException(status_code=422, detail={"message": exc.message, "errors": exc.errors}) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"message": str(exc), "errors": []}) from exc
    except Exception as exc:
        logger.exception("Tax data %s failed", label)
        raise HTTPException(status_code=500, detail=f"{label} failed: {exc}") from exc


@router.get("/tax-data")
async def tax_data_list() -> list[dict[str, Any]]:
    return await _tax_call("Tax table list", tax_data.list_tables)


@router.get("/tax-data/{key}")
async def tax_data_get(key: str, year: int | None = Query(default=None, ge=2000, le=2100)) -> dict[str, Any]:
    return await _tax_call("Tax table", tax_data.get_table, key, year)


@router.put("/tax-data/{key}")
async def tax_data_save(key: str, body: TaxRowsBody) -> dict[str, Any]:
    """Replace one year's rows (the whole table when it has no year column). 422 with per-cell errors writes nothing."""
    return await _tax_call("Save tax table", tax_data.save_rows, key, body.year, body.rows)


@router.get("/tax-data/{key}/download")
async def tax_data_download(key: str) -> Response:
    filename, data = await _tax_call("Tax table download", tax_data.download, key)
    return Response(data, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/tax-data/{key}/validate-upload")
async def tax_data_validate_upload(key: str, body: TaxCsvBody) -> dict[str, Any]:
    return await _tax_call("Upload validation", tax_data.validate_upload, key, body.csv)


@router.put("/tax-data/{key}/upload")
async def tax_data_upload(key: str, body: TaxCsvBody) -> dict[str, Any]:
    """Replace the whole file with a validated CSV (the previous file is backed up)."""
    return await _tax_call("Tax table upload", tax_data.replace_table, key, body.csv)


# ---------------------------------------------------------------------------
# Advanced Strategy Tools (calculators)
# ---------------------------------------------------------------------------

Filing = Literal["married_filing_jointly", "single"]
_Money = Field(default=0, ge=0, le=1e10)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaxPlannerBody(_Strict):
    wages: float = Field(default=0, ge=-1e10, le=1e10)
    trad_dist: float = Field(default=0, ge=-1e10, le=1e10)
    interest: float = Field(default=0, ge=-1e10, le=1e10)
    ltcg: float = Field(default=0, ge=-1e10, le=1e10)
    stcg: float = Field(default=0, ge=-1e10, le=1e10)
    medicare: Literal[0, 1, 2] = 0
    year: int = Field(ge=2000, le=2100)
    maxdaf: Literal["N", "Y"] = "N"
    charitable: float = Field(default=0, ge=-1e10, le=1e10)
    headroom_pct: Literal[10, 12, 22, 24, 32, 35, 37] = 24
    daf_type: Literal["securities", "cash"] = "securities"
    roth_amount: float = Field(default=0, ge=-1e10, le=1e10)
    prepaid: float = Field(default=0, ge=-1e10, le=1e10)


class MultiYearBody(_Strict):
    start_year: int = Field(ge=2000, le=2100)
    filing_status: Filing = "married_filing_jointly"
    income: float = _Money
    cg_lt: float = _Money
    conversion: float = _Money
    qbi: float = _Money
    loss_cf: float = _Money
    window: int = Field(default=5, ge=3, le=10)


class QbiBody(_Strict):
    qbi_income: float = _Money
    total_taxable_income: float = _Money
    filing_status: Filing = "married_filing_jointly"
    w2_wages: float = _Money
    ubia: float = _Money
    is_sstb: bool = False


class BackdoorBody(_Strict):
    year: int = Field(ge=2000, le=2100)
    age: int = Field(default=45, ge=18, le=80)
    magi: float = _Money
    trad_balance: float = _Money
    basis: float = _Money
    filing_status: Filing = "married_filing_jointly"


class BetrBody(_Strict):
    conversion_amount: float = Field(default=50_000, ge=1_000, le=1e10)
    trad_balance: float = Field(default=500_000, ge=1_000, le=1e10)
    basis: float = _Money
    current_rate: float = Field(default=0.24, ge=0.10, le=0.37)
    future_rate: float = Field(default=0.22, ge=0.10, le=0.37)
    annual_return: float = Field(default=0.07, ge=0.02, le=0.12)
    years: int = Field(default=20, ge=1, le=40)
    pay_from_taxable: bool = True
    taxable_balance: float = _Money


class MegaBackdoorBody(_Strict):
    year: int = Field(ge=2000, le=2100)
    age: int = Field(default=45, ge=18, le=80)
    employee_deferral: float = _Money
    employer_match: float = _Money
    plan_allows_after_tax: bool = True
    plan_allows_in_plan_conversion: bool = True


class NuaBody(_Strict):
    cost_basis: float = _Money
    current_value: float = _Money
    ordinary_rate: float = Field(default=0.24, ge=0.10, le=0.37)
    ltcg_rate: float = Field(default=0.15, ge=0, le=0.20)
    years: int = Field(default=5, ge=0, le=30)


class QcdBody(_Strict):
    year: int = Field(ge=2000, le=2100)
    age: int = Field(default=73, ge=70, le=100)
    ira_balance: float = _Money
    rmd: float = _Money
    agi: float = _Money
    charitable: float = _Money
    marginal_rate: float = Field(default=0.22, ge=0.10, le=0.37)
    filing_status: Filing = "married_filing_jointly"


class SeppBody(_Strict):
    balance: float = Field(default=500_000, ge=1_000, le=1e10)
    age: int = Field(default=50, ge=18, le=58)
    rate: float = Field(default=0.05, ge=0.005, le=0.10)
    method: str = "Fixed Amortization"
    marginal_rate: float = Field(default=0.22, ge=0.10, le=0.37)


class HarvestBody(_Strict):
    start_year: int = Field(ge=2000, le=2100)
    window: int = Field(default=5, ge=1, le=10)
    filing_status: Filing = "married_filing_jointly"
    income: float = _Money
    unrealized_losses: float = _Money


async def _advanced_call(label: str, fn, *args, **kwargs) -> dict[str, Any]:
    try:
        return await run_in_threadpool(lambda: fn(*args, **kwargs))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Advanced %s failed", label)
        raise HTTPException(status_code=500, detail=f"{label} failed: {exc}") from exc


@router.get("/advanced/meta")
async def advanced_meta() -> dict[str, Any]:
    return await _advanced_call("Advanced meta", advanced.meta)


@router.post("/advanced/tax-planner")
async def advanced_tax_planner(body: TaxPlannerBody) -> dict[str, Any]:
    return await _advanced_call("Tax planner", advanced.tax_planner, **body.model_dump())


@router.post("/advanced/multi-year")
async def advanced_multi_year(body: MultiYearBody) -> dict[str, Any]:
    return await _advanced_call("Multi-year projection", advanced.multi_year, **body.model_dump())


@router.post("/advanced/qbi")
async def advanced_qbi(body: QbiBody) -> dict[str, Any]:
    return await _advanced_call("QBI deduction", advanced.qbi, **body.model_dump())


@router.post("/advanced/backdoor")
async def advanced_backdoor(body: BackdoorBody) -> dict[str, Any]:
    return await _advanced_call("Backdoor Roth", advanced.backdoor, **body.model_dump())


@router.post("/advanced/betr")
async def advanced_betr(body: BetrBody) -> dict[str, Any]:
    return await _advanced_call("BETR", advanced.betr, **body.model_dump())


@router.post("/advanced/mega-backdoor")
async def advanced_mega_backdoor(body: MegaBackdoorBody) -> dict[str, Any]:
    return await _advanced_call("Mega backdoor Roth", advanced.mega_backdoor, **body.model_dump())


@router.post("/advanced/nua")
async def advanced_nua(body: NuaBody) -> dict[str, Any]:
    return await _advanced_call("NUA analysis", advanced.nua, **body.model_dump())


@router.post("/advanced/qcd")
async def advanced_qcd(body: QcdBody) -> dict[str, Any]:
    return await _advanced_call("QCD optimization", advanced.qcd, **body.model_dump())


@router.post("/advanced/sepp")
async def advanced_sepp(body: SeppBody) -> dict[str, Any]:
    return await _advanced_call("SEPP", advanced.sepp, **body.model_dump())


@router.post("/advanced/harvest")
async def advanced_harvest(body: HarvestBody) -> dict[str, Any]:
    return await _advanced_call("Loss harvesting", advanced.harvest, **body.model_dump())


# ---------------------------------------------------------------------------
# Background Jobs
# ---------------------------------------------------------------------------

@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str) -> dict[str, Any]:
    """Poll status of a background job."""
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job


# ---------------------------------------------------------------------------
# Monte Carlo Simulation Endpoints
# ---------------------------------------------------------------------------

class MonteCarloInputsBody(BaseModel):
    portfolio: float = Field(ge=10_000, default=1_500_000)
    withdrawal: float = Field(ge=1_000, default=80_000)
    start_age: int = Field(ge=40, le=80, default=62)
    end_age: int = Field(ge=70, le=110, default=90)
    ss_annual: float = Field(ge=0, default=40_000)
    ss_start_age: int = Field(ge=62, le=70, default=70)
    inflation_pct: float = Field(ge=0.5, le=20.0, default=2.9)
    allocation: str = Field(default="Moderate (70/30)")
    n_simulations: int = Field(ge=100, le=50_000, default=10_000)
    random_seed: int = Field(default=42)


class StressTestsBody(BaseModel):
    inputs: MonteCarloInputsBody
    scenarios: list[str] = Field(default_factory=list)


class LongevityBody(BaseModel):
    inputs: MonteCarloInputsBody
    scenarios: list[str] = Field(default_factory=list)


class HeatmapBody(BaseModel):
    inputs: MonteCarloInputsBody
    base_withdrawal: float = Field(ge=1_000, default=80_000)
    n_sims: int = Field(ge=100, le=5_000, default=1_000)


class ComparisonBody(BaseModel):
    inputs: MonteCarloInputsBody
    stress_scenarios: list[str] = Field(default_factory=list)
    longevity_scenarios: list[str] = Field(default_factory=list)


class ExportCsvBody(BaseModel):
    inputs: MonteCarloInputsBody
    include_stress: bool = True
    include_longevity: bool = True


@router.get("/monte-carlo/meta")
async def monte_carlo_meta() -> dict[str, Any]:
    """Return preset allocations and stress/longevity scenario names."""
    return monte_carlo_service.get_monte_carlo_meta()


@router.get("/monte-carlo/defaults")
async def monte_carlo_defaults() -> dict[str, Any]:
    """Derive starting default inputs from config and portfolio net worth."""
    return await run_in_threadpool(monte_carlo_service.get_monte_carlo_defaults)


@router.post("/monte-carlo/run")
async def monte_carlo_run(body: MonteCarloInputsBody) -> dict[str, str]:
    """Submit background Monte Carlo simulation."""
    inputs_dict = body.model_dump()
    if body.end_age <= body.start_age:
        raise HTTPException(status_code=422, detail="Plan to age must be greater than retirement age")

    job_id = jobs.submit_job(
        "monte_carlo_simulation",
        lambda progress_cb: monte_carlo_service.run_simulation_job(inputs_dict, progress_cb),
    )
    return {"job_id": job_id, "status": "pending"}


@router.post("/monte-carlo/stress-tests")
async def monte_carlo_stress_tests(body: StressTestsBody) -> dict[str, str]:
    """Submit background stress testing job."""
    inputs_dict = body.inputs.model_dump()
    job_id = jobs.submit_job(
        "monte_carlo_stress_tests",
        lambda progress_cb: monte_carlo_service.run_stress_tests_job(inputs_dict, body.scenarios, progress_cb),
    )
    return {"job_id": job_id, "status": "pending"}


@router.post("/monte-carlo/longevity")
async def monte_carlo_longevity(body: LongevityBody) -> dict[str, str]:
    """Submit background longevity analysis job."""
    inputs_dict = body.inputs.model_dump()
    job_id = jobs.submit_job(
        "monte_carlo_longevity",
        lambda progress_cb: monte_carlo_service.run_longevity_job(inputs_dict, body.scenarios, progress_cb),
    )
    return {"job_id": job_id, "status": "pending"}


@router.post("/monte-carlo/heatmap")
async def monte_carlo_heatmap(body: HeatmapBody) -> dict[str, str]:
    """Submit background success heatmap job."""
    inputs_dict = body.inputs.model_dump()
    job_id = jobs.submit_job(
        "monte_carlo_heatmap",
        lambda progress_cb: monte_carlo_service.run_heatmap_job(
            inputs_dict, body.base_withdrawal, body.n_sims, progress_cb
        ),
    )
    return {"job_id": job_id, "status": "pending"}


@router.post("/monte-carlo/comparison")
async def monte_carlo_comparison(body: ComparisonBody) -> dict[str, str]:
    """Submit background full scenario comparison job."""
    inputs_dict = body.inputs.model_dump()
    job_id = jobs.submit_job(
        "monte_carlo_comparison",
        lambda progress_cb: monte_carlo_service.run_comparison_job(
            inputs_dict, body.stress_scenarios, body.longevity_scenarios, progress_cb
        ),
    )
    return {"job_id": job_id, "status": "pending"}


@router.post("/monte-carlo/export-csv")
async def monte_carlo_export_csv(body: ExportCsvBody) -> Response:
    """Export Monte Carlo CSV report."""
    inputs_dict = body.inputs.model_dump()
    try:
        import datetime as _dt
        csv_bytes = await run_in_threadpool(
            monte_carlo_service.export_report_csv,
            inputs_dict,
            body.include_stress,
            body.include_longevity,
        )
        filename = f"monte_carlo_report_{_dt.datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        return Response(
            csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        logger.exception("Monte Carlo export CSV failed")
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Estate Planning Endpoints
# ---------------------------------------------------------------------------

class EstateUpdateBody(BaseModel):
    patch: dict[str, Any] = Field(min_length=1)


class EstateTaxBody(BaseModel):
    year: int = Field(ge=2020, le=2050, default=2026)
    estate_value: float = Field(ge=0, default=10_000_000)
    prior_taxable_gifts: float = Field(ge=0, default=0)
    marital_status: str = Field(default="married")
    state: str = Field(default="None")
    surviving_spouse: bool = Field(default=False)
    deceased_spousal_unused_exemption: float = Field(ge=0, default=0)
    gift_recipients: int = Field(ge=1, le=20, default=2)
    gift_years: int = Field(ge=1, le=40, default=10)
    estate_growth_rate: float = Field(ge=0, le=0.20, default=0.05)


class BeneficiaryCalcBody(BaseModel):
    strategy_type: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class CharitableCalcBody(BaseModel):
    tool_type: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


@router.get("/estate")
async def get_estate() -> dict[str, Any]:
    """Retrieve full estate data, metadata, recommendations, and progress summary."""
    return await run_in_threadpool(estate.get_estate_overview)


@router.put("/estate/{section}")
async def put_estate_section(section: str, body: EstateUpdateBody) -> dict[str, Any]:
    """Partially update an estate planning section and persist changes."""
    valid_sections = {"assessment", "legal", "financial", "property", "document_locations", "review_schedule"}
    if section not in valid_sections:
        raise HTTPException(status_code=422, detail=f"Invalid estate section: '{section}'")
    return await run_in_threadpool(estate.update_estate_section, section, body.patch)


@router.post("/estate/calculate-tax")
async def post_estate_calculate_tax(body: EstateTaxBody) -> dict[str, Any]:
    """Calculate comprehensive estate tax, TCJA comparison, and gifting impact."""
    return await run_in_threadpool(estate.calculate_estate_tax, body.model_dump())


@router.post("/estate/calculate-beneficiary")
async def post_estate_calculate_beneficiary(body: BeneficiaryCalcBody) -> dict[str, Any]:
    """Calculate inherited IRA and beneficiary strategies."""
    try:
        return await run_in_threadpool(estate.calculate_beneficiary, body.strategy_type, body.params)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/estate/calculate-charitable")
async def post_estate_calculate_charitable(body: CharitableCalcBody) -> dict[str, Any]:
    """Calculate charitable giving trusts (CRT/CLT), foundation vs DAF, and QCD."""
    try:
        return await run_in_threadpool(estate.calculate_charitable, body.tool_type, body.params)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Scenario Planning Endpoints
# ---------------------------------------------------------------------------

class ScenarioCreateBody(BaseModel):
    name: str = Field(min_length=1, default="New Scenario")
    description: str = Field(default="")
    financial: dict[str, Any] = Field(default_factory=dict)
    personal: dict[str, Any] = Field(default_factory=dict)
    income_sources: dict[str, Any] = Field(default_factory=dict)
    life_events: list[dict[str, Any]] = Field(default_factory=list)
    tax_strategy: dict[str, Any] = Field(default_factory=dict)


class ScenarioUpdateBody(BaseModel):
    name: str | None = None
    description: str | None = None
    initial_portfolio: float | None = None
    annual_expenses: float | None = None
    inflation_rate: float | None = None
    retirement_age: int | None = None
    plan_to_age: int | None = None
    financial: dict[str, Any] | None = None
    personal: dict[str, Any] | None = None
    income_sources: dict[str, Any] | None = None
    social_security: dict[str, Any] | None = None
    life_events: list[dict[str, Any]] | None = None


class LifeEventBody(BaseModel):
    name: str = Field(min_length=1)
    event_type: str = Field(default="custom")
    start_age: int = Field(ge=18, le=120)
    end_age: int | None = None
    income_change: float = Field(default=0.0)
    expense_change: float = Field(default=0.0)
    one_time_amount: float = Field(default=0.0)
    notes: str = Field(default="")
    color: str = Field(default="#3B82F6")


class ScenarioAnalyzeBody(BaseModel):
    n_simulations: int = Field(default=5000, ge=100, le=50000)


@router.get("/scenarios")
async def get_scenarios() -> list[dict[str, Any]]:
    """List all available retirement planning scenarios."""
    return await run_in_threadpool(scenario_service.list_scenarios)


@router.post("/scenarios")
async def post_create_scenario(body: ScenarioCreateBody) -> dict[str, Any]:
    """Create a new scenario."""
    return await run_in_threadpool(scenario_service.create_scenario, body.model_dump())


@router.get("/scenarios/templates")
async def get_scenario_templates() -> list[dict[str, Any]]:
    """Get list of pre-defined life event templates."""
    return await run_in_threadpool(scenario_service.get_templates)


@router.get("/scenarios/{scenario_id}")
async def get_scenario_by_id(scenario_id: str) -> dict[str, Any]:
    """Get full scenario details by ID."""
    sc = await run_in_threadpool(scenario_service.get_scenario, scenario_id)
    if not sc:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    return sc


@router.put("/scenarios/{scenario_id}")
async def put_update_scenario(scenario_id: str, body: ScenarioUpdateBody) -> dict[str, Any]:
    """Update scenario parameters."""
    updated = await run_in_threadpool(
        scenario_service.update_scenario,
        scenario_id,
        body.model_dump(exclude_unset=True),
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    return updated


@router.delete("/scenarios/{scenario_id}")
async def delete_scenario_by_id(scenario_id: str) -> dict[str, Any]:
    """Delete a scenario."""
    success = await run_in_threadpool(scenario_service.delete_scenario, scenario_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot delete baseline or missing scenario")
    return {"status": "deleted", "scenario_id": scenario_id}


@router.post("/scenarios/{scenario_id}/clone")
async def post_clone_scenario(scenario_id: str) -> dict[str, Any]:
    """Clone an existing scenario."""
    cloned = await run_in_threadpool(scenario_service.clone_scenario, scenario_id)
    if not cloned:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    return cloned


@router.post("/scenarios/{scenario_id}/events")
async def post_scenario_event(scenario_id: str, body: LifeEventBody) -> dict[str, Any]:
    """Add a life event to a scenario."""
    updated = await run_in_threadpool(scenario_service.add_life_event, scenario_id, body.model_dump())
    if not updated:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    return updated


@router.delete("/scenarios/{scenario_id}/events/{event_id}")
async def delete_scenario_event(scenario_id: str, event_id: str) -> dict[str, Any]:
    """Delete a life event from a scenario."""
    updated = await run_in_threadpool(scenario_service.delete_life_event, scenario_id, event_id)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    return updated


@router.post("/scenarios/{scenario_id}/analyze")
async def post_scenario_analyze(scenario_id: str, body: ScenarioAnalyzeBody) -> dict[str, Any]:
    """Run Monte Carlo simulation and timeline calculations for a scenario."""
    res = await run_in_threadpool(scenario_service.analyze_scenario, scenario_id, body.n_simulations)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Analysis failed"))
    return res


# ---------------------------------------------------------------------------
# Reports & PDF Export Endpoints
# ---------------------------------------------------------------------------

class ReportGenerateBody(BaseModel):
    template_id: str = Field(default="comprehensive_retirement_plan")
    title: str | None = None
    prepared_for: str | None = None
    filename: str | None = None
    sections: dict[str, bool] = Field(default_factory=dict)


@router.get("/reports/templates")
async def get_report_templates() -> list[dict[str, Any]]:
    """List available report templates."""
    return await run_in_threadpool(reports_service.list_templates)


@router.get("/reports/templates/{template_id}")
async def get_report_template_by_id(template_id: str) -> dict[str, Any]:
    """Get report template details and section structure."""
    tpl = await run_in_threadpool(reports_service.get_template_details, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    return tpl


@router.post("/reports/generate")
async def post_generate_report(body: ReportGenerateBody) -> dict[str, str]:
    """Submit asynchronous PDF report generation job."""
    job_id = await run_in_threadpool(reports_service.start_report_generation_job, body.model_dump())
    return {"job_id": job_id, "status": "pending"}


@router.get("/reports/history")
async def get_report_history() -> list[dict[str, Any]]:
    """List generated PDF report history."""
    return await run_in_threadpool(reports_service.list_report_history)


@router.delete("/reports/history/{filename}")
async def delete_report_file(filename: str) -> dict[str, Any]:
    """Delete a single generated PDF report."""
    success = await run_in_threadpool(reports_service.delete_report, filename)
    if not success:
        raise HTTPException(status_code=404, detail=f"Report '{filename}' not found")
    return {"status": "deleted", "filename": filename}


@router.delete("/reports/history")
async def delete_all_reports() -> dict[str, Any]:
    """Clear all generated PDF reports."""
    count = await run_in_threadpool(reports_service.clear_all_reports)
    return {"status": "cleared", "deleted_count": count}


@router.get("/reports/download/{filename}")
async def get_download_report(filename: str) -> Response:
    """Download a generated PDF report."""
    file_path = await run_in_threadpool(reports_service.get_report_file_path, filename)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Report '{filename}' not found")

    content = file_path.read_bytes()
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/expense-healthcare-data")
async def get_expense_healthcare_data() -> dict[str, Any]:
    """Extract structured data for the printable Expense & Healthcare report."""
    return await run_in_threadpool(reports_service.get_expense_healthcare_data)
