# 専用サーバーについて調べたこと（2026-11-08 時点）

ねらい：メインPCの裏で専用サーバーを動かし、誰も接続していない状態で、アドオンが機体を置き、物理を進めて実験を回す（決定 D-002、試作 Q4）。

結論の現状：**専用サーバーの上でアドオンのスクリプトが動いている証拠が、ひとつも得られていない。** 理由はまだ絞れていない（下の「分かっていないこと」）。

---

## 1. 専用サーバーの起動

| 項目 | 分かったこと | 出どころ |
|---|---|---|
| 入っている場所 | ゲーム本体に同梱。`Steam\steamapps\common\Stormworks\server64.exe`。Steam の「ツール」にあった別売りの Stormworks Dedicated Server を起動すると「移動した」と案内が出る | 本人の画面 |
| バージョン | v1.15.26 | サーバーの画面 |
| 設定ファイル | `%APPDATA%\Stormworks\server_config.xml`（サーバーの画面の「Server Config」に表示される）。初回の起動で作られる | サーバーの画面、Steam のガイド |
| 起動中の表示 | Uptime、Tickrate（64 tps）、Players、vehicles・objects（active / inactive）、tiles など | サーバーの画面 |
| 起動時の表示 | 「Please forward ports: 25565 & Steam P2P ports」「Starting server on ports: 25565 & Steam P2P ports...」 | 本人の画面 |

## 2. 設定ファイル（server_config.xml）の中身

受け付けられた設定の全体は `docs/examples/server_config.xml`。主な項目：

| 項目 | 値 | メモ |
|---|---|---|
| `port` | 25564 | ただしサーバーの画面は 25565 と表示。食い違いの理由は未確認 |
| `name` | Stormworks-Server | サーバー一覧での名前。ありふれていて一覧で探しにくい |
| `password` | 空 | 誰でも入れる状態 |
| `save_name` | autosave_server | 読み込むワールド。`%APPDATA%\Stormworks\saves\autosave_server` |
| `base_island` | data/tiles/island12.xml | 最初の島 |
| `<playlists>` | 読み込むアドオンの一覧 | 下の 3 章 |
| `<mods>` | 空 | |

注意：

- サーバーを動かしている間に書き換えると、上書きされることがある（フォーラムの助言）。止めてから書き換える。
- 起動のあと、`<playlists>` の行が消えて保存し直されていることがあった（3 章）。消えた理由は分かっていない。
  「消えた＝受け付けなかった」「残った＝受け付けた」は Claude の推測で、サーバーがアドオンを読めたかの証拠ではない。
- 初回の起動時の `<playlists>` には、標準のミッションが `rom/data/missions/default_ai` などの形で25行ほど並んでいた。
- 標準のミッションの `playlist.xml`（`rom\data\missions\default_tutorial\playlist.xml`）の1行目は
  `<playlist folder_path="../../assets/data/missions/default_tutorial" file_store="3" name="Default Tutorial">`。`path_id` はない。

## 3. アドオンの入れ方（試した順）

どの回も、`<playlists>` の中は ClaudeBridge の1行だけにしてから、専用サーバーを起動した。

| # | 置き場所 | `<playlists>` の書き方 | `playlist.xml` | 起動後の設定ファイル | アドオンからの連絡 |
|---|---|---|---|---|---|
| 1 | `Steam\…\Stormworks\rom\data\missions\ClaudeBridge` | `rom/data/missions/ClaudeBridge` | 最初の版（`path_id` なし、場所に島の指定なし） | 行が消えて `<playlists/>` になっていた | なし |
| 2 | `Steam\…\Stormworks\ClaudeBridge`（`server64.exe` の直下） | `ClaudeBridge` | 最初の版 | 行が消えていた | なし |
| 3 | 同上 | `ClaudeBridge` | 新しい版（`path_id="app_data/data/missions/ClaudeBridge"`、場所に `tile="data/tiles/island12.xml"`） | 見ていない | なし |
| 4 | `%APPDATA%\Stormworks\data\missions\ClaudeBridge`（Q3 でゲーム用に置いた場所） | `app_data/data/missions/ClaudeBridge` | 新しい版 | 行が残っていた | なし |

