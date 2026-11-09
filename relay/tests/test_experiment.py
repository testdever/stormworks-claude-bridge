"""手順書を流す仕組み（試作 Q6・Q7）のテスト。"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import relay  # noqa: E402


class World:
    """アドオンと機体のマイコンの代わり。0.05 秒ごとに動く。"""

    def __init__(self, spawn_ok=True, first_value_delay=0.0, never_values=False):
        self.ops, self.com = relay.AddonOps(), relay.Commander()
        self.rec = relay.Recorder(expected_values=32)
        self.spawn_ok = spawn_ok
        self.vid, self.next_vid, self.seq, self.ack = -1, 10, 0, 0
        self.cmd = {i: 0.0 for i in range(1, 9)}
        self.paused_from = None
        self.player = (0.0, 5.0, 0.0)
        self.first_value_delay, self.never_values, self.spawned_t = first_value_delay, never_values, None
        self.moved_to = []
        self.ghost_from = None  # この時刻から、片付けられずに残った別の機体のマイコンも値を送る
        self.ghost_seq = 6

    def tick(self, t: float) -> None:
        if self.paused_from is not None and t >= self.paused_from:
            return  # ゲームが止まると、アドオンもマイコンも何も送らない
        if self.ghost_from is not None and t >= self.ghost_from:
            self.ghost_seq += 1
            self.rec.add(seq=self.ghost_seq, tick=3000 + self.ghost_seq * 3, values=[0.0] * 32, t=t)
        p = self.ops.pending()
        if p:
            ok = True
            if p["op"] == "spawn":
                ok = self.spawn_ok
                if ok:
                    self.next_vid += 1
                    self.vid, self.seq, self.ack = self.next_vid, 0, 0
                    self.spawned_t = t
                    self.cmd = {i: 0.0 for i in range(1, 9)}
            elif p["op"] == "despawn":
                self.vid = -1
            elif p["op"] == "move_player":
                self.moved_to.append(tuple(float(x) for x in p["args"]))
            self.ops.on_poll(ack=p["id"], ok=ok, vid=self.vid, sim=1 if self.vid >= 0 else -1, players=1, t=t)
        else:
            self.ops.on_poll(ack=0, ok=True, vid=self.vid, sim=1 if self.vid >= 0 else -1, players=1, t=t)
        if self.vid >= 0 and not self.never_values and t - self.spawned_t >= self.first_value_delay:
            body = self.com.reply_body()
            if body.startswith("ok|"):
                _, cid, rest = body.split("|", 2)
                for kv in rest.split(","):
                    ch, v = kv.split("=")
                    self.cmd[int(ch)] = float(v)
                self.ack = int(cid)
            self.seq += 1
            v = [0.0] * 32
            v[7] = -1.0 * (t % 3)  # 縦の速度（ch8）
            v[16] = (t * 1.25 * self.cmd[1]) % 1
            if self.cmd[8] > 0.5:
                v = [math.nan] * 32
            self.rec.add(seq=self.seq, tick=self.seq * 3, values=v, t=t, ack=self.ack)
            self.com.on_ack(self.ack, t=t)

    def run(self, script, limit=200.0):
        r = relay.ExperimentRunner(self.ops, self.rec, self.com, script)
        t = 0.0
        self.tick(t)
        while not r.done and t < limit:
            t += 0.05
            r.step(t)
            self.tick(t)
        return r


BASIC = {
    "name": "基本",
    "steps": [
        {"op": "move_player", "pos": [100, 5, 200]},
        {"op": "spawn", "vehicle": "claude_test", "offset": [0, 3, 15]},
        {"op": "wait", "seconds": 2, "label": "settle"},
        {"op": "set", "outputs": {"1": 1}},
        {"op": "wait", "seconds": 3, "label": "spinning"},
        {"op": "set", "outputs": {"1": 0}},
        {"op": "despawn"},
    ],
}


def with_steps(extra_after_spin, watch=None):
    s = {"name": "異常", "steps": [
        {"op": "spawn", "vehicle": "claude_test", "offset": [0, 3, 15]},
        {"op": "wait", "seconds": 2},
        {"op": "set", "outputs": {"1": 1}},
        {"op": "wait", "seconds": 2},
        *extra_after_spin,
        {"op": "wait", "seconds": 20},
        {"op": "despawn"},
    ]}
    if watch:
        s["watch"] = watch
    return s


class ExperimentRunnerTest(unittest.TestCase):
    def test_completes_without_anyone(self):
        w = World()
        r = w.run(BASIC)
        res = r.result()
        self.assertEqual(res["status"], "completed", res.get("reason"))
        self.assertTrue(all(s["ok"] for s in res["steps"]))
        self.assertEqual([s["op"] for s in res["steps"]],
                         ["move_player", "spawn", "wait", "set", "wait", "set", "despawn"])
        self.assertEqual(w.moved_to, [(100.0, 5.0, 200.0)])
        self.assertEqual(w.vid, -1)
        labels = {s.get("label") for s in res["steps"]}
        self.assertIn("spinning", labels)

    def test_vehicle_vanishing_stops_within_10s(self):
        w = World()
        r = w.run(with_steps([{"op": "inject", "kind": "despawn"}]))
        res = r.result()
        self.assertEqual(res["status"], "stopped")
        self.assertIn("機体が消えた", res["reason"])
        self.assertLessEqual(res["stop_latency_s"], 10.0)

    def test_broken_values_stop(self):
        w = World()
        r = w.run(with_steps([{"op": "inject", "kind": "nan"}]))
        res = r.result()
        self.assertEqual(res["status"], "stopped")
        self.assertIn("値が壊れた", res["reason"])
        self.assertLessEqual(res["stop_latency_s"], 10.0)
        self.assertEqual(w.vid, -1)  # 止めたら片付ける

    def test_game_pause_stops(self):
        w = World()
        w.paused_from = 6.0
        r = w.run(with_steps([{"op": "wait", "seconds": 1, "label": "ここで一時停止"}]))
        res = r.result()
        self.assertEqual(res["status"], "stopped")
        self.assertTrue("途切れた" in res["reason"], res["reason"])
        self.assertLessEqual(res["stopped_at_s"] - 6.0, 10.0)

    def test_stop_if_condition(self):
        w = World()
        script = with_steps([], watch={"stop_if": [{"ch": 8, "lt": -1.5, "reason": "縦の速度が -1.5 を下回った"}]})
        res = w.run(script).result()
        self.assertEqual(res["status"], "stopped")
        self.assertIn("縦の速度が -1.5 を下回った", res["reason"])

    def test_spawn_failure_stops(self):
        w = World(spawn_ok=False)
        res = w.run(BASIC).result()
        self.assertEqual(res["status"], "stopped")
        self.assertIn("機体を置けなかった", res["reason"])

    def test_slow_first_values_after_move_are_waited_for(self):
        w = World(first_value_delay=6.0)  # プレイヤーを移した直後で、機体が動き出すまで6秒かかる
        res = w.run(BASIC).result()
        self.assertEqual(res["status"], "completed", res.get("reason"))

    def test_no_values_at_all_stops_after_grace(self):
        w = World(never_values=True)
        res = w.run(BASIC).result()
        self.assertEqual(res["status"], "stopped")
        self.assertIn("値が届かない", res["reason"])

    def test_values_from_two_vehicles_stop(self):
        w = World()
        w.ghost_from = 0.0
        r = w.run(BASIC)
        res = r.result()
        self.assertEqual(res["status"], "stopped")
        self.assertIn("2台以上のマイコン", res["reason"])
        self.assertLess(res["stopped_at_s"], 4.0)

    def test_respawn_does_not_look_like_two_vehicles(self):
        script = {"name": "置き直し", "steps": [
            {"op": "spawn", "vehicle": "claude_test", "offset": [0, 3, 15]},
            {"op": "wait", "seconds": 2},
            {"op": "spawn", "vehicle": "claude_test", "offset": [0, 3, 15]},  # 前の機体を片付けてから置く
            {"op": "wait", "seconds": 3},
            {"op": "despawn"},
        ]}
        r = World().run(script)
        self.assertEqual(r.result()["status"], "completed", r.result()["reason"])

    def test_bad_script_is_rejected(self):
        with self.assertRaises(ValueError):
            relay.ExperimentRunner(relay.AddonOps(), relay.Recorder(), relay.Commander(),
                                   {"steps": [{"op": "fly"}]})


if __name__ == "__main__":
    unittest.main()
