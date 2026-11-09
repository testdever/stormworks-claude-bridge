"""tools/put_lua.py：機体のファイルの中のマイコンの Lua を置き換える。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import put_lua  # noqa: E402

VEHICLE = """<?xml version="1.0" encoding="UTF-8"?><vehicle><bodies><body><components>
<c d="microprocessor"><o><microprocessor_definition name="a"><group><components>
<c type="56"><object id="1" script='-- FCS bridge: old
if a&lt;b then x=1 end'><pos/></object></c></components></group></microprocessor_definition></o></c>
<c d="microprocessor"><o><microprocessor_definition name="b"><group><components>
<c type="56"><object id="1" script='-- other mcu
y=2'><pos/></object></c></components></group></microprocessor_definition></o></c>
</components></body></bodies></vehicle>"""


class PutLuaTest(unittest.TestCase):
    def test_replaces_only_the_marked_script_and_escapes(self):
        lua = "-- FCS bridge: new\nif a<b and c>d then s=\"x\" .. 'y' end\r\n"
        new, n = put_lua.put_lua(VEHICLE, lua, "-- FCS bridge:")
        self.assertEqual(n, 1)
        got = [put_lua.unescape(m.group("body")) for m in put_lua.SCRIPT_ATTR.finditer(new)]
        self.assertEqual(got[0], lua.replace("\r\n", "\n"))
        self.assertEqual(got[1], "-- other mcu\ny=2")

    def test_refuses_when_no_script_matches(self):
        with self.assertRaises(ValueError):
            put_lua.put_lua(VEHICLE, "-- nothing: x\n", "-- nothing:")

    def test_refuses_a_lua_that_could_not_be_found_next_time(self):
        with self.assertRaises(ValueError):
            put_lua.put_lua(VEHICLE, "x=1\n", "-- FCS bridge:")


if __name__ == "__main__":
    unittest.main()
