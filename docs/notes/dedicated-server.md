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

## 分かっていないこと

アドオンからの連絡がない理由として、次の3つが残っている。

1. **アドオンが読み込まれていない。** #4 で行が残ったことは、読み込みに成功した証拠にはならない。#1〜#3 の書き方のどれかが正しかった可能性も残る。
2. **読み込まれているが、プレイヤーが一度も接続しないと動き出さない。**
3. **動いているが、外に何も出ていない。** 専用サーバー（`server64.exe`）の `debug.log` が DebugView に出るかと、通信が外に出るかは、確かめていない。

ほかに、設定の `port`（25564）と画面の表示（25565）の食い違いも、理由は分かっていない。

## 次に試すこと

1. `server_config.xml` の `name` を独自の名前に、`password` を付けて、一覧で探せるようにする（今は誰でも入れる状態でもある）。
2. 中継プログラム（`--mode q3`）と DebugView を開いたまま、ゲーム本体からサーバーに接続する（メインPCで見つからなければ別PCから）。
3. 見分け方：
   - 接続した途端に機体の出し入れが始まる → 理由2。続けて、一度接続して抜けたあともアドオンが動き続けるかを見る。
   - 接続しても何も起きない → 理由1か3。ゲームのチャットに「[Claude] …」が出るかで見分ける。
