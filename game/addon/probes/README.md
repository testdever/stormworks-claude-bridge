# 専用サーバーの読み込みを見分けるアドオン

- ProbeRom3：`file_store="3"`（標準のミッションと同じ）、`path_id` なし。最初から置く機体が1台。
- ProbeRom4：`path_id="rom/data/missions/ProbeRom4"`、`file_store="4"`。最初から置く機体が2台。

どちらも `Stormworks\rom\data\missions\` の下に置き、`server_config.xml` に `rom/data/missions/ProbeRom3` と `rom/data/missions/ProbeRom4` を書く。
サーバー画面の vehicles の合計が 0 ならどちらも読み込まれていない、1 なら ProbeRom3、2 なら ProbeRom4、3 なら両方。

機体のファイル `vehicle_*.xml` は、SWAsteroidsAddon（Cuh4、https://github.com/Cuh4/SWAsteroidsAddon ）の `src/vehicle_1.xml` をそのまま使っている。
Apache License 2.0（`LICENSE-SWAsteroidsAddon.txt`）。
