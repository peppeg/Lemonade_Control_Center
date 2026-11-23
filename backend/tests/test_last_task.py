from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.log_parser import parse_last_task


def _fake_journal(monkeypatch, lines):
    """Make parse_last_task see exactly these journal lines."""
    monkeypatch.setattr(
        "app.services.log_parser.subprocess.run",
        lambda command, **kwargs: SimpleNamespace(returncode=0, stdout="\n".join(lines)),
    )


def _slot(task, text, tag="Process", slot=0):
    return f"2026-11-23 16:07:41.036 [Info] ({tag}) 0.18.432.412 I slot print_timing: id  {slot} | task {task} | {text}"


def _prompt(task, tokens, tps=50.0, **kwargs):
    return _slot(task, f"prompt eval time =     484.83 ms /    {tokens} tokens (   17.96 ms per token,    {tps:.2f} tokens per second)", **kwargs)


def _eval(task, tokens, tps=28.3, **kwargs):
    return _slot(task, f"       eval time =    4699.53 ms /   {tokens} tokens (   35.33 ms per token,    {tps:.2f} tokens per second)", **kwargs)


def _total(task, seconds, tokens, **kwargs):
    return _slot(task, f"      total time =    {seconds * 1000:.2f} ms /   {tokens} tokens", **kwargs)


def _release(task, truncated=0, slot=0):
    return (
        "2026-11-23 16:07:41.037 [Info] (Process) 0.18.432.420 I slot      release: "
        f"id  {slot} | task {task} | stop processing: n_tokens = 10, truncated = {truncated}"
    )


def _completed(tokens_in, tokens_out, ttft=0.485, tps=28.3, model="Gemma-4-31B-it-MTP-GGUF", second=41):
    return (
        f"2026-11-23 16:07:{second}.037 [Info] (Process) Inference completed: model={model}, "
        f"tokens={tokens_in + tokens_out} (in={tokens_in}, out={tokens_out}), ttft={ttft}s, tps={tps}"
    )


def _task(task, tokens_in, tokens_out, seconds, truncated=0, **completed):
    return [
        _prompt(task, tokens_in),
        _eval(task, tokens_out),
        _total(task, seconds, tokens_in + tokens_out),
        _release(task, truncated),
        _completed(tokens_in, tokens_out, **completed),
    ]


def test_a_missing_total_time_is_not_taken_from_an_earlier_task(monkeypatch):
    """Lemonade 2026.45.3 can drop a line when threads interleave."""
    _fake_journal(monkeypatch, [
        *_task(7, 300, 317, 11.5, truncated=1, second=20),
        _prompt(9, 27, 55.69),
        _eval(9, 134, tag="Telemetry"),
        _completed(27, 134),
    ])

    stats = parse_last_task()

    assert (stats.input_tokens, stats.output_tokens, stats.prompt_eval_tps) == (27, 134, 55.69)
    assert stats.total_duration_seconds == 5.2  # 0.485 + 134 / 28.3
    assert stats.truncated is None


def test_a_task_without_any_timing_line_uses_its_own_telemetry(monkeypatch):
    _fake_journal(monkeypatch, [*_task(7, 300, 317, 11.5, second=20), _completed(27, 134)])

    stats = parse_last_task()

    assert stats.total_duration_seconds == 5.2
    assert stats.prompt_eval_tps == 56.25  # 27 / 0.48


def test_lines_that_land_after_their_own_telemetry_are_used(monkeypatch):
    _fake_journal(monkeypatch, [
        *_task(7, 300, 317, 11.5, second=20),
        _prompt(9, 27),
        _completed(27, 134),
        _eval(9, 134),
        _total(9, 5.3, 161),
        _release(9, truncated=1),
    ])

    stats = parse_last_task()

    assert stats.total_duration_seconds == 5.3
    assert stats.truncated is True


def test_late_lines_of_the_previous_task_are_ignored(monkeypatch):
    late = [_eval(7, 317), _total(7, 11.5, 617), _release(7, truncated=1)]
    _fake_journal(monkeypatch, [_prompt(7, 300), _completed(300, 317, second=20), *late, *_task(9, 27, 134, 5.3)])

    stats = parse_last_task()

    assert (stats.total_duration_seconds, stats.truncated) == (5.3, False)


