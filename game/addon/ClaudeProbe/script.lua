-- Claude Probe: check whether addon scripts run on a server with no players.
-- On the first tick, spawn one saved vehicle (no HTTP). If the script runs,
-- the server screen shows vehicles other than 0/0.
VEHICLE="claude_test"
X,Y,Z=-260.9,8,-18949
done_=false

function onTick(game_ticks)
	if done_ then return end
	done_=true
	local v,ok=server.spawnVehicle(matrix.translation(X,Y,Z),VEHICLE)
	debug.log("[ClaudeProbe] spawn "..VEHICLE.." ok="..tostring(ok).." id="..tostring(v))
end
