import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
import calendar

# Page configuration
st.set_page_config(page_title="Market Momentum Strategy Engine", layout="wide")
st.title("📈 Market Momentum Strategy Engine")
st.markdown("Automated ranking engine based on pure quantitative momentum and relative velocity.")

# --- Data Fetching Setup ---
@st.cache_data(ttl=3600)  # Cache data for 1 hour to avoid slow reloads
def fetch_data(tickers, period="1y"):
    """Fetch historical data for a list of tickers."""
    try:
        data = yf.download(tickers, period=period, progress=False)
        return data
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

def calculate_atr(df, window=14):
    if 'High' not in df.columns or 'Low' not in df.columns or 'Close' not in df.columns:
        return 0
    high = df['High']
    low = df['Low']
    close_prev = df['Close'].shift(1)
    
    tr1 = high - low
    tr2 = (high - close_prev).abs()
    tr3 = (low - close_prev).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=window).mean()
    return atr.iloc[-1]

# --- Module 1: Market Regime Shield ---
st.header("1. Market Regime Shield")
benchmark_ticker = "^NSEI"  # Nifty 50

with st.spinner("Checking Market Regime..."):
    nifty_data = fetch_data([benchmark_ticker], period="1y")

if not nifty_data.empty:
    nifty_df = nifty_data.xs(benchmark_ticker, level='Ticker', axis=1) if isinstance(nifty_data.columns, pd.MultiIndex) else nifty_data
    nifty_close_series = nifty_df['Close'].dropna() if 'Close' in nifty_df else pd.Series()
    
    if not nifty_close_series.empty:
        nifty_close = nifty_close_series.iloc[-1]
        # Calculate 200 DMA (approx 200 trading days)
        if len(nifty_close_series) >= 200:
            nifty_200_dma = nifty_close_series.iloc[-200:].mean()
        else:
            nifty_200_dma = nifty_close_series.mean() # Fallback if less than 200 days
            
        is_market_uptrend = nifty_close > nifty_200_dma
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Nifty 50 Latest Close", f"{nifty_close:.2f}")
        col2.metric("Nifty 50 200 DMA", f"{nifty_200_dma:.2f}")
        
        if is_market_uptrend:
            col3.success("✅ Market is in Uptrend. Safe to deploy capital.")
        else:
            col3.error("❌ Market is in Downtrend. Caution: Avoid long deployments.")
    else:
        st.error("Failed to extract Nifty 50 close data.")
        is_market_uptrend = False
else:
    st.error("Failed to fetch Nifty 50 data.")
    is_market_uptrend = False

st.divider()

# --- Universe Selection ---
st.header("2. Candidate Filtering & 3. Brutal Strength Ranking")
st.markdown("Scanning Nifty 500 universe for momentum candidates.")

