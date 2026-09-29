(()=>{
  const message=(text,isError=false)=>{
    const box=document.querySelector('[data-agent-message]');
    if(!box) return;
    box.hidden=false;
    box.textContent=text;
    box.classList.toggle('error',Boolean(isError));
  };

  const postJson=async(url)=>{
    const response=await fetch(url,{
      method:'POST',
      credentials:'same-origin',
      headers:{'Accept':'application/json','X-Requested-With':'MakiaClient'}
    });
    let data={};
    try{ data=await response.json(); }catch(_err){}
    if(!response.ok){
      throw new Error(data.detail||('Request failed ('+response.status+')'));
    }
    return data;
  };

  const register=async()=>{
    if(!('serviceWorker' in navigator)) return;
    try{
      await navigator.serviceWorker.register('/client-app/sw.js',{scope:'/client-app/'});
    }catch(_err){
      // Client App remains usable as a normal secure web application.
    }
  };

  const wireAgentActions=()=>{
    const pair=document.querySelector('[data-agent-pair]');
    if(pair){
      pair.addEventListener('click',async()=>{
        pair.disabled=true;
        try{
          const data=await postJson('/client-app/api/agent/pairing-grant');
          message('در حال باز کردن Makia Agent… Pairing فقط ۵ دقیقه اعتبار دارد.');
          window.location.href=data.deep_link;
        }catch(err){
          message(err.message||'Pairing failed',true);
        }finally{
          setTimeout(()=>{pair.disabled=false},1200);
        }
      });
    }

    document.querySelectorAll('[data-agent-connect]').forEach(button=>{
      button.addEventListener('click',async()=>{
        const binding=button.getAttribute('data-binding-id');
        if(!binding) return;
        button.disabled=true;
        try{
          const data=await postJson('/client-app/api/access/'+encodeURIComponent(binding)+'/grant');
          message('Grant یک‌بارمصرف ساخته شد. در حال باز کردن Makia Agent…');
          window.location.href=data.deep_link;
        }catch(err){
          message(err.message||'Connection grant failed',true);
        }finally{
          setTimeout(()=>{button.disabled=false},1200);
        }
      });
    });
  };

  const boot=()=>{
    register();
    wireAgentActions();
  };
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot,{once:true});
  else boot();
})();