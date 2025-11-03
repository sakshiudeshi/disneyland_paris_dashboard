import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class DisneyPriceAPI:
    """Client for Disneyland Paris pricing calendar API."""

    API_URL = "https://api.disneylandparis.com/prices-calendar/api/v2/prices/ticket-price-calendar"

    PRODUCT_TYPES = {
        "1-day-1-park": {
            "productType": "1-day-1-park",
            "adultProductCode": "TKITK6001A",
            "childProductCode": "TKITK6001C"
        },
        "1-day-2-parks": {
            "productType": "1-day-2-parks",
            "adultProductCode": "TKITHL001A",
            "childProductCode": "TKITHL001C"
        },
        "2-day-2-parks": {
            "productType": "2-day-2-parks",
            "adultProductCode": "TKITHS002A",
            "childProductCode": "TKITHS002C"
        },
        "3-day-2-parks": {
            "productType": "3-day-2-parks",
            "adultProductCode": "TKITHS003A",
            "childProductCode": "TKITHS003C"
        },
        "4-day-2-parks": {
            "productType": "4-day-2-parks",
            "adultProductCode": "TKITHS004A",
            "childProductCode": "TKITHS004C"
        }
    }

    def __init__(self, market: str = "en-int", currency: str = "EUR"):
        """
        Initialize Disney Price API client.

        Args:
            market: Market code (default: en-int)
            currency: Currency code (default: EUR)
        """
        self.market = market
        self.currency = currency
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def fetch_prices(
        self,
        start_date: str,
        end_date: str,
        product_types: Optional[List[str]] = None,
        max_retries: int = 3
    ) -> Dict:
        """
        Fetch pricing data for specified date range and product types.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            product_types: List of product type keys (default: all)
            max_retries: Maximum number of retry attempts

        Returns:
            Dictionary containing pricing calendar data

        Raises:
            requests.exceptions.RequestException: If API request fails
        """
        if product_types is None:
            product_types = list(self.PRODUCT_TYPES.keys())

        products = [self.PRODUCT_TYPES[pt] for pt in product_types]

        payload = {
            "market": self.market,
            "currency": self.currency,
            "startDate": start_date,
            "endDate": end_date,
            "products": products,
            "eligibilityInformation": {
                "salesChannel": "DIRECT",
                "membershipType": "",
                "masterCategoryCodes": ["EVENT", " TICKET", " TKTEXPERI"]
            }
        }

        logger.info(
            f"Fetching prices from {start_date} to {end_date} "
            f"for {len(product_types)} product types"
        )

        for attempt in range(max_retries):
            try:
                response = self.session.post(
                    self.API_URL,
                    data=json.dumps(payload),
                    timeout=30
                )
                response.raise_for_status()

                data = response.json()
                logger.info(
                    f"Successfully fetched {len(data.get('calendar', []))} days of pricing data"
                )
                return data

            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}"
                )
                if attempt == max_retries - 1:
                    logger.error(f"Failed to fetch prices after {max_retries} attempts")
                    raise

        return {}

    def fetch_all_products(
        self,
        start_date: str,
        end_date: str
    ) -> Dict[str, Dict]:
        """
        Fetch prices for all product types separately.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Dictionary mapping product type to pricing data
        """
        results = {}

        for product_type in self.PRODUCT_TYPES.keys():
            logger.info(f"Fetching prices for {product_type}")
            try:
                data = self.fetch_prices(
                    start_date,
                    end_date,
                    product_types=[product_type]
                )
                results[product_type] = data
            except Exception as e:
                logger.error(f"Failed to fetch {product_type}: {str(e)}")
                results[product_type] = None

        return results

    @staticmethod
    def get_default_date_range(months_ahead: int = 12) -> tuple:
        """
        Get default date range starting from today.

        Args:
            months_ahead: Number of months to look ahead

        Returns:
            Tuple of (start_date, end_date) in YYYY-MM-DD format
        """
        today = datetime.now()
        end_date = today + timedelta(days=months_ahead * 30)
        return today.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


if __name__ == "__main__":
    api = DisneyPriceAPI()
    start, end = api.get_default_date_range(months_ahead=12)

    logger.info(f"Fetching prices from {start} to {end}")
    data = api.fetch_prices(start, end, product_types=["1-day-1-park"])

    if data:
        logger.info(f"Sample response: {json.dumps(data, indent=2)[:500]}...")