行が消えた・残ったことが、サーバーがアドオンを読めたかどうかを表すのかは分からない（Claude の推測では、消えた＝見つけられなかった、残った＝見つけた）。
どの回もアドオンからの連絡はなかったので、**サーバーがアドオンを正しく読めたことは、どの形でも確かめられていない。**

根拠にした資料：

- 1：Steam のガイドとフォーラム（「`rom/data/missions` に置き、`<playlists>` に足す」）。
- 2：Carsa's Commands（専用サーバー向けの手順がある有名なアドオン）の README（「`server64.exe` のフォルダに置き、フォルダ名だけを書く」）。古い手順の可能性がある。
- 3：Carsa's Commands の `playlist.xml` の形（1行目に `path_id`、場所に島の指定）。
- 4：`path_id` の値（`app_data/…`）と、標準のミッションの書き方（`rom/…`）が同じ種類の識別名だという見立て。

## 4. ワールド（セーブ）

- アドオンは、ワールドを作るときに決まり、あとから足せない（ゲーム本体と同じ。Steam の掲示板・アドオンの説明書き）。
- 初回の起動で、標準のミッション入りのワールドが作られていた（画面の vehicles 0/687、objects 0/2676）。
- 作り直すには、`%APPDATA%\Stormworks\saves\autosave_server` の名前を変えてから起動する。
- `<playlists>` を変えて作り直したあとは vehicles 0/0 になり、標準のミッションは外れた。

## 5. アドオンを受け付けたあとの様子（#4 の形）

| 見たもの | 結果 |
|---|---|
| 中継プログラム（`--mode q4`） | 一度も連絡が来なかった |
| DebugView（`*ClaudeBridge*` で絞り込み） | 何も出なかった（`onCreate` も、5秒ごとの `tick=` も） |
| サーバーの画面 | Players 0、vehicles 0/0、objects 0/2202、tiles 0、64 tps |
| 比べるための確かめ | 同じ DebugView のまま、ゲーム本体の1人用ワールドで同じアドオンを動かすと、出力が出た |

## 6. プレイヤーとしての接続

- ゲームのマルチプレイの画面は「Host」「Friends」「Internet」の3つ。Internet は Valve の一覧に出た専用サーバーを表示する。
- 「Storm」で検索しても、自分のサーバーは見つからなかった。一覧には多くのサーバーが並んでいた。
- 同じPCで動かしているサーバーには入れないことがあり、Microsoft Loopback Adapter を入れると直るという報告がある（第三者のガイド。未確認）。
- まだ一度も接続できていない。

## 7. 調べた資料（関数）

ゲームに入っている Lua の説明書きを書き出したもの（gcrtnst/sw-luadocs、v1.15.26）から：

- アドオンの通信は `server.httpGet(port, request)` と `httpReply(port, request, reply)`。宛先は同じPCだけ。
- `onVehicleSpawn` の説明に「スクリプトが出した機体も、プレイヤーの近くで読み込まれないと物理が動き始めない」とある。
- キープアクティブブロックが、誰もいないサーバーで機体を動かし続けるかの公式の説明は見つからなかった（パッチノートに「キープアクティブブロックの修正」とあるだけ）。

---

## 8. 画面の数で読み込みを見分ける試み