@st.cache_data(ttl=86400) # Cache for 1 day
def get_nifty500_data():
    try:
        # Largecap (Nifty 100)
        df_large = pd.read_csv("https://archives.nseindia.com/content/indices/ind_nifty100list.csv")
        large_tickers = [f"{symbol}.NS" for symbol in df_large['Symbol']]
        
        # Nifty 200
        df_200 = pd.read_csv("https://archives.nseindia.com/content/indices/ind_nifty200list.csv")
        nifty200_tickers = [f"{symbol}.NS" for symbol in df_200['Symbol']]
        
        # Midcap (Nifty Midcap 150)
        df_mid = pd.read_csv("https://archives.nseindia.com/content/indices/ind_niftymidcap150list.csv")
        mid_tickers = [f"{symbol}.NS" for symbol in df_mid['Symbol']]
        
        # Smallcap (Nifty Smallcap 250)
        df_small = pd.read_csv("https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv")
        small_tickers = [f"{symbol}.NS" for symbol in df_small['Symbol']]
        
        all_tickers = large_tickers + mid_tickers + small_tickers
        
        cap_dict = {}
        for t in large_tickers: cap_dict[t] = "Large Cap"
        for t in mid_tickers: cap_dict[t] = "Mid Cap"
        for t in small_tickers: cap_dict[t] = "Small Cap"
        macro_map = {
            'Automobile and Auto Components': 'Auto',
            'Capital Goods': 'Infra',
            'Chemicals': 'Commodities',
            'Construction': 'Infra',
            'Construction Materials': 'Infra',
            'Consumer Durables': 'Consumer',
            'Consumer Services': 'Consumer',
            'Fast Moving Consumer Goods': 'FMCG',
            'Financial Services': 'Financial Services',
            'Healthcare': 'Pharma & Healthcare',
            'Information Technology': 'IT',
            'Media Entertainment & Publication': 'Media',
            'Metals & Mining': 'Metal',
            'Oil Gas & Consumable Fuels': 'Energy',
            'Power': 'Energy',
            'Realty': 'Realty',
            'Services': 'Consumer', 
            'Telecommunication': 'Telecom',
            'Textiles': 'Textiles',
            'Diversified': 'Commodities'
        }
        
        sector_dict = {}
        for idx, row in pd.concat([df_large, df_mid, df_small]).iterrows():
            industry = row['Industry']
            sector_dict[f"{row['Symbol']}.NS"] = macro_map.get(industry, industry)
            
        return {
            "all": all_tickers,
            "large": large_tickers,
            "mid": mid_tickers,
            "small": small_tickers,
            "nifty200": nifty200_tickers
        }, cap_dict, sector_dict
    except Exception as e:
        st.error("Could not fetch index lists from NSE. Using fallback list.")
        fallback = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]
        return {"all": fallback, "large": fallback, "mid": [], "small": [], "nifty200": fallback}, {t: "Unknown" for t in fallback}, {t: "Unknown" for t in fallback}

@st.cache_data(ttl=3600)
def get_fno_long_buildup():
    url = 'https://www.nseindia.com/api/live-analysis-oi-spurts-underlyings'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    try:
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
        response = session.get(url, headers=headers, timeout=10)
        data = response.json()
        oi_data = {}
        for item in data.get('data', []):
            symbol = item['symbol']
            change_in_oi_pct = item.get('avgInOI', 0)
            oi_data[symbol] = change_in_oi_pct
        return oi_data
    except Exception as e:
        st.error(f"Failed to fetch OI data from NSE: {e}")
        return {}

@st.cache_data(ttl=3600)
def get_official_sector_momentum():
    index_mapping = {
        "IT": "^CNXIT",
        "Bank": "^NSEBANK",
        "Pharma & Healthcare": "^CNXPHARMA",
        "Auto": "^CNXAUTO",
        "FMCG": "^CNXFMCG",
        "Metal": "^CNXMETAL",
        "Energy": "^CNXENERGY",
        "Realty": "^CNXREALTY",
        "Infra": "^CNXINFRA",
        "Consumer": "^CNXCONSUM",
        "PSU Bank": "^CNXPSUBANK",
        "Media": "^CNXMEDIA",
        "Financial Services": "^CNXFIN",
        "Commodities": "^CNXCMDT",
        "Public Sector (PSE)": "^CNXPSE"
    }
    
    sector_results = []
    try:
        index_data = yf.download(list(index_mapping.values()), period="1y", progress=False)
        for sector_name, symbol in index_mapping.items():
            if isinstance(index_data.columns, pd.MultiIndex):
                prices = index_data['Close'][symbol].dropna()
            else:
                prices = index_data['Close'].dropna()
                
            if len(prices) >= 21:
                current = prices.iloc[-1]
                p1m = prices.iloc[-21] if len(prices) >= 21 else prices.iloc[0]
                p3m = prices.iloc[-63] if len(prices) >= 63 else prices.iloc[0]
                p6m = prices.iloc[-126] if len(prices) >= 126 else prices.iloc[0]
                p12m = prices.iloc[-252] if len(prices) >= 252 else prices.iloc[0]
                
                sector_results.append({
                    "Sector": sector_name,
                    "1-Month Velocity (%)": round(((current - p1m) / p1m) * 100, 2),
                    "3-Month Velocity (%)": round(((current - p3m) / p3m) * 100, 2),
                    "6-Month Velocity (%)": round(((current - p6m) / p6m) * 100, 2),
                    "12-Month Velocity (%)": round(((current - p12m) / p12m) * 100, 2)
                })
        df = pd.DataFrame(sector_results)
        df['1-Month Rank'] = df['1-Month Velocity (%)'].rank(ascending=False, method='min').astype(int)
        df['3-Month Rank'] = df['3-Month Velocity (%)'].rank(ascending=False, method='min').astype(int)
        df['6-Month Rank'] = df['6-Month Velocity (%)'].rank(ascending=False, method='min').astype(int)
        df['12-Month Rank'] = df['12-Month Velocity (%)'].rank(ascending=False, method='min').astype(int)
        df = df[['Sector', '1-Month Rank', '3-Month Rank', '6-Month Rank', '12-Month Rank']]
        return df
    except Exception as e:
        return pd.DataFrame()

