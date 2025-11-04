import json
import os
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from src.storage.price_history import PriceHistoryStore


@pytest.fixture
def temp_data_dir():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def storage(temp_data_dir):
    return PriceHistoryStore(data_dir=temp_data_dir)


def test_has_snapshot_for_today_no_snapshot(storage):
    assert not storage.has_snapshot_for_today("1-day-1-park")


def test_has_snapshot_for_today_with_snapshot(storage):
    product_type = "1-day-1-park"
    test_data = {"calendar": [{"date": "2025-11-04", "products": {}}]}

    storage.save_snapshot(product_type, test_data)

    assert storage.has_snapshot_for_today(product_type)


def test_has_snapshot_for_today_old_snapshot(storage, temp_data_dir):
    product_type = "1-day-1-park"
    old_date = "20231104"
    filename = f"{product_type}_{old_date}_120000.json"
    filepath = Path(temp_data_dir) / filename

    test_data = {
        "timestamp": "2023-11-04T12:00:00",
        "product_type": product_type,
        "data": {"calendar": []}
    }

    with open(filepath, "w") as f:
        json.dump(test_data, f)

    assert not storage.has_snapshot_for_today(product_type)


def test_save_and_load_snapshot(storage):
    product_type = "1-day-2-parks"
    test_data = {
        "calendar": [
            {
                "date": "2025-11-04",
                "products": {
                    product_type: {
                        "priceAdult": 100.0,
                        "priceChild": 90.0
                    }
                }
            }
        ]
    }

    storage.save_snapshot(product_type, test_data)
    loaded = storage.load_latest_snapshot(product_type)

    assert loaded == test_data


def test_load_latest_snapshot_no_data(storage):
    assert storage.load_latest_snapshot("nonexistent-product") is None


def test_save_mapped_data_creates_csv(storage):
    product_type = "1-day-1-park"
    df = pd.DataFrame({"tier": ["A", "B"], "price": [10, 20]})

    saved_path = Path(storage.save_mapped_data(product_type, df))

    assert saved_path.exists()
    loaded_df = pd.read_csv(saved_path)
    pd.testing.assert_frame_equal(loaded_df, df, check_dtype=False)


def test_load_all_snapshots_returns_all_entries(storage):
    product_type = "1-day-1-park"
    ts1 = datetime(2024, 1, 1, 10, 0, 0)
    ts2 = datetime(2024, 1, 2, 10, 0, 0)

    storage.save_snapshot(product_type, {"calendar": []}, timestamp=ts1)
    storage.save_snapshot(product_type, {"calendar": []}, timestamp=ts2)

    snapshots = storage.load_all_snapshots(product_type)

    assert [snap["timestamp"] for snap in snapshots] == [ts1.isoformat(), ts2.isoformat()]


def test_get_price_trends_returns_dataframe(storage):
    product_type = "1-day-1-park"
    target_date = "2025-01-01"
    ts1 = datetime(2024, 1, 1, 9, 0, 0)
    ts2 = datetime(2024, 1, 2, 9, 0, 0)

    storage.save_snapshot(
        product_type,
        {
            "calendar": [
                {
                    "date": target_date,
                    "products": {
                        product_type: {
                            "priceAdult": 100.0,
                            "priceChild": 80.0,
                            "range": "A"
                        }
                    }
                }
            ]
        },
        timestamp=ts1
    )
    storage.save_snapshot(
        product_type,
        {
            "calendar": [
                {
                    "date": target_date,
                    "products": {
                        product_type: {
                            "priceAdult": 120.0,
                            "priceChild": 90.0,
                            "range": "B"
                        }
                    }
                }
            ]
        },
        timestamp=ts2
    )

    df = storage.get_price_trends(product_type, target_date)

    assert len(df) == 2
    assert df["snapshot_timestamp"].is_monotonic_increasing
    assert df["price_adult"].tolist() == [100.0, 120.0]
    assert df["disney_range"].tolist() == ["A", "B"]


def test_export_to_excel_writes_expected_sheets(storage, temp_data_dir, monkeypatch):
    output_file = Path(temp_data_dir) / "export.xlsx"
    df = pd.DataFrame({"value": [1, 2, 3]})

    writer_instances = []
    write_calls = []

    class DummyWriter:
        def __init__(self, path, engine=None):
            self.path = path
            self.engine = engine
            self.closed = False
            writer_instances.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.closed = True
            return False

    def fake_to_excel(self, writer, sheet_name=None, index=None):
        write_calls.append({
            "writer": writer,
            "sheet_name": sheet_name,
            "index": index,
            "data": self.copy()
        })

    monkeypatch.setattr(pd, "ExcelWriter", DummyWriter)
    monkeypatch.setattr(pd.DataFrame, "to_excel", fake_to_excel, raising=False)

    storage.export_to_excel(str(output_file), {"Summary": df})

    assert writer_instances
    writer = writer_instances[0]
    assert writer.path == str(output_file)
    assert writer.engine == "openpyxl"
    assert writer.closed

    assert write_calls
    call = write_calls[0]
    assert call["writer"] is writer
    assert call["sheet_name"] == "Summary"
    assert call["index"] is False
    pd.testing.assert_frame_equal(call["data"], df, check_dtype=False)


def test_clean_old_snapshots_removes_stale_files(storage, temp_data_dir):
    recent_path = Path(temp_data_dir) / "recent.json"
    old_path = Path(temp_data_dir) / "old.json"

    for path in (recent_path, old_path):
        path.write_text(json.dumps({"timestamp": datetime.now().isoformat()}))

    thirty_days = 30 * 86400
    now = time.time()
    os_cutoff_margin = 5 * 86400
    old_timestamp = now - thirty_days - os_cutoff_margin
    recent_timestamp = now

    old_path.touch()
    recent_path.touch()

    os.utime(old_path, (old_timestamp, old_timestamp))
    os.utime(recent_path, (recent_timestamp, recent_timestamp))

    storage.clean_old_snapshots(days_to_keep=30)

    assert not old_path.exists()
    assert recent_path.exists()