- 標準のミッション1つ（`rom/data/missions/default_landmarks`）だけを入れると、行は残り、objects が 0/3287 になった。
- 同じミッションを `%APPDATA%\Stormworks\data\missions\TestLandmarks` にコピーし、`app_data/data/missions/TestLandmarks` と書いても、同じ結果だった。
- ところが、`<playlists>` を空にしてワールドを消して起動しても、同じ結果だった。
- objects の数は、アドオンを入れていないはずの回でも 2202、2743 とばらついていた。**objects の数では、アドオンが読み込まれたかを見分けられない。**
- そこで、何も入れていないと 0/0 になる vehicles の数を使う。確かめ専用のアドオン ClaudeProbe（`game/addon/ClaudeProbe`）は、最初の tick に通信を使わず `claude_test` を1台だけ置く。スクリプトが動けば vehicles が 0/0 でなくなる。
- **結果：ClaudeProbe を `app_data/data/missions/ClaudeProbe` で入れ、ワールドを消して起動しても、vehicles は 0/0 のままだった。**
  誰も接続していない専用サーバーでは、通信を使わない処理（機体を置く）でも、アドオンの働きが見えなかった。
  理由は「スクリプトが動いていない（読み込まれていない、または誰もいないと動かない）」か、「スクリプトは動いたが、誰もいないサーバーでは機体を置けない」のどちらか。
- **`%APPDATA%` に置いたアドオンが専用サーバーに読み込まれた証拠は、まだ一度もない**（本人の指摘）。確実に読み込まれたと言えるのは、最初の起動の標準のミッション（vehicles 0/687）だけ。
- そこで ClaudeProbe の playlist.xml に、標準のミッションと同じ仕組み（環境 MOD、`is_env_mod="true"`）で最初から置く機体を1台書き足した。
  機体のファイルは、本人の `claude_test.xml` を `vehicle_1.xml` としてフォルダに入れる。書き方は SWAsteroidsAddon と Carsa's Commands の playlist.xml に合わせた。
  （`<spawn_transform 30="0" …>` のように数字で始まる属性名は、厳密な XML としては誤りだが、ゲームはこの形を使っている）
  vehicles が 0 なら読み込まれていない（または書き方の誤り）、1 なら読み込まれたがスクリプトは何もしていない、2 なら両方。

## 9. 1人用での確かめと、rom に置く形の試し

- ClaudeProbe（最初から置く機体つき）を、ゲーム本体の1人用ワールドで有効にすると、固定されて浮いた機体が1台出た。最初から置く機体の書き方は正しい。
  スクリプトが最初の tick に置くはずの2台目は見つからなかった（ワールドが始まった直後で早すぎた可能性）。
- 同じ ClaudeProbe が専用サーバーでは vehicles 0/0 だった。標準のミッションが入っていたときは、誰も接続していなくても 0/687（動いていない機体も右側に数えられる）だったので、0/0 は「機体が存在しない」＝**`app_data/data/missions/ClaudeProbe` の指定では読み込まれていない**と読める。
- ガイドはどれも「`rom\data\…` の下に置き、`rom/data/…` と書く」としている（AMP のテンプレート、Steam のガイド、サーバー貸し業者の手引き）。
  標準のミッションは `file_store="3"`、手元のアドオンは `"4"` で、`app_data/…` が 4 に当たると見て、3 が rom ではないかと考えた。
- そこで `game/addon/probes` に、`rom` に置く形を2通り用意した（ProbeRom3：`file_store="3"`・機体1台、ProbeRom4：`path_id="rom/…"`・`file_store="4"`・機体2台）。
  両方を同時に入れ、vehicles の合計（0／1／2／3）でどちらが読み込まれたかを見分ける。機体のファイルは SWAsteroidsAddon（Apache 2.0）のものを使った。

## 10. 結果：rom に置く形なら読み込まれた

