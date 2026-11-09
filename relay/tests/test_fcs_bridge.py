"""FCS のつなぎの Lua（game/fcs_bridge.lua）を、ゲームの代わりの環境で中継プログラムにつないで試す。"""

from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import relay  # noqa: E402
from test_q1_lua import FakeVehicle, lupa  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[2] / "game" / "fcs_bridge.lua"


class FcsRig(FakeVehicle):
    """FCS のデバッグ出力の代わり。砲身の角度（ch20、回転数）を変えると、反動に見える。"""

    def __init__(self, port: int, reply: bool = True):
        super().__init__(port, reply=reply, script=SCRIPT)
        self.nums = {7: 3.04, 8: 2037.5, 9: 3.2, 13: 0.15, 20: 3.2 / 360, 21: 0.0}
        self.ready = True
        self.bools: dict[int, bool] = {}
        g = self.lua.globals()
        g.input = self.lua.table_from({"getNumber": lambda i: self.nums.get(int(i), 0.0),
                                       "getBool": lambda i: self.ready if int(i) == 5 else False})
        g.output = self.lua.table_from({"setNumber": self._set_number, "setBool": self._set_bool})

    def _set_bool(self, ch, v):
        self.bools[int(ch)] = bool(v)

    def kick(self):
        """1 tick だけ砲身が 0.5°跳ねる（撃った）。"""
        self.nums[20] += 0.5 / 360
        self.tick(1)
        self.nums[20] -= 0.5 / 360


@unittest.skipIf(lupa is None, "lupa がない")
class FcsBridgeTest(unittest.TestCase):
    def setUp(self):
        self.rec = relay.Recorder(expected_values=32)
        self.com = relay.Commander()
        self.server = relay.make_server("127.0.0.1", 0, self.rec, self.com)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_sends_only_the_selected_channels_and_not_every_tick(self):
        v = FcsRig(self.port)
        v.tick(60)
        self.assertLessEqual(len(v.sent), 8, "1秒に6回ほど")
        self.assertGreaterEqual(len(v.sent), 4)
        self.assertIn("&ch=7,8,9,13,20,21&", v.sent[-1])
        self.assertEqual(self.rec.summary()["bad_values"], 0)

    def test_shot_is_detected_every_tick_and_reaches_the_relay(self):
        v = FcsRig(self.port)
        v.tick(10)
        v.nums[9] = 3.21    # 撃った瞬間の解。砲身は 3.2° なので、ずれ -0.01°
        v.tick(1)
        v.kick()
        v.tick(15)
        shots = self.rec.shots()
        self.assertEqual(len(shots), 1)
        self.assertAlmostEqual(shots[0]["diff"], -0.01, places=4)
        self.assertAlmostEqual(shots[0]["range"], 2037.5, places=1)
        self.assertAlmostEqual(shots[0]["tof"], 3.04, places=2)
        self.assertEqual(v.outputs[29], 1)

    def test_recoil_is_counted_once_and_needs_ready(self):
        v = FcsRig(self.port)
        v.tick(10)
        v.kick()
        v.kick()            # 揺れ戻し。1秒以内は同じ1発
        v.tick(70)
        v.ready = False
        v.tick(10)
        v.kick()            # 射撃可でないときの動きは、撃ったとみなさない
        v.tick(15)
        self.assertEqual(len(self.rec.shots()), 1)

    def test_fire_permission_and_target_come_from_the_relay(self):
        v = FcsRig(self.port)
        v.tick(5)
        self.com.issue({1: -1985.9, 2: -24089.3, 3: -0.2, 5: 1})
        v.tick(15)
        self.assertTrue(v.bools[1])
        self.assertAlmostEqual(v.outputs[2], -24089.3, places=3)
        self.com.issue({5: 0})
        v.tick(15)
        self.assertFalse(v.bools[1])

    def test_fire_permission_turns_off_when_the_relay_is_gone(self):
        v = FcsRig(self.port)
        v.tick(5)
        self.com.issue({5: 1})
        v.tick(15)
        self.assertTrue(v.bools[1])
        v.reply = False     # 中継プログラムが止まった
        v.tick(150)
        self.assertFalse(v.bools[1], "返事が2秒来なければ、自分で射撃許可を切る")

    def test_shots_are_kept_until_the_relay_answers(self):
        v = FcsRig(self.port, reply=False)
        v.tick(10)
        v.kick()
        v.tick(200)
        g = v.lua.globals()
        self.assertEqual(g.shotN, 1)
        self.assertEqual(len(self.rec.shots()), 0)
        v.reply = True
        v.tick(700)         # 送り直しの間隔が伸びているので、次に送るまで待つ
        self.assertEqual(len(self.rec.shots()), 1)

    def test_script_is_short_enough(self):
        self.assertLess(len(SCRIPT.read_text(encoding="utf-8")), 8192)


