import pytest

from app.services import log_parser
from app.services.metrics import store, task_history


@pytest.fixture(autouse=True)
def _warn_about_every_skipped_record():
    """Each test sees the first warning of its own, not one held back by an
    earlier test's."""
    for warning in (log_parser._skipped_records, store._skipped_rows, task_history._skipped_records):
        warning.reset()


@pytest.fixture(autouse=True)
def _close_metrics_stores(monkeypatch):
    """A store keeps its write connection open; close those a test opened."""
    opened: list[store.MetricsStore] = []
    real_init = store.MetricsStore.__init__

    def init(self, *args, **kwargs):
        real_init(self, *args, **kwargs)
        opened.append(self)

    monkeypatch.setattr(store.MetricsStore, "__init__", init)
    yield
    for metrics_store in opened:
        metrics_store.close()
