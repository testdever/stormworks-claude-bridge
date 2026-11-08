"""中継プログラム（試作 Q1）のテスト。python -m unittest discover -s relay/tests"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import relay  # noqa: E402


def values(n: int = 32) -> list[float]:
    return [float(i) for i in range(n)]


class RecorderSummaryTest(unittest.TestCase):
    def make(self) -> relay.Recorder:
        return relay.Recorder(expected_values=32)

    def feed(self, rec: relay.Recorder, per_sec: int, seconds: int, skip: set[int] = frozenset()) -> None:
        seq = 0
        for s in range(seconds):
            for k in range(per_sec):
                seq += 1
                if seq in skip:
                    continue
                rec.add(seq=seq, tick=seq * 2, values=values(), t=s + k / per_sec)

    def test_steady_stream_passes(self):
        rec = self.make()
        self.feed(rec, per_sec=30, seconds=61)
        s = rec.summary()
        self.assertEqual(s["missing"], 0)
        self.assertEqual(s["min_per_sec"], 30)
        self.assertTrue(s["q1_pass"])

    def test_gap_in_sequence_is_counted_and_fails(self):
        rec = self.make()
        self.feed(rec, per_sec=30, seconds=61, skip={100, 101})
        s = rec.summary()
        self.assertEqual(s["missing"], 2)
        self.assertFalse(s["q1_pass"])

    def test_slow_second_fails(self):
        rec = self.make()
        self.feed(rec, per_sec=9, seconds=61)
        s = rec.summary()
        self.assertEqual(s["min_per_sec"], 9)
        self.assertFalse(s["q1_pass"])

    def test_too_short_fails(self):
        rec = self.make()
        self.feed(rec, per_sec=30, seconds=30)
        self.assertFalse(rec.summary()["q1_pass"])

    def test_wrong_value_count_fails(self):
        rec = self.make()
        self.feed(rec, per_sec=30, seconds=61)
        rec.add(seq=99999, tick=0, values=values(31), t=61.5)
        s = rec.summary()
        self.assertEqual(s["bad_values"], 1)
        self.assertFalse(s["q1_pass"])

    def test_duplicate_is_counted(self):
        rec = self.make()
        self.feed(rec, per_sec=30, seconds=61)
        rec.add(seq=5, tick=10, values=values(), t=61.5)
        self.assertEqual(rec.summary()["duplicates"], 1)

    def test_empty(self):
        s = self.make().summary()
        self.assertEqual(s["received"], 0)
        self.assertFalse(s["q1_pass"])


class ParseTest(unittest.TestCase):
    def test_parse_query(self):
        seq, tick, vals = relay.parse_q1("/q1?s=3&t=7&v=1.5,-2,3e-05,nan")
        self.assertEqual((seq, tick), (3, 7))
        self.assertEqual(vals[:3], [1.5, -2.0, 3e-05])
        self.assertNotEqual(vals[3], vals[3])  # nan

    def test_parse_rejects_missing_fields(self):
        with self.assertRaises(ValueError):
            relay.parse_q1("/q1?s=3")


class ServerTest(unittest.TestCase):
    def test_http_roundtrip_writes_log(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "q1.jsonl"
            rec = relay.Recorder(expected_values=32, log_path=log)
            server = relay.make_server("127.0.0.1", 0, rec)
            port = server.server_address[1]
            th = threading.Thread(target=server.serve_forever, daemon=True)
            th.start()
            try:
                v = ",".join(str(x) for x in values())
                body = urllib.request.urlopen(f"http://127.0.0.1:{port}/q1?s=1&t=2&v={v}", timeout=5).read()
                self.assertEqual(body, b"ok")
                bad = urllib.request.urlopen(f"http://127.0.0.1:{port}/q1?s=x", timeout=5).read()
                self.assertTrue(bad.startswith(b"error"))
            finally:
                server.shutdown()
                server.server_close()
                rec.close()
            lines = log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["seq"], 1)
            self.assertEqual(rec.summary()["malformed"], 1)


if __name__ == "__main__":
    unittest.main()
