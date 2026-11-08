-- Q2: send composite input values, apply commands from relay replies
-- Wire: Physics Sensor (composite) -> this Lua block (composite in)
-- out num 1-8: command values from relay
-- out num 29: ignored replies to old requests
-- out num 30: requests sent, 31: ok replies, 32: error replies
PORT=8765
N=32
C=8
TIMEOUT=60
seq=0
tick=0
waitT=-1
okN=0
errN=0
oldN=0
ack=0
cmd={}
for i=1,C do cmd[i]=0 end

function onTick()
	tick=tick+1
	for i=1,C do output.setNumber(i,cmd[i]) end
	output.setNumber(29,oldN)
	output.setNumber(30,seq)
	output.setNumber(31,okN)
	output.setNumber(32,errN)
	if waitT>=0 and tick-waitT<TIMEOUT then return end
	local v={}
	for i=1,N do
		v[i]=string.format("%.7g",input.getNumber(i))
	end
	seq=seq+1
	waitT=tick
	async.httpGet(PORT,"/v?s="..seq.."&t="..tick.."&a="..ack.."&v="..table.concat(v,","))
end

function httpReply(port,req,res)
	if port~=PORT then return end
	local s=tonumber(string.match(req,"s=(%d+)"))
	if s and s~=seq then
		oldN=oldN+1
		return
	end
	waitT=-1
	if string.sub(res,1,2)~="ok" then
		errN=errN+1
		return
	end
	okN=okN+1
	local id,body=string.match(res,"^ok|(%d+)|(.*)$")
	id=tonumber(id)
	if id==nil or id<=ack then return end
	for ch,val in string.gmatch(body,"(%d+)=([^,]+)") do
		local c=tonumber(ch)
		local x=tonumber(val)
		if c and x and c>=1 and c<=C then cmd[c]=x end
	end
	ack=id
end
