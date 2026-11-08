-- Claude Bridge addon (Q3): spawn / despawn vehicles on relay commands
-- Polls the relay at /addon and reports the result of the last command.
-- Reply from relay: "ok" or "ok|<id>|spawn|<save_name>|<x>|<y>|<z>|<rel>" or "ok|<id>|despawn"
--   rel=1: x,y,z are offsets from the first player's position
PORT=8765
TIMEOUT=60
seq=0
t=0
waitT=-1
ack=0
res=1
vid=-1
gid=-1

function onTick(game_ticks)
	t=t+1
	if waitT>=0 and t-waitT<TIMEOUT then return end
	seq=seq+1
	waitT=t
	server.httpGet(PORT,"/addon?s="..seq.."&a="..ack.."&r="..res.."&vid="..vid.."&sim="..simState().."&np="..playerCount())
end

function httpReply(port,request,reply)
	if port~=PORT then return end
	local s=tonumber(string.match(request,"s=(%d+)"))
	if s and s~=seq then return end
	waitT=-1
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
	end
	return false
end

function spawn(a)
	local name=a[1]
	local x,y,z=tonumber(a[2]),tonumber(a[3]),tonumber(a[4])
	if name==nil or x==nil or y==nil or z==nil then return false end
	if a[5]=="1" then
		local p=firstPlayer()
		if p==nil then return false end
		local px,py,pz=matrix.position((server.getPlayerPos(p)))
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
	server.announce("[Claude]","spawned "..name.." id="..v)
	return true
end

function despawn()
	if vid<0 then return true end
	local ok
	if gid>=0 then
		ok=server.despawnVehicleGroup(gid,true)
	else
		ok=server.despawnVehicle(vid,true)
	end
	server.announce("[Claude]","despawned id="..vid)
	vid=-1
	gid=-1
	return ok
end

function simState()
	if vid<0 then return -1 end
	local s,ok=server.getVehicleSimulating(vid)
	if not ok then return -1 end
	return s and 1 or 0
end

function firstPlayer()
	for _,p in pairs(server.getPlayers()) do
		return p.id
	end
	return nil
end

function playerCount()
	local n=0
	for _ in pairs(server.getPlayers()) do n=n+1 end
	return n
end
