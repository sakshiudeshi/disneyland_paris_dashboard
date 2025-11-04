import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.disney_api import DisneyPriceAPI
from src.models.tier_mapper import TierMapper
from src.storage.price_history import PriceHistoryStore
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

st.set_page_config(
    page_title="Disneyland Paris Pricing Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

PRODUCT_TYPES = {
    "1-day-1-park": "1 Day 1 Park",
    "1-day-2-parks": "1 Day 2 Parks",
    "2-day-2-parks": "2 Day 2 Parks",
    "3-day-2-parks": "3 Day 2 Parks",
    "4-day-2-parks": "4 Day 2 Parks"
}

TIER_COLORS = {
    "Low Peak": "#2ecc71",
    "Shoulder (Normal)": "#3498db",
    "Peak": "#f39c12",
    "Super Peak": "#e74c3c",
    "Mega Peak": "#8e44ad"
}

PRICE_OPTIONS = {
    "Adult": ("price_adult", "Adult Price (EUR)"),
    "Child": ("price_child", "Child Price (EUR)")
}


@st.cache_resource
def get_api_client():
    """Get cached API client."""
    return DisneyPriceAPI()


@st.cache_resource
def get_storage():
    """Get cached storage instance."""
    return PriceHistoryStore()


def fetch_and_process_data(
    api: DisneyPriceAPI,
    product_type: str,
    start_date: str,
    end_date: str,
    save_snapshot: bool = True
) -> tuple:
    """
    Fetch pricing data and map to tiers.

    Returns:
        Tuple of (DataFrame, TierMapper, raw_data)
    """
    try:
        logger.info(f"Fetching {product_type} from {start_date} to {end_date}")
        data = api.fetch_prices(start_date, end_date, product_types=[product_type])

        if save_snapshot:
            storage = get_storage()
            storage.save_snapshot(product_type, data)

        mapper = TierMapper(product_type)
        df = mapper.map_calendar(data)

        if save_snapshot:
            storage.save_mapped_data(product_type, df)

        return df, mapper, data

    except Exception as e:
        logger.error(f"Error fetching data: {str(e)}")
        st.error(f"Failed to fetch data: {str(e)}")
        return None, None, None


def create_calendar_heatmap(df: pd.DataFrame, product_name: str) -> go.Figure:
    """Create calendar heatmap visualization."""
    df_copy = df.copy()
    df_copy["date"] = pd.to_datetime(df_copy["date"])
    df_copy["year"] = df_copy["date"].dt.year
    df_copy["week"] = df_copy["date"].dt.isocalendar().week
    df_copy["weekday"] = df_copy["date"].dt.dayofweek

    fig = px.density_heatmap(
        df_copy,
        x="week",
        y="weekday",
        z="price_adult",
        color_continuous_scale="RdYlGn_r",
        labels={"price_adult": "Adult Price (EUR)", "week": "Week", "weekday": "Day"},
        title=f"{product_name} - Price Calendar Heatmap"
    )

    return fig


def create_tier_distribution(df: pd.DataFrame) -> go.Figure:
    """Create tier distribution chart."""
    tier_counts = df["globaltix_tier"].value_counts()

    fig = go.Figure(data=[
        go.Bar(
            x=tier_counts.index,
            y=tier_counts.values,
            marker_color=[TIER_COLORS.get(t, "#95a5a6") for t in tier_counts.index]
        )
    ])

    fig.update_layout(
        title=dict(text="Days per Tier", font=dict(color='white')),
        xaxis_title="GlobalTix Tier",
        yaxis_title="Number of Days",
        showlegend=False,
        plot_bgcolor='#0e1117',
        paper_bgcolor='#0e1117',
        font=dict(color='white'),
        xaxis=dict(gridcolor='#262730'),
        yaxis=dict(gridcolor='#262730')
    )

    return fig


def create_price_timeline(df: pd.DataFrame, product_name: str, price_column: str, price_label: str) -> go.Figure:
    """Create price timeline with tier colors for selected price type."""
    df_copy = df.copy()
    df_copy["date"] = pd.to_datetime(df_copy["date"])

    # Drop rows without the selected price to avoid plotting gaps
    df_copy = df_copy[pd.notna(df_copy[price_column])]

    fig = go.Figure()

    for tier in df_copy["globaltix_tier"].unique():
        if pd.notna(tier):
            tier_data = df_copy[df_copy["globaltix_tier"] == tier]
            fig.add_trace(go.Scatter(
                x=tier_data["date"],
                y=tier_data[price_column],
                mode="markers+lines",
                name=tier,
                marker=dict(color=TIER_COLORS.get(tier, "#95a5a6"), size=8),
                line=dict(color=TIER_COLORS.get(tier, "#95a5a6"), width=2)
            ))

    fig.update_layout(
        title=dict(text=f"{product_name} - Price Timeline", font=dict(color='white')),
        xaxis_title="Date",
        yaxis_title=price_label,
        hovermode="x unified",
        plot_bgcolor='#0e1117',
        paper_bgcolor='#0e1117',
        font=dict(color='white'),
        xaxis=dict(gridcolor='#262730'),
        yaxis=dict(gridcolor='#262730'),
        legend=dict(
            bgcolor='#262730',
            bordercolor='#3498db',
            borderwidth=1
        )
    )

    return fig


def create_monthly_heatmap(df: pd.DataFrame, month_str: str, price_column: str, price_label: str) -> go.Figure:
    """Create calendar heatmap for a specific month and price type."""
    from datetime import datetime
    import calendar

    try:
        # Parse month string to get year and month
        year, month = map(int, month_str.split('-'))
    except (ValueError, AttributeError):
        logger.error(f"Invalid month string: {month_str}")
        return None

    # Get number of days in the month
    num_days = calendar.monthrange(year, month)[1]

    # Get the first day of the month to know which weekday it starts on
    first_date = datetime(year, month, 1)
    first_weekday = first_date.weekday()  # Monday=0, Sunday=6

    # Get today's date for comparison
    today = datetime.now().date()

    # Filter data for this month (handle empty dataframe)
    if df.empty:
        df_month = pd.DataFrame()
    else:
        df_month = df[df["date"].dt.to_period("M").astype(str) == month_str].copy()
        if not df_month.empty:
            df_month[price_column] = pd.to_numeric(df_month[price_column], errors="coerce")

    # Create a dictionary of existing data
    data_dict = {}
    if not df_month.empty:
        for _, row in df_month.iterrows():
            day = row["date"].day
            price_value = row.get(price_column)
            if pd.notna(price_value):
                data_dict[day] = {
                    "price": price_value,
                    "tier": row["globaltix_tier"],
                    "date_str": row["date"].strftime("%Y-%m-%d")
                }

    # Direct color mapping - no interpolation
    def get_tier_color(tier_name, date_obj):
        """Get the exact color for a tier."""
        if tier_name and tier_name in TIER_COLORS:
            return TIER_COLORS[tier_name]
        elif date_obj < today:
            return "#4a4a4a"  # NA - past date with no data
        else:
            return "#1a1a1a"  # Future date with no data

    # Create a proper calendar grid with ALL days of the month
    calendar_data = []
    hover_text = []
    display_text = []
    cell_colors = []

    for day in range(1, num_days + 1):
        date = datetime(year, month, day).date()
        weekday = datetime(year, month, day).weekday()

        # Calculate which week (row) this day falls in
        days_from_start = day - 1
        week_num = (days_from_start + first_weekday) // 7

        if day in data_dict:
            # We have data for this day
            tier = data_dict[day]["tier"]
            color = get_tier_color(tier, date)
            price_display = data_dict[day]['price']
            hover = (
                f"Date: {data_dict[day]['date_str']}"
                f"<br>{price_label}: {price_display:.0f} EUR"
                f"<br>Tier: {tier}"
            )
            text = str(day)
        elif date < today:
            # Past date with no data - mark as NA
            tier = None
            color = get_tier_color(None, date)
            hover = f"Date: {date.strftime('%Y-%m-%d')}<br>No data available"
            text = "NA"
        else:
            # Future date with no data yet - mark as empty
            tier = None
            color = get_tier_color(None, date)
            hover = f"Date: {date.strftime('%Y-%m-%d')}<br>No data yet"
            text = str(day)

        calendar_data.append({
            "day": day,
            "weekday": weekday,
            "week": week_num
        })
        hover_text.append(hover)
        display_text.append(text)
        cell_colors.append(color)

    cal_df = pd.DataFrame(calendar_data)
    weeks_in_view = (cal_df["week"].max() + 1) if not cal_df.empty else 1
    row_height = 90  # controls how tall each calendar row appears
    fig_height = 80 + weeks_in_view * row_height
    cell_size = row_height * 0.75

    # Create individual scatter points for each day with direct color assignment
    fig = go.Figure()

    for idx, row in cal_df.iterrows():
        fig.add_trace(go.Scatter(
            x=[row["weekday"]],
            y=[row["week"]],
            mode="markers+text",
            marker=dict(
                size=cell_size,
                color=cell_colors[idx],
                symbol="square",
                line=dict(width=1, color="#262730")
            ),
            text=display_text[idx],
            textposition="middle center",
            textfont=dict(size=12, color="white", family="Arial"),
            hovertext=hover_text[idx],
            hoverinfo="text",
            showlegend=False
        ))

    fig.update_xaxes(
        tickmode='array',
        tickvals=[0, 1, 2, 3, 4, 5, 6],
        ticktext=['M', 'T', 'W', 'T', 'F', 'S', 'S'],
        side='top',
        tickfont=dict(color='white'),
        range=[-0.5, 6.5],
        showgrid=False,
        zeroline=False
    )

    fig.update_yaxes(
        autorange="reversed",
        range=[-0.5, weeks_in_view - 0.5],
        visible=False,
        showgrid=False,
        zeroline=False
    )

    fig.update_layout(
        title=dict(
            text=f"📅 {month_str}",
            font=dict(color='white')
        ),
        height=fig_height,
        margin=dict(l=20, r=20, t=60, b=20),
        plot_bgcolor='#0e1117',
        paper_bgcolor='#0e1117',
        hovermode='closest'
    )

    return fig


def display_monthly_recommendations(
    mapper: TierMapper,
    df: pd.DataFrame,
    month_str: str,
    price_column: str,
    price_label: str
):
    """Display monthly tier recommendations for the selected price type."""
    monthly = mapper.get_monthly_recommendations(df, price_column=price_column)

    # Filter to selected month
    month_data = monthly[monthly["month"] == month_str]

    st.subheader(f"{price_label} Recommendations: {month_str}")
    st.markdown("*Recommended price is the 80th percentile for each tier in that month*")

    if month_data.empty:
        st.info(f"No data available for {month_str}")
        return

    # Create a formatted table
    display_data = []
    for _, row in month_data.iterrows():
        display_data.append({
            "Tier": row["tier"],
            price_label: f"{row['recommended_price']:.2f}",
            "Price Range (EUR)": f"{row['min_price']:.0f} - {row['max_price']:.0f}",
            "Dates": row["dates"]
        })

    display_df = pd.DataFrame(display_data)

    # Apply color styling
    def color_tier_row(row):
        tier_name = row["Tier"]
        color = TIER_COLORS.get(tier_name, "#ffffff")
        return [f"background-color: {color}; color: white; font-weight: bold;"] + [""] * (len(row) - 1)

    styled = display_df.style.apply(color_tier_row, axis=1)

    st.dataframe(styled, width="stretch", hide_index=True)

    # Show monthly heatmap
    heatmap_fig = create_monthly_heatmap(df, month_str, price_column, price_label)
    if heatmap_fig:
        st.plotly_chart(heatmap_fig, use_container_width=True)


def main():
    st.title("Disneyland Paris Pricing Dashboard")
    st.markdown("Map Disney pricing to GlobalTix tiers")

    api = get_api_client()

    st.sidebar.header("Configuration")

    # Single product selector
    selected_product = st.sidebar.selectbox(
        "Select Product",
        options=list(PRODUCT_TYPES.keys()),
        format_func=lambda x: PRODUCT_TYPES[x],
        index=0
    )

    price_choice = st.sidebar.radio(
        "Price Type",
        options=list(PRICE_OPTIONS.keys()),
        index=0,
        horizontal=True
    )
    price_column, price_label = PRICE_OPTIONS[price_choice]

    # Fixed date range: today to 6 months in future
    start_date = datetime.now().date()
    end_date = (datetime.now() + timedelta(days=180)).date()

    fetch_new = st.sidebar.button("Fetch New Data", type="primary")

    use_cached = st.sidebar.checkbox("Use Cached Data", value=True)

    storage = get_storage()

    # Check if data already fetched today
    already_fetched_today = storage.has_snapshot_for_today(selected_product)

    # Fetch or load data
    if fetch_new or not use_cached:
        if fetch_new and already_fetched_today:
            st.sidebar.info("Data already fetched today. Using today's snapshot.")
            # Load the latest snapshot instead
            raw_data = storage.load_latest_snapshot(selected_product)
            if raw_data:
                mapper = TierMapper(selected_product)
                df = mapper.map_calendar(raw_data)
                st.session_state["current_data"] = (df, mapper, raw_data, selected_product)
            else:
                st.error("Failed to load cached data")
                return
        elif fetch_new:
            with st.spinner("Fetching pricing data..."):
                df, mapper, raw_data = fetch_and_process_data(
                    api,
                    selected_product,
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d"),
                    save_snapshot=True
                )
                if df is not None:
                    st.session_state["current_data"] = (df, mapper, raw_data, selected_product)
                    st.success("Data fetched successfully")
                else:
                    st.error("Failed to fetch data")
                    return
        else:
            # Use cached data when checkbox is checked
            if "current_data" not in st.session_state:
                st.info("No cached data. Click 'Fetch New Data' to load pricing information.")
                return
            df, mapper, raw_data, cached_product = st.session_state["current_data"]

            # If product changed, need to fetch new data
            if cached_product != selected_product:
                st.warning("Product changed. Please click 'Fetch New Data' to load new data.")
                return
    else:
        # Use cached data when checkbox is not checked
        if "current_data" not in st.session_state:
            st.info("No cached data. Click 'Fetch New Data' to load pricing information.")
            return
        df, mapper, raw_data, cached_product = st.session_state["current_data"]

        # If product changed, need to fetch new data
        if cached_product != selected_product:
            st.warning("Product changed. Please click 'Fetch New Data' to load new data.")
            return

    product_name = PRODUCT_TYPES[selected_product]

    # Filter data to show only today to 6 months in future
    df["date"] = pd.to_datetime(df["date"])
    today = pd.Timestamp.now().normalize()
    six_months_future = today + pd.Timedelta(days=180)
    df = df[(df["date"] >= today) & (df["date"] <= six_months_future)].copy()

    for price_col in ("price_adult", "price_child"):
        if price_col in df.columns:
            df[price_col] = pd.to_numeric(df[price_col], errors="coerce")

    # Get available months
    available_months = sorted(df["date"].dt.to_period("M").astype(str).unique())

    # Month selector
    selected_month = st.sidebar.selectbox(
        "Select Month",
        options=available_months,
        index=0
    )

    st.sidebar.markdown("---")
    st.sidebar.caption("Disneyland Paris Pricing Dashboard v2.0")

    # Filter data for selected month
    df_month = df[df["date"].dt.to_period("M").astype(str) == selected_month].copy()
    if price_column not in df_month.columns:
        df_month[price_column] = pd.NA

    # Display metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Product", product_name)
    with col2:
        st.metric("Month", selected_month)
    with col3:
        avg_price = df_month[price_column].mean()
        avg_display = f"{avg_price:.2f} EUR" if pd.notna(avg_price) else "No data"
        st.metric(f"Avg {price_choice} Price", avg_display)

    # Display date range and quartile information
    st.markdown("---")
    info_col1, info_col2 = st.columns(2)

    with info_col1:
        st.markdown("### Date Range Analyzed")
        min_date = df["date"].min().strftime("%Y-%m-%d") if not df.empty else "N/A"
        max_date = df["date"].max().strftime("%Y-%m-%d") if not df.empty else "N/A"
        total_days = len(df) if not df.empty else 0
        st.markdown(f"**From:** {min_date}")
        st.markdown(f"**To:** {max_date}")
        st.markdown(f"**Total Days:** {total_days}")

    with info_col2:
        st.markdown(f"### {price_choice} Price Quartiles (Full Dataset)")
        if not df.empty and df[price_column].notna().any():
            prices = df[price_column].dropna()
            q0 = prices.min()
            q25 = prices.quantile(0.25)
            q50 = prices.quantile(0.50)
            q75 = prices.quantile(0.75)
            q100 = prices.max()
            st.markdown(f"**Min (0%):** {q0:.2f} EUR")
            st.markdown(f"**Q1 (25%):** {q25:.2f} EUR")
            st.markdown(f"**Median (50%):** {q50:.2f} EUR")
            st.markdown(f"**Q3 (75%):** {q75:.2f} EUR")
            st.markdown(f"**Max (100%):** {q100:.2f} EUR")
        else:
            st.markdown("No price data available")

    st.markdown("---")

    # Price timeline for selected month
    if df_month[price_column].notna().any():
        st.plotly_chart(
            create_price_timeline(
                df_month,
                f"{product_name} - {selected_month}",
                price_column,
                price_label
            ),
            use_container_width=True
        )
    else:
        st.info(f"No {price_choice.lower()} price data available for {selected_month}.")

    # Tier distribution for selected month
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(create_tier_distribution(df_month), use_container_width=True)
    with col2:
        # Show tier legend
        st.markdown("### Tier Legend")
        for tier, color in TIER_COLORS.items():
            st.markdown(f'<div style="background-color: {color}; color: white; padding: 5px; margin: 2px; border-radius: 3px;">{tier}</div>', unsafe_allow_html=True)

    # Monthly recommendations with heatmap
    display_monthly_recommendations(
        mapper,
        df,
        selected_month,
        price_column,
        price_label
    )

    # Detailed data
    with st.expander("View Detailed Data"):
        st.dataframe(df_month, width="stretch")


if __name__ == "__main__":
    main()
