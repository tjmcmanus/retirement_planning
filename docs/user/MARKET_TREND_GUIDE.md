# Market Trend Analysis — User Guide

The **Dashboard → Market Forecast** tabs show three independent market condition assessments
for the S&P 500 (SPY), each using a different EMA timeframe.  This guide explains how
conditions and sub-phases are calculated, what each label means, and what tactical action
is appropriate for each state.

---

## How It Works

Each timeframe uses **two exponential moving averages (EMAs)**:

| Timeframe | Long EMA (regime) | Short EMA (sub-phase) |
|---|---|---|
| Short-Term | 50-day | 10-day |
| Intermediate | 50-week | 10-week |
| Long-Term | 18-month | 8-month |

**Long EMA → Regime** — The longer EMA slope determines whether you are in a Bull, Neutral,
or Bear market.  This is the primary signal and does not change based on the short EMA.

**Short EMA → Sub-Phase** — The shorter EMA slope tells you *where within* that regime you
currently sit: Accumulation (rising), Consolidating (flat), or Distribution (falling).

A slope is classified as:
- **Positive** if the EMA is rising faster than +0.1% per period
- **Negative** if the EMA is falling faster than −0.1% per period
- **Neutral** if the slope is between −0.1% and +0.1% per period

The combined display label reads `Regime (Sub-Phase)`, for example **Bull (Consolidating)**
or **Bear (Distribution)**.

---

## The 9 Market States

### 🟢 Bull Regime — Long EMA Positive

| Sub-Phase | Short EMA | Signal | Tactical Action |
|---|---|---|---|
| **Bull (Accumulation)** | Positive ↑ | Long trend up, short momentum rising | Maintain or add exposure — most favorable state |
| **Bull (Consolidating)** | Neutral → | Long trend up, short momentum flat | Hold positions; healthy pause, wait for momentum to resume |
| **Bull (Distribution)** | Negative ↓ | Long trend up, short momentum fading | Tighten stop-losses; avoid adding new positions |

**Key point:** Even in Bull (Distribution) the long-term trend is still intact.  Do not exit
outright — tighten risk controls and watch for the long EMA slope to turn negative before
reducing allocation.

---

### ⚪ Neutral Regime — Long EMA Flat

| Sub-Phase | Short EMA | Signal | Tactical Action |
|---|---|---|---|
| **Neutral (Accumulation)** | Positive ↑ | Long EMA flat, short momentum rising | Watch for breakout; wait for long EMA confirmation before adding |
| **Neutral (Consolidating)** | Neutral → | Both EMAs flat — sideways market | Maintain positions; no directional edge — avoid new bets |
| **Neutral (Distribution)** | Negative ↓ | Long EMA flat, short momentum falling | Reduce exposure; risk of transition to Bear |

**Key point:** Neutral (Accumulation) is *not* a buy signal — it means short-term momentum
is picking up while the long trend has not yet confirmed.  Wait for the long EMA to turn
positive first.

---

### 🔴 Bear Regime — Long EMA Negative

| Sub-Phase | Short EMA | Signal | Tactical Action |
|---|---|---|---|
| **Bear (Accumulation)** | Positive ↑ | Long trend down, short bouncing | Possible relief rally — **not a confirmed reversal**; wait for long EMA to turn |
| **Bear (Consolidating)** | Neutral → | Long trend down, short flat | Downtrend pausing, not reversing — maintain defensive posture |
| **Bear (Distribution)** | Negative ↓ | Both EMAs falling — sustained downtrend | Full defensive posture; higher cash; avoid new long positions |

**Key point:** Bear (Accumulation) is the most commonly misread state.  A short-term bounce
inside a bear market is normal and does not signal a trend reversal.  Only act when the
long EMA slope itself turns positive.

---

## Allocation Adjustments

The dashboard suggests a tactical allocation adjustment for each regime:

| Regime | Default Adjustment | Rationale |
|---|---|---|
| Bull | 0% | Trend intact — maintain target allocation |
| Neutral | 0% | No directional edge — hold current allocation |
| Bear (Short-Term) | −8% | Reduce equity by ~8% |
| Bear (Intermediate) | −20% | Reduce equity by ~20% |
| Bear (Long-Term) | −15% | Reduce equity by ~15% |

These are *suggestions*, not automatic trades.  The sub-phase provides further context:
a Bear (Accumulation) may not warrant the full adjustment if a reversal looks likely,
while a Bear (Distribution) that has persisted for many periods strengthens the case.

---

## Reading the Dashboard

Each Market Forecast tab shows four metrics in the summary row:

| Metric | What it shows |
|---|---|
| **Market Condition** | The headline label, e.g. `🟢 Bull (Consolidating)` |
| **Momentum Phase** | Same combined label used by the recommendations engine |
| **Tactical Adjustment** | Suggested change to stock allocation (% points) |
| **Confidence Score** | Strength of the EMA slopes — higher = more conviction |

