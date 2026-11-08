from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from conftest import FakeSEC, calendar_company, fake_prices, submissions
from investment_os.pipeline import build_bundle

APP = str(Path(__file__).resolve().parents[1] / "dashboard" / "app.py")
PAGES = ["Company Research", "Reverse DCF", "Thesis Lab", "Alternative Data Lab", "Private Markets", "IC Memo"]


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_without_exception(page, tmp_path, monkeypatch):
    build_bundle("FIX", client=FakeSEC(calendar_company(), submissions()), price_fetcher=fake_prices, output_dir=tmp_path)
    monkeypatch.setenv("INVESTMENT_OS_OUTPUTS", str(tmp_path))
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, [e.value for e in at.exception]
