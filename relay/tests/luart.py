"""テストで使う Lua の実行環境を選ぶ。

lupa（Python から Lua を動かすライブラリ）には、Lua の版ごとの部品が入っている。
Windows のアプリ制御（スマート アプリ コントロール）が一部の部品を止めることがあるので、
新しい版から順に試し、動いたものを使う。どれも動かなければ None（Lua のテストは飛ばす）。
Stormworks の Lua は 5.3。このリポジトリの Lua は 5.1 でも同じように動く書き方にしている。
"""

from __future__ import annotations

import importlib


def pick_lua():
    try:
        import lupa  # type: ignore  # noqa: F401
    except ImportError:
        return None
    for name in ("lua54", "lua53", "lua52", "lua51"):
        try:
            mod = importlib.import_module(f"lupa.{name}")
            mod.LuaRuntime().execute("return 1")
            return mod
        except Exception:  # 部品がない、またはアプリ制御で読み込めない
            continue
    return None


lupa = pick_lua()
