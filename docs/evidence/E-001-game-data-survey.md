+++
id = "E-001"
grade = "third_party"
date = "2026-11-08"
source = "https://steamdb.info/patchnotes/5301820 , https://cuhhub.gitbook.io/noir/api-reference/built-ins/services/httpservice , https://github.com/Cuh4/PythonToSW , https://github.com/Koenqr/swTools , https://ddprojects.chickenkiller.com/cuhHub/DebugViewLogger , https://steamcommunity.com/app/573090/discussions/0/3053985636026268803 , https://gitlab.com/stormworks-tools/dedicated-server-install-script"
quote = ""
questions = []
claims = [
  "Stormworks は Lua スクリプト（アドオン・機体のマイコン）から HTTP サーバーと通信できる。公式の目的は外部ソフトへのテレメトリ送信",
  "HTTP の宛先は同じPC（localhost）だけ",
  "通信はゲーム側からの要求とその返事だけ。外からゲームへ押し込めないので、指示はゲーム側が問い合わせて返事で受け取る",
  "HTTP 経由の実例（PythonToSW）では、1秒に約32回が上限",
  "Lua の debug.log の出力を Windows の DebugView で拾い、CSV にする道具がある（保守終了のものを含む）",
  "Stormworks には単体で動く専用サーバー（server64.exe、Windows 用）がある",
  "Stormworks 用の Cheat Engine（メモリを書き換え・読み取りする道具）の表はあるが、機体の値を読む用途の例は見つからない",
]
+++

調べた先：Web 検索（「Stormworks addon Lua server.httpGet localhost」「Stormworks microcontroller Lua HTTP」「Stormworks dedicated server headless」「Stormworks lua debug.log DebugView」「Stormworks MCP / telemetry bridge」「Stormworks cheat engine memory read」）。Stormworks のパッチノート（SteamDB の写し）、Noir（アドオン用ライブラリ）の HTTPService の説明、PythonToSW（Python でアドオンを書く道具）、swTools と DebugViewLogger（debug.log を拾う道具）、Steam の掲示板、専用サーバーの導入手順。公式の Lua API の一覧はゲーム内のヘルプにあり、Web では見つからなかった。

解き方：
- 一番良いとされる（公式が想定している）のは、ゲーム内の Lua スクリプトから同じPCの HTTP サーバーへ値を送る方法。アドオン（ワールド全体を扱うスクリプト）と機体のマイコン（機体に載せる電子回路の部品。Lua を書ける）の両方から使える。
- ゲームへの指示は、ゲーム側が定期的に問い合わせ、返事に指示を載せて受け取る。PythonToSW がこの形で、アドオンの処理を丸ごと外の Python で動かしている。
- Lua の debug.log を Windows のデバッグ出力として外で拾う方法もあり、記録とグラフ化に使われている。読み取り専用。
- 画面の画像認識や、メモリの読み取りで値を取る方法は、Stormworks での実例が見つからなかった。
- Claude などの AI とつなぐ既存の仕組みは見つからなかった。
- Claude の知識（未確認）：アドオンは server.httpGet と httpReply、機体の Lua は async.httpGet と httpReply を使う。アドオンは機体の値を、名前を付けたダイヤルやボタン経由でしか読めない。マイコンは配線した値をそのまま読める。
