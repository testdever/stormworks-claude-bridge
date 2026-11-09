"""アドオンへの指示（試作 Q3：機体を置く・片付ける）のテスト。"""

from __future__ import annotations

import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import relay  # noqa: E402

try:
    import lupa  # type: ignore
except ImportError:  # pragma: no cover
    lupa = None

ADDON = Path(__file__).resolve().parents[2] / "game" / "addon" / "ClaudeBridge" / "script.lua"


class AddonOpsTest(unittest.TestCase):
    def test_reply_sends_oldest_pending_op_in_order(self):
        ops = relay.AddonOps()
        self.assertEqual(ops.reply_body(), "ok")
        a = ops.spawn("test boat", (0, 3, 15), relative=True, t=1.0)
        b = ops.despawn(t=1.1)
        self.assertEqual(ops.reply_body(), f"ok|{a}|spawn|test boat|0|3|15|1")
        ops.on_poll(ack=a, ok=True, vid=7, sim=0, players=1, t=1.5)
        self.assertEqual(ops.reply_body(), f"ok|{b}|despawn")
        ops.on_poll(ack=b, ok=True, vid=-1, sim=-1, players=1, t=1.7)
        self.assertEqual(ops.reply_body(), "ok")
        s = ops.summary()
        self.assertEqual([(o["op"], o["ok"], o["latency_s"]) for o in s["ops"]],
                         [("spawn", True, 0.5), ("despawn", True, 0.6)])

    def test_failed_op_is_recorded(self):
        ops = relay.AddonOps()
        a = ops.spawn("nope", (0, 0, 0), relative=False, t=0.0)
        ops.on_poll(ack=a, ok=False, vid=-1, sim=-1, players=1, t=0.2)
        self.assertFalse(ops.get(a)["ok"])

    def test_poll_without_new_ack_does_not_complete(self):
        ops = relay.AddonOps()
        a = ops.spawn("x", (0, 0, 0), relative=False, t=0.0)
        ops.on_poll(ack=0, ok=True, vid=-1, sim=-1, players=1, t=0.2)
        self.assertIsNone(ops.get(a)["done_t"])
        self.assertEqual(ops.status()["players"], 1)

    def test_bad_vehicle_name_is_rejected(self):
        ops = relay.AddonOps()
        for bad in ("", "a|b", "a\nb"):
            with self.assertRaises(ValueError):
                ops.spawn(bad, (0, 0, 0), relative=False)


class Q3RunnerTest(unittest.TestCase):
    def run_cycles(self, spawn_ok=True, addon_answers=True, cycles=3):
        ops = relay.AddonOps()
        rec = relay.Recorder(expected_values=32)
        r = relay.Q3Runner(ops, rec, vehicle="boat", offset=(0, 3, 15), relative=True,
                           cycles=cycles, hold=1.0, gap=0.5, timeout=2.0)
        t = 0.0
        ops.on_poll(ack=0, ok=True, vid=-1, sim=-1, players=1, t=t)
        vid = 0
        while not r.done and t < 100:
            t += 0.05
            r.step(t)
            if addon_answers:
                pending = ops.pending()
                if pending:
                    if pending["op"] == "spawn":
                        vid += 1
                        ops.on_poll(ack=pending["id"], ok=spawn_ok, vid=vid if spawn_ok else -1, sim=1, players=1, t=t)
                        if spawn_ok:
                            rec.add(seq=1, tick=1, values=[0.0] * 32, t=t + 0.1)  # 出した機体のマイコンから届く
                    else:
                        ops.on_poll(ack=pending["id"], ok=True, vid=-1, sim=-1, players=1, t=t)
        return r

    def test_all_cycles_pass(self):
        r = self.run_cycles(cycles=3)
        s = r.summary()
        self.assertTrue(r.done)
        self.assertEqual((s["spawn_ok"], s["despawn_ok"], s["cycles"]), (3, 3, 3))
        self.assertTrue(all(c["mc_values"] > 0 for c in s["results"]))

    def test_q3_pass_needs_ten(self):
        self.assertFalse(self.run_cycles(cycles=3).summary()["q3_pass"])
        self.assertTrue(self.run_cycles(cycles=10).summary()["q3_pass"])

    def test_spawn_failure_fails(self):
        s = self.run_cycles(spawn_ok=False, cycles=10).summary()
        self.assertEqual(s["spawn_ok"], 0)
        self.assertFalse(s["q3_pass"])

    def test_no_answer_times_out_and_finishes(self):
        r = self.run_cycles(addon_answers=False, cycles=2)
        self.assertTrue(r.done)
        s = r.summary()
        self.assertEqual(s["spawn_ok"], 0)
        self.assertEqual(s["despawn_ok"], 0)


