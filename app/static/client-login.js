(()=>{"use strict";
const $=s=>document.querySelector(s);
let installPrompt=null;
function platform(){
  const ua=navigator.userAgent||"",p=navigator.platform||"";
  if(/iPhone|iPad|iPod/i.test(ua)||(/Mac/i.test(p)&&navigator.maxTouchPoints>1))return"ios";
  if(/Android/i.test(ua))return"android";
  if(/Win/i.test(p)||/Windows/i.test(ua))return"windows";
  if(/Mac/i.test(p)||/Macintosh/i.test(ua))return"macos";
  return"web";
}
function label(v){return({ios:"iPhone / iPad",android:"Android",windows:"Windows",macos:"macOS",web:"مرورگر وب"})[v]||"مرورگر وب"}
function standalone(){return window.matchMedia?.("(display-mode: standalone)")?.matches||window.navigator.standalone===true}
function copy(v){
  if(standalone())return"نسخه Makia روی این دستگاه نصب شده است. وارد حساب شوید و ادامه دهید.";
  if(v==="ios")return"در Safari: Share → Add to Home Screen → Add. سپس Makia مثل یک اپ از Home Screen باز می‌شود.";
  if(v==="android")return"در Chrome یا Samsung Internet گزینه Install app یا Add to Home screen را بزنید. بعد از ورود، Direct Connect برای پروتکل‌های پشتیبانی‌شده فعال می‌شود.";
  if(v==="windows")return"در Edge یا Chrome می‌توانید Makia را به‌صورت Web App نصب کنید؛ Direct Connect با Makia Connector اجرا می‌شود.";
  if(v==="macos")return"در Safari از Add to Dock یا در Chrome/Edge از Install app استفاده کنید.";
  return"می‌توانید ابتدا وارد شوید؛ اگر مرورگر نصب Web App را پشتیبانی کند گزینه نصب نمایش داده می‌شود.";
}
function refresh(){
  const p=platform(),name=$("#loginPlatformName"),hint=$("#loginPlatformHint"),guide=$("#loginInstallGuide"),button=$("#installLoginClient"),device=$("#deviceLabel");
  if(name)name.textContent=label(p);
  if(hint)hint.textContent=copy(p);
  if(guide)guide.innerHTML="<strong>ورود روی "+label(p)+"</strong><p>"+copy(p)+"</p>";
  if(device&&!device.value)device.placeholder=({ios:"مثلاً iPhone شخصی",android:"مثلاً Android شخصی",windows:"مثلاً لپ‌تاپ شخصی",macos:"مثلاً MacBook شخصی"})[p]||"مثلاً دستگاه شخصی";
  if(button){button.hidden=standalone();button.textContent=p==="ios"?"راهنمای نصب روی Home Screen":"نصب Makia روی دستگاه";}
}
window.addEventListener("beforeinstallprompt",e=>{e.preventDefault();installPrompt=e;refresh()});
$("#installLoginClient")?.addEventListener("click",async()=>{
  if(standalone())return;
  if(installPrompt){
    installPrompt.prompt();
    await installPrompt.userChoice.catch(()=>null);
    installPrompt=null;
    refresh();
    return;
  }
  const guide=$("#loginInstallGuide");
  if(guide){guide.scrollIntoView({behavior:"smooth",block:"center"});guide.classList.add("is-highlight");setTimeout(()=>guide.classList.remove("is-highlight"),1400)}
});
window.addEventListener("appinstalled",()=>{installPrompt=null;refresh()});
if("serviceWorker"in navigator)window.addEventListener("load",()=>navigator.serviceWorker.register("/client/sw.js",{scope:"/client/"}).catch(()=>{}));
refresh();
})();