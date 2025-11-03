import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class PriceHistoryStore:
    """Store and retrieve historical pricing data."""

    def __init__(self, data_dir: str = "data"):
        """
        Initialize price history store.

        Args:
            data_dir: Directory to store historical data files
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        logger.info(f"Initialized price history store at {self.data_dir}")

    def save_snapshot(
        self,
        product_type: str,
        pricing_data: Dict,
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        Save a snapshot of pricing data.

        Args:
            product_type: Product type identifier
            pricing_data: Pricing data from API
            timestamp: Optional timestamp (default: now)

        Returns:
            Path to saved file
        """
        if timestamp is None:
            timestamp = datetime.now()

        filename = f"{product_type}_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.data_dir / filename

        with open(filepath, "w") as f:
            json.dump({
                "timestamp": timestamp.isoformat(),
                "product_type": product_type,
                "data": pricing_data
            }, f, indent=2)

        logger.info(f"Saved snapshot to {filepath}")
        return str(filepath)

    def save_mapped_data(
        self,
        product_type: str,
        df: pd.DataFrame,
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        Save mapped pricing data with tiers.

        Args:
            product_type: Product type identifier
            df: DataFrame with mapped tier data
            timestamp: Optional timestamp (default: now)

        Returns:
            Path to saved file
        """
        if timestamp is None:
            timestamp = datetime.now()

        filename = f"{product_type}_mapped_{timestamp.strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = self.data_dir / filename

        df.to_csv(filepath, index=False)
        logger.info(f"Saved mapped data to {filepath}")
        return str(filepath)

    def load_latest_snapshot(self, product_type: str) -> Optional[Dict]:
        """
        Load the most recent snapshot for a product type.

        Args:
            product_type: Product type identifier

        Returns:
            Pricing data dictionary or None if not found
        """
        pattern = f"{product_type}_*.json"
        files = sorted(self.data_dir.glob(pattern), reverse=True)

        if not files:
            logger.warning(f"No snapshots found for {product_type}")
            return None

        filepath = files[0]
        with open(filepath, "r") as f:
            data = json.load(f)

        logger.info(f"Loaded snapshot from {filepath}")
        return data.get("data")

    def load_all_snapshots(self, product_type: str) -> List[Dict]:
        """
        Load all historical snapshots for a product type.

        Args:
            product_type: Product type identifier

        Returns:
            List of pricing data dictionaries with timestamps
        """
        pattern = f"{product_type}_*.json"
        files = sorted(self.data_dir.glob(pattern))

        snapshots = []
        for filepath in files:
            with open(filepath, "r") as f:
                snapshot = json.load(f)
                snapshots.append(snapshot)

        logger.info(f"Loaded {len(snapshots)} snapshots for {product_type}")
        return snapshots

    def get_price_trends(
        self,
        product_type: str,
        target_date: str
    ) -> pd.DataFrame:
        """
        Get price trends for a specific date across multiple snapshots.

        Args:
            product_type: Product type identifier
            target_date: Date to track in YYYY-MM-DD format

        Returns:
            DataFrame with timestamp and price information
        """
        snapshots = self.load_all_snapshots(product_type)
        trends = []

        for snapshot in snapshots:
            timestamp = snapshot.get("timestamp")
            data = snapshot.get("data", {})
            calendar = data.get("calendar", [])

            for day in calendar:
                if day.get("date") == target_date:
                    products = day.get("products", {})
                    if product_type in products:
                        product_data = products[product_type]
                        trends.append({
                            "snapshot_timestamp": timestamp,
                            "date": target_date,
                            "price_adult": product_data.get("priceAdult"),
                            "price_child": product_data.get("priceChild"),
                            "disney_range": product_data.get("range")
                        })
                    break

        df = pd.DataFrame(trends)
        if not df.empty:
            df["snapshot_timestamp"] = pd.to_datetime(df["snapshot_timestamp"])
            df = df.sort_values("snapshot_timestamp")

        logger.info(f"Retrieved {len(df)} price points for {target_date}")
        return df

    def export_to_excel(
        self,
        output_file: str,
        data_frames: Dict[str, pd.DataFrame]
    ):
        """
        Export multiple DataFrames to Excel with separate sheets.

        Args:
            output_file: Output file path
            data_frames: Dictionary mapping sheet names to DataFrames
        """
        with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
            for sheet_name, df in data_frames.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)

        logger.info(f"Exported data to {output_file}")

    def clean_old_snapshots(self, days_to_keep: int = 90):
        """
        Remove snapshots older than specified days.

        Args:
            days_to_keep: Number of days of history to retain
        """
        cutoff = datetime.now().timestamp() - (days_to_keep * 86400)
        deleted = 0

        for filepath in self.data_dir.glob("*.json"):
            if filepath.stat().st_mtime < cutoff:
                filepath.unlink()
                deleted += 1

        logger.info(f"Cleaned {deleted} old snapshots")