class FcsRelayTest(unittest.TestCase):
    def test_parse_shots(self):
        s = relay.parse_shots("/v?s=1&shot=3:120:-0.00280:3.23000:2037.50:0.150:3.040;4:270:0.001:3.2:2037:0.1:3.0")
        self.assertEqual(s[0]["n"], 3)
        self.assertEqual(s[0]["tick"], 120)
        self.assertAlmostEqual(s[0]["diff"], -0.0028)
        with self.assertRaises(ValueError):
            relay.parse_shots("/v?shot=1:2:3")

    def test_partial_channels_are_placed_by_number(self):
        rec = relay.Recorder(expected_values=32)
        got = []
        rec.add_listener(lambda t, seq, tick, values: got.append(values))
        rec.add(1, 1, [3.0, 2000.0], t=0.0, channels=[7, 8])
        self.assertEqual(got[0][6], 3.0)
        self.assertEqual(got[0][7], 2000.0)
        self.assertEqual(len(got[0]), 32)
        self.assertEqual(rec.summary()["bad_values"], 0)

    def test_same_shot_sent_twice_is_counted_once(self):
        rec = relay.Recorder(expected_values=32)
        shot = {"n": 1, "tick": 5, "diff": 0.0, "req": 3.0, "range": 2000.0, "pred": 0.1, "tof": 3.0}
        rec.add(1, 1, [1.0], t=0.0, channels=[7], shots=[shot])
        rec.add(2, 4, [1.0], t=0.1, channels=[7], shots=[shot])
        self.assertEqual(rec.shot_count(), 1)

    def test_fcs_summary_counts_hits_per_shot_by_range(self):
        shots = [
            {"n": 1, "t": 10.0, "range": 1003.0, "diff": 0.0, "pred": 0.1, "tof": 1.5},
            {"n": 2, "t": 20.0, "range": 1001.0, "diff": 0.01, "pred": 0.1, "tof": 1.5},
            {"n": 3, "t": 40.0, "range": 2040.0, "diff": -0.005, "pred": 0.1, "tof": 3.0},
        ]
        damage = [{"t": 11.6, "vehicle": 9}, {"t": 11.7, "vehicle": 9},   # 1発目が当たった
                  {"t": 21.5, "vehicle": 5},                              # 2発目のころ、別の機体
                  {"t": 43.2, "vehicle": 9}]                              # 3発目が当たった
        f = relay.fcs_summary(shots, damage, {9})
        self.assertEqual([r["hit"] for r in f["shots"]], [True, False, True])
        g = {x["range_m"]: x for x in f["by_range"]}
        self.assertEqual((g[1000]["shots"], g[1000]["hits"]), (2, 1))
        self.assertEqual((g[2000]["shots"], g[2000]["hits"]), (1, 1))
        self.assertAlmostEqual(f["shots"][1]["aim_miss_m"], 1001.0 * 0.000174533, places=3)
        self.assertIn("1発中 1発当たり", relay.report_fcs(f)[1])

    def test_commands_not_yet_received_are_sent_together(self):
        c = relay.Commander()
        c.issue({5: 0.0}, t=1.0)         # 射撃許可を切る
        c.issue({1: 100.0, 2: 5.0}, t=1.1)  # その直後に座標を渡し直す
        self.assertEqual(c.reply_body(), "ok|2|1=100,2=5,5=0")
        c.on_ack(2, t=1.2)
        self.assertEqual(c.reply_body(), "ok")


if __name__ == "__main__":
    unittest.main()
