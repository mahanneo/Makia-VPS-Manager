(()=>{
  const register=async()=>{
    if(!('serviceWorker' in navigator)) return;
    try{
      await navigator.serviceWorker.register('/client-app/sw.js',{scope:'/client-app/'});
    }catch(_err){
      // Client App remains usable as a normal secure web application.
    }
  };
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',register,{once:true});
  else register();
})();