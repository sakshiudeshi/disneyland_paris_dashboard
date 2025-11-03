from enum import Enum
from typing import Dict, List, Optional
import pandas as pd
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class PriceTier(Enum):
    """GlobalTix pricing tiers."""
    LOW_PEAK = "Low Peak"
    SHOULDER = "Shoulder (Normal)"
    PEAK = "Peak"
    SUPER_PEAK = "Super Peak"
    MEGA_PEAK = "Mega Peak"


class TierMapper:
    """Maps Disney pricing data to GlobalTix pricing tiers."""

    def __init__(self, product_type: str):
        """
        Initialize tier mapper for a specific product type.

        Args:
            product_type: Product type identifier (e.g., "1-day-1-park")
        """
        self.product_type = product_type
        self.thresholds = None

    def calculate_thresholds(self, pricing_data: Dict) -> Dict[PriceTier, tuple]:
        """
        Calculate price thresholds based on statistical analysis of pricing data.

        Args:
            pricing_data: Pricing calendar data from Disney API

        Returns:
            Dictionary mapping tiers to (min_price, max_price) tuples
        """
        calendar = pricing_data.get("calendar", [])
        if not calendar:
            logger.warning("No calendar data available for threshold calculation")
            self.thresholds = {}
            return {}

        prices = []
        for day in calendar:
            products = day.get("products", {})
            if self.product_type in products:
                price_adult = products[self.product_type].get("priceAdult")
                if price_adult:
                    prices.append(price_adult)

        if not prices:
            logger.warning(f"No prices found for {self.product_type}")
            self.thresholds = {}
            return {}

        prices_series = pd.Series(prices)
        min_price = prices_series.min()
        max_price = prices_series.max()

        percentile_20 = prices_series.quantile(0.20)
        percentile_40 = prices_series.quantile(0.40)
        percentile_60 = prices_series.quantile(0.60)
        percentile_80 = prices_series.quantile(0.80)

        self.thresholds = {
            PriceTier.LOW_PEAK: (min_price, percentile_20),
            PriceTier.SHOULDER: (percentile_20, percentile_40),
            PriceTier.PEAK: (percentile_40, percentile_60),
            PriceTier.SUPER_PEAK: (percentile_60, percentile_80),
            PriceTier.MEGA_PEAK: (percentile_80, max_price)
        }

        logger.info(f"Calculated thresholds for {self.product_type}:")
        for tier, (min_p, max_p) in self.thresholds.items():
            logger.info(f"  {tier.value}: {min_p:.2f} - {max_p:.2f} EUR")

        return self.thresholds

    def set_custom_thresholds(self, thresholds: Dict[PriceTier, tuple]):
        """
        Set custom price thresholds.

        Args:
            thresholds: Dictionary mapping tiers to (min_price, max_price) tuples
        """
        self.thresholds = thresholds
        logger.info(f"Custom thresholds set for {self.product_type}")

    def map_price_to_tier(self, price: float) -> Optional[PriceTier]:
        """
        Map a price to a GlobalTix tier.

        Args:
            price: Adult ticket price in EUR

        Returns:
            Corresponding PriceTier or None if thresholds not set
        """
        if not self.thresholds:
            logger.warning("Thresholds not set. Call calculate_thresholds first.")
            return None

        for tier, (min_price, max_price) in self.thresholds.items():
            if min_price <= price <= max_price:
                return tier

        logger.warning(f"Price {price} does not fall within any tier")
        return None

    def map_calendar(self, pricing_data: Dict) -> pd.DataFrame:
        """
        Map entire pricing calendar to tiers.

        Args:
            pricing_data: Pricing calendar data from Disney API

        Returns:
            DataFrame with dates, prices, and assigned tiers
        """
        if not self.thresholds:
            logger.info("Calculating thresholds from data")
            self.calculate_thresholds(pricing_data)

        calendar = pricing_data.get("calendar", [])
        rows = []

        for day in calendar:
            date = day.get("date")
            products = day.get("products", {})

            if self.product_type in products:
                product_data = products[self.product_type]
                price_adult = product_data.get("priceAdult")
                price_child = product_data.get("priceChild")
                disney_range = product_data.get("range")
                available = product_data.get("available")

                tier = self.map_price_to_tier(price_adult) if price_adult else None

                rows.append({
                    "date": date,
                    "price_adult": price_adult,
                    "price_child": price_child,
                    "disney_range": disney_range,
                    "available": available,
                    "globaltix_tier": tier.value if tier else None
                })

        df = pd.DataFrame(rows)
        logger.info(f"Mapped {len(df)} days to tiers for {self.product_type}")

        return df

    def get_monthly_recommendations(
        self,
        df: pd.DataFrame,
        price_column: str = "price_adult"
    ) -> pd.DataFrame:
        """
        Generate month-level tier recommendations showing each tier's price and dates.

        Args:
            df: DataFrame from map_calendar
            price_column: Column containing the price to summarize

        Returns:
            DataFrame with price recommendations for each tier per month
        """
        df["date"] = pd.to_datetime(df["date"])
        df["year_month"] = df["date"].dt.to_period("M").astype(str)

        results = []

        for month in df["year_month"].unique():
            month_data = df[df["year_month"] == month]

            for tier in PriceTier:
                tier_data = month_data[
                    (month_data["globaltix_tier"] == tier.value)
                    & pd.notna(month_data[price_column])
                ]

                if len(tier_data) > 0:
                    dates = tier_data["date"].dt.strftime("%Y-%m-%d").tolist()
                    date_ranges = self._format_date_ranges(dates)

                    results.append({
                        "month": month,
                        "tier": tier.value,
                        "recommended_price": round(tier_data[price_column].median(), 2),
                        "min_price": tier_data[price_column].min(),
                        "max_price": tier_data[price_column].max(),
                        "num_days": len(tier_data),
                        "dates": date_ranges
                    })

        result_df = pd.DataFrame(results)
        logger.info(f"Generated monthly recommendations for {len(result_df)} month-tier combinations")

        return result_df

    def _format_date_ranges(self, dates: List[str]) -> str:
        """
        Format list of dates into readable date ranges.

        Args:
            dates: List of date strings in YYYY-MM-DD format

        Returns:
            Formatted string like "Nov 1-3, 8-10, 15"
        """
        from datetime import datetime, timedelta

        if not dates:
            return ""

        date_objs = sorted([datetime.strptime(d, "%Y-%m-%d") for d in dates])

        ranges = []
        start = date_objs[0]
        end = date_objs[0]

        for i in range(1, len(date_objs)):
            if date_objs[i] - end == timedelta(days=1):
                end = date_objs[i]
            else:
                if start == end:
                    ranges.append(start.strftime("%-d"))
                else:
                    ranges.append(f"{start.strftime('%-d')}-{end.strftime('%-d')}")
                start = date_objs[i]
                end = date_objs[i]

        if start == end:
            ranges.append(start.strftime("%-d"))
        else:
            ranges.append(f"{start.strftime('%-d')}-{end.strftime('%-d')}")

        month_name = date_objs[0].strftime("%b")
        return f"{month_name} {', '.join(ranges)}"

    def detect_price_alerts(
        self,
        df: pd.DataFrame,
        threshold_pct: float = 20.0
    ) -> List[Dict]:
        """
        Detect significant price changes or tier boundary crossings.

        Args:
            df: DataFrame from map_calendar
            threshold_pct: Percentage change threshold for alerts

        Returns:
            List of alert dictionaries
        """
        df = df.sort_values("date").copy()
        df["price_change_pct"] = df["price_adult"].pct_change(fill_method=None) * 100
        df["tier_change"] = df["globaltix_tier"] != df["globaltix_tier"].shift(1)

        alerts = []

        for idx, row in df.iterrows():
            if abs(row.get("price_change_pct", 0)) >= threshold_pct:
                alerts.append({
                    "date": row["date"],
                    "type": "price_spike",
                    "message": f"Price changed by {row['price_change_pct']:.1f}%",
                    "price": row["price_adult"],
                    "tier": row["globaltix_tier"]
                })

            if row.get("tier_change") and idx > 0:
                prev_tier = df.loc[idx - 1, "globaltix_tier"]
                alerts.append({
                    "date": row["date"],
                    "type": "tier_change",
                    "message": f"Tier changed from {prev_tier} to {row['globaltix_tier']}",
                    "price": row["price_adult"],
                    "tier": row["globaltix_tier"]
                })

        logger.info(f"Detected {len(alerts)} price alerts")

        return alerts
