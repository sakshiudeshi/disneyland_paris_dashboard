import pytest
from unittest.mock import Mock, patch
import json
from datetime import datetime, timedelta

from src.api.disney_api import DisneyPriceAPI


class TestDisneyPriceAPI:
    """Test suite for DisneyPriceAPI class."""

    def test_initialization(self):
        """Test API client initialization."""
        api = DisneyPriceAPI()
        assert api.market == "en-int"
        assert api.currency == "EUR"
        assert api.session is not None

    def test_initialization_custom_params(self):
        """Test API client initialization with custom parameters."""
        api = DisneyPriceAPI(market="en-gb", currency="GBP")
        assert api.market == "en-gb"
        assert api.currency == "GBP"

    def test_product_types_defined(self):
        """Test that all product types are defined."""
        expected_products = [
            "1-day-1-park",
            "1-day-2-parks",
            "2-day-2-parks",
            "3-day-2-parks",
            "4-day-2-parks"
        ]
        for product in expected_products:
            assert product in DisneyPriceAPI.PRODUCT_TYPES
            assert "productType" in DisneyPriceAPI.PRODUCT_TYPES[product]
            assert "adultProductCode" in DisneyPriceAPI.PRODUCT_TYPES[product]
            assert "childProductCode" in DisneyPriceAPI.PRODUCT_TYPES[product]

    @patch("src.api.disney_api.requests.Session.post")
    def test_fetch_prices_success(self, mock_post):
        """Test successful price fetching."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "calendar": [
                {
                    "date": "2025-11-03",
                    "products": {
                        "1-day-1-park": {
                            "priceAdult": 86.0,
                            "priceChild": 80.0,
                            "range": 4,
                            "available": True
                        }
                    }
                }
            ],
            "priceRanges": [
                {"id": 0, "min": 0.0, "max": 57.0},
                {"id": 5, "min": 90.0}
            ],
            "roundedPrices": True
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        api = DisneyPriceAPI()
        result = api.fetch_prices("2025-11-03", "2025-11-03", ["1-day-1-park"])

        assert result is not None
        assert "calendar" in result
        assert len(result["calendar"]) == 1
        assert result["calendar"][0]["date"] == "2025-11-03"

    @patch("src.api.disney_api.requests.Session.post")
    def test_fetch_prices_retry_on_failure(self, mock_post):
        """Test retry logic on API failure."""
        mock_post.side_effect = [
            Exception("Network error"),
            Exception("Network error"),
            Mock(json=lambda: {"calendar": []}, raise_for_status=Mock())
        ]

        api = DisneyPriceAPI()
        result = api.fetch_prices(
            "2025-11-03",
            "2025-11-03",
            ["1-day-1-park"],
            max_retries=3
        )

        assert result is not None
        assert mock_post.call_count == 3

    @patch("src.api.disney_api.requests.Session.post")
    def test_fetch_prices_max_retries_exceeded(self, mock_post):
        """Test that exception is raised after max retries."""
        mock_post.side_effect = Exception("Network error")

        api = DisneyPriceAPI()

        with pytest.raises(Exception):
            api.fetch_prices(
                "2025-11-03",
                "2025-11-03",
                ["1-day-1-park"],
                max_retries=3
            )

        assert mock_post.call_count == 3

    @patch("src.api.disney_api.requests.Session.post")
    def test_fetch_all_products(self, mock_post):
        """Test fetching all product types."""
        mock_response = Mock()
        mock_response.json.return_value = {"calendar": [], "priceRanges": []}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        api = DisneyPriceAPI()
        results = api.fetch_all_products("2025-11-03", "2025-11-03")

        assert len(results) == 5
        for product_type in DisneyPriceAPI.PRODUCT_TYPES.keys():
            assert product_type in results
            assert results[product_type] is not None

    @patch("src.api.disney_api.requests.Session.post")
    def test_fetch_all_products_with_failure(self, mock_post):
        """Test fetch_all_products handles individual failures."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if 2 <= call_count[0] <= 4:
                raise Exception("Network error")
            mock_resp = Mock()
            mock_resp.json.return_value = {"calendar": []}
            mock_resp.raise_for_status = Mock()
            return mock_resp

        mock_post.side_effect = side_effect

        api = DisneyPriceAPI()
        results = api.fetch_all_products("2025-11-03", "2025-11-03")

        assert len(results) == 5
        failed_products = [k for k, v in results.items() if v is None]
        assert len(failed_products) == 1

    def test_get_default_date_range(self):
        """Test default date range generation."""
        start, end = DisneyPriceAPI.get_default_date_range(months_ahead=12)

        start_date = datetime.strptime(start, "%Y-%m-%d")
        end_date = datetime.strptime(end, "%Y-%m-%d")

        assert start_date <= datetime.now()
        assert end_date > start_date
        assert (end_date - start_date).days >= 350

    def test_get_default_date_range_custom_months(self):
        """Test default date range with custom months."""
        start, end = DisneyPriceAPI.get_default_date_range(months_ahead=6)

        start_date = datetime.strptime(start, "%Y-%m-%d")
        end_date = datetime.strptime(end, "%Y-%m-%d")

        assert (end_date - start_date).days >= 170
        assert (end_date - start_date).days <= 190

    @patch("src.api.disney_api.requests.Session.post")
    def test_fetch_prices_payload_format(self, mock_post):
        """Test that request payload is correctly formatted."""
        mock_response = Mock()
        mock_response.json.return_value = {"calendar": []}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        api = DisneyPriceAPI(market="test-market", currency="USD")
        api.fetch_prices("2025-11-03", "2025-11-10", ["1-day-1-park"])

        call_args = mock_post.call_args
        payload = json.loads(call_args[1]["data"])

        assert payload["market"] == "test-market"
        assert payload["currency"] == "USD"
        assert payload["startDate"] == "2025-11-03"
        assert payload["endDate"] == "2025-11-10"
        assert len(payload["products"]) == 1
        assert payload["products"][0]["productType"] == "1-day-1-park"
