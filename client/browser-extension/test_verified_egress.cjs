// Reproducible mock of Chrome MV3 extension proxy control and exit-IP probes.
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm"),path=require("node:path");
const source=fs.readFileSync(path.join(__dirname,"background.js"),"utf8");

async function scenario({direct="198.51.100.9",proxied="212.100.171.183",effective=true,probeFails=false}={}){
  const local={},session={};let applied=false;let listener;
  const area=store=>({
    async get(keys){return Object.fromEntries(keys.map(k=>[k,store[k]]));},
    async set(values){Object.assign(store,values);},
    async remove(keys){for(const key of keys)delete store[key];}
  });
  const chrome={
    storage:{local:area(local),session:area(session)},
    extension:{inIncognitoContext:false},
    privacy:{network:{
      webRTCIPHandlingPolicy:{async set(){},async clear(){}},
      networkPredictionEnabled:{async set(){},async clear(){}}
    }},
    proxy:{
      settings:{
        async clear(){applied=false;},
        async set(){applied=true;},
        async get(){return {
          levelOfControl:effective&&applied?"controlled_by_this_extension":"controllable_by_this_extension",
          value:applied?{mode:"fixed_servers",rules:{singleProxy:{scheme:"https",host:"p.mahinet.shop",port:9444}}}:{mode:"direct"}
        }; }
      },
      onProxyError:{addListener(){}}
    },
    webRequest:{onAuthRequired:{addListener(){}}},
    runtime:{onInstalled:{addListener(){}},onStartup:{addListener(){}},onMessage:{addListener(fn){listener=fn;}}}
  };
  const mockFetch=async url=>{
    if(probeFails&&applied)throw new Error("test proxy blocked");
    return {ok:true,json:async()=>({ip:applied?proxied:direct}),text:async()=>applied?proxied:direct};
  };
  const context={chrome,fetch:mockFetch,AbortController,Date,Error,Number,String,Promise,console,setTimeout,clearTimeout};
  vm.runInNewContext(source,context,{filename:"background.js",timeout:1500});
  async function send(action,proxy){
    return new Promise(resolve=>{
      listener({action,proxy},{},resolve);
    });
  }
  return {send,local,session,proxy:{scheme:"https",host:"p.mahinet.shop",port:9444,username:"test",password:"test-secret"},get applied(){return applied;}};
}

(async()=>{
  let s=await scenario();
  let c=await s.send("connect",s.proxy);
  assert.equal(c.ok,true,JSON.stringify(c));
  assert.equal(c.result.exitIp,"212.100.171.183");
  assert.equal(s.local.connected,true);
  assert.equal(s.local.exitIp,"212.100.171.183");
  assert.equal((await s.send("status")).result.connected,true);
  assert.equal((await s.send("verify")).ok,true);
  assert.equal((await s.send("disconnect")).ok,true);
  assert.equal(s.applied,false);
  assert.equal(s.local.connected,false);

  s=await scenario({direct:"198.51.100.9",proxied:"198.51.100.9"});
  c=await s.send("connect",s.proxy);
  assert.equal(c.ok,false);
  assert.equal(s.local.connected,false);
  assert.equal(s.applied,false);
  assert.match(s.local.connectionError,/IP has not changed/);

  s=await scenario({effective:false});
  c=await s.send("connect",s.proxy);
  assert.equal(c.ok,false);
  assert.equal(s.local.connected,false);
  assert.match(s.local.connectionError,/did not apply/);

  s=await scenario({probeFails:true});
  c=await s.send("connect",s.proxy);
  assert.equal(c.ok,false);
  assert.equal(s.local.connected,false);
  assert.match(s.local.connectionError,/IP verification unavailable/);
  console.log("BROWSER VERIFIED-EGRESS CONTRACT: 4 scenarios PASS");
})().catch(e=>{console.error(e);process.exitCode=1;});
