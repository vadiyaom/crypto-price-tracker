"""
================================================================================
CryptoPulse: Real-Time Cryptocurrency Price Tracker & Market Analytics Dashboard
================================================================================

A production-grade, portfolio-ready Streamlit application that fetches, analyzes,
and visualizes cryptocurrency market data using the CoinGecko REST API, Pandas,
and Plotly.

Author: Data Science Portfolio Project
License: MIT
Data Source: CoinGecko API (https://www.coingecko.com)
================================================================================
"""

import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# 1. ENVIRONMENT CONFIGURATION & SETUP
# -----------------------------------------------------------------------------
# Attempt to load local environment variables from a .env file (if present)
load_dotenv()

# Streamlit Page Setup - MUST be the first Streamlit command
st.set_page_config(
    page_title="CryptoPulse | Crypto Tracker",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# 2. CONSTANTS & SYSTEM CONFIGURATION
# -----------------------------------------------------------------------------
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

# Required cryptocurrencies as specified in project specifications
# CoinGecko uses specific API IDs (e.g., 'binancecoin' for BNB, 'ripple' for XRP)
CORE_CRYPTOCURRENCIES = {
    "bitcoin": {"name": "Bitcoin", "symbol": "BTC"},
    "ethereum": {"name": "Ethereum", "symbol": "ETH"},
    "solana": {"name": "Solana", "symbol": "SOL"},
    "binancecoin": {"name": "BNB", "symbol": "BNB"},
    "ripple": {"name": "XRP", "symbol": "XRP"},
    "dogecoin": {"name": "Dogecoin", "symbol": "DOGE"},
    "cardano": {"name": "Cardano", "symbol": "ADA"},
}

# Optional additional popular cryptocurrencies users can add to their tracking
ADDITIONAL_CRYPTOCURRENCIES = {
    "avalanche-2": {"name": "Avalanche", "symbol": "AVAX"},
    "polkadot": {"name": "Polkadot", "symbol": "DOT"},
    "chainlink": {"name": "Chainlink", "symbol": "LINK"},
    "shiba-inu": {"name": "Shiba Inu", "symbol": "SHIB"},
    "polygon-ecosystem-token": {"name": "Polygon (POL)", "symbol": "POL"},
}

ALL_SUPPORTED_COINS = {**CORE_CRYPTOCURRENCIES, **ADDITIONAL_CRYPTOCURRENCIES}

# Supported Fiat Currencies
CURRENCY_CONFIG = {
    "USD": {"code": "usd", "symbol": "$", "locale": "en-US"},
    "INR": {"code": "inr", "symbol": "₹", "locale": "en-IN"},
}

# Cache Duration Constants (Free-tier friendly to prevent HTTP 429 rate limits)
CACHE_TTL_MARKETS = 120    # 2 minutes cache for live market prices
CACHE_TTL_CHARTS = 300     # 5 minutes cache for historical chart data
REQUEST_TIMEOUT = 12       # 12 seconds network timeout

# -----------------------------------------------------------------------------
# 3. CUSTOM UI STYLING (CSS)
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Metric Card Styling */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0.02) 100%);
        border: 1px solid rgba(255, 255, 255, 0.12);
        padding: 16px 20px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.15);
    }
    
    /* Subtle Accent Badge */
    .badge-pill {
        display: inline-block;
        padding: 3px 10px;
        font-size: 0.78rem;
        font-weight: 600;
        border-radius: 9999px;
        margin-left: 8px;
    }
    .badge-live {
        background-color: rgba(34, 197, 94, 0.15);
        color: #22c55e;
        border: 1px solid rgba(34, 197, 94, 0.3);
    }
    .badge-cached {
        background-color: rgba(234, 179, 8, 0.15);
        color: #eab308;
        border: 1px solid rgba(234, 179, 8, 0.3);
    }

    /* Attribution & Footer */
    .footer-container {
        margin-top: 48px;
        padding: 20px 0;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
        text-align: center;
        font-size: 0.88rem;
        color: #888888;
    }
    .footer-container a {
        color: #38bdf8;
        text-decoration: none;
    }
    .footer-container a:hover {
        text-decoration: underline;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# 4. UTILITY & HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def get_api_key() -> str:
    """
    Retrieve the CoinGecko API key securely.
    
    Security Best Practice:
    1. Check Streamlit Secrets (`.streamlit/secrets.toml` or Cloud Secrets)
    2. Check System Environment Variables (`COINGECKO_API_KEY`)
    3. Return empty string if not configured (app runs in free public mode).
    
    Never hardcode API keys directly into source code.
    """
    key = ""
    # 1. Attempt retrieval from Streamlit secrets
    try:
        if "COINGECKO_API_KEY" in st.secrets:
            key = st.secrets["COINGECKO_API_KEY"]
    except Exception:
        pass

    # 2. If not found, attempt retrieval from system environment variables
    if not key:
        key = os.getenv("COINGECKO_API_KEY", "")

    return key.strip() if key else ""


def build_request_headers(api_key: str) -> Dict[str, str]:
    """
    Construct HTTP headers for CoinGecko API requests.
    
    - Free Demo API Keys use the 'x-cg-demo-api-key' header.
    - Pro API Keys use 'x-cg-pro-api-key'.
    - If no key is provided, standard JSON acceptance headers are used.
    """
    headers = {
        "Accept": "application/json",
        "User-Agent": "CryptoPulse-Tracker/1.0",
    }
    if api_key:
        # CoinGecko Demo keys typically begin with 'CG-'
        headers["x-cg-demo-api-key"] = api_key
    return headers


def format_currency(value: Optional[float], currency_symbol: str) -> str:
    """
    Format numeric currency values cleanly for dashboard display.
    Handles NaN/None values, very small fractions, and large values.
    """
    if value is None or pd.isna(value):
        return "N/A"
    
    # Large numbers: Billions or Millions abbreviation if appropriate
    if abs(value) >= 1_000_000_000:
        return f"{currency_symbol}{value / 1_000_000_000:,.2f} B"
    elif abs(value) >= 1_000_000:
        return f"{currency_symbol}{value / 1_000_000:,.2f} M"
    elif abs(value) >= 1:
        return f"{currency_symbol}{value:,.2f}"
    elif abs(value) >= 0.0001:
        return f"{currency_symbol}{value:,.4f}"
    else:
        return f"{currency_symbol}{value:,.8f}"


def format_percentage(value: Optional[float]) -> str:
    """
    Format percentage values with appropriate +/- sign and two decimals.
    """
    if value is None or pd.isna(value):
        return "0.00%"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


# -----------------------------------------------------------------------------
# 5. DATA FETCHING WITH STREAMLIT CACHING & ERROR HANDLING
# -----------------------------------------------------------------------------
@st.cache_data(ttl=CACHE_TTL_MARKETS, show_spinner=False)
def fetch_market_data(
    coin_ids: List[str],
    vs_currency: str,
    api_key: str,
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Fetch live cryptocurrency market summary data from CoinGecko.
    
    Key Features:
    - Streamlit Caching: Minimizes redundant HTTP requests to stay well within
      CoinGecko's free-tier rate limits (approx 10-30 calls/minute).
    - Robust Exception Handling: Catches timeouts, connection failures,
      HTTP 429 rate limits, and JSON parsing errors.
      
    Returns:
        Tuple[Optional[pd.DataFrame], Optional[str]]:
            (DataFrame with cleaned market data, error_message if failed)
    """
    endpoint = f"{COINGECKO_BASE_URL}/coins/markets"
    params = {
        "vs_currency": vs_currency.lower(),
        "ids": ",".join(coin_ids),
        "order": "market_cap_desc",
        "per_page": len(coin_ids),
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h,7d",
    }
    headers = build_request_headers(api_key)

    try:
        response = requests.get(
            endpoint,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )

        # Handle HTTP 429 Rate Limiting specifically
        if response.status_code == 429:
            return None, (
                "CoinGecko API Rate Limit Reached (HTTP 429). "
                "The free demo API allows ~10-30 requests per minute. "
                "Please wait 60 seconds before refreshing, or provide a free Demo API key in the sidebar."
            )

        # Raise exception for 4xx/5xx status codes
        response.raise_for_status()
        raw_data = response.json()

        if not isinstance(raw_data, list) or len(raw_data) == 0:
            return None, "CoinGecko API returned an empty or invalid response format."

        # Convert to Pandas DataFrame
        df = pd.DataFrame(raw_data)

        # Verify critical columns exist and standardize them
        expected_cols = [
            "id", "symbol", "name", "image", "current_price",
            "market_cap", "market_cap_rank", "total_volume",
            "high_24h", "low_24h", "price_change_percentage_24h",
            "price_change_24h", "ath", "ath_change_percentage",
            "circulating_supply", "total_supply", "last_updated"
        ]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None

        # Clean symbols to uppercase
        df["symbol"] = df["symbol"].str.upper()

        return df, None

    except requests.exceptions.Timeout:
        return None, f"Network timeout after {REQUEST_TIMEOUT}s while contacting CoinGecko. Please check your connection."
    except requests.exceptions.ConnectionError:
        return None, "Unable to establish connection to CoinGecko API. Please verify your internet connection or proxy settings."
    except requests.exceptions.HTTPError as http_err:
        return None, f"CoinGecko HTTP Error: {http_err}"
    except Exception as general_err:
        return None, f"Unexpected error during data retrieval: {str(general_err)}"


@st.cache_data(ttl=CACHE_TTL_CHARTS, show_spinner=False)
def fetch_historical_chart_data(
    coin_id: str,
    vs_currency: str,
    days: str,
    api_key: str,
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Fetch historical price data for a single coin over 1, 7, or 30 days.
    
    CoinGecko Endpoint:
    GET /coins/{id}/market_chart?vs_currency={curr}&days={days}
    
    Response format:
    {
      "prices": [[timestamp_ms, price], ...],
      "market_caps": [[timestamp_ms, cap], ...],
      "total_volumes": [[timestamp_ms, vol], ...]
    }
    """
    endpoint = f"{COINGECKO_BASE_URL}/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": vs_currency.lower(),
        "days": days,
    }
    headers = build_request_headers(api_key)

    try:
        response = requests.get(
            endpoint,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 429:
            return None, (
                "Rate limit exceeded (HTTP 429) while fetching historical chart data. "
                "Please wait 60 seconds."
            )

        response.raise_for_status()
        data = response.json()

        prices = data.get("prices", [])
        if not prices:
            return None, f"No historical price records returned for {coin_id}."

        df_chart = pd.DataFrame(prices, columns=["timestamp_ms", "price"])
        # Convert timestamp in milliseconds to Pandas Datetime
        df_chart["datetime"] = pd.to_datetime(df_chart["timestamp_ms"], unit="ms")
        df_chart["price"] = pd.to_numeric(df_chart["price"], errors="coerce")
        df_chart.dropna(subset=["price"], inplace=True)

        return df_chart, None

    except requests.exceptions.Timeout:
        return None, "Chart request timed out. Please retry."
    except requests.exceptions.ConnectionError:
        return None, "Connection error while fetching historical chart."
    except requests.exceptions.HTTPError as http_err:
        return None, f"HTTP Error fetching chart data: {http_err}"
    except Exception as err:
        return None, f"Error parsing historical data: {str(err)}"


def get_mock_fallback_data(vs_currency: str) -> pd.DataFrame:
    """
    Provide realistic offline fallback market data.
    
    Portfolio Benefit:
    If an interviewer or recruiter runs this app while CoinGecko's public IP
    quota is temporarily exhausted, this fallback dataset allows them to
    evaluate all dashboard features, sorting, charting, and CSV export without crashing.
    """
    # Realistic multiplier for USD vs INR conversion
    fx = 87.0 if vs_currency.lower() == "inr" else 1.0

    mock_records = [
        {
            "id": "bitcoin", "symbol": "BTC", "name": "Bitcoin",
            "image": "https://assets.coingecko.com/coins/images/1/large/bitcoin.png",
            "current_price": 95200.0 * fx, "market_cap": 1880000000000.0 * fx,
            "market_cap_rank": 1, "total_volume": 42000000000.0 * fx,
            "high_24h": 96100.0 * fx, "low_24h": 94300.0 * fx,
            "price_change_percentage_24h": 2.45, "price_change_24h": 2280.0 * fx,
            "ath": 108900.0 * fx, "ath_change_percentage": -12.58,
            "circulating_supply": 19800000, "total_supply": 21000000,
            "last_updated": datetime.utcnow().isoformat(),
        },
        {
            "id": "ethereum", "symbol": "ETH", "name": "Ethereum",
            "image": "https://assets.coingecko.com/coins/images/279/large/ethereum.png",
            "current_price": 2740.0 * fx, "market_cap": 330000000000.0 * fx,
            "market_cap_rank": 2, "total_volume": 21000000000.0 * fx,
            "high_24h": 2810.0 * fx, "low_24h": 2690.0 * fx,
            "price_change_percentage_24h": -1.15, "price_change_24h": -31.8 * fx,
            "ath": 4878.0 * fx, "ath_change_percentage": -43.82,
            "circulating_supply": 120400000, "total_supply": 120400000,
            "last_updated": datetime.utcnow().isoformat(),
        },
        {
            "id": "binancecoin", "symbol": "BNB", "name": "BNB",
            "image": "https://assets.coingecko.com/coins/images/825/large/bnb-icon2_2x.png",
            "current_price": 645.0 * fx, "market_cap": 94000000000.0 * fx,
            "market_cap_rank": 3, "total_volume": 1400000000.0 * fx,
            "high_24h": 655.0 * fx, "low_24h": 638.0 * fx,
            "price_change_percentage_24h": 0.85, "price_change_24h": 5.4 * fx,
            "ath": 717.0 * fx, "ath_change_percentage": -10.04,
            "circulating_supply": 145000000, "total_supply": 145000000,
            "last_updated": datetime.utcnow().isoformat(),
        },
        {
            "id": "solana", "symbol": "SOL", "name": "Solana",
            "image": "https://assets.coingecko.com/coins/images/4128/large/solana.png",
            "current_price": 182.50 * fx, "market_cap": 87000000000.0 * fx,
            "market_cap_rank": 4, "total_volume": 4900000000.0 * fx,
            "high_24h": 188.0 * fx, "low_24h": 177.5 * fx,
            "price_change_percentage_24h": 5.12, "price_change_24h": 8.9 * fx,
            "ath": 259.96 * fx, "ath_change_percentage": -29.80,
            "circulating_supply": 477000000, "total_supply": 589000000,
            "last_updated": datetime.utcnow().isoformat(),
        },
        {
            "id": "ripple", "symbol": "XRP", "name": "XRP",
            "image": "https://assets.coingecko.com/coins/images/44/large/xrp-symbol-white-128.png",
            "current_price": 2.15 * fx, "market_cap": 122000000000.0 * fx,
            "market_cap_rank": 5, "total_volume": 7800000000.0 * fx,
            "high_24h": 2.28 * fx, "low_24h": 2.05 * fx,
            "price_change_percentage_24h": 7.42, "price_change_24h": 0.15 * fx,
            "ath": 3.84 * fx, "ath_change_percentage": -44.01,
            "circulating_supply": 57000000000, "total_supply": 99980000000,
            "last_updated": datetime.utcnow().isoformat(),
        },
        {
            "id": "dogecoin", "symbol": "DOGE", "name": "Dogecoin",
            "image": "https://assets.coingecko.com/coins/images/5/large/dogecoin.png",
            "current_price": 0.224 * fx, "market_cap": 33000000000.0 * fx,
            "market_cap_rank": 6, "total_volume": 2500000000.0 * fx,
            "high_24h": 0.235 * fx, "low_24h": 0.218 * fx,
            "price_change_percentage_24h": -3.20, "price_change_24h": -0.007 * fx,
            "ath": 0.731 * fx, "ath_change_percentage": -69.35,
            "circulating_supply": 147000000000, "total_supply": 147000000000,
            "last_updated": datetime.utcnow().isoformat(),
        },
        {
            "id": "cardano", "symbol": "ADA", "name": "Cardano",
            "image": "https://assets.coingecko.com/coins/images/975/large/cardano.png",
            "current_price": 0.74 * fx, "market_cap": 26000000000.0 * fx,
            "market_cap_rank": 7, "total_volume": 980000000.0 * fx,
            "high_24h": 0.77 * fx, "low_24h": 0.72 * fx,
            "price_change_percentage_24h": 1.65, "price_change_24h": 0.012 * fx,
            "ath": 3.09 * fx, "ath_change_percentage": -76.05,
            "circulating_supply": 35700000000, "total_supply": 45000000000,
            "last_updated": datetime.utcnow().isoformat(),
        },
    ]
    return pd.DataFrame(mock_records)


# -----------------------------------------------------------------------------
# 6. SIDEBAR: USER CONTROLS, SETTINGS & ATTRIBUTION
# -----------------------------------------------------------------------------
def render_sidebar() -> Tuple[str, List[str], str, bool]:
    """
    Renders the sidebar navigation and filter controls.
    Returns:
        (selected_currency_key, selected_coin_ids, user_api_key, force_refresh)
    """
    st.sidebar.title("🪙 CryptoPulse")
    st.sidebar.caption("Real-Time Cryptocurrency Market Tracker")
    st.sidebar.markdown("---")

    # 1. Currency Selector (USD vs INR)
    st.sidebar.subheader("💱 Fiat Currency")
    currency_choice = st.sidebar.radio(
        "Display prices in:",
        options=["USD ($)", "INR (₹)"],
        index=0,
        help="Select the base currency for all market valuations and charts.",
    )
    currency_key = "USD" if "USD" in currency_choice else "INR"

    st.sidebar.markdown("---")

    # 2. Cryptocurrency Selection
    st.sidebar.subheader("📋 Tracked Cryptocurrencies")
    # Default selection contains all 7 core required coins
    default_selected_ids = list(CORE_CRYPTOCURRENCIES.keys())
    all_coin_options = list(ALL_SUPPORTED_COINS.keys())

    selected_coin_ids = st.sidebar.multiselect(
        "Select coins to monitor:",
        options=all_coin_options,
        default=default_selected_ids,
        format_func=lambda cid: f"{ALL_SUPPORTED_COINS[cid]['name']} ({ALL_SUPPORTED_COINS[cid]['symbol']})",
        help="Choose any combination of cryptocurrencies. 7 core assets are preselected.",
    )

    # Ensure at least one coin is selected to prevent rendering errors
    if not selected_coin_ids:
        st.sidebar.warning("⚠️ Please select at least one cryptocurrency. Defaulting to Bitcoin.")
        selected_coin_ids = ["bitcoin"]

    st.sidebar.markdown("---")

    # 3. Data Refresh & Cache Invalidation
    st.sidebar.subheader("🔄 Live Cache Controls")
    force_refresh = st.sidebar.button(
        "Clear Cache & Refresh",
        use_container_width=True,
        help="Clears Streamlit cache to force an immediate fresh fetch from CoinGecko.",
    )
    if force_refresh:
        st.cache_data.clear()

    # 4. API Key Configuration & Status
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔑 CoinGecko API Status")
    
    existing_key = get_api_key()
    if existing_key:
        st.sidebar.success("✅ Demo API Key Configured")
        st.sidebar.caption("Using stored key from Streamlit secrets / environment.")
        active_api_key = existing_key
    else:
        st.sidebar.info("ℹ️ Running in Public Mode")
        with st.sidebar.expander("Add Free Demo API Key"):
            st.markdown(
                """
                CoinGecko provides a **free Demo API key** (~30 calls/min).
                1. Register at [coingecko.com/en/api](https://www.coingecko.com/en/api).
                2. Enter your key below or save it in `.streamlit/secrets.toml`.
                """
            )
            manual_key = st.text_input(
                "Demo API Key:",
                type="password",
                help="Starts with 'CG-'. Optional but provides higher request limits.",
            )
            active_api_key = manual_key.strip() if manual_key else ""

    # 5. CoinGecko Attribution Link (Mandatory Requirement)
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        <div style="font-size: 0.82rem; color: #94a3b8; text-align: center;">
            Data actively provided by<br>
            <a href="https://www.coingecko.com/en/api" target="_blank" style="color: #38bdf8; font-weight: 600;">
                🦎 CoinGecko Demo API
            </a>
            <br>Free tier rate limits apply.
        </div>
        """,
        unsafe_allow_html=True,
    )

    return currency_key, selected_coin_ids, active_api_key, force_refresh


# -----------------------------------------------------------------------------
# 7. DASHBOARD SECTIONS & CHARTS
# -----------------------------------------------------------------------------
def render_header_and_kpis(
    df: pd.DataFrame,
    curr_symbol: str,
    is_fallback: bool = False,
):
    """
    Renders top KPI metric cards summarizing market performance.
    """
    # Header Banner
    col_title, col_status = st.columns([3, 1])
    with col_title:
        st.title("🪙 Cryptocurrency Market Tracker")
        st.markdown(
            "Live tracking, multi-currency valuation, historical trends, and market cap analysis."
        )
    with col_status:
        badge_class = "badge-cached" if is_fallback else "badge-live"
        badge_text = "OFFLINE DEMO DATA" if is_fallback else "LIVE COINGECKO FEED"
        st.markdown(
            f"""
            <div style="text-align: right; margin-top: 18px;">
                <span class="badge-pill {badge_class}">● {badge_text}</span>
                <div style="font-size: 0.75rem; color: #888; margin-top: 4px;">
                    Updated: {datetime.now().strftime('%H:%M:%S')}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Top KPI Metrics (Bitcoin, Ethereum, Top 24h Gainer, Top 24h Loser)
    st.markdown("### 📌 Market Highlights")
    kpi_cols = st.columns(4)

    # 1. Bitcoin Price
    btc_row = df[df["id"] == "bitcoin"]
    with kpi_cols[0]:
        if not btc_row.empty:
            price = btc_row["current_price"].values[0]
            change = btc_row["price_change_percentage_24h"].values[0]
            st.metric(
                label="Bitcoin (BTC)",
                value=format_currency(price, curr_symbol),
                delta=f"{change:+.2f}% (24h)" if pd.notna(change) else None,
            )
        else:
            st.metric("Bitcoin (BTC)", "N/A")

    # 2. Ethereum Price
    eth_row = df[df["id"] == "ethereum"]
    with kpi_cols[1]:
        if not eth_row.empty:
            price = eth_row["current_price"].values[0]
            change = eth_row["price_change_percentage_24h"].values[0]
            st.metric(
                label="Ethereum (ETH)",
                value=format_currency(price, curr_symbol),
                delta=f"{change:+.2f}% (24h)" if pd.notna(change) else None,
            )
        else:
            st.metric("Ethereum (ETH)", "N/A")

    # 3. Top 24h Gainer
    valid_change = df.dropna(subset=["price_change_percentage_24h"])
    with kpi_cols[2]:
        if not valid_change.empty:
            top_gainer = valid_change.sort_values(by="price_change_percentage_24h", ascending=False).iloc[0]
            st.metric(
                label=f"🚀 Top Gainer ({top_gainer['symbol']})",
                value=format_currency(top_gainer["current_price"], curr_symbol),
                delta=f"+{top_gainer['price_change_percentage_24h']:.2f}%",
            )
        else:
            st.metric("🚀 Top Gainer", "N/A")

    # 4. Total Tracked Market Cap
    with kpi_cols[3]:
        total_mcap = df["market_cap"].sum()
        st.metric(
            label="🌐 Total Tracked M-Cap",
            value=format_currency(total_mcap, curr_symbol),
            delta=f"{len(df)} Assets",
            delta_color="off",
        )

    st.markdown("---")


def render_interactive_charts(df: pd.DataFrame, curr_symbol: str):
    """
    Renders Plotly interactive charts comparing market metrics.
    """
    st.subheader("📊 Market Visualizations & Comparisons")

    tab_mcap, tab_pct, tab_scatter = st.tabs([
        "💰 Market Capitalization",
        "📈 24h Price Change (%)",
        "🔄 Volume vs. Market Cap",
    ])

    # Tab 1: Market Capitalization Bar Chart
    with tab_mcap:
        sorted_mcap = df.sort_values(by="market_cap", ascending=True)
        fig_mcap = px.bar(
            sorted_mcap,
            x="market_cap",
            y="name",
            orientation="h",
            color="market_cap",
            color_continuous_scale="Viridis",
            labels={"market_cap": f"Market Capitalization ({curr_symbol})", "name": "Cryptocurrency"},
            title="Market Capitalization Comparison (Horizontal)",
        )
        fig_mcap.update_layout(
            height=400,
            margin=dict(l=20, r=20, t=40, b=20),
            coloraxis_showscale=False,
            template="plotly_dark",
        )
        st.plotly_chart(fig_mcap, use_container_width=True)

    # Tab 2: 24h Percentage Change Bar Chart (Green for positive, Red for negative)
    with tab_pct:
        sorted_change = df.sort_values(by="price_change_percentage_24h", ascending=True)
        colors = [
            "#22c55e" if val >= 0 else "#ef4444"
            for val in sorted_change["price_change_percentage_24h"]
        ]
        fig_pct = go.Figure(
            go.Bar(
                x=sorted_change["price_change_percentage_24h"],
                y=sorted_change["name"],
                orientation="h",
                marker_color=colors,
                text=[f"{val:+.2f}%" for val in sorted_change["price_change_percentage_24h"]],
                textposition="auto",
            )
        )
        fig_pct.update_layout(
            title="24-Hour Price Percentage Change (%)",
            xaxis_title="Percentage Change (%)",
            yaxis_title="Cryptocurrency",
            height=400,
            margin=dict(l=20, r=20, t=40, b=20),
            template="plotly_dark",
        )
        st.plotly_chart(fig_pct, use_container_width=True)

    # Tab 3: Trading Volume vs Market Cap Scatter
    with tab_scatter:
        fig_scatter = px.scatter(
            df,
            x="market_cap",
            y="total_volume",
            size="total_volume",
            color="price_change_percentage_24h",
            color_continuous_scale="RdYlGn",
            text="symbol",
            labels={
                "market_cap": f"Market Cap ({curr_symbol})",
                "total_volume": f"24h Volume ({curr_symbol})",
                "price_change_percentage_24h": "24h Change (%)",
            },
            title="Trading Volume vs. Market Capitalization (Bubble size = Volume)",
        )
        fig_scatter.update_traces(textposition="top center")
        fig_scatter.update_layout(
            height=420,
            margin=dict(l=20, r=20, t=40, b=20),
            template="plotly_dark",
        )
        st.plotly_chart(fig_scatter, use_container_width=True)


def render_historical_trends(
    df: pd.DataFrame,
    curr_code: str,
    curr_symbol: str,
    api_key: str,
):
    """
    Renders interactive historical price charts for 1 day, 7 days, and 30 days.
    """
    st.subheader("🕒 Historical Price Trends")
    st.markdown("Analyze historical price action over short and medium-term horizons.")

    col_select, col_days = st.columns([2, 2])

    with col_select:
        coin_options = df["id"].tolist()
        coin_names = {row["id"]: f"{row['name']} ({row['symbol']})" for _, row in df.iterrows()}
        selected_coin_id = st.selectbox(
            "Select asset for historical analysis:",
            options=coin_options,
            format_func=lambda cid: coin_names.get(cid, cid),
        )

    with col_days:
        timeframe = st.radio(
            "Select Timeframe:",
            options=["1 Day", "7 Days", "30 Days"],
            index=1,
            horizontal=True,
        )

    days_param = "1" if timeframe == "1 Day" else ("7" if timeframe == "7 Days" else "30")

    # Fetch chart data
    with st.spinner(f"Loading {timeframe} historical price data for {selected_coin_id}..."):
        chart_df, chart_err = fetch_historical_chart_data(
            coin_id=selected_coin_id,
            vs_currency=curr_code,
            days=days_param,
            api_key=api_key,
        )

    if chart_err or chart_df is None or chart_df.empty:
        st.warning(f"⚠️ {chart_err or 'Historical data unavailable at this moment.'}")
        # Generate synthetic smooth trend for demo preview if API limits hit
        st.info("Displaying simulated preview curve for visual demonstration:")
        timestamps = pd.date_range(end=datetime.now(), periods=50, freq="h")
        base_price = df[df["id"] == selected_coin_id]["current_price"].values[0] if not df[df["id"] == selected_coin_id].empty else 1000.0
        import numpy as np
        synthetic_prices = base_price * (1 + np.sin(np.linspace(0, 3.14, 50)) * 0.05)
        chart_df = pd.DataFrame({"datetime": timestamps, "price": synthetic_prices})

    # Render Plotly interactive line chart
    coin_label = coin_names.get(selected_coin_id, selected_coin_id)
    min_price = chart_df["price"].min()
    max_price = chart_df["price"].max()
    latest_price = chart_df["price"].iloc[-1]
    first_price = chart_df["price"].iloc[0]
    period_change_pct = ((latest_price - first_price) / first_price) * 100

    trend_color = "#22c55e" if period_change_pct >= 0 else "#ef4444"

    fig_line = go.Figure()
    fig_line.add_trace(
        go.Scatter(
            x=chart_df["datetime"],
            y=chart_df["price"],
            mode="lines",
            name=coin_label,
            line=dict(color=trend_color, width=2.5),
            fill="tozeroy",
            fillcolor="rgba(34, 197, 94, 0.08)" if period_change_pct >= 0 else "rgba(239, 68, 68, 0.08)",
            hovertemplate="<b>Date</b>: %{x|%b %d, %Y %H:%M}<br><b>Price</b>: "
            + curr_symbol
            + "%{y:,.2f}<extra></extra>",
        )
    )

    fig_line.update_layout(
        title=f"{coin_label} — {timeframe} Price Action ({period_change_pct:+.2f}%)",
        xaxis_title="Timeline",
        yaxis_title=f"Price ({curr_symbol})",
        height=450,
        margin=dict(l=20, r=20, t=40, b=20),
        template="plotly_dark",
    )

    st.plotly_chart(fig_line, use_container_width=True)

    # Timeframe summary statistics
    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    stat_col1.metric("Period Low", format_currency(min_price, curr_symbol))
    stat_col2.metric("Period High", format_currency(max_price, curr_symbol))
    stat_col3.metric("Period Change", f"{period_change_pct:+.2f}%")
    stat_col4.metric("Data Points", len(chart_df))


# -----------------------------------------------------------------------------
# 8. MAIN APPLICATION ORCHESTRATOR
# -----------------------------------------------------------------------------
def main():
    """
    Main application execution loop.
    """
    # 1. Render Sidebar and retrieve user inputs
    curr_key, selected_coin_ids, api_key, _ = render_sidebar()
    curr_meta = CURRENCY_CONFIG[curr_key]
    curr_code = curr_meta["code"]
    curr_symbol = curr_meta["symbol"]

    # 2. Fetch Market Data from CoinGecko API
    with st.spinner("Fetching latest cryptocurrency market metrics..."):
        df, error_msg = fetch_market_data(
            coin_ids=selected_coin_ids,
            vs_currency=curr_code,
            api_key=api_key,
        )

    # 3. Handle errors and fallback mode
    is_fallback = False
    if error_msg or df is None or df.empty:
        st.warning(f"⚠️ {error_msg}")
        st.info(
            "💡 Switching to offline demonstration dataset so you can continue testing "
            "all filters, interactive Plotly visualizations, and CSV exports."
        )
        df = get_mock_fallback_data(vs_currency=curr_code)
        # Filter fallback to user selection
        df = df[df["id"].isin(selected_coin_ids)]
        is_fallback = True

    # 4. Render Header and KPIs
    render_header_and_kpis(df, curr_symbol, is_fallback=is_fallback)

    # 5. Search, Filter & Sort Controls
    st.subheader("🔍 Market Overview & Data Explorer")
    filter_col1, filter_col2, filter_col3 = st.columns([2, 1.5, 1])

    with filter_col1:
        search_query = st.text_input(
            "Search by Asset Name or Symbol:",
            placeholder="e.g. Bitcoin, ETH, Solana...",
        ).strip().lower()

    with filter_col2:
        sort_by = st.selectbox(
            "Sort Table By:",
            options=[
                "Market Cap Rank (Ascending)",
                "Current Price (High to Low)",
                "Current Price (Low to High)",
                "24h Price Change % (Highest First)",
                "24h Price Change % (Lowest First)",
                "24h Trading Volume (High to Low)",
            ],
            index=0,
        )

    with filter_col3:
        st.write("")  # Alignment spacing
        st.write("")
        # CSV Export Button placed near table controls
        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Export CSV",
            data=csv_data,
            file_name=f"cryptopulse_market_data_{curr_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            help="Download currently loaded market dataset as a standard CSV file.",
            use_container_width=True,
        )

    # 6. Apply Search Filtering
    filtered_df = df.copy()
    if search_query:
        filtered_df = filtered_df[
            filtered_df["name"].str.lower().str.contains(search_query)
            | filtered_df["symbol"].str.lower().str.contains(search_query)
        ]

    # 7. Apply Sorting
    if sort_by == "Market Cap Rank (Ascending)":
        filtered_df = filtered_df.sort_values(by="market_cap_rank", ascending=True)
    elif sort_by == "Current Price (High to Low)":
        filtered_df = filtered_df.sort_values(by="current_price", ascending=False)
    elif sort_by == "Current Price (Low to High)":
        filtered_df = filtered_df.sort_values(by="current_price", ascending=True)
    elif sort_by == "24h Price Change % (Highest First)":
        filtered_df = filtered_df.sort_values(by="price_change_percentage_24h", ascending=False)
    elif sort_by == "24h Price Change % (Lowest First)":
        filtered_df = filtered_df.sort_values(by="price_change_percentage_24h", ascending=True)
    elif sort_by == "24h Trading Volume (High to Low)":
        filtered_df = filtered_df.sort_values(by="total_volume", ascending=False)

    # 8. Format Data for Clean Table Display
    display_df = filtered_df.copy()
    display_df["Rank"] = display_df["market_cap_rank"].fillna("-").astype(str)
    display_df["Asset"] = display_df["name"] + " (" + display_df["symbol"] + ")"
    display_df["Price"] = display_df["current_price"].apply(lambda v: format_currency(v, curr_symbol))
    display_df["24h Change"] = display_df["price_change_percentage_24h"].apply(format_percentage)
    display_df["24h High"] = display_df["high_24h"].apply(lambda v: format_currency(v, curr_symbol))
    display_df["24h Low"] = display_df["low_24h"].apply(lambda v: format_currency(v, curr_symbol))
    display_df["24h Volume"] = display_df["total_volume"].apply(lambda v: format_currency(v, curr_symbol))
    display_df["Market Cap"] = display_df["market_cap"].apply(lambda v: format_currency(v, curr_symbol))

    table_cols = [
        "Rank", "Asset", "Price", "24h Change", "24h High", "24h Low", "24h Volume", "Market Cap"
    ]
    st.dataframe(
        display_df[table_cols],
        use_container_width=True,
        hide_index=True,
    )
    st.caption(f"Showing {len(filtered_df)} of {len(df)} tracked cryptocurrency assets.")

    st.markdown("---")

    # 9. Main Visualizations
    render_interactive_charts(filtered_df if not filtered_df.empty else df, curr_symbol)

    st.markdown("---")

    # 10. Historical Price Trends
    render_historical_trends(df, curr_code, curr_symbol, api_key)

    # 11. Portfolio & Educational Technical Deep-Dive
    with st.expander("🔬 Deep Dive: Market Health & Technical Metrics"):
        st.markdown(
            """
            This section highlights additional institutional metrics fetched from the CoinGecko API:
            - **All-Time High (ATH)**: The peak recorded valuation of the asset and its current percentage drawdown.
            - **Circulating Supply vs Total Supply**: Insights into token inflation, issuance limits, and dilution risk.
            """
        )
        tech_cols = [
            "symbol", "name", "current_price", "ath", "ath_change_percentage",
            "circulating_supply", "total_supply"
        ]
        tech_df = filtered_df[tech_cols].copy()
        tech_df["Price"] = tech_df["current_price"].apply(lambda v: format_currency(v, curr_symbol))
        tech_df["ATH"] = tech_df["ath"].apply(lambda v: format_currency(v, curr_symbol))
        tech_df["ATH Drawdown"] = tech_df["ath_change_percentage"].apply(format_percentage)
        tech_df["Circulating Supply"] = tech_df["circulating_supply"].apply(
            lambda v: f"{v:,.0f}" if pd.notna(v) else "N/A"
        )
        tech_df["Total Supply"] = tech_df["total_supply"].apply(
            lambda v: f"{v:,.0f}" if pd.notna(v) else "N/A"
        )
        st.dataframe(
            tech_df[["name", "symbol", "Price", "ATH", "ATH Drawdown", "Circulating Supply", "Total Supply"]],
            use_container_width=True,
            hide_index=True,
        )

    # 12. Footer with CoinGecko Attribution
    st.markdown(
        """
        <div class="footer-container">
            <p>
                🪙 <strong>CryptoPulse</strong> — Cryptocurrency Market Intelligence Dashboard<br>
                Market data proudly powered by <a href="https://www.coingecko.com/en/api" target="_blank">CoinGecko REST API</a>.
                Designed for Python Data Science & Analytics Portfolio.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# 9. APPLICATION ENTRY POINT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    main()
