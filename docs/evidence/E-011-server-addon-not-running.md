+++
id = "E-011"
grade = "measured"
date = "2026-11-08"
source = "docs/examples/server_config.xml"
quote = "特に何も出なかった"
questions = []
claims = [
  "誰も接続していない専用サーバー（v1.15.26、server64.exe）では、ClaudeBridge アドオンが動かなかった。onCreate も onTick も debug.log に何も出ず、中継プログラムにも一度も連絡が来なかった",
  "同じ DebugView の設定で、ゲーム本体の1人用ワールドでは ClaudeBridge の出力が見えた。DebugView の使い方の問題ではない",
  "server_config.xml の playlists は app_data/data/missions/ClaudeBridge と書くと受け付けられた（起動後も行が残る）。rom/data/missions/ClaudeBridge や ClaudeBridge と書く形では、サーバーが行を消した",
  "誰も接続していない専用サーバーの画面は tiles : 0 で、地図のどこも読み込まれていなかった",
  "同じPCのゲーム本体から、そのサーバーはインターネットの一覧に出ず、接続できなかった",
]
+++

手順：本人がメインPCで、Claude の示した手順で行った。server_config.xml の playlists を app_data/data/missions/ClaudeBridge の1行にし、専用サーバーのワールド（saves\autosave_server）を作り直した。デバッグ出力を足した版のアドオン（onCreate、5秒ごとの tick、返事を debug.log に出す）を %APPDATA%\Stormworks\data\missions\ClaudeBridge に置き、ワールドを作り直してから、中継プログラム（--mode q4）と server64.exe を起動した。DebugView（Include に *ClaudeBridge*）で30秒ほど見た。そのあと確かめとして、専用サーバーを閉じ、同じ DebugView のまま、ClaudeBridge を有効にした新しい1人用ワールドをゲーム本体で作って入った。

結果：専用サーバーのときは、DebugView に何も出ず、中継プログラムにも何も届かなかった。サーバーの画面は Players 0、vehicles 0/0、tiles 0。1人用ワールドのときは、DebugView に ClaudeBridge の出力が出た。専用サーバーの上でアドオンが動いていないと分かる。誰も接続していないことが理由かは、接続を試せなかったため分からない。
