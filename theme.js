(function(){
'use strict';

var BASE='https://kjjin628.github.io/lifeinfo-data';
var URLS={
  subsidies:BASE+'/subsidies.json',
  business:BASE+'/business.json',
  festivals:BASE+'/festivals.json',
  upcoming:BASE+'/upcoming.json',
  meta:BASE+'/meta.json',
  posted:BASE+'/posted_urls.json'
};

var REGIONS=['전체','서울','경기','부산','대구','인천','광주','대전','울산','세종','강원','충북','충남','전북','전남','경북','경남','제주'];
var MONTHS=[];
var now=new Date();
for(var mi=0;mi<6;mi++){
  var md=new Date(now.getFullYear(),now.getMonth()+mi,1);
  MONTHS.push({label:(md.getMonth()+1)+'월',value:md.getMonth()+1});
}

var TAB_TITLES={
  subsidies:'💰 지원금',
  business:'🏢 사업자 지원',
  festivals:'🎪 진행중 축제',
  upcoming:'📅 다가오는 행사'
};

var state={
  tab:'subsidies',
  region:'전체',
  month:MONTHS[0]?MONTHS[0].value:null,
  data:{subsidies:[],business:[],festivals:[],upcoming:[]},
  posted:{subsidies:{},business:{},festivals:{}}
};

var $grid=document.getElementById('cardGrid');
var $title=document.getElementById('mainTitle');
var $count=document.getElementById('mainCount');
var $tabs=document.getElementById('localTabsHolder');

var $toggle=document.getElementById('themeToggle');
$toggle.onclick=function(){
  var d=document.documentElement;
  var dark=d.getAttribute('data-theme')==='dark';
  d.setAttribute('data-theme',dark?'light':'dark');
  $toggle.textContent=dark?'🌙':'☀️';
  localStorage.setItem('bz-theme',dark?'light':'dark');
};
(function(){
  var s=localStorage.getItem('bz-theme');
  if(s==='dark'||(!s&&window.matchMedia('(prefers-color-scheme:dark)').matches)){
    document.documentElement.setAttribute('data-theme','dark');
    $toggle.textContent='☀️';
  }
})();

function fetchJSON(url,cb){
  fetch(url).then(function(r){return r.ok?r.json():null;}).then(function(d){cb(d);}).catch(function(){cb(null);});
}

var loaded=0;
function checkReady(){loaded++;if(loaded>=6)render();}

fetchJSON(URLS.subsidies,function(d){state.data.subsidies=d||[];buildRanking('rank-subsidies',state.data.subsidies,'name');checkReady();});
fetchJSON(URLS.business,function(d){state.data.business=d||[];buildRanking('rank-business',state.data.business,'title');checkReady();});
fetchJSON(URLS.festivals,function(d){state.data.festivals=d||[];buildRanking('rank-festivals',state.data.festivals,'title');checkReady();});
fetchJSON(URLS.upcoming,function(d){state.data.upcoming=d||[];checkReady();});
fetchJSON(URLS.meta,function(d){
  if(d){
    var el=document.getElementById('footerStats');
    if(el) el.innerHTML='지원금 '+d.subsidies_count+'건 · 사업자 '+d.business_count+'건 · 축제 '+d.festivals_count+'건 · 업데이트 '+d.updated_at+' KST';
  }
  checkReady();
});
fetchJSON(URLS.posted,function(d){state.posted=d||{subsidies:{},business:{},festivals:{}};checkReady();});

function buildRanking(elId,items,key){
  var el=document.getElementById(elId);
  if(!el)return;
  var list=items.slice(0,5);
  if(!list.length){el.innerHTML='<div style="font-size:0.8rem;color:var(--text-muted)">데이터 없음</div>';return;}
  var h='';
  for(var i=0;i<list.length;i++){
    h+='<div class="ranking-item"><span class="ranking-num">'+(i+1)+'</span><span class="ranking-title">'+esc(list[i][key]||'')+'</span></div>';
  }
  el.innerHTML=h;
}

document.querySelectorAll('.nav-tab').forEach(function(t){
  t.addEventListener('click',function(){
    document.querySelectorAll('.nav-tab').forEach(function(x){x.classList.remove('active');});
    t.classList.add('active');
    state.tab=t.getAttribute('data-tab');
    state.region='전체';
    state.month=MONTHS[0]?MONTHS[0].value:null;
    render();
  });
});

function buildSubTabs(){
  $tabs.innerHTML='';
  if(state.tab==='upcoming'){
    MONTHS.forEach(function(m){
      var b=document.createElement('button');
      b.className='l-tab'+(m.value===state.month?' active':'');
      b.textContent=m.label;
      b.onclick=function(){state.month=m.value;render();};
      $tabs.appendChild(b);
    });
  }else{
    REGIONS.forEach(function(r){
      var b=document.createElement('button');
      b.className='l-tab'+(r===state.region?' active':'');
      b.textContent=r;
      b.onclick=function(){state.region=r;render();};
      $tabs.appendChild(b);
    });
  }
}

function getItems(){
  var items=state.data[state.tab]||[];
  if(state.tab==='upcoming'){
    if(state.month){
      items=items.filter(function(x){
        var s=x.start||'';
        return s.length>=6&&parseInt(s.substring(4,6),10)===state.month;
      });
    }
  }else{
    if(state.region!=='전체'){
      items=items.filter(function(x){
        var r=x.region||'전국';
        return r===state.region||r==='전국';
      });
    }
  }
  return items;
}

function getUrl(tab,item){
  var p=state.posted||{};
  var blog=null;
  if(tab==='subsidies'&&p.subsidies)blog=p.subsidies[item.id]||null;
  else if(tab==='business'&&p.business)blog=p.business[item.title]||null;
  else if(p.festivals)blog=p.festivals[item.contentid]||null;
  if(blog)return blog;
  if(item.url&&item.url.length>5)return item.url;
  if(tab==='subsidies'){
    if(item.id)return 'https://www.gov.kr/portal/rcvfvrSvc/dtlEx/'+item.id;
    return 'https://www.gov.kr/search?srhQuery='+encodeURIComponent(item.name||'');
  }
  if(tab==='business'){
    return 'https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId='+encodeURIComponent(item.title||'');
  }
  if(item.contentid)return 'https://korean.visitkorea.or.kr/detail/ms_detail.do?cotid='+item.contentid;
  return 'https://korean.visitkorea.or.kr/search/search.do?keyword='+encodeURIComponent(item.title||'');
}

function hasBlog(tab,item){
  var p=state.posted||{};
  if(tab==='subsidies'&&p.subsidies)return !!p.subsidies[item.id];
  if(tab==='business'&&p.business)return !!p.business[item.title];
  if(p.festivals)return !!p.festivals[item.contentid];
  return false;
}

function render(){
  buildSubTabs();
  var items=getItems();
  var regionLabel=state.tab==='upcoming'?(state.month+'월'):state.region;
  $title.textContent=TAB_TITLES[state.tab]+' — '+regionLabel;
  $count.textContent='총 '+items.length+'건';
  if(!items.length){
    $grid.innerHTML='<div class="state-box">해당 조건의 데이터가 없습니다.</div>';
    return;
  }
  var h='';
  var tab=state.tab;
  for(var i=0;i<items.length;i++){
    var item=items[i];
    var url=getUrl(tab,item);
    var oc=url?(' onclick="window.open(\''+escA(url)+'\',\'_blank\')"'):'';
    var bb=hasBlog(tab,item)?'<span class="badge badge-blog">📝 블로그</span>':'';
    if(tab==='festivals'||tab==='upcoming'){
      var img=item.image||item.thumb||'';
      var ds='';
      if(item.start){ds=item.start.replace(/(\d{4})(\d{2})(\d{2})/,'$1.$2.$3');if(item.end)ds+=' ~ '+item.end.replace(/(\d{4})(\d{2})(\d{2})/,'$1.$2.$3');}
      h+='<div class="card festival-card"'+oc+'>'+(img?'<img class="festival-img" src="'+esc(img)+'" alt="" loading="lazy" onerror="this.style.display=\'none\'"/>':'')+'<div class="festival-body"><div class="card-badges"><span class="badge badge-region">'+esc(item.region||'')+'</span>'+bb+'</div><div class="card-title">'+esc(item.title||'')+'</div>'+(ds?'<div class="card-desc">'+esc(ds)+'</div>':'')+'<div class="card-meta"><span>'+esc(item.addr||'')+'</span></div></div></div>';
    }else if(tab==='business'){
      h+='<div class="card"'+oc+'><div class="card-badges"><span class="badge badge-region">'+esc(item.region||'전국')+'</span>'+(item.field?'<span class="badge badge-field">'+esc(item.field)+'</span>':'')+bb+'</div><div class="card-title">'+esc(item.title||'')+'</div><div class="card-desc">'+esc(item.desc||'')+'</div><div class="card-meta"><span>'+esc(item.org||item.exec_org||'')+'</span>'+(item.apply_date?'<span>'+esc(item.apply_date)+'</span>':'')+'</div></div>';
    }else{
      h+='<div class="card"'+oc+'><div class="card-badges"><span class="badge badge-region">'+esc(item.region||'전국')+'</span>'+(item.category?'<span class="badge badge-category">'+esc(item.category)+'</span>':'')+bb+'</div><div class="card-title">'+esc(item.name||'')+'</div><div class="card-desc">'+esc(item.desc||'')+'</div><div class="card-meta"><span>'+esc(item.org||'')+'</span></div></div>';
    }
  }
  $grid.innerHTML=h;
}

function esc(s){if(!s)return '';var d=document.createElement('div');d.textContent=s;return d.innerHTML;}
function escA(s){if(!s)return '';return s.replace(/\\/g,'\\\\').replace(/'/g,"\\'");}

})();
