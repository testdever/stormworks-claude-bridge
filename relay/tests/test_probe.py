"""確かめ用アドオン（game/addon/ClaudeProbe）のテスト。最初の tick に1台だけ置く。"""

from __future__ import annotations

import unittest
from pathlib import Path

from luart import lupa  # noqa: E402  動く版の Lua を選ぶ（なければ None）

SCRIPT = Path(__file__).resolve().parents[2] / "game" / "addon" / "ClaudeProbe" / "script.lua"


@unittest.skipIf(lupa is None, "lupa がない")
class ProbeTest(unittest.TestCase):
    def test_spawns_once_on_first_tick(self):
        L = lupa.LuaRuntime(unpack_returned_tuples=True)
        spawned, logs = [], []
        g = L.globals()
        g.server = L.table_from({"spawnVehicle": lambda m, name: (spawned.append((m["x"], m["y"], m["z"], name)) or (5, True))})
        g.matrix = L.table_from({"translation": lambda x, y, z: L.table_from({"x": x, "y": y, "z": z})})
        g.debug = L.table_from({"log": lambda m: logs.append(str(m))})
        L.execute(SCRIPT.read_text(encoding="utf-8"))
        for _ in range(100):
            g.onTick(1)
        self.assertEqual(spawned, [(-260.9, 8, -18949, "claude_test")])
        self.assertEqual(len(logs), 1)


if __name__ == "__main__":
    unittest.main()
