"""マイコンの Lua（game/q2_values_and_commands.lua）を、ゲームの代わりの環境で中継プログラムにつないで試す。"""

from __future__ import annotations

import sys
import threading
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import relay  # noqa: E402
from test_q1_lua import FakeVehicle, lupa  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[2] / "game" / "q2_values_and_commands.lua"


@unittest.skipIf(lupa is None, "lupa がない")
class LuaQ2Test(unittest.TestCase):
    def setUp(self):
        self.rec = relay.Recorder(expected_values=32)
        self.com = relay.Commander()
        self.server = relay.make_server("127.0.0.1", 0, self.rec, self.com)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.v = FakeVehicle(self.port, script=SCRIPT)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_outputs_start_at_zero(self):
        self.v.tick(5)
        self.assertEqual([self.v.outputs[i] for i in range(1, 9)], [0] * 8)

    def test_command_reaches_output_and_is_acked(self):
        self.v.tick(10)
        self.com.issue({1: 0.5, 8: -3.25})
        self.v.tick(6)
        self.assertEqual(self.v.outputs[1], 0.5)
        self.assertEqual(self.v.outputs[8], -3.25)
        self.assertEqual(self.v.outputs[2], 0)
        s = self.com.summary()
        self.assertEqual(s["acked"], 1)
        self.assertIsNotNone(s["commands"][0]["latency_s"])

    def test_ten_commands_in_a_row(self):
        self.v.tick(4)
        for i in range(10):
            self.com.issue({1: float(i % 2)})
            self.v.tick(6)
            self.assertEqual(self.v.outputs[1], float(i % 2))
        s = self.com.summary()
        self.assertEqual(s["acked"], 10)
        self.assertEqual(self.rec.summary()["missing"], 0)
        self.assertEqual(self.v.outputs[32], 0)  # エラーの返事なし

    def test_out_of_range_channel_is_ignored(self):
        self.v.tick(2)
        # 中継プログラムは 1〜8 しか出さないが、Lua 側でも範囲外を無視する
        self.v.lua.globals().httpReply(self.port, "", "ok|99|9=5,1=2")
        self.v.tick(1)
        self.assertEqual(self.v.outputs[1], 2)
        self.assertNotIn(9, [k for k, val in self.v.outputs.items() if val == 5])

    def test_old_command_id_is_not_reapplied(self):
        self.v.tick(2)
        g = self.v.lua.globals()
        g.httpReply(self.port, "", "ok|5|1=1")
        g.httpReply(self.port, "", "ok|4|1=7")
        self.v.tick(1)
        self.assertEqual(self.v.outputs[1], 1)

    def test_error_reply_is_counted(self):
        self.v.tick(2)
        self.v.lua.globals().httpReply(self.port, "", "connect(): Connection refused")
        self.v.tick(1)
        self.assertEqual(self.v.outputs[32], 1)

    def test_command_8_sends_nan_for_fault_test(self):
        self.v.tick(4)
        self.com.issue({8: 1.0})
        self.v.tick(8)
        last = self.v.sent[-1]
        self.assertIn("v=nan,nan", last)
        self.assertGreater(self.rec.summary()["received"], 0)

    def test_script_is_short_enough(self):
        self.assertLess(len(SCRIPT.read_text(encoding="utf-8")), 4096)


class QueuedVehicle(FakeVehicle):
    """ゲームの HTTP の代わり。要求を順に1 tick に1件ずつ送り、中継プログラムが止まっている間は溜める。"""

    def __init__(self, port: int):
        self.queue: list[str] = []
        self.relay_up = False
        super().__init__(port, script=SCRIPT)

    def _http_get(self, port, url):
        self.sent.append(url)
        self.queue.append(url)

    def tick(self, n: int = 1) -> None:
        for _ in range(n):
            if self.relay_up and self.queue:
                url = self.queue.pop(0)
                body = urllib.request.urlopen(f"http://127.0.0.1:{self.port}{url}", timeout=5).read().decode()
                self.pending.append((self.port, url, body))
            super().tick(1)


@unittest.skipIf(lupa is None, "lupa がない")
class BacklogTest(unittest.TestCase):
    def test_backlog_drains_and_commands_are_fast_again(self):
        rec = relay.Recorder(expected_values=32)
        com = relay.Commander()
        server = relay.make_server("127.0.0.1", 0, rec, com)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            v = QueuedVehicle(port)
            v.tick(60 * 50)            # 中継プログラムなしで50秒。待ちきれず送り直した要求が溜まる
            self.assertGreaterEqual(len(v.queue), 45)
            v.relay_up = True
            v.tick(120)                # 溜まった分が流れ切るのに十分な時間
            self.assertLessEqual(len(v.queue), 1)  # 最新の1件だけが送られ待ち
            com.issue({1: 1.0})
            for n in range(1, 30):
                v.tick(1)
                if com.summary()["acked"] == 1:
                    break
            self.assertLessEqual(n, 6, "溜まった要求が流れ切ったあとは、数 tick で指示が届く")
            self.assertEqual(v.outputs[1], 1.0)
            self.assertGreater(v.outputs[29], 0)  # 古い返事を無視した数
            self.assertGreater(rec.summary()["resent"], 0)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
