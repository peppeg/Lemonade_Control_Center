"""Alert history persistence."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.services.diagnostics.models import AlertHistoryEntry, DiagnosticReport, Severity

HISTORY_FILE = Path(__file__).parent.parent.parent / "data" / "diagnostic_history.json"


class AlertHistory:
    def __init__(self) -> None:
        self._entries: list[AlertHistoryEntry] = []
        self._active_rules: set[str] = set()
        self._dismissed: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not HISTORY_FILE.exists():
            return
        try:
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            self._entries = [AlertHistoryEntry(**entry) for entry in data.get("entries", [])]
            self._active_rules = set(data.get("active_rules", []))
            self._dismissed = set(data.get("dismissed", []))
        except (OSError, ValueError, TypeError):
            self._entries = []
            self._active_rules = set()
            self._dismissed = set()

    def _save(self) -> None:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "entries": [entry.model_dump(mode="json") for entry in self._entries[-200:]],
            "active_rules": sorted(self._active_rules),
            "dismissed": sorted(self._dismissed),
        }
        HISTORY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def record(self, report: DiagnosticReport) -> DiagnosticReport:
        current_alert_ids = {alert.rule_id for alert in report.alerts}

        for alert in report.alerts:
            if alert.rule_id not in self._active_rules and alert.rule_id not in self._dismissed:
                self._entries.append(
                    AlertHistoryEntry(
                        timestamp=datetime.now(timezone.utc),
                        rule_id=alert.rule_id,
                        rule_name=alert.rule_name,
                        severity=alert.severity,
                        event="appeared",
                        title=alert.title,
                    )
                )

        for rule_id in self._active_rules - current_alert_ids:
            self._entries.append(
                AlertHistoryEntry(
                    timestamp=datetime.now(timezone.utc),
                    rule_id=rule_id,
                    rule_name=rule_id,
                    severity=Severity.info,
                    event="resolved",
                    title=f"{rule_id} resolved",
                )
            )

        self._active_rules = current_alert_ids
        self._dismissed &= current_alert_ids
        self._save()
        return self.filter_report(report)

    def filter_report(self, report: DiagnosticReport) -> DiagnosticReport:
        alerts = [alert for alert in report.alerts if alert.rule_id not in self._dismissed]
        return report.model_copy(
            update={
                "alerts": alerts,
                "warnings": sum(1 for alert in alerts if alert.severity in {Severity.medium, Severity.high}),
                "errors": sum(1 for alert in alerts if alert.severity == Severity.critical),
            }
        )

    def dismiss(self, rule_id: str) -> None:
        self._dismissed.add(rule_id)
        self._entries.append(
            AlertHistoryEntry(
                timestamp=datetime.now(timezone.utc),
                rule_id=rule_id,
                rule_name=rule_id,
                severity=Severity.info,
                event="dismissed",
                title=f"{rule_id} dismissed",
            )
        )
        self._save()

    def get_entries(self, limit: int = 50) -> list[dict]:
        return [entry.model_dump(mode="json") for entry in reversed(self._entries[-limit:])]
