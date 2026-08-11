# Strategy Blueprint: Momentum Investing vs. Hybrid Breakout

This document summarizes the core outcomes, architectural designs, and strategic distinctions of the automated **Market Momentum Strategy Engine**, detailing the implementation of both pure quantitative momentum (Alok Jain style) and custom **Hybrid Technical Breakout** strategies (F&O).

---

## 1. Strategic Alignment: The Crucial Distinction

The strategy engine accommodates multiple philosophies, allowing a toggle between broad market pure momentum and targeted technical setups in derivatives.

| Feature / Rule | Pure Quantitative Momentum | Hybrid F&O Breakout Setup |
| :--- | :--- | :--- |
| **Asset Universe** | Nifty 500, Nifty 200, Nifty 100, Midcap 150, Smallcap 250. | F&O Segment (~180 liquid stocks) tracking Open Interest. |
| **Core Indicators** | Price > 200 DMA, Comparative Velocity (1M, 3M, 6M). | Price > 200 DMA + Long Buildup (OI% & Price% positive). |
| **Risk Management** | Trailing Stop Loss at 2x ATR (Average True Range). | Tighter Trailing Stop Loss at 1.5x ATR. |
| **Execution Focus** | Ride structural trends based on relative strength ranking. | Capture high-velocity short-term setups backed by OI buildup. |

---

## 2. Quantitative System Architecture

The execution pipeline implemented in `momentum_app.py` consists of a structured quantitative stack with the following modules:

```text
+--------------------------------------------------------+
| 1. MARKET REGIME SHIELD                                |
| Check if Benchmark Index (Nifty 50) > 200 DMA          |
| (Flags a warning if market is in a downtrend)          |
+---------------------------+----------------------------+
                            |
                            v
+--------------------------------------------------------+
| 2. CANDIDATE FILTERING                                 |
| Base Filter: Price > 200 DMA                           |
| F&O Add-on : Positive OI Change + Positive Price Change|
| Metrics Calculated: RSI (14), Golden Cross, ATR (14)   |
+---------------------------+----------------------------+
                            |
                            v
+--------------------------------------------------------+
| 3. BRUTAL STRENGTH RANKING                            |
| Calculate Velocity across 1-Month, 3-Month, or 6-Month |
| Rank universe and select Top N (10, 20, 30 depending   |
| on selected index model)                               |
+---------------------------+----------------------------+
                            |
                            v
+--------------------------------------------------------+
| 4. RISK MANAGEMENT & EXITS                             |
| Dynamic Trailing SL assigned per stock based on ATR:   |
| - Standard: Current Price - (2 * ATR)                  |
| - F&O: Current Price - (1.5 * ATR)                     |
+--------------------------------------------------------+
```

---

## 3. Automation Implementation Guide

### Key Stack Components
* **UI & Core Analytics:** `streamlit`, Python, `pandas`, `numpy`.
* **Data Pipelines:** `yfinance` (historical price data, DMA, RSI, ATR), NSE Live API (for F&O Open Interest Long Buildup data).
* **Grid Display:** `st_aggrid` with dynamic index management, custom column visibility toggles, and CSV export functionality.

### Core Logic Highlights
1. **Dynamic Universe Selection:** Users can switch between broad indices (Nifty 500), concentrated lists (Nifty 100/200, Mid/Small caps), F&O specific long buildup scans, or custom ticker lists.
2. **Flexible Timeframes:** Velocity ranking can be toggled between 1-Month, 3-Month, and 6-Month return periods to suit different momentum speeds.
3. **F&O Filtering Order:** The engine ranks the top F&O candidates by strength first, and then explicitly filters for those currently exhibiting Long Buildup (OI and Price increase), ensuring only the strongest trending stocks with institutional backing are selected.
4. **Calculated Metrics Displayed:** RSI (14) and Golden Cross (50 DMA > 200 DMA) are calculated and displayed for reference, though the core filter relies primarily on the 200 DMA and velocity.