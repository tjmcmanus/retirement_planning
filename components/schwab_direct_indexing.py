"""
Schwab Direct Index Connector
==============================
Extends the existing Schwab API integration specifically for the direct
indexing workflow.

Responsibilities
----------------
- Identify which Schwab positions are RSP constituents (direct index positions)
- Sync those positions into the direct_index / cost-basis DB tables
- Fetch real-time quotes via the existing SchwabAPI client
- Expose a simple status dict so the UI can show sync results without
  coupling to Schwab internals

Design notes
------------
* This class wraps the already-working ``SchwabConnector`` / ``SchwabAPI``
  and adds only what direct indexing needs — it does NOT duplicate auth.
* All DB writes go through the existing ``add_tax_lot`` / ``get_tax_lots``
  helpers so cost-basis tracking stays consistent.
* ``get_real_time_prices`` falls back gracefully to the cached RSP prices
  when the Schwab API is unavailable (e.g., market closed, token expired).

Author: Bob
Date: April 2026
Version: 1.0
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DB_PATH = Path("data/rsp_holdings.db")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _rsp_symbol_set() -> set[str]:
    """Return the set of RSP constituent symbols from the local DB."""
    from components.rsp_holdings_fetcher import load_constituents
    constituents = load_constituents()
    return {c.symbol for c in constituents}


def _extract_positions_from_raw(raw_positions: List[Dict]) -> List[Dict]:
    """
    Normalise the ``{'account_number': ..., 'position': {...}}`` dicts that
    ``SchwabConnector.get_positions()`` returns into a flat list of:

        {
            'account_number': str,
            'symbol': str,
            'shares': float,
            'average_price': float,      # cost basis per share
            'current_price': float,      # mark price
            'current_value': float,
        }
    """
    results = []
    for item in raw_positions:
        account_number = item.get("account_number", "Unknown")
        pos = item.get("position", {})

        instrument = pos.get("instrument", {})
        symbol = instrument.get("symbol", "").strip().upper()

        if not symbol:
            continue

        long_qty = float(pos.get("longQuantity", 0) or 0)
        short_qty = float(pos.get("shortQuantity", 0) or 0)
        shares = long_qty - short_qty  # net long position

        average_price = float(pos.get("averagePrice", 0) or 0)
        current_price = float(pos.get("marketValue", 0) or 0)
        if shares > 0:
            current_price_per_share = current_price / shares
        else:
            current_price_per_share = 0.0

        results.append(
            {
                "account_number": account_number,
                "symbol": symbol,
                "shares": shares,
                "average_price": average_price,
                "current_price": current_price_per_share,
                "current_value": current_price,
            }
        )
    return results


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------

class SchwabDirectIndexConnector:
    """
    Layer on top of the existing ``SchwabConnector`` that adds direct-indexing
    specific operations.

    Usage
    -----
    The caller is responsible for creating and authenticating a
    ``SchwabConnector`` before passing it here::

        from components.schwab_connector import SchwabConnector
        schwab = SchwabConnector(app_key, app_secret, callback_url)
        schwab.load_saved_tokens()   # or complete_authorization(...)

        di = SchwabDirectIndexConnector(schwab)
        positions = di.get_direct_index_positions()
        result = di.sync_positions_to_db("Schwab Brokerage")
    """

    def __init__(self, schwab_connector) -> None:
        """
        Parameters
        ----------
        schwab_connector:
            An authenticated ``SchwabConnector`` instance.
        """
        self._schwab = schwab_connector
        self._rsp_symbols: Optional[set[str]] = None   # lazy-loaded

    # ------------------------------------------------------------------
    # RSP symbol cache
    # ------------------------------------------------------------------

    def _get_rsp_symbols(self) -> set[str]:
        if self._rsp_symbols is None:
            self._rsp_symbols = _rsp_symbol_set()
        return self._rsp_symbols

    def refresh_rsp_symbols(self) -> None:
        """Force a reload of the RSP constituent list from the local DB."""
        self._rsp_symbols = _rsp_symbol_set()

    # ------------------------------------------------------------------
    # Core methods
    # ------------------------------------------------------------------

    def get_direct_index_positions(
        self,
        account_hash: Optional[str] = None,
    ) -> List[Dict]:
        """
        Fetch all Schwab positions that are RSP constituents.

        Parameters
        ----------
        account_hash:
            Optional specific Schwab account hash.  Pass ``None`` to search
            all linked accounts.

        Returns
        -------
        List of dicts::

            {
                'account_number': str,
                'symbol': str,
                'shares': float,
                'average_price': float,   # avg cost per share
                'current_price': float,   # latest market price per share
                'current_value': float,   # shares × current_price
            }

        Raises
        ------
        RuntimeError
            If the Schwab connector is not authenticated.
        """
        if not self._schwab.is_connected():
            raise RuntimeError(
                "Schwab connector is not authenticated. "
                "Complete OAuth authorization first."
            )

        logger.info("Fetching Schwab positions for direct index sync…")
        raw = self._schwab.get_positions(
            account_hash=account_hash,
            import_transactions=False,   # we handle lot-level import ourselves
        )

        flat = _extract_positions_from_raw(raw)
        rsp = self._get_rsp_symbols()

        di_positions = [p for p in flat if p["symbol"] in rsp]
        logger.info(
            f"Found {len(di_positions)} RSP constituents out of "
            f"{len(flat)} total Schwab positions"
        )
        return di_positions

    def sync_positions_to_db(
        self,
        account_name: str,
        account_hash: Optional[str] = None,
        account_type: str = "Brokerage",
        purchase_date_fallback: Optional[date] = None,
        overwrite_existing: bool = False,
    ) -> Dict[str, int]:
        """
        Sync Schwab direct-index positions into the cost-basis DB.

        For each RSP-constituent position found in Schwab:
        - If a lot for that symbol + account already exists **and**
          ``overwrite_existing`` is False → skip (avoids duplicate lots).
        - Otherwise create a new ``TaxLot`` using the Schwab average price
          as cost basis.

        Parameters
        ----------
        account_name:
            Human-readable account name stored in the DB (e.g. "Schwab Brokerage").
        account_hash:
            Optional Schwab account hash to restrict to one account.
        account_type:
            Account type string (default "Brokerage").
        purchase_date_fallback:
            Date to record when Schwab does not supply a purchase date.
            Defaults to today.
        overwrite_existing:
            When True, existing lots for a symbol are removed before adding
            the Schwab-sourced lot.  Use with caution.

        Returns
        -------
        ``{'added': N, 'skipped': M, 'errors': K}``
        """
        from components.cost_basis_tracker import TaxLot, add_tax_lot, get_tax_lots

        if purchase_date_fallback is None:
            purchase_date_fallback = date.today()

        di_positions = self.get_direct_index_positions(account_hash=account_hash)

        if not di_positions:
            logger.warning("No RSP-constituent positions found in Schwab account(s).")
            return {"added": 0, "skipped": 0, "errors": 0}

        added = skipped = errors = 0

        for pos in di_positions:
            symbol = pos["symbol"]
            try:
                # Check for existing lots
                existing = get_tax_lots(symbol=symbol, account_name=account_name)
                if existing and not overwrite_existing:
                    skipped += 1
                    continue

                if existing and overwrite_existing:
                    _delete_lots_for_symbol(symbol, account_name)

                lot = TaxLot(
                    lot_id=str(uuid.uuid4()),
                    symbol=symbol,
                    account_name=account_name,
                    account_type=account_type,
                    shares=pos["shares"],
                    purchase_price=pos["average_price"],
                    purchase_date=purchase_date_fallback,
                    cost_basis=pos["shares"] * pos["average_price"],
                    notes=(
                        f"Synced from Schwab account {pos['account_number']} "
                        f"on {datetime.now().strftime('%Y-%m-%d')}"
                    ),
                )
                add_tax_lot(lot)
                added += 1

            except Exception as exc:
                logger.error(f"Failed to sync {symbol}: {exc}")
                errors += 1

        logger.info(
            f"Schwab sync complete — added: {added}, skipped: {skipped}, errors: {errors}"
        )
        return {"added": added, "skipped": skipped, "errors": errors}

    def get_real_time_prices(
        self,
        symbols: List[str],
        fallback_to_cache: bool = True,
    ) -> Dict[str, float]:
        """
        Fetch real-time prices for a list of symbols via Schwab's quotes API.

        Parameters
        ----------
        symbols:
            List of ticker symbols, e.g. ``["AAPL", "MSFT"]``.
        fallback_to_cache:
            When True, any symbol that fails to return a price from Schwab
            falls back to the cached price in the RSP holdings DB.

        Returns
        -------
        ``{symbol: price}`` mapping.  Missing symbols are omitted.
        """
        if not self._schwab.is_connected():
            logger.warning(
                "Schwab connector not authenticated — using cached prices only."
            )
            return self._cached_prices(symbols) if fallback_to_cache else {}

        results: Dict[str, float] = {}
        batch_size = 100   # Schwab quotes API accepts up to 500; 100 is safe

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]
            try:
                raw = self._schwab.api.get_quotes(batch)
                for sym, quote in raw.items():
                    price = (
                        quote.get("mark")
                        or quote.get("lastPrice")
                        or quote.get("closePrice")
                    )
                    if price and float(price) > 0:
                        results[sym.upper()] = float(price)
            except Exception as exc:
                logger.warning(f"Quote batch {i}–{i+batch_size} failed: {exc}")

        # Fall back to cache for any that failed
        if fallback_to_cache:
            missing = [s for s in symbols if s.upper() not in results]
            if missing:
                cached = self._cached_prices(missing)
                results.update(cached)

        return results

    # ------------------------------------------------------------------
    # Price update helper
    # ------------------------------------------------------------------

    def update_db_prices(
        self,
        symbols: Optional[List[str]] = None,
    ) -> int:
        """
        Refresh current prices in the RSP holdings DB using Schwab quotes.

        Parameters
        ----------
        symbols:
            Subset of RSP symbols to update.  Defaults to all RSP constituents.

        Returns
        -------
        Number of symbols successfully updated.
        """
        from components.rsp_holdings_fetcher import load_constituents

        if symbols is None:
            constituents = load_constituents()
            symbols = [c.symbol for c in constituents]

        if not symbols:
            return 0

        prices = self.get_real_time_prices(symbols, fallback_to_cache=False)

        if not prices:
            logger.warning("No prices returned from Schwab — DB not updated.")
            return 0

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        updated = 0

        for sym, price in prices.items():
            cursor.execute(
                "UPDATE rsp_holdings SET current_price = ?, last_updated = ? WHERE symbol = ?",
                (price, datetime.now().isoformat(), sym),
            )
            if cursor.rowcount > 0:
                updated += 1

        conn.commit()
        conn.close()

        logger.info(f"Updated {updated} RSP constituent prices from Schwab.")
        return updated

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cached_prices(symbols: List[str]) -> Dict[str, float]:
        """Read prices from the local RSP holdings cache."""
        from components.rsp_holdings_fetcher import get_constituent
        result = {}
        for sym in symbols:
            c = get_constituent(sym)
            if c and c.current_price > 0:
                result[sym.upper()] = c.current_price
        return result


# ---------------------------------------------------------------------------
# Standalone helper (used by sync_positions_to_db overwrite path)
# ---------------------------------------------------------------------------

def _delete_lots_for_symbol(symbol: str, account_name: str) -> int:
    """
    Delete all tax lots for *symbol* in *account_name* from the DB.

    Returns the number of rows deleted.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM tax_lots WHERE symbol = ? AND account_name = ?",
        (symbol, account_name),
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    logger.debug(f"Deleted {deleted} lots for {symbol} / {account_name}")
    return deleted


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------

