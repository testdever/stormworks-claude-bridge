-- FCS bridge: gets target coordinates and fire permission from the relay, sends one record per shot
-- in composite: FCS debug output (OUT4) + number ch20 barrel Tilt (turns) + ch21 pitch pivot angle,
--   on/off ch5 = FCS ready to fire (as in test E3)
-- out number 1-8: command values from the relay (target coordinates, in the order the procedure says)
-- out on/off 1: fire permission (command FIRE > 0.5). Off by itself if the relay stops answering for SAFE ticks
-- out number 29: shots seen, 30: requests sent, 31: ok replies, 32: error replies
-- Sends only the SEL channels, every SENDT ticks (sooner when a shot is waiting to be sent)
-- Shot: fire permission was on and FCS was ready within READY ticks, and the barrel moved KICK deg or more
--   in one tick (recoil). Without permission the gun cannot fire, so turret slewing is not counted.
--   The record is the tick before: n:tick:diff:req:range:pred:tof (diff = barrel - solution, deg)
PORT=8765
SEL={7,8,9,13,20,21}
SENDT=10
C=8
FIRE=5
SAFE=120
TIMEOUT=60
MAXHOLD=600
KICK=0.15
READY=6
REFR=60
seq=0
tick=0
waitT=-1
hold=0
holdT=0
okN=0
errN=0
okT=0
ack=0
lastSend=-999
cmd={}
for i=1,C do cmd[i]=0 end
shots={}
sentN=0
shotN=0
prev=nil
sinceReady=99
sinceFire=99
sinceKick=999

function onTick()
	tick=tick+1
	if tick-okT>SAFE then cmd[FIRE]=0 end
	for i=1,C do output.setNumber(i,cmd[i]) end
	output.setBool(1,cmd[FIRE]>0.5)
	output.setNumber(29,shotN)
	output.setNumber(30,seq)
	output.setNumber(31,okN)
	output.setNumber(32,errN)
	local now={b=input.getNumber(20)*360,r=input.getNumber(9),g=input.getNumber(8),p=input.getNumber(13),f=input.getNumber(7)}
	local ready=input.getBool(5)
	sinceReady=ready and 0 or sinceReady+1
	sinceKick=sinceKick+1
	sinceFire=cmd[FIRE]>0.5 and 0 or sinceFire+1
	if prev and sinceFire<=READY and sinceReady<=READY and sinceKick>REFR and math.abs(now.b-prev.b)>=KICK then
		sinceKick=0
		shotN=shotN+1
		if #shots<50 then
			shots[#shots+1]=string.format("%d:%d:%.5f:%.5f:%.2f:%.3f:%.3f",shotN,tick-1,prev.b-prev.r,prev.r,prev.g,prev.p,prev.f)
		end
	end
	prev=now
	if waitT>=0 then
		if tick-waitT<TIMEOUT then return end
		waitT=-1
		backoff()
	end
	if tick<holdT then return end
	if #shots==0 and tick-lastSend<SENDT then return end
	local v={}
	for i,c in ipairs(SEL) do v[i]=string.format("%.9g",input.getNumber(c)) end
	sentN=#shots
	seq=seq+1
	waitT=tick
	lastSend=tick
	local q="/v?s="..seq.."&t="..tick.."&a="..ack.."&b="..(ready and 16 or 0).."&ch="..table.concat(SEL,",").."&v="..table.concat(v,",")
	if sentN>0 then q=q.."&shot="..table.concat(shots,";",1,sentN) end
	async.httpGet(PORT,q)
end

function backoff()
	hold=math.min(math.max(hold*2,TIMEOUT),MAXHOLD)
	holdT=tick+hold
end

function httpReply(port,req,res)
	if port~=PORT then return end
	local s=tonumber(string.match(req,"s=(%d+)"))
	if s and s~=seq then return end
	waitT=-1
	if string.sub(res,1,2)~="ok" then
		errN=errN+1
		backoff()
		return
	end
	okN=okN+1
	okT=tick
	hold=0
	holdT=0
	if sentN>0 then
		local rest={}
		for i=sentN+1,#shots do rest[#rest+1]=shots[i] end
		shots=rest
		sentN=0
	end
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