ticker_lists, cap_mapping, sector_mapping = get_nifty500_data()
oi_data = get_fno_long_buildup()

universe_option = st.selectbox(
    "Select Momentum Model:",
    (
        "Momentum 30 (Nifty 500)", 
        "Momentum 3M Velocity + Long Buildup (F&O)",
        "Momentum 20 (Nifty 200)",
        "Momentum 10 (Nifty 100)",
        "Momentum 30 (Midcap 150)",
        "Momentum 30 (Smallcap 250)",
        "Custom Tickers"
    )
)

ranking_timeframe = st.selectbox(
    "Rank Stocks By:",
    ("6-Month Velocity", "3-Month Velocity", "1-Month Velocity", "12-Month Velocity")
)

top_n = 30
remove_cap_col = False

if universe_option == "Momentum 30 (Nifty 500)":
    tickers_to_scan = ticker_lists["all"]
    top_n = 40
elif universe_option == "Momentum 3M Velocity + Long Buildup (F&O)":
    tickers_to_scan = [f"{sym}.NS" for sym in oi_data.keys()]
    top_n = 30
    
    # Calculate current F&O expiry (Last Thursday of the month)
    today_date = datetime.today().date()
    def get_last_thursday(year, month):
        num_days = calendar.monthrange(year, month)[1]
        last_day = datetime(year, month, num_days).date()
        offset = (last_day.weekday() - 3) % 7
        return last_day - timedelta(days=offset)
        
    current_expiry = get_last_thursday(today_date.year, today_date.month)
    if today_date > current_expiry:
        if today_date.month == 12:
            current_expiry = get_last_thursday(today_date.year + 1, 1)
        else:
            current_expiry = get_last_thursday(today_date.year, today_date.month + 1)
            
    st.info(f"📅 **Active F&O Expiry Cycle:** {current_expiry.strftime('%d %b %Y')} *(Standard Last Thursday)*")
elif universe_option == "Momentum 10 (Nifty 100)":
    tickers_to_scan = ticker_lists["large"]
    top_n = 10
    remove_cap_col = True
elif universe_option == "Momentum 20 (Nifty 200)":
    tickers_to_scan = ticker_lists["nifty200"]
    top_n = 20
elif universe_option == "Momentum 30 (Midcap 150)":
    tickers_to_scan = ticker_lists["mid"]
    top_n = 30
    remove_cap_col = True
elif universe_option == "Momentum 30 (Smallcap 250)":
    tickers_to_scan = ticker_lists["small"]
    top_n = 30
    remove_cap_col = True
