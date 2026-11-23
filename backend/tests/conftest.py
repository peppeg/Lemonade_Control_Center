import pytest

from app.services import log_parser
from app.services.metrics import store, task_history


@pytest.fixture(autouse=True)
def _warn_about_every_skipped_record():
    """Each test sees the first warning of its own, not one held back by an
    earlier test's."""
    for warning in (log_parser._skipped_records, store._skipped_rows, task_history._skipped_records):
        warning.reset()
