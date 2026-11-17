(()=>{
const K="cybers_profile",api=()=>typeof API!=="undefined"?API:"";
let P=null;try{P=JSON.parse(localStorage.getItem(K)||"null")}catch(e){}
const st=document.createElement("style");
st.textContent=`#cpChip{display:none;align-items:center;gap:8px;background:#35190d;color:#fbf1dc;border:1px solid #e8b73a;border-radius:99px;padding:4px 14px 4px 5px;font:600 14px Figtree,system-ui,sans-serif;cursor:pointer;margin-left:10px}
#cpChip i{width:26px;height:26px;border-radius:50%;background:#e8b73a;color:#2a1409;display:grid;place-items:center;font-style:normal;font-weight:700}
#cpPanel{position:fixed;top:0;right:0;bottom:0;width:min(400px,100%);background:#2a1409;color:#fbf1dc;border-left:1px solid #5a3320;z-index:60;transform:translateX(100%);transition:transform .3s;padding:20px;overflow:auto;font:15px Figtree,system-ui,sans-serif}
#cpPanel.open{transform:none}#cpPanel h3,#cpPanel h4{font-family:Fraunces,serif;margin:0}#cpPanel small{color:#c9ad92}
.cpTop{display:flex;justify-content:space-between;align-items:center}.cpX{background:none;border:0;color:#fbf1dc;font-size:28px;cursor:pointer}
.cpHead{display:flex;gap:12px;align-items:center;margin:18px 0}.cpHead i{width:52px;height:52px;border-radius:50%;background:#e8b73a;color:#2a1409;display:grid;place-items:center;font:700 24px Fraunces,serif;font-style:normal}
.cpO{border:1px solid #5a3320;border-radius:12px;padding:12px;margin-top:10px;background:#35190d}.cpO div{display:flex;justify-content:space-between;gap:8px}
.cpB{background:#e8b73a;color:#2a1409;border:0;border-radius:99px;padding:9px 16px;font:700 14px Figtree,system-ui,sans-serif;cursor:pointer;text-decoration:none;display:inline-block}
.cpG{background:none;border:1px solid #5a3320;color:#fbf1dc;border-radius:99px;padding:9px 16px;cursor:pointer;font:inherit;margin-top:20px}
#cpBill{background:#2a1409;color:#fbf1dc;border:1px solid #5a3320;border-radius:16px;width:min(460px,94vw);padding:14px}#cpBill::backdrop{background:#000b}#cpBill img{width:100%;border-radius:10px;display:block}.cpAct{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}`;
document.head.append(st);
const h=(t,c,x)=>{const e=document.createElement(t);if(c)e.className=c;if(x!=null)e.textContent=x;return e};
const chip=h("button",null);chip.id="cpChip";chip.append(h("i",null,""),h("span",null,""));
const nav=document.querySelector("nav .wrap");if(nav)nav.append(chip);else{chip.style.cssText+="position:fixed;top:12px;right:14px;z-index:35";document.body.append(chip)}
const panel=h("aside");panel.id="cpPanel";
panel.innerHTML='<div class="cpTop"><h3>My profile</h3><button class="cpX" aria-label="Close">×</button></div><div class="cpHead"><i></i><div><b></b><br><small></small></div></div><h4>Your orders</h4><div id="cpList"></div><button class="cpG">Not you? Sign out</button>';
document.body.append(panel);
const dlg=document.createElement("dialog");dlg.id="cpBill";
dlg.innerHTML='<img alt="Your bill"><div class="cpAct"><a class="cpB">Download bill</a><button class="cpB">Share on WhatsApp</button><button class="cpG" style="margin:0">Close</button></div>';
document.body.append(dlg);
const img=dlg.querySelector("img"),dl=dlg.querySelector("a"),[sh,cl]=dlg.querySelectorAll("button");
function showBill(p){img.src=api()+p;dl.href=api()+p+"?dl=1";dlg.showModal()}
cl.onclick=()=>dlg.close();
sh.onclick=async()=>{try{const b=await (await fetch(img.src)).blob(),f=new File([b],"cybers-bill.png",{type:"image/png"});
  if(navigator.canShare&&navigator.canShare({files:[f]}))await navigator.share({files:[f],text:"My bill from Cyber’s Tea Point"});else dl.click()}catch(e){}};
function paint(){if(!P){chip.style.display="none";return}
  chip.style.display="inline-flex";chip.querySelector("i").textContent=(P.name||"?")[0].toUpperCase();chip.querySelector("span").textContent=(P.name||"").split(" ")[0];
  panel.querySelector(".cpHead i").textContent=(P.name||"?")[0].toUpperCase();panel.querySelector("b").textContent=P.name;panel.querySelector("small").textContent="+91 "+P.phone}
async function load(){const L=document.getElementById("cpList");L.textContent="Loading…";
  try{const r=await fetch(api()+"/api/my-orders",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({phone:P.phone,token:P.token})});
    const j=await r.json();if(!r.ok)throw 0;L.textContent="";if(!j.orders.length)L.textContent="No orders yet.";
    j.orders.forEach(o=>{const c=h("div","cpO"),a=h("div"),b=h("div");
      a.append(h("b",null,"Order #"+o.id),h("b",null,"₹"+o.total));b.append(h("small",null,o.date),h("small",null,o.status));
      const it=h("p",null,o.items.map(x=>x.replace(/ @\d+$/,"")).join(", "));it.style.cssText="margin:8px 0;color:#c9ad92";
      const bt=h("button","cpB","View bill");bt.onclick=()=>showBill(o.bill);c.append(a,b,it,bt);L.append(c)})
  }catch(e){L.textContent="Could not load your orders. Please try again later."}}
chip.onclick=()=>{panel.classList.add("open");load()};
panel.querySelector(".cpX").onclick=()=>panel.classList.remove("open");
panel.querySelector(".cpG").onclick=()=>{localStorage.removeItem(K);P=null;panel.classList.remove("open");paint()};
document.addEventListener("keydown",e=>{if(e.key==="Escape")panel.classList.remove("open")});
window.Cybers={done(j){P={name:j.name,phone:j.phone,token:j.ptoken};try{localStorage.setItem(K,JSON.stringify(P))}catch(e){}paint();showBill(j.bill)}};
if(P)[["who","ph"],["nm","ph"]].forEach(([n,p])=>{const a=document.getElementById(n),b=document.getElementById(p);if(a&&!a.value)a.value=P.name;if(a&&b&&!b.value)b.value=P.phone});
paint();
})();
