+++
id = "E-009"
grade = "official"
date = "2026-11-08"
source = "https://github.com/gcrtnst/sw-luadocs/tree/main/data/v1.15.26/markdown"
quote = ""
questions = []
claims = [
  "アドオンの HTTP は server.httpGet(port, request)、返事は httpReply(port, request, reply)",
  "機体のマイコンの HTTP は async.httpGet(port, request_body)、返事は httpReply(port, request_body, response_body)。宛先は同じPC（localhost）",
  "server.spawnVehicle(transform_matrix, save_name) で、保存済みの機体をファイル名で出せる。返り値は vehicle_id, is_success, group_vehicles, group_id",
  "server.despawnVehicle(vehicle_id, is_instant) と server.despawnVehicleGroup(group_id, is_instant) で片付けられる",
  "server.getVehicleSimulating(vehicle_id) で、機体が読み込みを終えて物理が動いているかが分かる",
  "onVehicleSpawn の説明に「スクリプトが出した機体も、プレイヤーの近くで読み込まれないと物理が動き始めない」とある",
  "onCreate(is_world_create)、onTick(game_ticks)、server.getPlayers()、server.getPlayerPos(peer_id)、matrix.translation(x,y,z)、matrix.position(m)、server.announce(name, message)",
]
+++

ゲームに入っている Lua の説明書きを書き出したもの（gcrtnst/sw-luadocs、v1.15.26。一部は手で直してあるとのこと）から、アドオンの試作に使う関数を拾った。アドオンのフォルダの形（playlist.xml）は、スクリプトだけのアドオンの実例（cuhHub/SWOptimizationAddon の src/playlist.xml）に合わせた。
