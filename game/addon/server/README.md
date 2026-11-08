# 専用サーバー用の ClaudeBridge

専用サーバーは、`%APPDATA%` に置いたアドオン（`app_data/…`）を読み込まなかった。
ゲーム本体のフォルダの `rom\data\missions\` に置き、`server_config.xml` に `rom/data/missions/ClaudeBridge` と書くと読み込まれる
（確かめ用アドオン ProbeRom3・ProbeRom4 で確認。`docs/notes/dedicated-server.md` の 10 章）。

- `playlist.xml` は専用サーバー用（`file_store="3"`、`path_id` なし。ProbeRom3 と同じ形）。
- `script.lua` は `game/addon/ClaudeBridge/script.lua` と同じもの。直したときは両方をそろえる。
