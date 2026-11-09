"""保存済みの機体のファイルの中のマイコンの Lua を、リポジトリの Lua に置き換える（エディターでの貼り付けの代わり）。

どのマイコンかは、いま入っている Lua の1行目で見分ける（例：「-- FCS bridge:」で始まるもの）。ちょうど1つでなければ何もしない。
置き換える前のファイルは backup に残す。ゲームはワークベンチやアドオンで機体を出すときにファイルを読むので、出し直せば新しい Lua で動く。

  python tools/put_lua.py "test calc" game/fcs_bridge.lua --marker "-- FCS bridge:"
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

VEHICLES = Path(os.environ.get("APPDATA", "")) / "Stormworks" / "data" / "vehicles"
SCRIPT_ATTR = re.compile(r"""script=(?P<q>['"])(?P<body>.*?)(?P=q)""", re.S)


def unescape(s: str) -> str:
    return (s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
            .replace("&apos;", "'").replace("&#13;", "\r").replace("&#10;", "\n").replace("&amp;", "&"))


def escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("'", "&apos;").replace('"', "&quot;"))


def find_scripts(text: str, marker: str) -> list[re.Match]:
    return [m for m in SCRIPT_ATTR.finditer(text) if unescape(m.group("body")).lstrip().startswith(marker)]


def put_lua(text: str, lua: str, marker: str) -> tuple[str, int]:
    """marker で始まる Lua をすべて置き換えた全文と、置き換えた数を返す（同じマイコンが本体の定義と写しの2か所にあることがある）。"""
    lua = lua.replace("\r\n", "\n")
    if not lua.lstrip().startswith(marker):
        raise ValueError(f"新しい Lua の1行目が {marker!r} で始まらない（次に見分けられなくなる）")
    hits = find_scripts(text, marker)
    if not hits:
        raise ValueError(f"{marker!r} で始まる Lua の入ったマイコンが見つからない")
    out, last = [], 0
    for m in hits:
        out.append(text[last:m.start()])
        out.append("script='" + escape(lua) + "'")
        last = m.end()
    out.append(text[last:])
    new = "".join(out)
    ET.fromstring(new.encode("utf-8"))  # 壊れていないか
    return new, len(hits)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("vehicle", help="機体の保存名（vehicles フォルダの .xml の名前）")
    ap.add_argument("lua", help="入れる Lua のファイル")
    ap.add_argument("--marker", required=True, help="置き換えるマイコンの Lua の1行目の始まり")
    ap.add_argument("--vehicles", default=str(VEHICLES))
    ap.add_argument("--backup", default=str(Path(__file__).resolve().parents[2] / "backup" / "vehicles"))
    a = ap.parse_args()
    path = Path(a.vehicles) / f"{a.vehicle}.xml"
    text = path.read_text(encoding="utf-8")
    lua = Path(a.lua).read_text(encoding="utf-8")
    hits = find_scripts(text, a.marker)
    if hits and all(unescape(m.group("body")).replace("\r\n", "\n") == lua.replace("\r\n", "\n") for m in hits):
        print(f"{path.name}：もう同じ Lua が入っている。何もしない")
        return 0
    try:
        new, n = put_lua(text, lua, a.marker)
    except ValueError as e:
        print(f"{path.name}：{e}", file=sys.stderr)
        return 1
    bdir = Path(a.backup)
    bdir.mkdir(parents=True, exist_ok=True)
    b = bdir / f"{a.vehicle}-{time.strftime('%Y%m%d-%H%M%S')}.xml"
    shutil.copy2(path, b)
    path.write_text(new, encoding="utf-8", newline="")
    print(f"{path.name}：マイコン {n} か所の Lua を置き換えた（{len(lua)} 文字）。前のファイルは {b}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