Expand **Detailed Analysis** to see the raw EMA values, slopes (% per period), and the
Tactical Guidance box which gives a plain-language action statement for the current state.

---

## Key Rules

1. **Long EMA is the regime anchor.**  Never override the regime based on short EMA alone.
   A short-term bounce inside a Bear is still a Bear.

2. **Distribution ≠ exit.**  Bull (Distribution) means momentum is fading, not that the
   uptrend has ended.  Tighten controls and watch the long EMA slope.

3. **Accumulation in Bear ≠ buy.**  Wait for the long EMA to cross above its neutral
   threshold before adding exposure.

4. **Neutral means wait.**  Neutral (Consolidating) has no directional edge.  Sit tight.

5. **Use all three timeframes together.**  Short-Term signals are noisy.  Intermediate
   and Long-Term signals carry more weight for strategic allocation decisions.

6. **Confidence score matters.**  A Confidence of 20% means the slopes are barely outside
   the neutral band — treat the signal cautiously.  A Confidence of 80%+ is a stronger signal.

---

## Complete Quick-Reference Table

### Short-Term (10-day / 50-day EMA)

| Long (50d) | Short (10d) | Label | Action |
|---|---|---|---|
| Positive ↑ | Positive ↑ | 🟢 Bull (Accumulation) | Add / maintain full exposure |
| Positive ↑ | Neutral → | 🟢 Bull (Consolidating) | Hold; wait for momentum |
| Positive ↑ | Negative ↓ | 🟢 Bull (Distribution) | Tighten stops; no new positions |
| Neutral → | Positive ↑ | ⚪ Neutral (Accumulation) | Watch for breakout; wait for confirmation |
| Neutral → | Neutral → | ⚪ Neutral (Consolidating) | Hold; no directional action |
| Neutral → | Negative ↓ | ⚪ Neutral (Distribution) | Reduce exposure; build cash |
| Negative ↓ | Positive ↑ | 🔴 Bear (Accumulation) | Relief rally only; do not add |
| Negative ↓ | Neutral → | 🔴 Bear (Consolidating) | Defensive posture |
| Negative ↓ | Negative ↓ | 🔴 Bear (Distribution) | Full defensive; higher cash |

### Intermediate (10-week / 50-week EMA)

| Long (50w) | Short (10w) | Label | Action |
|---|---|---|---|
| Positive ↑ | Positive ↑ | 🟢 Bull (Accumulation) | Maintain or increase allocation |
| Positive ↑ | Neutral → | 🟢 Bull (Consolidating) | Hold; healthy pause |
| Positive ↑ | Negative ↓ | 🟢 Bull (Distribution) | Avoid adding; monitor for transition |
| Neutral → | Positive ↑ | ⚪ Neutral (Accumulation) | Hold; wait for 50-week confirmation |
| Neutral → | Neutral → | ⚪ Neutral (Consolidating) | Maintain; no tactical edge |
| Neutral → | Negative ↓ | ⚪ Neutral (Distribution) | Reduce ~10%; risk of bear transition |
| Negative ↓ | Positive ↑ | 🔴 Bear (Accumulation) | Relief rally; wait for confirmation |
| Negative ↓ | Neutral → | 🔴 Bear (Consolidating) | Defensive; no new longs |
| Negative ↓ | Negative ↓ | 🔴 Bear (Distribution) | Reduce ~20%; capital preservation |

### Long-Term (8-month / 18-month EMA)

| Long (18m) | Short (8m) | Label | Action |
|---|---|---|---|
| Positive ↑ | Positive ↑ | 🟢 Bull (Accumulation) | Full equity exposure; add to allocation |
| Positive ↑ | Neutral → | 🟢 Bull (Consolidating) | Hold; avoid major changes |
| Positive ↑ | Negative ↓ | 🟢 Bull (Distribution) | Review overweights; monitor for regime change |
| Neutral → | Positive ↑ | ⚪ Neutral (Accumulation) | Early bull possible; wait for 18-month confirmation |
| Neutral → | Neutral → | ⚪ Neutral (Consolidating) | Maintain allocation; avoid strategic shifts |
| Neutral → | Negative ↓ | ⚪ Neutral (Distribution) | Consider reducing exposure; build cash |
| Negative ↓ | Positive ↑ | 🔴 Bear (Accumulation) | Recovery attempt; wait for 18-month confirmation |
| Negative ↓ | Neutral → | 🔴 Bear (Consolidating) | Defensive posture; higher cash |
| Negative ↓ | Negative ↓ | 🔴 Bear (Distribution) | Reduce up to 40%; watch for value opportunities after 6+ months |

---

## Disclaimer

Market trend indicators are educational tools based on historical price data.  They do not
constitute financial advice and do not guarantee future results.  Always consult a qualified
financial professional before making allocation changes.

---

[← Back to User Guides](../guides.md) | [← Back to Home](../index.md)

<!-- Made with Bob -->
