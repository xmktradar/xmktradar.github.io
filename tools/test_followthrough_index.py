"""by_ticker index: split is kept, homepage rows stay bull/bear only."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import followthrough as ft  # noqa: E402


def test_index_groups_sides():
    rows = [
        {"ticker": "NVDA", "side": "bull", "status": "settled", "ret": -0.02, "xs": -0.01},
        {"ticker": "NVDA", "side": "bull", "status": "immature"},
        {"ticker": "NVDA", "side": "split", "status": "settled", "ret": 0.04, "xs": 0.01},
        {"ticker": "QQQ", "side": "bear", "status": "settled", "ret": -0.03, "xs": 0.02},
    ]
    book = ft.index_by_ticker(rows)
    assert book["NVDA"]["bull"]["opened"] == 2
    assert book["NVDA"]["bull"]["settled"] == 1
    assert book["NVDA"]["bull"]["immature"] == 1
    assert book["NVDA"]["split"]["hit"] == 1
    assert "bear" not in book["NVDA"]
    assert book["QQQ"]["bear"]["avg_xs"] == 0.02


if __name__ == "__main__":
    test_index_groups_sides()
    print("ok")