def test_a_newer_task_still_being_logged_is_not_mixed_in(monkeypatch):
    _fake_journal(monkeypatch, [
        *_task(9, 27, 134, 5.3),
        _prompt(12, 900, 999.0),
        _eval(12, 134, 1.0),
        _total(12, 60.0, 1034),
        _release(12, truncated=1),
    ])

    stats = parse_last_task()

    assert (stats.input_tokens, stats.output_tokens, stats.generation_tps) == (27, 134, 28.3)
    assert (stats.prompt_eval_tps, stats.total_duration_seconds, stats.truncated) == (50.0, 5.3, False)


def test_tasks_that_ran_together_are_told_apart_by_their_tokens(monkeypatch):
    _fake_journal(monkeypatch, [
        *_task(1, 10, 10, 1.0, second=10),
        _prompt(9, 27, slot=0), _eval(9, 134, slot=0), _total(9, 5.3, 161, slot=0), _release(9, slot=0),
        _prompt(10, 40, 80.0, slot=1), _eval(10, 12, slot=1), _total(10, 9.9, 52, slot=1), _release(10, 1, slot=1),
        _completed(27, 134),
    ])

    stats = parse_last_task()

    assert (stats.prompt_eval_tps, stats.total_duration_seconds, stats.truncated) == (50.0, 5.3, False)


def test_the_same_task_number_in_another_slot_is_another_task(monkeypatch):
    _fake_journal(monkeypatch, [
        _prompt(9, 27, slot=0), _eval(9, 134, slot=0),
        _total(9, 99.0, 999, slot=1),
        _completed(27, 134),
    ])

    assert parse_last_task().total_duration_seconds == 5.2


def test_a_cached_prompt_still_fits_its_task(monkeypatch):
    _fake_journal(monkeypatch, [
        _prompt(9, 4, 70.0), _eval(9, 134), _total(9, 5.3, 138), _release(9), _completed(27, 134),
    ])

    stats = parse_last_task()

    assert (stats.input_tokens, stats.prompt_eval_tps, stats.total_duration_seconds) == (27, 70.0, 5.3)


@pytest.mark.parametrize(
    ("timings", "duration", "prompt_tps"),
    [
        pytest.param([_prompt(9, 27), _total(9, 5.3, 161)], 5.3, 50.0, id="total-of-this-task"),
        pytest.param([_prompt(9, 27), _total(9, 99.0, 999)], 5.2, 56.25, id="total-of-another-task"),
        pytest.param([_total(9, 5.3, 161)], 5.3, 56.25, id="total-only"),
        pytest.param([_total(9, 99.0, 999)], 5.2, 56.25, id="another-total-only"),
        pytest.param([_prompt(9, 4, 70.0)], 5.2, 70.0, id="cached-prompt-only"),
        pytest.param([_prompt(9, 5000)], 5.2, 56.25, id="prompt-of-another-task"),
        pytest.param([_release(9, truncated=1)], 5.2, 56.25, id="release-only"),
    ],
)
def test_partial_timings_must_fit_the_telemetry(monkeypatch, timings, duration, prompt_tps):
    _fake_journal(monkeypatch, [*timings, _completed(27, 134)])

    stats = parse_last_task()

    assert (stats.total_duration_seconds, stats.prompt_eval_tps, stats.truncated) == (duration, prompt_tps, None)


def test_an_earlier_task_with_the_same_tokens_is_not_used(monkeypatch):
    _fake_journal(monkeypatch, [*_task(7, 27, 134, 11.5, second=20), _completed(27, 134)])
    assert parse_last_task().total_duration_seconds == 5.2

    late = [_eval(7, 134), _total(7, 11.5, 161)]
    _fake_journal(monkeypatch, [_prompt(7, 27), _completed(27, 134, second=20), *late, *_task(9, 27, 134, 5.3)])
    assert parse_last_task().total_duration_seconds == 5.3


