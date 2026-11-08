-- Q1: send all number channels of the composite input to the relay
-- Wire: Physics Sensor (composite) -> this Lua block (composite in)
-- out num 1: requests sent, out num 2: ok replies, out num 3: error replies
PORT=8765
N=32
TIMEOUT=60
seq=0
tick=0
waitT=-1
okN=0
errN=0

function onTick()
	tick=tick+1
	output.setNumber(1,seq)
	output.setNumber(2,okN)
	output.setNumber(3,errN)
	if waitT>=0 and tick-waitT<TIMEOUT then return end
	local v={}
	for i=1,N do
		v[i]=string.format("%.7g",input.getNumber(i))
	end
	seq=seq+1
	waitT=tick
	async.httpGet(PORT,"/q1?s="..seq.."&t="..tick.."&v="..table.concat(v,","))
end

function httpReply(port,req,res)
	if port~=PORT then return end
	waitT=-1
	if res=="ok" then okN=okN+1 else errN=errN+1 end
end
