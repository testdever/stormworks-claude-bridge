-- Claude Bridge addon (Q3): spawn / despawn vehicles on relay commands
-- Polls the relay at /addon and reports the result of the last command.
-- Reply from relay: "ok" or "ok|<id>|spawn|<save_name>|<x>|<y>|<z>|<rel>" or "ok|<id>|despawn"
--   (rel: 0 = world position, 1 = offset from the player, 2 = [right, up, forward] of where the player looks)
--   or "ok|<id>|lift|<dy>" (teleport the vehicle dy metres up, to check physics keeps running)
--   or "ok|<id>|move_player|<x>|<y>|<z>" (move the first real player there, so the ground and sea load)
--   rel=1: x,y,z are offsets from the first player's position
--   or "ok|<id>|target|<save_name>|<distance>|<y>|<same>" (place a target <distance> m ahead of where the player looks,
--   at height y; same=1: from the same place and in the same direction as the previous target)
--   or "ok|<id>|target_despawn" or "ok|<id>|weather|<fog>|<rain>|<wind>" (0-1)
--   or "ok|<id>|target_reset" (put the target back where and how it was placed; it is unloaded and reloaded,
--   but keeps spinning and moving if it was hit)
--   or "ok|<id>|target_renew" (replace the target with a fresh one where it was placed: no spin, no speed, no damage)
-- The target's heading (tyaw, deg) and the up axis height (tup, 1 = upright) are reported with each poll
-- Chat "?claude stop": despawn the vehicle and the target now, and tell the relay to stop the experiment (stop=<count>)
-- Damage to the placed vehicle or the target is reported as dmg=<vehicle>:<amount>:<x>:<y>:<z>:<body>;...
-- No reply: wait longer before each resend (1s, 2s, 4s .. 10s) so the game does not pile up requests
PORT=8765
TIMEOUT=60
MAXHOLD=600
seq=0
t=0
waitT=-1
hold=0
holdT=0
-- No ok reply for this long while a vehicle is placed: the relay is gone, so clean up the vehicle ourselves
ORPHAN=1800
okT=0
-- Saved with the world, so a vehicle left behind (game paused or crashed mid-experiment) is cleaned up on load
g_savedata={vid=-1,gid=-1,tvid=-1,tgid=-1}
-- Chat messages sent before a player is in the game are lost; hold them until someone is here
pending={}
ack=0
res=1
vid=-1
gid=-1
tvid=-1
tgid=-1
tmat=nil
tbase=nil
tname=nil
-- damage events not yet received by the relay; sentN of them went out with the request now waiting
dmg={}
sentN=0
MAXDMG=500
dmgLost=0
hitN=0
hitShownN=0
stopN=0
replyN=0

function log(msg)
	debug.log("[ClaudeBridge] "..msg)
end