elif universe_option == "Custom Tickers":
    custom_input = st.text_input("Enter tickers separated by comma (e.g., RELIANCE.NS, TCS.NS):", "RELIANCE.NS, TCS.NS")
    tickers_to_scan = [t.strip() for t in custom_input.split(",") if t.strip()]
    top_n = 50

def calculate_rsi(prices, window=14):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=window, min_periods=1).mean()
    avg_loss = loss.rolling(window=window, min_periods=1).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

if st.button("Run Momentum Engine"):
    if not is_market_uptrend:
         st.warning("Market is below 200 DMA. Proceeding with scan, but remember the regime shield rule.")
         
    with st.spinner("Fetching data and calculating velocity (this may take a few minutes for 500 stocks)..."):
        # Fetch 1 year of data for the selected universe
        stock_data = fetch_data(tickers_to_scan, period="1y")
        
        if stock_data.empty:
            st.error("Failed to fetch stock data.")
        else:
            results = []
            for ticker in tickers_to_scan:
                if isinstance(stock_data.columns, pd.MultiIndex):
                    if ticker not in stock_data.columns.get_level_values('Ticker'):
                        continue
                    ticker_df = stock_data.xs(ticker, level='Ticker', axis=1).dropna()
                else:
                    ticker_df = stock_data.dropna()
                
                if 'Close' not in ticker_df.columns:
                    continue
                    
                prices = ticker_df['Close']
                if len(prices) < 21: # Ensure we have enough data for at least 1-month velocity
                    continue
                
                current_price = prices.iloc[-1]
                
                # Calculate DMAs
                dma_200 = prices.iloc[-200:].mean() if len(prices) >= 200 else prices.mean()
                dma_50 = prices.iloc[-50:].mean() if len(prices) >= 50 else prices.mean()
                
                # Filter 1: Price > 200 DMA
                is_above_200dma = current_price > dma_200
                
                # Indicator: Golden Cross
                golden_cross = dma_50 > dma_200
                
                # Indicator: RSI
                rsi = calculate_rsi(prices)
                
                # Indicator: ATR
                atr_14 = calculate_atr(ticker_df)
                
                # Rank: Velocity (Return)
                price_ago_6m = prices.iloc[-126] if len(prices) >= 126 else prices.iloc[0]
                velocity_6m = ((current_price - price_ago_6m) / price_ago_6m) * 100
                
                price_ago_3m = prices.iloc[-63] if len(prices) >= 63 else prices.iloc[0]
                velocity_3m = ((current_price - price_ago_3m) / price_ago_3m) * 100
                
                price_ago_1m = prices.iloc[-21] if len(prices) >= 21 else prices.iloc[0]
                velocity_1m = ((current_price - price_ago_1m) / price_ago_1m) * 100
                
                price_ago_12m = prices.iloc[-252] if len(prices) >= 252 else prices.iloc[0]
                velocity_12m = ((current_price - price_ago_12m) / price_ago_12m) * 100
                
                # Determine Cap Size and Sector
                cap_size = cap_mapping.get(ticker, "Unknown")
                sector = sector_mapping.get(ticker, "Unknown")
                
                # Check Long Buildup and Calculate Trailing SL
                is_long_buildup = False
                trailing_sl = current_price - (2 * atr_14)
                sl_col_name = "Trailing SL Ref (2x ATR)"
                
                if universe_option == "Momentum 3M Velocity + Long Buildup (F&O)":
                    sym = ticker.replace(".NS", "")
                    oi_change = oi_data.get(sym, 0)
                    price_change_1d = ((current_price - prices.iloc[-2]) / prices.iloc[-2]) * 100 if len(prices) >= 2 else 0
                    if oi_change > 0 and price_change_1d > 0:
                        is_long_buildup = True
                    trailing_sl = current_price - (1.5 * atr_14)
                    sl_col_name = "F&O Trailing Stop (1.5x ATR)"
                
                res_dict = {
                    "Ticker": ticker.replace(".NS", ""),
                    "Sector": sector,
                    "Cap Size": cap_size,
                    "Current Price": round(current_price, 2),
                    "200 DMA": round(dma_200, 2),
                    "Above 200 DMA?": "✅ Yes" if is_above_200dma else "❌ No"
                }
                
                if universe_option == "Momentum 3M Velocity + Long Buildup (F&O)":
                    res_dict["Long Buildup?"] = "✅ Yes" if is_long_buildup else "❌ No"
                
                res_dict[sl_col_name] = round(trailing_sl, 2)
                res_dict["6-Month Velocity (%)"] = round(velocity_6m, 2)
                res_dict["3-Month Velocity (%)"] = round(velocity_3m, 2)
                res_dict["1-Month Velocity (%)"] = round(velocity_1m, 2)
                res_dict["12-Month Velocity (%)"] = round(velocity_12m, 2)
                res_dict["RSI (14)"] = round(rsi, 2)
                res_dict["Golden Cross?"] = "✅ Yes" if golden_cross else "❌ No"
                
                results.append(res_dict)
            
            if not results:
                st.write("Not enough data to calculate metrics.")
            else:
                st.session_state["results_df"] = pd.DataFrame(results)

