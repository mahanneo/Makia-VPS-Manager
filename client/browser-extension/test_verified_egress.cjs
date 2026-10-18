// Reproducible mock of Chrome MV3 extension proxy control and exit-IP probes.
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm"),path=require("node:path");
const source=fs.readFileSync(path.join(__dirname,"background.js"),"utf8");

async function scenario({direct="198.51.100.9",proxied="212.100.171.183",effective=true,probeFails=false}={}){
  const local={},session={};let applied=false;let listener;let onProxyError;let onInstalled;let onStartup;let failNextProxyProbe=false;
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
      onProxyError:{addListener(fn){onProxyError=fn;}}
    },
    webRequest:{onAuthRequired:{addListener(){}}},
    runtime:{onInstalled:{addListener(fn){onInstalled=fn;}},onStartup:{addListener(fn){onStartup=fn;}},onMessage:{addListener(fn){listener=fn;}}}
  };
  const mockFetch=async url=>{
    if((probeFails||failNextProxyProbe)&&applied)throw new Error("test proxy blocked");
    return {ok:true,json:async()=>({ip:applied?proxied:direct}),text:async()=>applied?proxied:direct};
  };
  const context={chrome,fetch:mockFetch,AbortController,Date,Error,Number,String,Promise,console,setTimeout,clearTimeout};
  vm.runInNewContext(source,context,{filename:"background.js",timeout:1500});
  async function send(action,proxy){
    return new Promise(resolve=>{
      listener({action,proxy},{},resolve);
    });
  }
  return {send,local,session,proxyError:(error)=>onProxyError({error}),
    restart:()=>onStartup(),update:()=>onInstalled({reason:"update"}),
    install:()=>onInstalled({reason:"install"}),setBlocked:(yes)=>{failNextProxyProbe=yes;},
    proxy:{scheme:"https",host:"p.mahinet.shop",port:9444,username:"test",password:"test-secret"},
    get applied(){return applied;}};
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
  assert.equal(s.applied,true,"Failed verification must not silently enable direct browsing");
  assert.match(s.local.connectionError,/IP has not changed/);
  assert.equal((await s.send("status")).result.proxyActive,true);
  assert.equal((await s.send("connect",s.proxy)).ok,false,"Held proxy requires explicit disconnect");
  assert.equal(s.applied,true);
  assert.equal((await s.send("disconnect")).ok,true);
  assert.equal(s.applied,false);

  s=await scenario({effective:false});
  c=await s.send("connect",s.proxy);
  assert.equal(c.ok,false);
  assert.equal(s.local.connected,false);
  assert.equal(s.applied,false,"Proxy not owned by Makia must not be treated as held");
  assert.match(s.local.connectionError,/did not apply/);

  s=await scenario({probeFails:true});
  c=await s.send("connect",s.proxy);
  assert.equal(c.ok,false);
  assert.equal(s.local.connected,false);
  assert.equal(s.applied,true,"Offline gateway stays installed until explicit disconnect");
  assert.equal((await s.send("status")).result.proxyActive,true);
  assert.match(s.local.connectionError,/IP verification unavailable/);
  assert.equal((await s.send("verify")).ok,false);
  assert.equal(s.applied,true,"Repeated verification failure must not clear installed proxy");
  await s.send("disconnect");
  assert.equal(s.applied,false);
  // A single failed subrequest does not mean the entire proxy is offline.
  s=await scenario();
  c=await s.send("connect",s.proxy);
  assert.equal(c.ok,true);
  await s.proxyError("net::ERR_TUNNEL_CONNECTION_FAILED");
  assert.equal(s.local.connected,true);
  assert.equal(s.local.exitIp,"212.100.171.183");

  // Repeated failures that prevent a fresh verified exit do mark it offline;
  // the proxy remains installed (no silent direct fallback).
  s.setBlocked(true);
  await s.proxyError("net::ERR_TUNNEL_CONNECTION_FAILED");
  assert.equal(s.local.connected,false);
  assert.equal(s.applied,true);
  assert.match(s.local.connectionError,/egress check failed/);
  assert.equal((await s.send("status")).result.proxyActive,true);
  s.setBlocked(false);
  assert.equal((await s.send("verify")).ok,true,"A repaired gateway is re-verifiable without direct fallback");
  assert.equal(s.local.connected,true);
  assert.equal(s.applied,true);
  s=await scenario();
  assert.equal((await s.send("connect",s.proxy)).ok,true);
  await s.restart();
  assert.equal(s.applied,true,"Browser restart must preserve a previously configured proxy");
  assert.equal(s.local.connected,false,"Browser restart must require fresh verification");
  assert.equal((await s.send("status")).result.proxyActive,true);
  assert.match(s.local.connectionError,/proxy is held but not verified/);
  await s.update();
  assert.equal(s.applied,true,"Extension update must not silently clear selected proxy");
  assert.equal(s.local.connected,false);
  assert.equal((await s.send("disconnect")).ok,true);
  assert.equal(s.applied,false);

  s=await scenario();
  await s.install();
  assert.equal(s.applied,false,"First install without an assigned proxy stays direct");

  // Opening a popup must not reuse a stale successful IP check as proof of egress.
  s=await scenario();
  assert.equal((await s.send("connect",s.proxy)).ok,true);
  s.local.verifiedAt=Date.now()-130000;
  s.setBlocked(true);
  const stale=await s.send("status");
  assert.equal(stale.result.connected,false,"Expired egress verification cannot remain green");
  assert.equal(stale.result.proxyActive,true,"Failed recheck must keep the proxy held");
  assert.equal(s.applied,true);
  assert.match(stale.result.connectionError,/Recent Browser Gateway egress verification failed/);
  await s.send("disconnect");

  // A previous valid connection must not remain Connected when its proxy
  // authentication token has expired, even with the same Chrome proxy setting.
  s=await scenario();
  const timedProxy={...s.proxy,expires_at:Math.floor(Date.now()/1000)+300};
  assert.equal((await s.send("connect",timedProxy)).ok,true);
  s.local.credentialExpiresAt=Math.floor(Date.now()/1000)-1;
  const expired=await s.send("status");
  assert.equal(expired.result.connected,false,"Expired credential cannot remain Connected");
  assert.equal(expired.result.proxyActive,true);
  assert.equal(s.applied,true,"Expiry must not silently route direct");
  assert.match(expired.result.connectionError,/credential expired/i);
  assert.equal((await s.send("verify")).ok,false,"An expired credential must fail a new verification");
  assert.equal(s.applied,true);
  await s.send("disconnect");

  // User-initiated credential renewal after browser restart keeps the HTTPS
  // proxy installed at every step; no direct fallback or remembered password.
  s=await scenario();
  const renewable={...s.proxy,expires_at:Math.floor(Date.now()/1000)+300,control_host:"p.mahinet.shop"};
  assert.equal((await s.send("connect",renewable)).ok,true);
  await s.restart();
  assert.equal(s.applied,true);
  assert.equal(s.local.connected,false);
  assert.equal((await s.send("reconnect",{...renewable,host:"evil.example"})).ok,false);
  assert.equal(s.applied,true);
  assert.equal((await s.send("reconnect",{...renewable,expires_at:1})).ok,false);
  assert.equal(s.applied,true);
  const renewed=await s.send("reconnect",{...renewable,password:"fresh-proxy-only"});
  assert.equal(renewed.ok,true,JSON.stringify(renewed));
  assert.equal(s.local.connected,true);
  assert.equal(s.local.exitIp,"212.100.171.183");
  assert.equal(s.session.proxyAuth.password,"fresh-proxy-only");
  assert.equal(s.applied,true);
  await s.send("disconnect");

  // If re-auth works but the actual exit check fails, retain the held proxy,
  // display unverified, and leave manual disconnect available.
  s=await scenario();
  assert.equal((await s.send("connect",renewable)).ok,true);
  await s.restart();
  s.setBlocked(true);
  const failedRenew=await s.send("reconnect",renewable);
  assert.equal(failedRenew.ok,false);
  assert.equal(s.applied,true);
  assert.equal(s.local.connected,false);
  assert.equal((await s.send("status")).result.proxyActive,true);
  await s.send("disconnect");

  console.log("BROWSER VERIFIED-EGRESS CONTRACT: 16 scenario groups PASS");
})().catch(e=>{console.error(e);process.exitCode=1;});
