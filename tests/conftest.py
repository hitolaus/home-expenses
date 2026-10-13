import datetime as dt
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(FIXTURES))

SAMPLE_PDF = FIXTURES / "1234567890_2026.01.01-2026.01.31.pdf"

CONFIG_TOML = """
currency = "DKK"
window_months = 12
reference_date = "{reference_date}"
model = "claude-haiku-5-5"
statements_dir = "./statements"
database = "./data/budget.db"
output = "./output/report.html"

[[category]]
name = "Groceries"
description = "Groceries"
yearly_limit = 1000

[[category]]
name = "Housing"
description = "Housing"
yearly_limit = 120000

[[category]]
name = "Transport"
description = "Transport"
yearly_limit = 1000

[[category]]
name = "Restaurant & takeaway"
description = "Cafés"
yearly_limit = 2000

[[category]]
name = "Miscellaneous"
description = "Other"
yearly_limit = 500

[[category]]
name = "Income"
description = "Salary"
budgeted = false

[[category]]
name = "Transfers"
description = "Own transfers"
budgeted = false
"""


@pytest.fixture
def config_path(tmp_path):
    def make(reference_date="2026-01-31"):
        p = tmp_path / "config.toml"
        p.write_text(CONFIG_TOML.format(reference_date=reference_date), encoding="utf-8")
        (tmp_path / "statements").mkdir(exist_ok=True)
        return p
    return make


@pytest.fixture
def config(config_path):
    from budget.config import load_config
    return load_config(config_path())
