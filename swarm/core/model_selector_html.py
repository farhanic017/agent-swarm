"""Model Selector HTML — interactive browser-based model management.

Renders a self-contained HTML file with categories (All, Recent, Favorites,
Free, Hidden), search, per-model star (favorite) and hide actions.
"""

from pathlib import Path
import json
import textwrap


def render_model_selector(output_path: str, payload: dict):
    """Write a self-contained HTML model selector to output_path."""
    data = json.dumps(payload, ensure_ascii=True)
    html = _TEMPLATE.replace("__PAYLOAD__", data)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html, encoding="utf-8")


_TEMPLATE = textwrap.dedent("""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Octo Code — Model Selector</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0d0e12;--panel:#15171d;--card:#1c1f28;--card-hover:#242836;
  --border:#2a2e3a;--text:#e8eaf0;--muted:#8b90a0;--accent:#6c5ce7;
  --green:#00d68f;--red:#ff6b6b;--yellow:#ffd166;--blue:#54a0ff;
  --star:#ffd166;--free:#00d68f;
}
body{font-family:Inter,-apple-system,system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
.app{max-width:900px;margin:0 auto;padding:24px}

/* Header */
.header{display:flex;align-items:center;gap:16px;margin-bottom:24px}
.header h1{font-size:22px;font-weight:700;letter-spacing:-0.5px}
.header .count{color:var(--muted);font-size:13px;margin-left:auto}

/* Search */
.search-wrap{position:relative;margin-bottom:20px}
.search-wrap input{width:100%;padding:12px 16px 12px 42px;background:var(--panel);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:14px;outline:none;transition:border-color .2s}
.search-wrap input:focus{border-color:var(--accent)}
.search-wrap .icon{position:absolute;left:14px;top:50%;transform:translateY(-50%);color:var(--muted);font-size:16px}

/* Categories */
.categories{display:flex;gap:6px;margin-bottom:20px;flex-wrap:wrap}
.cat-btn{padding:7px 16px;border-radius:20px;border:1px solid var(--border);background:transparent;color:var(--muted);font-size:12px;font-weight:600;cursor:pointer;transition:all .2s;letter-spacing:0.3px}
.cat-btn:hover{border-color:var(--accent);color:var(--text)}
.cat-btn.active{background:var(--accent);border-color:var(--accent);color:#fff}
.cat-btn .badge{display:inline-block;background:rgba(255,255,255,.15);border-radius:8px;padding:1px 6px;margin-left:4px;font-size:10px;font-weight:700}

/* Model grid */
.models{display:flex;flex-direction:column;gap:6px}
.model-card{display:grid;grid-template-columns:auto 1fr auto auto;align-items:center;gap:12px;padding:12px 16px;background:var(--card);border:1px solid var(--border);border-radius:10px;cursor:pointer;transition:all .15s}
.model-card:hover{background:var(--card-hover);border-color:var(--accent)}
.model-card.active{border-color:var(--green);background:rgba(0,214,143,.06)}
.model-card.hidden-card{opacity:.45}

/* Status dot */
.dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.dot.healthy{background:var(--green)}
.dot.unhealthy{background:var(--red)}
.dot.depleted{background:var(--yellow)}

/* Model info */
.model-info{min-width:0}
.model-name{font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.model-meta{font-size:11px;color:var(--muted);margin-top:2px;display:flex;gap:8px;align-items:center}
.tag{padding:2px 6px;border-radius:4px;font-size:9px;font-weight:700;letter-spacing:0.5px}
.tag.free{background:rgba(0,214,143,.15);color:var(--free)}
.tag.paid{background:rgba(139,144,160,.15);color:var(--muted)}
.tag.active-tag{background:rgba(0,214,143,.2);color:var(--green)}
.tag.specialty{background:rgba(108,92,231,.15);color:var(--accent)}

/* Score */
.score{font-size:11px;color:var(--muted);min-width:32px;text-align:right}

/* Actions */
.actions{display:flex;gap:4px;align-items:center}
.star-btn,.hide-btn{width:30px;height:30px;border:none;border-radius:6px;background:transparent;cursor:pointer;font-size:16px;display:flex;align-items:center;justify-content:center;transition:all .15s;color:var(--muted)}
.star-btn:hover{background:rgba(255,209,102,.15);color:var(--star)}
.star-btn.starred{color:var(--star)}
.hide-btn:hover{background:rgba(255,107,107,.15);color:var(--red)}
.hide-btn.hidden-active{color:var(--red)}

/* Empty state */
.empty{text-align:center;padding:60px 20px;color:var(--muted)}
.empty .icon{font-size:40px;margin-bottom:12px}
.empty p{font-size:14px}

/* Health msg tooltip */
.health-tip{position:relative}
.health-tip:hover::after{content:attr(data-tip);position:absolute;bottom:calc(100% + 6px);left:50%;transform:translateX(-50%);background:#2a2e3a;color:var(--text);padding:6px 10px;border-radius:6px;font-size:11px;white-space:nowrap;z-index:10;pointer-events:none}

@media(max-width:600px){
  .model-card{grid-template-columns:auto 1fr auto;gap:8px;padding:10px 12px}
  .score{display:none}
}
</style>
</head>
<body>
<div class="app">
  <div class="header">
    <h1>Model Selector</h1>
    <span class="count" id="count"></span>
  </div>
  <div class="search-wrap">
    <span class="icon">&#128269;</span>
    <input type="text" id="search" placeholder="Search models..." autocomplete="off">
  </div>
  <div class="categories" id="categories"></div>
  <div class="models" id="models"></div>
</div>
<script>
const DATA = __PAYLOAD__;
let models = DATA.models || [];
let activeCat = 'all';
let searchQuery = '';

const cats = [
  {id:'all',label:'All Models',icon:''},
  {id:'favorites',label:'Favorites',icon:'\u2605'},
  {id:'recent',label:'Recent',icon:'\u23F3'},
  {id:'free',label:'Free',icon:'\u2601'},
  {id:'hidden',label:'Hidden',icon:'\u25CE'},
];

function renderCategories(){
  const el=document.getElementById('categories');
  el.innerHTML='';
  cats.forEach(c=>{
    const count=getCatModels(c.id).length;
    const btn=document.createElement('button');
    btn.className='cat-btn'+(activeCat===c.id?' active':'');
    btn.innerHTML=(c.icon?c.icon+' ':' '+c.label)+'<span class="badge">'+count+'</span>';
    btn.onclick=()=>{activeCat=c.id;render()};
    el.appendChild(btn);
  });
}

function getCatModels(cat){
  let list=[...models];
  if(cat==='favorites')list=list.filter(m=>m.is_fav);
  else if(cat==='recent'){
    const recentKeys=DATA.recent||[];
    list=recentKeys.map(k=>list.find(m=>m.key===k)).filter(Boolean);
  }
  else if(cat==='free')list=list.filter(m=>m.is_free);
  else if(cat==='hidden')list=list.filter(m=>m.is_hidden);
  else list=list.filter(m=>!m.is_hidden);
  if(searchQuery){
    const q=searchQuery.toLowerCase();
    list=list.filter(m=>m.key.toLowerCase().includes(q)||m.provider.toLowerCase().includes(q)||m.model_id.toLowerCase().includes(q)||m.specialty.toLowerCase().includes(q));
  }
  return list;
}

function renderModels(){
  const el=document.getElementById('models');
  const list=getCatModels(activeCat);
  document.getElementById('count').textContent=list.length+' model'+(list.length!==1?'s':'');
  if(!list.length){
    el.innerHTML='<div class="empty"><div class="icon">\u2205</div><p>No models match your filter.</p></div>';
    return;
  }
  el.innerHTML='';
  list.forEach(m=>{
    const card=document.createElement('div');
    card.className='model-card'+(m.is_active?' active':'')+(m.is_hidden?' hidden-card':'');
    const dotClass=m.is_depleted?'depleted':m.healthy?'healthy':'unhealthy';
    const tip=m.is_depleted?'depleted — cooldown active':m.health_msg;
    const tags=[];
    tags.push('<span class="tag '+(m.is_free?'free':'paid')+'">'+(m.is_free?'FREE':'PAID')+'</span>');
    if(m.specialty&&m.specialty!=='general')tags.push('<span class="tag specialty">'+m.specialty.toUpperCase()+'</span>');
    if(m.is_active)tags.push('<span class="tag active-tag">ACTIVE</span>');
    card.innerHTML=
      '<div class="dot '+dotClass+' health-tip" data-tip="'+tip+'"></div>'+
      '<div class="model-info">'+
        '<div class="model-name">'+m.provider+'/'+m.model_id+'</div>'+
        '<div class="model-meta">'+tags.join('')+'</div>'+
      '</div>'+
      '<div class="score health-tip" data-tip="Score: '+m.score+'" >'+m.score+'</div>'+
      '<div class="actions">'+
        '<button class="star-btn'+(m.is_fav?' starred':'')+'" data-key="'+m.key+'" title="'+(m.is_fav?'Remove from favorites':'Add to favorites')+'">'+(m.is_fav?'\u2605':'\u2606')+'</button>'+
        '<button class="hide-btn'+(m.is_hidden?' hidden-active':'')+'" data-key="'+m.key+'" title="'+(m.is_hidden?'Show model':'Hide model')+'">'+(m.is_hidden?'\u25C9':'\u25CB')+'</button>'+
      '</div>';
    card.querySelector('.star-btn').onclick=e=>{e.stopPropagation();toggleFav(m.key)};
    card.querySelector('.hide-btn').onclick=e=>{e.stopPropagation();toggleHide(m.key)};
    el.appendChild(card);
  });
}

function toggleFav(key){
  const m=models.find(x=>x.key===key);
  if(m){m.is_fav=!m.is_fav;render()}
}
function toggleHide(key){
  const m=models.find(x=>x.key===key);
  if(m){m.is_hidden=!m.is_hidden;render()}
}

function render(){renderCategories();renderModels()}

document.getElementById('search').addEventListener('input',e=>{
  searchQuery=e.target.value;render();
});

render();
</script>
</body>
</html>
""")
