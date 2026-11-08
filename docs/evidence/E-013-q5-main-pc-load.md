+++
id = "E-013"
grade = "measured"
date = "2026-11-08"
source = "docs/evidence/data/q4-20261108-233757-summary.json"
quote = "全く重く感じなかった。というかこの時点で重かったら望み薄どころではない。"
questions = ["Q5"]
claims = [
  "ほかのアドオンを外した専用サーバー（ClaudeBridge だけ）をメインPCの裏で動かし、機体を置いて60秒ずつ2台を試す実験を回す間、本人はメインPCで重さを感じなかった",
  "専用サーバー（server64）の CPU 使用率は平均 1.6%・最大 5.7%（16論理コアに対する割合）、メモリ最大 1365.1 MB（5秒ごと、26回）",
  "1回前の同じ実験（E-012）でも CPU 平均 1.4%・最大 2.1%、メモリ最大 1362.6 MB だった",
]
+++

手順：本人がメインPCで、README.md の「試作 Q4・Q5」のとおりに行った。server_config.xml の playlists を専用サーバー用の ClaudeBridge（rom/data/missions/ClaudeBridge）の1行だけにし、ゲーム本体は閉じて、中継プログラム（--mode q4）と server64.exe を起動した。中継プログラムは5秒ごとに PowerShell で server64 の CPU 時間とメモリを記録した。その間、本人はメインPCで作業をし、重さを感じたかを答えた。

結果：本人は重さを感じなかった。CPU とメモリの値は claims のとおり。Q5 の基準（実験を1回回す間、普段の作業で重さを感じない）を満たした。