if "results_df" in st.session_state:
    results_df = st.session_state["results_df"]
    
    # Filter out stocks below 200 DMA (Pure Jain Style)
    filtered_df = results_df[results_df["Above 200 DMA?"] == "✅ Yes"]
    
    # Cap Current Price to 6500 for all models except F&O Long Buildup
    if universe_option != "Momentum 3M Velocity + Long Buildup (F&O)":
        filtered_df = filtered_df[filtered_df["Current Price"] <= 6500]
    
    # Set sorting column
    if ranking_timeframe == "6-Month Velocity":
        sort_col = "6-Month Velocity (%)"
    elif ranking_timeframe == "3-Month Velocity":
        sort_col = "3-Month Velocity (%)"
    elif ranking_timeframe == "12-Month Velocity":
        sort_col = "12-Month Velocity (%)"
    else:
        sort_col = "1-Month Velocity (%)"
        
    # Rank by Brutal Strength and get Top N FIRST
    ranked_df = filtered_df.sort_values(by=sort_col, ascending=False).reset_index(drop=True)
    top_n_df = ranked_df.head(top_n).copy()
    
    # Insert static rank column as the first column (reflecting original pre-buildup strength)
    top_n_df.insert(0, "Velocity Rank", top_n_df.index + 1)
    
    # NOW filter for Long Buildup ONLY inside those top 30 ranked stocks
    if universe_option == "Momentum 3M Velocity + Long Buildup (F&O)":
        top_n_df = top_n_df[top_n_df["Long Buildup?"] == "✅ Yes"]
        
    # (Removed static index insertion to allow AgGrid to handle numbering dynamically)
    
    if remove_cap_col and "Cap Size" in top_n_df.columns:
        top_n_df = top_n_df.drop(columns=["Cap Size"])
        
    if "Above 200 DMA?" in top_n_df.columns:
        top_n_df = top_n_df.drop(columns=["Above 200 DMA?"])
    
    st.subheader("📊 Sector-wise Momentum Summary (True Index)")
    st.markdown("Actual market-cap weighted momentum scores using official NSE Sector Indices.")
    
    sector_summary = get_official_sector_momentum()
    
    if not sector_summary.empty:
        # Sort sector summary by the selected timeframe
        rank_sort_col = sort_col.replace("Velocity (%)", "Rank")
        if rank_sort_col in sector_summary.columns:
            sector_summary = sector_summary.sort_values(by=rank_sort_col, ascending=True).reset_index(drop=True)
        st.dataframe(sector_summary, use_container_width=True)
    else:
        st.warning("Could not fetch official sector index data.")
    st.divider()
    
    st.subheader(f"🏆 Top {top_n} Ranked Momentum Portfolio")
    st.markdown(f"Found **{len(filtered_df)}** stocks above their 200 DMA. Displaying the **Top {top_n}** ranked by {ranking_timeframe}.")
    
    if not sector_summary.empty:
        sector_6m_map = sector_summary.set_index('Sector')['6-Month Rank'].to_dict()
        sector_3m_map = sector_summary.set_index('Sector')['3-Month Rank'].to_dict()
        sector_12m_map = sector_summary.set_index('Sector')['12-Month Rank'].to_dict()
        top_n_df['Sector 6M Rank'] = top_n_df['Sector'].map(sector_6m_map).fillna(1)
        top_n_df['Sector 3M Rank'] = top_n_df['Sector'].map(sector_3m_map).fillna(1)
        top_n_df['Sector 12M Rank'] = top_n_df['Sector'].map(sector_12m_map).fillna(1)
    
    gb = GridOptionsBuilder.from_dataframe(top_n_df)
    gb.configure_default_column(filterable=True, sortable=True)
    gb.configure_side_bar()
    gridOptions = gb.build()
    
    if universe_option != "Momentum 3M Velocity + Long Buildup (F&O)":
        gridOptions['getRowStyle'] = JsCode("""
        function(params) {
            if (params.data && (params.data['Sector 6M Rank'] > 10)) {
                return {
                    'backgroundColor': '#ffb347',
                    'color': 'black'
                };
            }
            if (params.data && (params.data['6-Month Velocity (%)'] < 0 || params.data['3-Month Velocity (%)'] < 0 || params.data['1-Month Velocity (%)'] < 0)) {
                return {
                    'backgroundColor': '#ffeba8',
                    'color': 'black'
                };
            }
            if (params.data) {
                return {
                    'backgroundColor': '#d4edda',
                    'color': 'black'
                };
            }
            return null;
        }
        """)
    
    # Prepend dynamic Index column to columnDefs directly (fully detached from dataframe data)
    # Prepend dynamic Index column to columnDefs directly (fully detached from dataframe data)
    gridOptions['columnDefs'].insert(0, {
        'headerName': 'Index',
        'colId': 'index_col',
        'valueGetter': JsCode("function(params) { return params.node.rowIndex != null ? params.node.rowIndex + 1 : null; }"),
        'pinned': 'left',
        'width': 80,
        'filter': False,
        'sortable': False,
        'suppressMenu': True
    })
    
    # Force AgGrid to refresh the Index column whenever rows are filtered or sorted
    gridOptions['onSortChanged'] = JsCode("function(params) { params.api.refreshCells({columns: ['index_col']}); }")
    gridOptions['onFilterChanged'] = JsCode("function(params) { params.api.refreshCells({columns: ['index_col']}); }")
    
    # Inject custom JavaScript for a direct 'Hide Column' menu item
    gridOptions['getMainMenuItems'] = JsCode("""
    function(params) {
        var menuItems = params.defaultItems.slice(0);
        menuItems.push('separator');
        menuItems.push({
            name: 'Hide Column 👁️‍🗨️',
            action: function() {
                params.api.setColumnsVisible([params.column.getId()], false);
            }
        });
        return menuItems;
    }
    """)
    
    AgGrid(top_n_df, gridOptions=gridOptions, fit_columns_on_grid_load=True, theme="streamlit", enable_enterprise_modules=True, allow_unsafe_jscode=True)
    
    csv = top_n_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Portfolio as CSV",
        data=csv,
        file_name='momentum_portfolio.csv',
        mime='text/csv',
    )
    
    # Show rejected
    rejected_df = results_df[results_df["Above 200 DMA?"] == "❌ No"].sort_values(by=sort_col, ascending=False).reset_index(drop=True)
    with st.expander("Show Filtered/Rejected Stocks (Below 200 DMA)"):
        st.dataframe(rejected_df, use_container_width=True)

st.markdown("---")
st.caption("Strategy based on WeekendInvesting Pure Momentum rules. For educational purposes only.")