def test_the_newest_llama_cpp_task_is_used_without_telemetry(monkeypatch):
    _fake_journal(monkeypatch, [
        _prompt(1, 10, 11.0), _eval(1, 20, 12.0), _total(1, 3.0, 30), _release(1, truncated=1),
        _prompt(2, 40, 41.0), _eval(2, 50, 42.0),
    ])

    stats = parse_last_task()

    assert (stats.input_tokens, stats.output_tokens, stats.prompt_eval_tps, stats.generation_tps) == (40, 50, 41.0, 42.0)
    assert stats.truncated is None
    assert stats.total_duration_seconds == 2.2  # 40 / 41 + 50 / 42


def _untagged(prompt, out, total):
    return [
        f"prompt eval time = 100.00 ms / {prompt} tokens (1.00 ms per token, {prompt * 10:.2f} tokens per second)",
        f"       eval time = 100.00 ms / {out} tokens (1.00 ms per token, {out * 10:.2f} tokens per second)",
        f"      total time = {total * 1000:.2f} ms / {prompt + out} tokens",
    ]


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        pytest.param([*_untagged(91, 61, 9.0), *_untagged(30, 20, 8.0)], (30, 20, 300.0, 8.0), id="complete"),
        pytest.param([*_untagged(91, 61, 9.0), *_untagged(30, 20, 8.0)[:2]], (30, 20, 300.0, 0.2), id="missing-total"),
        pytest.param([*_untagged(91, 61, 9.0), *_untagged(30, 20, 8.0)[1:]], (None, 20, None, 8.0), id="missing-prompt"),
        pytest.param([*_untagged(91, 61, 9.0)[1:], *_untagged(30, 20, 8.0)], (30, 20, 300.0, 8.0), id="cut-window"),
        pytest.param([*_untagged(91, 61, 9.0), *_untagged(30, 20, 8.0), _completed(91, 61)], (91, 61, 910.0, 9.0), id="together"),
    ],
)
def test_timing_lines_without_a_task_id_are_kept_apart(monkeypatch, lines, expected):
    _fake_journal(monkeypatch, lines)

    stats = parse_last_task()

    assert (stats.input_tokens, stats.output_tokens, stats.prompt_eval_tps, stats.total_duration_seconds) == expected


def test_the_older_format_does_not_mix_two_records(monkeypatch):
    first = ["Input tokens: 40", "Output tokens: 12", "TTFT (s): 0.55", "TPS: 22.5"]

    _fake_journal(monkeypatch, [*first, _total(1, 9.0, 52), "Input tokens: 80", "Output tokens: 24"])
    stats = parse_last_task()
    assert (stats.input_tokens, stats.output_tokens, stats.ttft_seconds, stats.generation_tps) == (80, 24, None, None)
    assert stats.total_duration_seconds is None

    _fake_journal(monkeypatch, [*first[1:], "Input tokens: 80", "Output tokens: 24", "TTFT (s): 1.00", "TPS: 12.0"])
    stats = parse_last_task()
    assert (stats.input_tokens, stats.output_tokens, stats.ttft_seconds, stats.generation_tps) == (80, 24, 1.0, 12.0)


def test_the_older_format_keeps_the_first_value_of_each_field(monkeypatch):
    _fake_journal(monkeypatch, ["Input tokens: 80", "Output tokens: 24", "out=9, tps=12.0"])

    stats = parse_last_task()

    assert (stats.output_tokens, stats.generation_tps) == (24, 12.0)


def test_stray_fields_after_a_record_do_not_change_it(monkeypatch):
    _fake_journal(monkeypatch, [*_task(9, 27, 134, 5.3), "Server note: tps=999", "Output tokens: 5"])

    stats = parse_last_task()

    assert (stats.output_tokens, stats.generation_tps, stats.total_duration_seconds) == (134, 28.3, 5.3)


def test_real_journal_slice_has_the_last_task(monkeypatch):
    lines = (Path(__file__).parent / "fixtures" / "lemond_journal_11_7.log").read_text(encoding="utf-8").splitlines()
    _fake_journal(monkeypatch, lines)

    stats = parse_last_task()
    newest = [line for line in lines if "Inference completed" in line][-1]

    assert f"in={stats.input_tokens}, out={stats.output_tokens})" in newest
    assert f"tps={stats.generation_tps}" in newest
