+++
id = "E-003"
grade = "third_party"
date = "2026-11-08"
source = "https://low.ms/knowledgebase/stormworks-server-configuration , https://low.ms/knowledgebase/stormworks-save-location-how-to-upload , https://low.ms/blog/stormworks-server-hosting-guide , https://hebergtonserv.com/en/tutoriels/install-stormworks-server-steamcmd , https://gitlab.com/stormworks-tools/dedicated-server-install-script , https://github.com/Cuh4/PythonToSW"
quote = ""
questions = []
claims = [
  "専用サーバー（server64.exe）はゲーム本体と別の無料の配布物で、SteamCMD で入れられる",
  "専用サーバーは server_config.xml の save_name で読み込むワールドを決め、起動するだけでそのワールドが始まる",
  "物理の計算はサーバーの CPU が行う。重さを決めるのは CPU の1コアの速さと機体の複雑さ",
  "専用サーバーの必要メモリは 4〜8GB 程度とされる（業者の目安で、ばらつきがある）",
  "ゲーム本体をコマンドラインでセーブに直接入らせる方法は見つからなかった",
  "アドオンは専用サーバーの上で動き、同じPCの外部プログラムとつなぐ例がある（PythonToSW）",
]
+++

調べた先：Web 検索（「Stormworks dedicated server server_config.xml load save」「Stormworks dedicated server same PC CPU RAM」「Stormworks command line load save skip menu」「Stormworks dedicated server headless」）。サーバー貸し業者の設定・導入の手引き（low.ms、hebergtonserv）、導入スクリプト（GitLab）、PythonToSW の説明。公式の資料は見つからなかった。

解き方：
- 人の操作なしで場面を用意する定番は、専用サーバーを使う方法。設定ファイルで読み込むワールドを決めて起動し、アドオンで機体を置く。画面を描かず、物理の計算は CPU で行う。
- ゲーム本体は、起動してからセーブを開くまでにメニューの操作が要る。それを省く起動のしかたは見つからなかった。
- 同じPCでゲーム本体と専用サーバーを両方動かした測定は見つからなかった。
- 見つからなかったこと：プレイヤーが誰も接続していないときに、専用サーバーが機体の物理を計算し続けるか。
