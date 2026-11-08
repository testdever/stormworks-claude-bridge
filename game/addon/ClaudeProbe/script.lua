-- Claude Probe: check whether the addon is loaded, and whether its script runs,
-- on a server with no players.
-- playlist.xml: one env-mod vehicle (vehicle_1.xml) is placed when the world is created -> proves loading.
-- script: on the first tick, spawn one more saved vehicle (no HTTP) -> proves the script runs.
-- Server screen "vehicles": 0 = not loaded, 1 = loaded but script did nothing, 2 = both.
VEHICLE="claude_test"
X,Y,Z=-260.9,8,-18949
done_=false

function onTick(game_ticks)
	if done_ then return end
	done_=true
	local v,ok=server.spawnVehicle(matrix.translation(X,Y,Z),VEHICLE)
	debug.log("[ClaudeProbe] spawn "..VEHICLE.." ok="..tostring(ok).." id="..tostring(v))
end
