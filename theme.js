(function(){
'use strict';

function init(){
var BASE='https://kjjin628.github.io/lifeinfo-data';
var URLS={
  subsidies:BASE+'/subsidies.json',
  business:BASE+'/business.json',
  meta:BASE+'/meta.json',
  posted:BASE+'/posted_urls.json'
};

var REGIONS=['전체','서울','경기','부산','대구','인천','광주','대전','울산','세종','강원','충북','충남','전북','전남','경북','경남','제주'];

var TAB_TITLES={
  subsidies:'💰 맞춤형 정부 지원금',
  business:'🏢 소상공인·사업자 자금 지원'
};

var state={
  tab:'subsidies',
  region:'전체',
  data:{subsidies:[],business:[]},
  posted:{subsidies:{},business:{}}
};

var $grid=document.getElementById('cardGrid');
var $title=document.getElementById('mainTitle');
var $count=document.getElementById('mainCount');
var $tabs=document.getElementById('localTabsHolder');

/* ---- 핵심 체크: DOM 요소가 없으면 0.5초 후 재시도 ---- */
if(!$grid||!$title||!$count||!$tabs){
  setTimeout(init,500);
  return;
}

var $toggle=document.getElementById('themeToggle');
if($toggle){
  $toggle.onclick=function(){
    var d=document.documentElement;
    var dark=d.getAttribute('data-theme')==='dark';
    d.setAttribute('data-theme',dark?'light':'dark');
    $toggle.textContent=dark?'🌙':'☀️';
    try{localStorage.setItem('bz-theme',dark?'light':'dark');}catch(e){}
  };
  (function(){
    try{
      var s=localStorage.getItem('bz-theme');
      if(s==='dark'||(!s&&window.matchMedia&&window.matchMedia('(prefers-color-scheme:dark)').matches)){
        document.documentElement.setAttribute('data-theme','dark');
        $toggle.textContent='☀️';
      }
    }catch(e){}
  })();
}

function fetchJSON(url,cb){
  var x=new XMLHttpRequest();
  x.open('GET',url,true);
  x.onreadystatechange=function(){
    if(x.readyState===4){
      if(x.status===200){
        try{cb(JSON.parse(x.responseText));}catch(e){cb(null);}
      }else{cb(null);}
    }
  };
  x.onerror=function(){cb(null);};
  try{x.send();}catch(e){cb(null);}
}

var loaded=0;
function checkReady(){loaded++;if(loaded>=4)render();}

fetchJSON(URLS.subsidies,function(d){state.data.subsidies=d||[];buildRanking('rank-subsidies',state.data.subsidies,'name');checkReady();});
fetchJSON(URLS.business,function(d){state.data.business=d||[];buildRanking('rank-business',state.data.business,'title');checkReady();});
fetchJSON(URLS.meta,function(d){
  if(d){
    var el=document.getElementById('footerStats');
    if(el) el.innerHTML='지원금 '+d.subsidies_count+'건 · 사업자 '+d.business_count+'건 · 업데이트 '+d.updated_at+' KST';
  }
  checkReady();
});
fetchJSON(URLS.posted,function(d){state.posted=d||{subsidies:{},business:{}};checkReady();});

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

/* 탭 클릭 이벤트 - 자금 정보 위주로 구성 */
var navTabs=document.querySelectorAll('.nav-tab');
for(var ti=0;ti<navTabs.length;ti++){
  (function(t){
    t.addEventListener('click',function(){
      for(var j=0;j<navTabs.length;j++) navTabs[j].classList.remove('active');
      t.classList.add('active');
      state.tab=t.getAttribute('data-tab');
      state.region='전체';
      render();
    });
  })(navTabs[ti]);
}

function buildSubTabs(){
  $tabs.innerHTML='';
  for(var ri=0;ri<REGIONS.length;ri++){
    (function(r){
      var b=document.createElement('button');
      b.className='l-tab'+(r===state.region?' active':'');
      b.textContent=r;
      b.onclick=function(){state.region=r;render();};
      $tabs.appendChild(b);
    })(REGIONS[ri]);
  }
}

function getItems(){
  var items=state.data[state.tab]||[];
  if(state.region!=='전체'){
    items=items.filter(function(x){
      var r=x.region||'전국';
      return r===state.region||r==='전국';
    });
  }
  return items;
}

function getUrl(tab,item){
  var p=state.posted||{};
  var blog=null;
  
  // 1순위: 자동 글쓰기 프로그램이 갱신해 준 내 블로그 실물 주소 체크
  if(tab==='subsidies' && p.subsidies) {
    blog = p.subsidies[item.id] || null;
  } else if(tab==='business' && p.business) {
    blog = p.business[item.title] || null;
  }
  
  if(blog) return blog;
  
  // 2순위: 블로그 글이 아직 안 올라갔을 때 작동하는 원본 공공기관 가이드라인
  if(tab==='subsidies'){
    if(item.id){
      if(item.region && item.region!=='전국'){
        return 'https://www.gov.kr/search?srhQuery='+encodeURIComponent(item.name||'');
      }
      return 'https://www.gov.kr/portal/rcvfvrSvc/dtlEx/'+item.id;
    }
    return 'https://www.gov.kr/search?srhQuery='+encodeURIComponent(item.name||'');
  }
  
  if(tab==='business'){
    return item.url || 'https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId='+encodeURIComponent(item.title||'');
  }
  
  return '#';
}

function hasBlog(tab,item){
  var p=state.posted||{};
  if(tab==='subsidies' && p.subsidies) return !!p.subsidies[item.id];
  if(tab==='business' && p.business) return !!p.business[item.title];
  return false;
}

function render(){
  buildSubTabs();
  var items=getItems();
  $title.textContent=TAB_TITLES[state.tab] + ' — ' + state.region;
  $count.textContent='총 '+items.length+'건';
  if(!items.length){
    $grid.innerHTML='<div class="state-box">해당 조건의 혜택 데이터가 없습니다.</div>';
    return;
  }
  var h='';
  var tab=state.tab;
  for(var i=0;i<items.length;i++){
    var item=items[i];
    var url=getUrl(tab,item);
    var oc=url?(' onclick="window.open(\''+escA(url)+'\',\'_blank\')"'):'';
    var bb=hasBlog(tab,item)?'<span class="badge badge-blog">📝 블로그 분석</span>':'';
    
    if(tab==='business'){
      h+='<div class="card"'+oc+'><div class="card-badges"><span class="badge badge-region">'+esc(item.region||'전국')+'</span>'+(item.field?'<span class="badge badge-field">'+esc(item.field)+'</span>':'')+bb+'</div><div class="card-title">'+esc(item.title||'')+'</div><div class="card-desc">'+esc((item.desc||'').replace(/<[^>]*>/g,''))+'</div><div class="card-meta"><span>'+esc(item.org||item.exec_org||'')+'</span>'+(item.apply_date?'<span>'+esc(item.apply_date)+'</span>':'')+'</div></div>';
    }else{
      h+='<div class="card"'+oc+'><div class="card-badges"><span class="badge badge-region">'+esc(item.region||'전국')+'</span>'+(item.category?'<span class="badge badge-category">'+esc(item.category)+'</span>':'')+bb+'</div><div class="card-title">'+esc(item.name||'')+'</div><div class="card-desc">'+esc(item.desc||'')+'</div><div class="card-meta"><span>'+esc(item.org||'')+'</span></div></div>';
    }
  }
  $grid.innerHTML=h;
}

function esc(s){if(!s)return '';var d=document.createElement('div');d.textContent=s;return d.innerHTML;}
function escA(s){if(!s)return '';return s.replace(/\\/g,'\\\\').replace(/'/g,"\\'");}

} /* end init */

if(document.readyState==='loading'){
  document.addEventListener('DOMContentLoaded',init);
}else{
  init();
}

})();
