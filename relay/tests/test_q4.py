"""専用サーバーで誰も接続していないときに物理が進むか（試作 Q4）と、負荷の記録（Q5）のテスト。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import relay  # noqa: E402


class Sim:
    """アドオンと機体の代わり。指示を受けて機体を出し、物理が動くなら値を変えながら送る。"""

    def __init__(self, physics=lambda name: True, stop_after=None, players=0):
        self.ops, self.com = relay.AddonOps(), relay.Commander()
        self.rec = relay.Recorder(expected_values=32)
        self.physics, self.stop_after, self.players = physics, stop_after, players
        self.vid, self.name, self.spawned_t, self.seq = -1, None, None, 0
        self.lifted_t = None
        self.lifts = 0

    def runner(self, vehicles, seconds=6.0):
        return relay.Q4Runner(self.ops, self.rec, self.com, vehicles=vehicles, pos=(-260.9, 8.0, -18949.0),
                              seconds=seconds, window=2.0, gap=0.5, timeout=2.0)

    def run(self, r, limit=200.0):
        t = 0.0
        self.ops.on_poll(ack=0, ok=True, vid=-1, sim=-1, players=self.players, t=t)
        while not r.done and t < limit:
            t += 0.05
            r.step(t)
            p = self.ops.pending()
            if p:
                if p["op"] == "spawn":
                    self.vid += 2
                    self.name, self.spawned_t, self.seq = p["args"][0], t, 0
                    self.lifted_t = t
                    self.ops.on_poll(ack=p["id"], ok=True, vid=self.vid, sim=1, players=self.players, t=t,
                                     pos=(0.0, 8.0, 0.0))
                elif p["op"] == "lift":
                    self.lifted_t, self.lifts = t, self.lifts + 1
                    self.ops.on_poll(ack=p["id"], ok=self.name is not None, vid=self.vid, sim=1, players=self.players, t=t)
                else:
                    self.name = None
                    self.ops.on_poll(ack=p["id"], ok=True, vid=-1, sim=-1, players=self.players, t=t)
            if self.name is not None:
                alive = self.stop_after is None or t - self.spawned_t < self.stop_after
                if alive:
                    self.seq += 1
                    # 物理が進んでいても、持ち上げてから2秒で落ちきって止まる（休んでいる機体）
                    moving = self.physics(self.name) and t - self.lifted_t < 2.0
                    v = [0.0] * 32
                    v[7] = -(t - self.lifted_t) * 9.8 if moving else 0.0  # 縦の速度（ch8）
                    self.rec.add(seq=self.seq, tick=self.seq * 3, values=v, t=t)
        return r


class Q4RunnerTest(unittest.TestCase):
    def test_moving_vehicle_passes(self):
        sim = Sim()
        r = sim.run(sim.runner(["a"]))
        q = r.summary()
        self.assertTrue(r.done)
        v = q["vehicles"][0]
        self.assertTrue(v["spawn_ok"])
        self.assertEqual(len(v["windows"]), 3)
        self.assertTrue(all(w["values"] > 0 and w["changed"] for w in v["windows"]))
        self.assertTrue(v["pass"])
        self.assertTrue(q["q4_pass"])

    def test_frozen_vehicle_fails(self):
        sim = Sim(physics=lambda name: False)
        q = sim.run(sim.runner(["a"])).summary()
        self.assertFalse(q["vehicles"][0]["pass"])
        self.assertFalse(q["q4_pass"])

    def test_values_stop_midway_fails(self):
        sim = Sim(stop_after=3.0)
        q = sim.run(sim.runner(["a"])).summary()
        v = q["vehicles"][0]
        self.assertEqual(v["windows"][-1]["values"], 0)
        self.assertFalse(v["pass"])

    def test_player_connected_fails(self):
        sim = Sim(players=1)
        q = sim.run(sim.runner(["a"])).summary()
        self.assertEqual(q["vehicles"][0]["max_players"], 1)
        self.assertFalse(q["vehicles"][0]["pass"])

    def test_two_vehicles_judged_separately(self):
        sim = Sim(physics=lambda name: name == "with_keep_active")
        q = sim.run(sim.runner(["plain", "with_keep_active"])).summary()
        self.assertEqual([v["name"] for v in q["vehicles"]], ["plain", "with_keep_active"])
        self.assertEqual([v["pass"] for v in q["vehicles"]], [False, True])
        self.assertTrue(q["q4_pass"])  # どちらか1台で物理が進めば、誰も接続しない形は使える

    def test_resting_vehicle_without_lift_fails(self):
        sim = Sim()
        r = sim.runner(["a"])
        r.lift = 0  # 持ち上げないと、落ちきったあとは止まって見える
        q = sim.run(r).summary()
        self.assertFalse(q["vehicles"][0]["pass"])

    def test_lift_each_window(self):
        sim = Sim()
        q = sim.run(sim.runner(["a"])).summary()
        self.assertEqual(sim.lifts, 3)
        self.assertEqual(q["vehicles"][0]["lifts"], [True, True, True])

    def test_addon_position_is_summarised_per_window(self):
        sim = Sim()
        r = sim.runner(["a"])
        t = 0.0
        sim.ops.on_poll(ack=0, ok=True, vid=-1, sim=-1, players=0, t=t)
        y = 8.0
        while not r.done and t < 100:
            t += 0.05
            r.step(t)
            p = sim.ops.pending()
            if p:
                sim.ops.on_poll(ack=p["id"], ok=True, vid=3, sim=1, players=0, t=t, pos=(0.0, y, 0.0))
            else:
                y = max(0.0, y - 0.5)
                sim.ops.on_poll(ack=0, ok=True, vid=3, sim=1, players=0, t=t, pos=(0.0, y, 0.0))
        pw = r.summary()["vehicles"][0]["addon_pos_windows"]
        self.assertEqual(len(pw), 3)
        self.assertTrue(all(w["samples"] > 0 for w in pw))
        self.assertLess(pw[0]["y_min"], pw[0]["y_max"])

    def test_spin_command_issued_per_vehicle(self):
        sim = Sim()
        sim.run(sim.runner(["a", "b"]))
        self.assertEqual(sim.com.issued(), 2)


class ProcessSamplerTest(unittest.TestCase):
    def test_cpu_percent_from_cpu_seconds(self):
        outputs = iter(["10.0 1000000000", "12.0 1100000000", "16.0 1200000000"])
        s = relay.ProcessSampler("server64", interval=5.0, cores=4, query=lambda: next(outputs))
        s.sample(t=0.0)
        s.sample(t=5.0)
        s.sample(t=10.0)
        r = s.summary()
        # 2秒/5秒/4コア = 10%、4秒/5秒/4コア = 20%
        self.assertEqual(r["cpu_percent_avg"], 15.0)
        self.assertEqual(r["cpu_percent_max"], 20.0)
        self.assertEqual(r["memory_mb_max"], round(1200000000 / 1048576, 1))
        self.assertTrue(r["available"])

    def test_missing_process(self):
        s = relay.ProcessSampler("server64", interval=5.0, cores=4, query=lambda: "")
        s.sample(t=0.0)
        self.assertFalse(s.summary()["available"])


if __name__ == "__main__":
    unittest.main()
