from datetime import datetime

from rcf.parser import LogParser, infer_level, split_line


def test_split_syslog_line():
    rec = split_line("Jun 14 15:16:01 combo sshd(pam_unix)[19939]: authentication failure; rhost=218.188.2.4", 7, 2005)
    assert rec.line_no == 7
    assert rec.timestamp == datetime(2005, 6, 14, 15, 16, 1)
    assert rec.host == "combo"
    assert rec.component == "sshd(pam_unix)"
    assert rec.message.startswith("authentication failure")
    assert rec.level == "ERROR"


def test_split_iso_line():
    rec = split_line("2026-10-11T10:00:05.123+00:00 web01 nginx[12]: worker process 13 started", 1, 1999)
    assert rec.timestamp == datetime(2026, 10, 11, 10, 0, 5)
    assert rec.component == "nginx"
    assert rec.level == "INFO"


def test_unknown_format_keeps_whole_line():
    rec = split_line("something odd with no header", 3, 2026)
    assert rec.timestamp is None and rec.component is None
    assert rec.message == "something odd with no header"


def test_infer_level():
    assert infer_level("ERROR: could not open file") == "ERROR"
    assert infer_level("[warn] disk almost full") == "WARNING"
    assert infer_level("Failed password for root") == "ERROR"
    assert infer_level("Connection timed out") == "ERROR"
    assert infer_level("Started Session 4 of user bob.") == "INFO"


def test_same_shape_lines_share_a_pattern_and_keep_values():
    lines = [
        "Dec 10 07:08:10 h sshd[1]: Failed password for root from 1.2.3.4 port 100 ssh2",
        "Dec 10 07:08:11 h sshd[2]: Failed password for root from 5.6.7.8 port 200 ssh2",
    ]
    p = LogParser(year=2026)
    a, b = p.parse_lines(lines)
    assert a.pattern_id == b.pattern_id
    assert p.template(a.pattern_id) == "sshd: Failed password for root from <IP> port <NUM> ssh2"
    assert a.values == ["1.2.3.4", "100"]
    assert b.values == ["5.6.7.8", "200"]


def test_failed_and_accepted_logins_stay_separate():
    lines = [
        "Dec 10 06:55:46 h sshd[1]: Accepted password for admin from 1.2.3.4 port 1 ssh2",
        "Dec 10 07:08:10 h sshd[2]: Failed password for root from 1.2.3.4 port 2 ssh2",
    ]
    p = LogParser(year=2026)
    ok, bad = p.parse_lines(lines)
    assert ok.pattern_id != bad.pattern_id
    assert "Failed" in p.template(bad.pattern_id)


def test_original_line_numbers_survive_blank_lines():
    lines = ["Oct 11 09:00:01 h CRON[1]: tick", "", "Oct 11 09:01:01 h CRON[2]: tick"]
    recs = LogParser(year=2026).parse_lines(lines)
    assert [r.line_no for r in recs] == [1, 3]


def test_year_rolls_over_from_december_to_january():
    lines = ["Dec 31 23:59:59 h CRON[1]: tick", "Jan  1 00:00:01 h CRON[2]: tick"]
    a, b = LogParser(year=2025).parse_lines(lines)
    assert a.timestamp.year == 2025 and b.timestamp.year == 2026
    assert b.timestamp > a.timestamp


def test_parse_fixture_file(data_path):
    recs = LogParser(year=2026).parse_file(data_path("normal_20.log"))
    assert len(recs) == 20
    assert all(r.timestamp for r in recs)


def test_docker_timestamp_lines():
    rec = split_line("2026-10-11T16:00:00.123456789Z 2026/10/11 16:00:00 [emerg] 1#1: unknown directive \"listn\"", 4, 2000)
    assert rec.timestamp == datetime(2026, 10, 11, 16, 0, 0)
    assert rec.host is None and rec.component is None
    assert rec.message.startswith("2026/10/11 16:00:00 [emerg]")
    assert rec.level == "CRITICAL"


def test_docker_line_with_plain_message():
    rec = split_line("2026-10-11T16:00:01Z Failed password for root from 172.17.0.3 port 4242 ssh2", 1, 2000)
    assert rec.timestamp == datetime(2026, 10, 11, 16, 0, 1)
    assert rec.message.startswith("Failed password")
    assert rec.level == "ERROR"


def test_embedded_levels():
    assert infer_level("2026-10-11 16:00:00.1 UTC [1] FATAL:  data directory has wrong ownership") == "CRITICAL"
    assert infer_level("2026/10/11 16:00:00 [warn] 1#1: conflicting server name") == "WARNING"
    assert infer_level("2026-10-11 16:00:00.1 UTC [1] LOG:  database system is ready") == "INFO"
