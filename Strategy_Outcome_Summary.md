# Strategy Blueprint: Momentum Investing vs. Hybrid Breakout

This document summarizes the core outcomes, architectural designs, and strategic distinctions discussed regarding the automation of **Alok Jain's (WeekendInvesting)** momentum engine versus a custom **Hybrid Technical Breakout** strategy.

---

## 1. Strategic Alignment: The Crucial Distinction

The discussion highlighted a fundamental divergence between Alok Jain's pure quantitative momentum philosophy and traditional technical trading setups.

| Feature / Rule | Alok Jain's Pure Style | Your Hybrid Breakout Setup |
| :--- | :--- | :--- |
| **Asset Universe** | Broad Market (Nifty 500), actively favoring small and mid-caps. | F&O Segment (~180 liquid large-cap stocks) due to OI constraints. |
| **Core Indicators** | **None.** Uses pure price action & comparative velocity tracking. | RSI (>70), Moving Average Crossovers (Golden Cross), and Futures Open Interest (OI). |
| **Execution Timing** | Strict **Weekly Rebalancing** window (e.g., Friday afternoons). | Triggered automatically when specific technical breakouts align. |
| **Philosophy** | Ride long-term structural trends; price is the ultimate truth. | Capture high-velocity short-term breakouts at maximum velocity. |

---

## 2. Quantitative System Architecture

To fully automate either version of the strategy, the execution pipeline requires a structured quantitative stack mapping four distinct modules:

```
+--------------------------------------------------------+
| 1. MARKET REGIME SHIELD                                |
| Check if Benchmark Index (Nifty 50) > 200 DMA          |
+---------------------------+----------------------------+
                            | (If Yes)
                            v
+--------------------------------------------------------+
| 2. CANDIDATE FILTERING                                 |
| Pure Momentum: Price > 200 DMA                         |
| Hybrid Style : Price > 200 DMA + Golden Cross + RSI>70 |
+---------------------------+----------------------------+
                            |
                            v
+--------------------------------------------------------+
| 3. BRUTAL STRENGTH RANKING                            |
| Calculate and rank entire universe by 6-Month Velocity |
+---------------------------+----------------------------+
                            |
                            v
+--------------------------------------------------------+
| 4. RISK MANAGEMENT & EXITS                             |
| Weekly rebalance cycle to drop stocks failing filters  |
| or falling significantly down the relative velocity rank|
+--------------------------------------------------------+
```

---

## 3. Automation Implementation Guide

### Key Stack Components
* **Language & Core Analytics:** Python, `pandas`, `numpy`.
* **Data Pipelines:** `yfinance` (for free cash market data), Broker APIs (e.g., Zerodha Kite Connect, Fyers, Angel One) for Derivatives/OI data.
* **Infrastructure Cloud Cron:** GitHub Actions workflow executing every Friday at 3:15 PM IST to check portfolio status and execute weekly rebalancing.

### Next Steps for Implementation
1. **Define Core Universe:** Lock in whether the automation scans the broad Nifty 500 (Jain style) or liquid F&O tickers (Hybrid style).
2. **Integrate Persistence:** Implement a localized ledger file (`portfolio.csv`) to preserve current holdings across weekly execution windows.
3. **Connect Notification Hooks:** Add a Telegram Bot or SMTP email block at the tail end of the Python engine to send the final investable list directly to your device.