def create_schwab_di_connector(
    app_key: Optional[str] = None,
    app_secret: Optional[str] = None,
    callback_url: Optional[str] = None,
) -> Optional["SchwabDirectIndexConnector"]:
    """
    Convenience factory.  Reads credentials from environment variables when
    explicit values are not supplied, attempts to load saved tokens, and
    returns a ``SchwabDirectIndexConnector`` or ``None`` if unavailable.

    Parameters
    ----------
    app_key / app_secret / callback_url:
        Override env vars ``SCHWAB_APP_KEY``, ``SCHWAB_APP_SECRET``,
        ``SCHWAB_CALLBACK_URL``.
    """
    import os

    key = app_key or os.getenv("SCHWAB_APP_KEY", "")
    secret = app_secret or os.getenv("SCHWAB_APP_SECRET", "")
    cb = callback_url or os.getenv("SCHWAB_CALLBACK_URL", "https://localhost:8080/callback")

    if not key or not secret:
        logger.info(
            "SCHWAB_APP_KEY / SCHWAB_APP_SECRET not set — "
            "SchwabDirectIndexConnector not created."
        )
        return None

    try:
        from components.schwab_connector import SchwabConnector
        from components.credential_manager import CredentialManager

        schwab = SchwabConnector(
            app_key=key,
            app_secret=secret,
            callback_url=cb,
            credential_manager=CredentialManager(),
        )
        schwab.load_saved_tokens()   # no-op if not previously authorised
        return SchwabDirectIndexConnector(schwab)

    except Exception as exc:
        logger.warning(f"Could not create SchwabDirectIndexConnector: {exc}")
        return None
