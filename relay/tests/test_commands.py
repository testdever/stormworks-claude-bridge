"""中継プログラムの指示の受け渡し（試作 Q2）のテスト。"""

from __future__ import annotations

import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import relay  # noqa: E402


class CommanderTest(unittest.TestCase):
    def test_no_command_replies_plain_ok(self):
        c = relay.Commander()
        self.assertEqual(c.reply_body(), "ok")

    def test_issued_command_is_in_reply_until_acked(self):
        c = relay.Commander()
        cid = c.issue({1: 0.5, 3: -2.0}, t=10.0)
        self.assertEqual(cid, 1)
        self.assertEqual(c.reply_body(), "ok|1|1=0.5,3=-2")
        c.on_ack(0, t=10.2)
        self.assertEqual(c.reply_body(), "ok|1|1=0.5,3=-2")
        c.on_ack(1, t=10.5)
        self.assertEqual(c.reply_body(), "ok")

    def test_latency_is_measured_from_issue_to_first_ack(self):
        c = relay.Commander()
        c.issue({1: 1.0}, t=5.0)
        c.on_ack(1, t=5.25)
        c.on_ack(1, t=6.0)  # 2回目の通知で上書きしない
        s = c.summary()
        self.assertEqual(s["commands"][0]["latency_s"], 0.25)

    def test_newer_command_replaces_older_and_ack_covers_both(self):
        c = relay.Commander()
        c.issue({1: 1.0}, t=1.0)
        c.issue({1: 2.0}, t=2.0)
        self.assertEqual(c.reply_body(), "ok|2|1=2")
        c.on_ack(2, t=2.5)
        lat = [x["latency_s"] for x in c.summary()["commands"]]
        self.assertEqual(lat, [1.5, 0.5])

    def test_q2_pass_requires_ten_acked_within_two_seconds(self):
        c = relay.Commander()
        for i in range(10):
            c.issue({1: float(i)}, t=i * 3.0)
            c.on_ack(i + 1, t=i * 3.0 + 0.2)
        self.assertTrue(c.summary()["q2_pass"])

    def test_q2_fails_when_one_is_slow_or_missing(self):
        c = relay.Commander()
        for i in range(10):
            c.issue({1: float(i)}, t=i * 3.0)
            if i != 9:
                c.on_ack(i + 1, t=i * 3.0 + (2.5 if i == 7 else 0.2))
        s = c.summary()
        self.assertFalse(s["q2_pass"])
        self.assertEqual(s["acked"], 9)
        self.assertEqual(s["max_latency_s"], 2.5)

    def test_format_value(self):
        self.assertEqual(relay.format_value(1.0), "1")
        self.assertEqual(relay.format_value(0.125), "0.125")
        self.assertEqual(relay.format_value(-1e-07), "-1e-07")


class ParseAckTest(unittest.TestCase):
    def test_ack_is_optional(self):
        self.assertEqual(relay.parse_values("/v?s=1&t=2&v=1,2")[3], None)
        self.assertEqual(relay.parse_values("/v?s=1&t=2&a=4&v=1,2")[3], 4)


class ServerCommandTest(unittest.TestCase):
    def test_cmd_endpoint_and_reply(self):
        rec = relay.Recorder(expected_values=2)
        com = relay.Commander()
        server = relay.make_server("127.0.0.1", 0, rec, com)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        get = lambda path: urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5).read().decode()
        try:
            self.assertEqual(get("/v?s=1&t=1&a=0&v=1,2"), "ok")
            self.assertEqual(get("/cmd?1=0.5&2=1"), "id=1")
            self.assertEqual(get("/v?s=2&t=4&a=0&v=1,2"), "ok|1|1=0.5,2=1")
            self.assertEqual(get("/v?s=3&t=7&a=1&v=1,2"), "ok")
            with self.assertRaises(urllib.error.HTTPError) as cm:
                get("/cmd?x=1")
            self.assertEqual(cm.exception.code, 400)
            self.assertTrue(cm.exception.read().decode().startswith("error"))
            self.assertEqual(get("/q1?s=4&t=10&v=1,2"), "ok")  # Q1 の Lua もそのまま使える
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(com.summary()["acked"], 1)
        self.assertEqual(rec.summary()["received"], 4)


if __name__ == "__main__":
    unittest.main()
