"""マイコンの Lua（game/q1_send_values.lua）を、ゲームの代わりの環境で中継プログラムにつないで試す。

lupa（Python から Lua を動かすライブラリ）がなければ飛ばす。pip install lupa
"""

from __future__ import annotations

import sys
import threading
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import relay  # noqa: E402

try:
    import lupa  # type: ignore
except ImportError:  # pragma: no cover
    lupa = None

SCRIPT = Path(__file__).resolve().parents[2] / "game" / "q1_send_values.lua"


class FakeVehicle:
    """Stormworks のマイコンの代わり。httpGet の返事は次の tick で httpReply に渡す。"""

    def __init__(self, port: int, reply: bool = True):
        self.lua = lupa.LuaRuntime(unpack_returned_tuples=True)
        self.port = port
        self.reply = reply
        self.pending: list[tuple[int, str, str]] = []
        self.outputs: dict[int, float] = {}
        self.sent: list[str] = []
        g = self.lua.globals()
        g.input = self.lua.table_from({"getNumber": lambda i: i * 1.5 - 7})
        g.output = self.lua.table_from({"setNumber": self._set_number})
        g["async"] = self.lua.table_from({"httpGet": self._http_get})
        self.lua.execute(SCRIPT.read_text(encoding="utf-8"))
        g.PORT = port

    def _set_number(self, ch, v):
        self.outputs[int(ch)] = v

    def _http_get(self, port, url):
        self.sent.append(url)
        if not self.reply:
            return
        body = urllib.request.urlopen(f"http://127.0.0.1:{port}{url}", timeout=5).read().decode()
        self.pending.append((port, url, body))

    def tick(self, n: int = 1) -> None:
        g = self.lua.globals()
        for _ in range(n):
            replies, self.pending = self.pending, []
            for port, url, body in replies:
                g.httpReply(port, url, body)
            g.onTick()


@unittest.skipIf(lupa is None, "lupa がない")
class LuaE2ETest(unittest.TestCase):
    def setUp(self):
        self.rec = relay.Recorder(expected_values=32)
        self.server = relay.make_server("127.0.0.1", 0, self.rec)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_values_arrive_without_gaps(self):
        v = FakeVehicle(self.port)
        v.tick(120)
        s = self.rec.summary()
        self.assertEqual(s["received"], len(v.sent))
        self.assertGreaterEqual(s["received"], 59)  # 返事を待って次を送るので2 tick に1回
        self.assertEqual(s["missing"], 0)
        self.assertEqual(s["bad_values"], 0)
        self.assertEqual(s["malformed"], 0)
        self.assertEqual(v.outputs[2], s["received"] - 1)  # 最後の返事はまだ次の tick 待ち
        self.assertEqual(v.outputs[3], 0)

    def test_resends_after_timeout_when_no_reply(self):
        v = FakeVehicle(self.port, reply=False)
        v.tick(130)
        self.assertEqual(len(v.sent), 3)  # 1, 61, 121 tick 目

    def test_script_is_short_enough(self):
        self.assertLess(len(SCRIPT.read_text(encoding="utf-8")), 4096)


if __name__ == "__main__":
    unittest.main()
