import ast
import logging
import os
import stat
from pathlib import Path

import pytest

from app.models.setup import LccConfig
from app.services import security, state_files
from app.services.setup import SetupService
from app.services.state_files import (
    append_private_line,
    ensure_private_dir,
    protect_data_dir,
    write_private_text,
)

APP_DIR = Path(state_files.__file__).parent.parent
WRITE_MODES = set("wax+")


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@pytest.fixture(autouse=True)
def _usual_umask():
    previous = os.umask(0o022)
    yield
    os.umask(previous)


# ── Replacing files ──


def test_written_files_and_created_directories_are_owner_only(tmp_path):
    path = tmp_path / "data" / "profiles" / "model.json"

    write_private_text(path, "{}")

    assert path.read_text(encoding="utf-8") == "{}"
    assert mode(path) == 0o600
    assert mode(path.parent) == 0o700
    assert mode(tmp_path / "data") == 0o700


def test_an_existing_world_readable_file_is_tightened(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("old", encoding="utf-8")
    path.chmod(0o644)

    write_private_text(path, "perché")

    assert path.read_text(encoding="utf-8") == "perché"
    assert mode(path) == 0o600


@pytest.mark.parametrize("failing", ["fsync", "replace"])
def test_an_interrupted_write_keeps_the_previous_content(tmp_path, monkeypatch, failing):
    path = tmp_path / "config.json"
    write_private_text(path, "previous")

    def fail(*_args):
        raise OSError("disk full")

    monkeypatch.setattr(f"app.services.state_files.os.{failing}", fail)
    with pytest.raises(OSError, match="disk full"):
        write_private_text(path, "new")

    assert path.read_text(encoding="utf-8") == "previous"
    assert [item.name for item in tmp_path.iterdir()] == ["config.json"]


def test_a_symbolic_link_is_kept(tmp_path):
    target = tmp_path / "elsewhere" / "config.json"
    target.parent.mkdir()
    target.write_text("old", encoding="utf-8")
    link = tmp_path / "config.json"
    link.symlink_to(target)

    write_private_text(link, "new")

    assert link.is_symlink()
    assert target.read_text(encoding="utf-8") == "new"


def test_existing_directories_are_not_changed_by_a_write(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)

    ensure_private_dir(shared)
    write_private_text(shared / "file.json", "{}")

    assert mode(shared) == 0o755


def test_the_saved_configuration_is_owner_only(tmp_path):
    service = SetupService(config_file=tmp_path / "data" / "config.json")

    service.save_config(LccConfig())

    assert mode(service.config_file) == 0o600
    assert service.get_config() == LccConfig.model_validate_json(service.config_file.read_text(encoding="utf-8"))


# ── Audit log ──


def test_audit_log_is_owner_only_and_appends(tmp_path):
    path = tmp_path / "data" / "audit.jsonl"

    for line in ("one", "two"):
        append_private_line(path, line, max_bytes=1000, backups=3)

    assert path.read_text(encoding="utf-8") == "one\ntwo\n"
    assert mode(path) == 0o600
    assert mode(path.parent) == 0o700


def test_rotation_keeps_recent_records_and_drops_the_oldest(tmp_path):
    path = tmp_path / "audit.jsonl"

    for number in range(6):
        append_private_line(path, f"record-{number}", max_bytes=1, backups=3)

    names = sorted(item.name for item in tmp_path.iterdir())
    assert names == ["audit.jsonl", "audit.jsonl.1", "audit.jsonl.2", "audit.jsonl.3"]
    kept = [(tmp_path / name).read_text(encoding="utf-8").strip() for name in names]
    assert kept == ["record-5", "record-4", "record-3", "record-2"]


def test_a_small_log_is_not_rotated(tmp_path):
    path = tmp_path / "audit.jsonl"

    for number in range(3):
        append_private_line(path, f"record-{number}", max_bytes=10_000, backups=3)

    assert [item.name for item in tmp_path.iterdir()] == ["audit.jsonl"]


def test_a_failed_rotation_still_records_the_request(tmp_path, monkeypatch, caplog):
    path = tmp_path / "audit.jsonl"
    path.write_text("old\n", encoding="utf-8")

    def fail(*_args):
        raise OSError("read-only")

    monkeypatch.setattr("app.services.state_files.os.replace", fail)
    with caplog.at_level(logging.WARNING, logger=state_files.logger.name):
        append_private_line(path, "new", max_bytes=1, backups=3)

    assert path.read_text(encoding="utf-8") == "old\nnew\n"
    assert "Could not rotate" in caplog.text


def test_audit_limits():
    assert (security.AUDIT_MAX_BYTES, security.AUDIT_BACKUPS) == (5 * 1024 * 1024, 3)


# ── Startup ──


def test_startup_creates_a_private_data_directory(tmp_path):
    protect_data_dir(tmp_path / "data")

    assert mode(tmp_path / "data") == 0o700


def test_startup_tightens_an_existing_installation(tmp_path):
    data = tmp_path / "data"
    data.mkdir(mode=0o755)
    for name in ("config.json", "run_evidence.json"):
        (data / name).write_text("{}", encoding="utf-8")

    protect_data_dir(data)

    assert mode(data) == 0o700
    assert mode(data / "config.json") == 0o600
    assert (data / "config.json").read_text(encoding="utf-8") == "{}"
    # Unreachable for other users through the directory; left as it is.
    assert mode(data / "run_evidence.json") == 0o644


def test_startup_survives_a_directory_it_cannot_change(tmp_path, monkeypatch, caplog):
    data = tmp_path / "data"
    data.mkdir(mode=0o755)

    def refuse(*_args, **_kwargs):
        raise PermissionError("not the owner")

    monkeypatch.setattr(Path, "chmod", refuse)
    with caplog.at_level(logging.WARNING, logger=state_files.logger.name):
        protect_data_dir(data)

    assert "Could not restrict access" in caplog.text


# ── No writer bypasses the helper ──


def _file_writes(tree: ast.AST) -> list[int]:
    """Lines that write files: write_text(), write_bytes(), open() for writing."""
    lines = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", getattr(node.func, "id", ""))
        arguments = [*node.args, *(keyword.value for keyword in node.keywords)]
        constants = [item.value for item in arguments if isinstance(item, ast.Constant)]
        opens_for_writing = name == "open" and any(
            isinstance(value, str) and len(value) <= 3 and set(value) & WRITE_MODES for value in constants
        )
        if name in {"write_text", "write_bytes"} or opens_for_writing:
            lines.append(node.lineno)
    return lines


def test_the_write_detector_recognizes_the_usual_forms():
    source = "p.write_text('x')\np.open('a', encoding='utf-8')\nopen(p, mode='wb')\nopen(p)\np.open('rb')\n"

    assert _file_writes(ast.parse(source)) == [1, 2, 3]


def test_no_writer_bypasses_the_helper():
    sources = {path: ast.parse(path.read_text(encoding="utf-8")) for path in APP_DIR.rglob("*.py")}
    assert len(sources) > 50

    bypasses = {
        f"{path.relative_to(APP_DIR)}:{line}"
        for path, tree in sources.items()
        if path.name != "state_files.py"
        for line in _file_writes(tree)
    }
    assert bypasses == set()
