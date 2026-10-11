from datetime import datetime

from analyze import main
from rcf import analyze_file
from rcf.flags import apply_flags
from rcf.grouping import group_records, time_span
from rcf.parser import LogParser


def test_group_counts_and_times(data_path):
    p = LogParser(year=2026)
    recs = p.parse_file(data_path("normal_20.log"))
    groups = group_records(recs, p)
    cron = next(g for g in groups.values() if g.template.startswith("CRON:"))
    assert cron.count == 10
    assert cron.first_seen == datetime(2026, 10, 11, 9, 0, 1)
    assert cron.last_seen == datetime(2026, 10, 11, 9, 9, 1)
    assert cron.line_numbers[:3] == [1, 3, 6]
    assert sum(cron.per_minute.values()) == 10
    assert sum(g.count for g in groups.values()) == len(recs)


def test_normal_log_has_nothing_suspicious(data_path):
    result = analyze_file(data_path("normal_20.log"), year=2026)
    assert result.suspicious == []


def test_disk_full_is_ranked_first(data_path):
    result = analyze_file(data_path("disk_full_40.log"), year=2026)
    top = result.suspicious[0]
    assert "No space left on device" in top.template
    assert set(top.flags) == {"error_words", "new_pattern", "spike"}
    assert top.line_numbers == list(range(27, 37))


def test_baseline_marks_only_unseen_patterns_new(data_path):
    result = analyze_file(data_path("disk_full_40.log"), baseline_path=data_path("normal_20.log"), year=2026)
    new = {g.template for g in result.groups.values() if "new_pattern" in g.flags}
    assert not any(t.startswith("CRON:") for t in new)
    assert any("Directory index full" in t for t in new)


def test_ssh_bruteforce_spike(data_path):
    result = analyze_file(data_path("ssh_bruteforce_30.log"), year=2026)
    top = result.suspicious[0]
    assert top.template.startswith("sshd: Failed password for root")
    assert "spike" in top.flags and top.count == 14


def test_steady_errors_are_not_a_spike():
    # One error every minute for 10 minutes: an error, but not a spike.
    lines = [f"Oct 11 09:{m:02d}:00 h app[1]: ERROR: retry failed" for m in range(10)]
    p = LogParser(year=2026)
    recs = p.parse_lines(lines)
    groups = group_records(recs, p)
    start, end = time_span(recs)
    (g,) = apply_flags(groups, start, end)
    assert "error_words" in g.flags and "spike" not in g.flags


def test_cli_prints_top_groups(data_path, capsys):
    assert main([data_path("disk_full_40.log"), "--top", "2", "--year", "2026"]) == 0
    out = capsys.readouterr().out
    assert "#1" in out and "#2" in out and "#3" not in out
    assert "lines:   27, 28" in out


def test_cli_empty_file(tmp_path, capsys):
    empty = tmp_path / "empty.log"
    empty.write_text("\n\n")
    assert main([str(empty)]) == 1
    assert "empty" in capsys.readouterr().out


def _flag(lines):
    p = LogParser(year=2026)
    recs = p.parse_lines(lines)
    groups = group_records(recs, p)
    start, end = time_span(recs)
    return groups, apply_flags(groups, start, end)


def test_new_info_only_pattern_is_not_suspicious_alone():
    # A reboot at the end prints a brand-new INFO line: it is "new" but not suspicious by itself.
    lines = [f"Oct 11 09:{m:02d}:01 h CRON[{m}]: (root) CMD (run-parts /etc/cron.hourly)" for m in range(10)]
    lines.append("Oct 11 09:59:00 h kernel: Linux version 2.6.5 started")
    groups, flagged = _flag(lines)
    boot = next(g for g in groups.values() if g.template.startswith("kernel:"))
    assert "new_pattern" in boot.flags
    assert boot not in flagged


def test_new_warning_pattern_is_suspicious():
    lines = [f"Oct 11 09:{m:02d}:01 h CRON[{m}]: (root) CMD (run-parts /etc/cron.hourly)" for m in range(10)]
    lines.append("Oct 11 09:59:00 h xinetd[5]: warning: can't get client address: Connection reset by peer")
    _, flagged = _flag(lines)
    assert [g.template for g in flagged] == ["xinetd: warning: can't get client address: Connection reset by peer"]
    assert flagged[0].flags == ["error_words", "new_pattern"]


def test_quiet_gaps_do_not_create_spikes():
    # 6 lines a minute, every active minute, with a week-long silence in between: steady, not a spike.
    lines = []
    for day in (1, 8):
        for m in range(5):
            lines += [f"Oct {day:02d} 09:{m:02d}:{s:02d} h ftpd[1]: connection from 10.0.0.1" for s in range(6)]
    _, flagged = _flag(lines)
    assert flagged == []