- ProbeRom3 と ProbeRom4 を `Stormworks\rom\data\missions\` に置き、`rom/data/missions/ProbeRom3`・`rom/data/missions/ProbeRom4` と書いて、ワールドを消して起動した。
- サーバー画面は **vehicles 0/3**（誰も接続していない）。両方とも読み込まれ、最初から置く機体が合計3台、動いていない状態で存在した。
- **専用サーバーにアドオンを入れる形は、`rom\data\missions\<名前>` に置き、`rom/data/missions/<名前>` と書く。**
  `file_store` は 3 でも 4 でもよかった。`%APPDATA%` に置いて `app_data/…` と書く形は読み込まれなかった。
- 最初（3 章の #1）に rom に置いて行が消えたのは、そのときの playlist.xml が古い形だったためかもしれない（確かめていない）。
- 専用サーバー用の ClaudeBridge は `game/addon/server/ClaudeBridge`（playlist.xml を ProbeRom3 と同じ形にしたもの）。

## 11. 専用サーバー用の ClaudeBridge で Q4 を回した（E-012）

- 誰も接続していなくても、アドオンは動き、中継プログラムと通信でき、保存した機体を置けた。
- キープアクティブブロックがない機体は動かず（マイコンの値0件）、ある機体はマイコンが60秒動き続けた。
- ある機体は落ちて転がり、約29秒で休んで値が止まった。物理が止まったのか休んだのか、この試しでは見分けられない。
- アドオンから見たプレイヤー数は1人（サーバー自身）だった。
- 物理センサーの位置（ch1〜3）は、専用サーバーでは 0 のままだった（理由は分からない）。
- 負荷は CPU 平均 1.4%、メモリ約 1.4GB。
- 次の試し：サーバー自身（steam_id 0）を数えない。10秒ごとに機体を15m持ち上げて落とす（アドオンの lift）。

## 12. 持ち上げて落とす試し（2026-11-08 23:37）

- 持ち上げ（lift）は2台とも6回すべて失敗した。プレイヤー数も1人のままだった。
  直した版のスクリプト（lift と、サーバー自身を数えない処理）が効いていない様子。古いスクリプトのまま読み込まれていた可能性がある（確かめていない）。
  あとで本人から「アドオンの更新を忘れてたかも」と連絡があった。古いスクリプトには lift がなく失敗を返し、サーバー自身も数えるので、結果と合う。**この試しは、持ち上げて落とす確かめ方の結果としては使えない。**
- キープアクティブの機体は、前回と同じく、マイコンが60秒動き、落ちて転がったあと約30秒で休んだ。
- 負荷は CPU 平均 1.6%・最大 5.7%、メモリ約 1.4GB。本人は重さを感じなかった（E-013）。ただし小さな機体を置くだけの試しなので、Q5 の判定には使わず、実際の計測実験の規模で改めて確かめる（本人の意向）。
- 次に回すときは、まず rom\data\missions\ClaudeBridge\script.lua が新しい版か（`lift` と `isRealPlayer` があるか）を確かめる。

## 分かっていないこと

アドオンからの連絡がない理由として、次の3つが残っている。

1. ~~アドオンが読み込まれていない~~ → `app_data/…` の形では読み込まれていなかった。rom に置く形で解決（10 章）。
2. ~~読み込まれたスクリプトが、誰も接続していなくても動くか~~ → 動いた（11 章）。
3. ~~専用サーバーから、スクリプトの通信が外に出るか~~ → 出た（11 章）。`debug.log` が DebugView に出るかは見ていない。
4. ~~保存した機体を `server.spawnVehicle` で置けるか~~ → 置けた（11 章）。
5. **キープアクティブブロックを積んだ機体で、誰もいない間も物理が進み続けるか。**（持ち上げて落とす試しで確かめる）
6. 物理センサーの位置が専用サーバーで 0 になる理由。

ほかに、設定の `port`（25564）と画面の表示（25565）の食い違いも、理由は分かっていない。

## 次に試すこと

1. `server_config.xml` の `name` を独自の名前に、`password` を付けて、一覧で探せるようにする（今は誰でも入れる状態でもある）。
2. 中継プログラム（`--mode q3`）と DebugView を開いたまま、ゲーム本体からサーバーに接続する（メインPCで見つからなければ別PCから）。
3. 見分け方：
   - 接続した途端に機体の出し入れが始まる → 理由2。続けて、一度接続して抜けたあともアドオンが動き続けるかを見る。
   - 接続しても何も起きない → 理由1か3。ゲームのチャットに「[Claude] …」が出るかで見分ける。