function onCreate(is_world_create)
	log("onCreate world_create="..tostring(is_world_create))
	local sv,sg=g_savedata.vid or -1,g_savedata.gid or -1
	if sv>=0 or sg>=0 then
		vid,gid=sv,sg
		log("despawning leftover vehicle id="..sv)
		pending[#pending+1]="despawned leftover vehicle id="..sv
		despawn(true)
	end
	local tv,tg=g_savedata.tvid or -1,g_savedata.tgid or -1
	if tv>=0 or tg>=0 then
		tvid,tgid=tv,tg
		log("despawning leftover target id="..tv)
		pending[#pending+1]="despawned leftover target id="..tv
		despawnTarget(true)
	end
end

function onCustomCommand(full_message,peer_id,is_admin,is_auth,command,one)
	if command~="?claude" then return end
	if one=="stop" then
		stopN=stopN+1
		log("stop requested by peer "..tostring(peer_id))
		server.announce("[Claude]","stop requested: despawning id="..vid.." target="..tvid)
		despawn(true)
		despawnTarget(true)
	else
		server.announce("[Claude]","commands: ?claude stop")
	end
end

function onVehicleDamaged(vehicle_id,amount,vx,vy,vz,body)
	if amount<=0 then return end
	if vehicle_id~=tvid and vehicle_id~=vid then return end
	if vehicle_id==tvid then hitN=hitN+1 end
	if #dmg>=MAXDMG then
		dmgLost=dmgLost+1
		return
	end
	dmg[#dmg+1]=string.format("%d:%.3f:%d:%d:%d:%d",vehicle_id,amount,vx,vy,vz,body)
end

function onTick(game_ticks)
	t=t+1
	if #pending>0 and playerCount()>0 then
		for _,m in ipairs(pending) do server.announce("[Claude]",m) end
		pending={}
	end
	if t%320==1 then
		log("tick="..t.." seq="..seq.." ack="..ack.." replies="..replyN.." waiting="..tostring(waitT>=0).." hold="..hold.." players="..playerCount())
	end
	if t%60==0 and hitN>hitShownN then
		server.announce("[Claude]","target damaged x"..(hitN-hitShownN).." (total "..hitN..")")
		hitShownN=hitN
	end
	if (vid>=0 or tvid>=0) and t-okT>ORPHAN then
		log("no reply from relay, despawning id="..vid.." target="..tvid)
		server.announce("[Claude]","no reply from relay, despawning id="..vid.." target="..tvid)
		despawn()
		despawnTarget()
	end
	if waitT>=0 then
		if t-waitT<TIMEOUT then return end
		waitT=-1
		backoff()
	end
	if t<holdT then return end
	seq=seq+1
	waitT=t
	server.httpGet(PORT,"/addon?s="..seq.."&a="..ack.."&r="..res.."&vid="..vid.."&sim="..simState().."&np="..playerCount()..posQuery()..targetQuery()..dmgQuery().."&stop="..stopN)
end

-- up to 20 damage events per request; they are dropped only after the relay answers this request
function dmgQuery()
	sentN=math.min(#dmg,20)
	local q=""
	if sentN>0 then
		local a={}
		for i=1,sentN do a[i]=dmg[i] end
		q="&dmg="..table.concat(a,";")
	end
	if dmgLost>0 then q=q.."&dlost="..dmgLost end
	return q
end

function backoff()
	hold=math.min(math.max(hold*2,TIMEOUT),MAXHOLD)
	holdT=t+hold
end

function httpReply(port,request,reply)
	if port~=PORT then return end
	replyN=replyN+1
	if replyN<=3 or string.sub(reply,1,2)~="ok" then
		log("reply "..replyN..": "..string.sub(reply,1,80))
	end
	local s=tonumber(string.match(request,"s=(%d+)"))
	if s and s~=seq then return end
	waitT=-1
	if string.sub(reply,1,2)~="ok" then
		backoff()
		return
	end
	hold=0
	holdT=0
	okT=t
	if sentN>0 then
		local rest={}
		for i=sentN+1,#dmg do rest[#rest+1]=dmg[i] end
		dmg=rest
		sentN=0
	end
	local id,op,rest=string.match(reply,"^ok|(%d+)|([%w_]+)|?(.*)$")
	id=tonumber(id)
	if id==nil or id<=ack then return end
	local a={}
	for x in string.gmatch(rest,"[^|]+") do a[#a+1]=x end
	res=run(op,a) and 1 or 0
	ack=id
end

function run(op,a)
	if op=="spawn" then
		return spawn(a)
	elseif op=="despawn" then
		return despawn()
	elseif op=="lift" then
		return lift(tonumber(a[1]) or 15)
	elseif op=="move_player" then
		return movePlayer(tonumber(a[1]),tonumber(a[2]),tonumber(a[3]))
	elseif op=="target" then
		return spawnTarget(a[1],tonumber(a[2]),tonumber(a[3]),a[4]=="1")
	elseif op=="target_despawn" then
		return despawnTarget()
	elseif op=="target_reset" then
		return resetTarget()
	elseif op=="target_renew" then
		return renewTarget()
	elseif op=="weather" then
		local f,r,w=tonumber(a[1]),tonumber(a[2]),tonumber(a[3])
		if f==nil or r==nil or w==nil then return false end
		server.setWeather(f,r,w)
		server.announce("[Claude]",string.format("weather fog=%.2f rain=%.2f wind=%.2f",f,r,w))
		return true
	end
	return false
end

function spawn(a)
	local name=a[1]
	local x,y,z=tonumber(a[2]),tonumber(a[3]),tonumber(a[4])
	if name==nil or x==nil or y==nil or z==nil then return false end
	if a[5]=="1" or a[5]=="2" then
		local p=firstPlayer()
		if p==nil then return false end
		local px,py,pz=matrix.position((server.getPlayerPos(p)))
		if a[5]=="2" then
			-- x = right, y = up, z = forward of where the player looks (horizontal)
			local lx,_,lz,okL=server.getPlayerLookDirection(p)
			local n=okL and math.sqrt(lx*lx+lz*lz) or 0
			if n<1e-6 then return false end
			lx,lz=lx/n,lz/n
			x,z=x*lz+z*lx,-x*lx+z*lz
		end
		x,y,z=x+px,y+py,z+pz
	end
	despawn()
	local v,ok,_,g=server.spawnVehicle(matrix.translation(x,y,z),name)
	if not ok then
		server.announce("[Claude]","spawn failed: "..name)
		return false
	end
	vid=v
	gid=g or -1
	okT=t
	g_savedata.vid=vid
	g_savedata.gid=gid
	server.announce("[Claude]","spawned "..name.." id="..v)
	return true
end

function despawn(quiet)
	if vid<0 and gid<0 then return true end
	local ok
	if gid>=0 then
		ok=server.despawnVehicleGroup(gid,true)
	else
		ok=server.despawnVehicle(vid,true)
	end
	if not quiet then server.announce("[Claude]","despawned id="..vid) end
	vid=-1
	gid=-1
	g_savedata.vid=-1
	g_savedata.gid=-1
	return ok
end

-- a target placed ahead of where the player is looking (horizontal direction only), at world height y
function spawnTarget(name,dist,y,same)
	if name==nil or dist==nil or y==nil then return false end
	if not (same and tbase) then
		local p=firstPlayer()
		if p==nil then return false end
		local lx,_,lz,okL=server.getPlayerLookDirection(p)
		local m,okP=server.getPlayerPos(p)
		if not okL or not okP then return false end
		local n=math.sqrt(lx*lx+lz*lz)
		if n<1e-6 then return false end
		local px,_,pz=matrix.position(m)
		tbase={px,pz,lx/n,lz/n}
	end
	local x,z=tbase[1]+dist*tbase[3],tbase[2]+dist*tbase[4]
	despawnTarget(true)
	local mt=matrix.translation(x,y,z)
	local v,ok,_,g=server.spawnVehicle(mt,name)
	if not ok then
		server.announce("[Claude]","target spawn failed: "..name)
		return false
	end
	tvid=v
	tgid=g or -1
	tmat=mt
	tname=name
	okT=t
	hitN=0
	hitShownN=0
	g_savedata.tvid=tvid
	g_savedata.tgid=tgid
	server.announce("[Claude]",string.format("target %s id=%d at X=%.1f Y=%.1f Z=%.1f (%.0f m)",name,v,x,y,z,dist))
	return true
end

function renewTarget()
	if tvid<0 or tmat==nil or tname==nil then return false end
	local m,name=tmat,tname
	despawnTarget(true)
	local v,ok,_,g=server.spawnVehicle(m,name)
	if not ok then
		server.announce("[Claude]","target spawn failed: "..name)
		return false
	end
	tvid=v
	tgid=g or -1
	tmat=m
	tname=name
	hitN=0
	hitShownN=0
	g_savedata.tvid=tvid
	g_savedata.tgid=tgid
	return true
end

function resetTarget()
	if tvid<0 or tmat==nil then return false end
	if tgid>=0 then return server.setGroupPos(tgid,tmat) end
	return server.setVehiclePos(tvid,tmat)
end

function despawnTarget(quiet)
	if tvid<0 and tgid<0 then return true end
	local ok
	if tgid>=0 then
		ok=server.despawnVehicleGroup(tgid,true)
	else
		ok=server.despawnVehicle(tvid,true)
	end
	if not quiet then server.announce("[Claude]","target despawned id="..tvid.." (damaged "..hitN.." times)") end
	tvid=-1
	tgid=-1
	tmat=nil
	g_savedata.tvid=-1
	g_savedata.tgid=-1
	return ok
end

function targetQuery()
	if tvid<0 then return "" end
	local m,ok=server.getVehiclePos(tvid)
	local s,ok2=server.getVehicleSimulating(tvid)
	local q="&tvid="..tvid.."&tsim="..((ok2 and (s and 1 or 0)) or -1)
	if ok then
		local x,y,z=matrix.position(m)
		q=q..string.format("&tx=%.3f&ty=%.3f&tz=%.3f",x,y,z)
		local fx,fz,uy=m[9],m[11],m[6]
		if fx and fz and uy then
			local at=math.atan2 or math.atan
			q=q..string.format("&tyaw=%.2f&tup=%.4f",math.deg(at(fx,fz)),uy)
		end
	end
	return q
end

function movePlayer(x,y,z)
	if x==nil or y==nil or z==nil then return false end
	local p=firstPlayer()
	if p==nil then return false end
	return server.setPlayerPos(p,matrix.translation(x,y,z))
end

function lift(dy)
	if vid<0 then return false end
	local m,ok=server.getVehiclePos(vid)
	if not ok then return false end
	local x,y,z=matrix.position(m)
	return server.setVehiclePos(vid,matrix.translation(x,y+dy,z))
end

-- the vehicle's world position as the game holds it (independent of on-board sensors)
function posQuery()
	if vid<0 then return "" end
	local m,ok=server.getVehiclePos(vid)
	if not ok then return "" end
	local x,y,z=matrix.position(m)
	return string.format("&px=%.3f&py=%.3f&pz=%.3f",x,y,z)
end

function simState()
	if vid<0 then return -1 end
	local s,ok=server.getVehicleSimulating(vid)
	if not ok then return -1 end
	return s and 1 or 0
end

-- On a dedicated server the list also holds the server itself (steam_id 0); skip it.
function isRealPlayer(p)
	return tostring(p.steam_id)~="0"
end

function firstPlayer()
	for _,p in pairs(server.getPlayers()) do
		if isRealPlayer(p) then return p.id end
	end
	return nil
end

function playerCount()
	local n=0
	for _,p in pairs(server.getPlayers()) do
		if isRealPlayer(p) then n=n+1 end
	end
	return n
end