class AddonServerTest(unittest.TestCase):
    def test_endpoints(self):
        rec, com, ops = relay.Recorder(expected_values=32), relay.Commander(), relay.AddonOps()
        server = relay.make_server("127.0.0.1", 0, rec, com, ops)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        get = lambda p: urllib.request.urlopen(f"http://127.0.0.1:{port}{p}", timeout=5).read().decode()
        try:
            self.assertEqual(get("/addon?s=1&a=0&r=1&vid=-1&sim=-1&np=1"), "ok")
            self.assertEqual(get("/spawn?name=test%20boat&x=0&y=3&z=15&rel=1"), "id=1")
            self.assertEqual(get("/addon?s=2&a=0&r=1&vid=-1&sim=-1&np=1"), "ok|1|spawn|test boat|0|3|15|1")
            self.assertEqual(get("/despawn"), "id=2")
            self.assertEqual(get("/addon?s=3&a=1&r=1&vid=5&sim=0&np=1"), "ok|2|despawn")
            with self.assertRaises(urllib.error.HTTPError) as cm:
                get("/spawn?x=1")
            self.assertEqual(cm.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(ops.get(1)["vid"], 5)
        self.assertEqual(ops.status()["vid"], 5)


class FakeServerApi:
    """アドオンの server.* の代わり。httpGet は1 tick に1件、本物の中継プログラムへ送る。"""

    def __init__(self, lua, port, spawn_ok=True):
        self.lua, self.port, self.spawn_ok = lua, port, spawn_ok
        self.queue: list[str] = []
        self.pending: list[tuple[int, str, str]] = []
        self.vehicles: dict[int, str] = {}
        self.next_id = 100
        self.announces: list[str] = []
        self.spawned_at: list[tuple] = []
        self.moved_to: list[tuple] = []
        self.players = [{"id": 0, "name": "p", "steam_id": "76561198000000000"}]

    def table(self):
        L = self.lua
        return L.table_from({
            "httpGet": lambda port, req: self.queue.append(req),
            "spawnVehicle": self.spawn,
            "despawnVehicleGroup": lambda gid, inst: self._despawn(gid - 1000),
            "despawnVehicle": lambda vid, inst: self._despawn(vid),
            "getVehicleSimulating": lambda vid: (vid in self.vehicles, True),
            "getPlayers": lambda: L.table_from({i + 1: L.table_from(p) for i, p in enumerate(self.players)}),
            "getVehiclePos": lambda vid: (L.table_from({"x": 1.0, "y": 2.0, "z": 3.0}), vid in self.vehicles),
            "setVehiclePos": lambda vid, m: (self.moved_to.append((vid, m["x"], m["y"], m["z"])) or vid in self.vehicles),
            "getPlayerPos": lambda pid: (L.table_from({"x": 10.0, "y": 2.0, "z": -5.0}), True),
            "announce": lambda name, msg: self.announces.append(str(msg)),
        })

    def spawn(self, m, name):
        if not self.spawn_ok:
            return 0, False, None, None
        self.next_id += 1
        self.vehicles[self.next_id] = name
        self.spawned_at.append((m["x"], m["y"], m["z"]))
        return self.next_id, True, self.lua.table_from({1: self.next_id}), self.next_id + 1000

    def _despawn(self, vid):
        return self.vehicles.pop(vid, None) is not None


@unittest.skipIf(lupa is None, "lupa がない")
class AddonLuaTest(unittest.TestCase):
    def setUp(self):
        self.rec, self.com, self.ops = relay.Recorder(expected_values=32), relay.Commander(), relay.AddonOps()
        self.server = relay.make_server("127.0.0.1", 0, self.rec, self.com, self.ops)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.lua = lupa.LuaRuntime(unpack_returned_tuples=True)
        self.api = FakeServerApi(self.lua, self.port)
        g = self.lua.globals()
        g.server = self.api.table()
        g.matrix = self.lua.table_from({
            "translation": lambda x, y, z: self.lua.table_from({"x": x, "y": y, "z": z}),
            "position": lambda m: (m["x"], m["y"], m["z"]),
        })
        self.logs: list[str] = []
        g.debug = self.lua.table_from({"log": lambda m: self.logs.append(str(m))})
        self.lua.execute(ADDON.read_text(encoding="utf-8"))
        g.PORT = self.port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def tick(self, n=1):
        g = self.lua.globals()
        for _ in range(n):
            replies, self.api.pending = self.api.pending, []
            for port, req, body in replies:
                g.httpReply(port, req, body)
            if self.api.queue:
                req = self.api.queue.pop(0)
                body = urllib.request.urlopen(f"http://127.0.0.1:{self.port}{req}", timeout=5).read().decode()
                self.api.pending.append((self.port, req, body))
            g.onTick(1)

    def test_spawn_relative_then_despawn(self):
        self.tick(5)
        a = self.ops.spawn("test boat", (0, 3, 15), relative=True)
        self.tick(6)
        self.assertTrue(self.ops.get(a)["ok"])
        self.assertEqual(list(self.api.vehicles.values()), ["test boat"])
        self.assertEqual(self.api.spawned_at, [(10.0, 5.0, 10.0)])
        self.assertEqual(self.ops.status()["sim"], 1)
        b = self.ops.despawn()
        self.tick(6)
        self.assertTrue(self.ops.get(b)["ok"])
        self.assertEqual(self.api.vehicles, {})

    def test_debug_log_shows_ticks_and_replies(self):
        self.lua.globals().onCreate(True)
        self.tick(330)
        self.assertTrue(any("onCreate world_create=true" in m for m in self.logs))
        self.assertTrue(any(m.startswith("[ClaudeBridge] tick=1 ") for m in self.logs))
        self.assertTrue(any("reply 1: ok" in m for m in self.logs))
        self.assertLess(len(self.logs), 10)  # 出しすぎない

    def test_lift_moves_vehicle_up(self):
        self.tick(3)
        self.ops.spawn("boat", (0, 0, 0), relative=False)
        self.tick(6)
        a = self.ops.lift(15)
        self.tick(6)
        self.assertTrue(self.ops.get(a)["ok"])
        self.assertEqual(self.api.moved_to[-1][1:], (1.0, 17.0, 3.0))

    def test_poll_reports_vehicle_position(self):
        self.tick(3)
        self.ops.spawn("boat", (0, 0, 0), relative=False)
        self.tick(8)
        self.assertEqual(self.ops.status()["pos"], (1.0, 2.0, 3.0))

    def test_lift_without_vehicle_fails(self):
        self.tick(3)
        a = self.ops.lift(15)
        self.tick(6)
        self.assertFalse(self.ops.get(a)["ok"])

    def test_dedicated_server_itself_is_not_counted(self):
        self.api.players = [{"id": 0, "name": "Server", "steam_id": "0"}]
        self.tick(5)
        self.assertEqual(self.ops.status()["players"], 0)
        a = self.ops.spawn("boat", (0, 3, 15), relative=True)  # プレイヤーがいないので相対位置は使えない
        self.tick(6)
        self.assertFalse(self.ops.get(a)["ok"])

    def test_absolute_position(self):
        self.tick(3)
        self.ops.spawn("boat", (1, 2, 3), relative=False)
        self.tick(6)
        self.assertEqual(self.api.spawned_at, [(1.0, 2.0, 3.0)])

    def test_spawn_replaces_previous_vehicle(self):
        self.tick(3)
        self.ops.spawn("a", (0, 0, 0), relative=False)
        self.ops.spawn("b", (0, 0, 0), relative=False)
        self.tick(12)
        self.assertEqual(list(self.api.vehicles.values()), ["b"])

    def test_spawn_failure_reported(self):
        self.api.spawn_ok = False
        self.tick(3)
        a = self.ops.spawn("missing", (0, 0, 0), relative=False)
        self.tick(6)
        self.assertFalse(self.ops.get(a)["ok"])

    def test_q3_runner_end_to_end(self):
        r = relay.Q3Runner(self.ops, self.rec, vehicle="boat", offset=(0, 3, 15), relative=True,
                           cycles=3, hold=0.2, gap=0.1, timeout=2.0)
        t = 0.0
        self.tick(3)
        for _ in range(2000):
            t += 1 / 60
            r.step(t)
            self.tick(1)
            if r.done:
                break
        s = r.summary()
        self.assertTrue(r.done)
        self.assertEqual((s["spawn_ok"], s["despawn_ok"]), (3, 3))
        self.assertEqual(self.api.vehicles, {})


if __name__ == "__main__":
    unittest.main()
