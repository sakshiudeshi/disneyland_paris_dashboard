import logging
import pytest
import pandas as pd
from src.models.tier_mapper import TierMapper, PriceTier


class TestTierMapper:
    """Test suite for TierMapper class."""

    @pytest.fixture
    def sample_pricing_data(self):
        """Create sample pricing data for testing."""
        return {
            "calendar": [
                {
                    "date": "2025-11-01",
                    "products": {
                        "1-day-1-park": {
                            "priceAdult": 70.0,
                            "priceChild": 65.0,
                            "range": 2,
                            "available": True
                        }
                    }
                },
                {
                    "date": "2025-11-02",
                    "products": {
                        "1-day-1-park": {
                            "priceAdult": 80.0,
                            "priceChild": 75.0,
                            "range": 3,
                            "available": True
                        }
                    }
                },
                {
                    "date": "2025-11-03",
                    "products": {
                        "1-day-1-park": {
                            "priceAdult": 90.0,
                            "priceChild": 85.0,
                            "range": 4,
                            "available": True
                        }
                    }
                },
                {
                    "date": "2025-11-04",
                    "products": {
                        "1-day-1-park": {
                            "priceAdult": 100.0,
                            "priceChild": 95.0,
                            "range": 5,
                            "available": True
                        }
                    }
                },
                {
                    "date": "2025-11-05",
                    "products": {
                        "1-day-1-park": {
                            "priceAdult": 110.0,
                            "priceChild": 105.0,
                            "range": 5,
                            "available": True
                        }
                    }
                }
            ],
            "priceRanges": [],
            "roundedPrices": True
        }

    def test_initialization(self):
        """Test TierMapper initialization."""
        mapper = TierMapper("1-day-1-park")
        assert mapper.product_type == "1-day-1-park"
        assert mapper.thresholds is None

    def test_calculate_thresholds(self, sample_pricing_data):
        """Test threshold calculation."""
        mapper = TierMapper("1-day-1-park")
        thresholds = mapper.calculate_thresholds(sample_pricing_data)

        assert len(thresholds) == 5
        assert PriceTier.LOW_PEAK in thresholds
        assert PriceTier.SHOULDER in thresholds
        assert PriceTier.PEAK in thresholds
        assert PriceTier.SUPER_PEAK in thresholds
        assert PriceTier.MEGA_PEAK in thresholds

        for tier, (min_price, max_price) in thresholds.items():
            assert min_price <= max_price
            assert min_price >= 70.0
            assert max_price <= 110.0

    def test_calculate_thresholds_empty_data(self):
        """Test threshold calculation with empty data."""
        mapper = TierMapper("1-day-1-park")
        thresholds = mapper.calculate_thresholds({"calendar": []})

        assert thresholds == {}
        assert mapper.thresholds == {}

    def test_set_custom_thresholds(self):
        """Test setting custom thresholds."""
        mapper = TierMapper("1-day-1-park")
        custom = {
            PriceTier.LOW_PEAK: (60.0, 70.0),
            PriceTier.SHOULDER: (70.0, 80.0),
            PriceTier.PEAK: (80.0, 90.0),
            PriceTier.SUPER_PEAK: (90.0, 100.0),
            PriceTier.MEGA_PEAK: (100.0, 120.0)
        }

        mapper.set_custom_thresholds(custom)
        assert mapper.thresholds == custom

    def test_map_price_to_tier(self, sample_pricing_data):
        """Test mapping a single price to a tier."""
        mapper = TierMapper("1-day-1-park")
        mapper.calculate_thresholds(sample_pricing_data)

        tier_70 = mapper.map_price_to_tier(70.0)
        tier_110 = mapper.map_price_to_tier(110.0)

        assert tier_70 is not None
        assert tier_110 is not None
        assert isinstance(tier_70, PriceTier)
        assert isinstance(tier_110, PriceTier)

    def test_map_price_to_tier_out_of_bounds(self, sample_pricing_data, caplog):
        """Prices above known thresholds should log a warning and return None."""
        mapper = TierMapper("1-day-1-park")
        mapper.calculate_thresholds(sample_pricing_data)

        with caplog.at_level(logging.WARNING):
            result = mapper.map_price_to_tier(999.0)

        assert result is None
        assert "does not fall within any tier" in caplog.text

    def test_map_price_to_tier_no_thresholds(self):
        """Test mapping price without thresholds set."""
        mapper = TierMapper("1-day-1-park")
        result = mapper.map_price_to_tier(80.0)

        assert result is None

    def test_map_calendar(self, sample_pricing_data):
        """Test mapping entire calendar."""
        mapper = TierMapper("1-day-1-park")
        df = mapper.map_calendar(sample_pricing_data)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5
        assert "date" in df.columns
        assert "price_adult" in df.columns
        assert "price_child" in df.columns
        assert "disney_range" in df.columns
        assert "available" in df.columns
        assert "globaltix_tier" in df.columns

        assert df["price_adult"].tolist() == [70.0, 80.0, 90.0, 100.0, 110.0]

    def test_map_calendar_auto_calculates_thresholds(self, sample_pricing_data):
        """Test that map_calendar auto-calculates thresholds if not set."""
        mapper = TierMapper("1-day-1-park")
        assert mapper.thresholds is None

        df = mapper.map_calendar(sample_pricing_data)

        assert mapper.thresholds is not None
        assert len(mapper.thresholds) == 5

    def test_get_monthly_recommendations(self, sample_pricing_data):
        """Test monthly recommendation generation."""
        mapper = TierMapper("1-day-1-park")
        df = mapper.map_calendar(sample_pricing_data)

        monthly = mapper.get_monthly_recommendations(df)

        assert isinstance(monthly, pd.DataFrame)
        assert "month" in monthly.columns
        assert "tier" in monthly.columns
        assert "recommended_price" in monthly.columns
        assert "min_price" in monthly.columns
        assert "max_price" in monthly.columns
        assert "num_days" in monthly.columns
        assert "dates" in monthly.columns

        # Should have multiple rows (one per tier that appears in the data)
        assert len(monthly) > 0
        # Total days across all tiers should equal 5
        assert monthly["num_days"].sum() == 5

    def test_format_date_ranges_handles_gaps(self):
        """Contiguous and non-contiguous dates should be formatted correctly."""
        mapper = TierMapper("1-day-1-park")
        dates = [
            "2025-11-01",
            "2025-11-02",
            "2025-11-05",
            "2025-11-06",
            "2025-11-08"
        ]

        formatted = mapper._format_date_ranges(dates)
        assert formatted == "Nov 1-2, 5-6, 8"

    def test_format_date_ranges_empty(self):
        """Empty date lists should return an empty string."""
        mapper = TierMapper("1-day-1-park")

        assert mapper._format_date_ranges([]) == ""

    def test_detect_price_alerts_spike(self):
        """Test price alert detection for price spikes."""
        mapper = TierMapper("1-day-1-park")
        data = {
            "calendar": [
                {
                    "date": "2025-11-01",
                    "products": {
                        "1-day-1-park": {
                            "priceAdult": 70.0,
                            "priceChild": 65.0,
                            "range": 2,
                            "available": True
                        }
                    }
                },
                {
                    "date": "2025-11-02",
                    "products": {
                        "1-day-1-park": {
                            "priceAdult": 100.0,
                            "priceChild": 95.0,
                            "range": 5,
                            "available": True
                        }
                    }
                }
            ]
        }

        df = mapper.map_calendar(data)
        alerts = mapper.detect_price_alerts(df, threshold_pct=20.0)

        assert len(alerts) > 0
        spike_alerts = [a for a in alerts if a["type"] == "price_spike"]
        assert len(spike_alerts) > 0

    def test_detect_price_alerts_tier_change(self):
        """Test price alert detection for tier changes."""
        mapper = TierMapper("1-day-1-park")
        mapper.set_custom_thresholds({
            PriceTier.LOW_PEAK: (60.0, 75.0),
            PriceTier.SHOULDER: (75.0, 85.0),
            PriceTier.PEAK: (85.0, 95.0),
            PriceTier.SUPER_PEAK: (95.0, 105.0),
            PriceTier.MEGA_PEAK: (105.0, 120.0)
        })

        data = {
            "calendar": [
                {
                    "date": "2025-11-01",
                    "products": {
                        "1-day-1-park": {
                            "priceAdult": 70.0,
                            "priceChild": 65.0,
                            "range": 2,
                            "available": True
                        }
                    }
                },
                {
                    "date": "2025-11-02",
                    "products": {
                        "1-day-1-park": {
                            "priceAdult": 80.0,
                            "priceChild": 75.0,
                            "range": 3,
                            "available": True
                        }
                    }
                }
            ]
        }

        df = mapper.map_calendar(data)
        alerts = mapper.detect_price_alerts(df, threshold_pct=50.0)

        tier_change_alerts = [a for a in alerts if a["type"] == "tier_change"]
        assert len(tier_change_alerts) > 0

    def test_price_tier_enum_values(self):
        """Test that PriceTier enum has correct values."""
        assert PriceTier.LOW_PEAK.value == "Low Peak"
        assert PriceTier.SHOULDER.value == "Shoulder (Normal)"
        assert PriceTier.PEAK.value == "Peak"
        assert PriceTier.SUPER_PEAK.value == "Super Peak"
        assert PriceTier.MEGA_PEAK.value == "Mega Peak"

    def test_map_calendar_missing_product(self):
        """Test map_calendar with missing product data."""
        mapper = TierMapper("1-day-1-park")
        data = {
            "calendar": [
                {
                    "date": "2025-11-01",
                    "products": {
                        "2-day-2-parks": {
                            "priceAdult": 150.0,
                            "priceChild": 140.0,
                            "range": 3,
                            "available": True
                        }
                    }
                }
            ]
        }

        df = mapper.map_calendar(data)
        assert len(df) == 0

    def test_thresholds_overlap(self, sample_pricing_data):
        """Test that calculated thresholds don't have gaps."""
        mapper = TierMapper("1-day-1-park")
        thresholds = mapper.calculate_thresholds(sample_pricing_data)

        tiers_ordered = [
            PriceTier.LOW_PEAK,
            PriceTier.SHOULDER,
            PriceTier.PEAK,
            PriceTier.SUPER_PEAK,
            PriceTier.MEGA_PEAK
        ]

        for i in range(len(tiers_ordered) - 1):
            current_max = thresholds[tiers_ordered[i]][1]
            next_min = thresholds[tiers_ordered[i + 1]][0]
            assert current_max == next_min
