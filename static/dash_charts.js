/* Dashboard chart kit (S151, v8). Loaded once by every Dashboard chart frame
   from app/static/dash_charts.js; each frame calls DashCharts.render(kind, spec).
   Values under the pointer, a finger dragged across, or the arrow keys; at rest
   the latest values. Colours come from the frame's CSS variables, which
   src/ui/dash_charts.py writes from src/ui/tokens.py. */
(function(){
const REDRAW = [];
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const dlong = s => { const [y,m,d] = s.split('-'); return `${+d} ${MON[+m-1]} ${y}`; };
const sg = (v,dp=1) => v==null ? '—' : (v>0?'+':v<0?'−':'') + Math.abs(v).toFixed(dp);
const inr = v => (v<0?'−':'+') + '₹' + Math.abs(v).toLocaleString('en-IN');
const NS = 'http://www.w3.org/2000/svg';
const mk = (tag, attrs={}, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };

function niceTicks(lo, hi, n=4){
  const span = hi-lo || 1, step0 = span/n, p = Math.pow(10, Math.floor(Math.log10(step0)));
  const step = [1,2,2.5,5,10].map(f=>f*p).find(s=>s>=step0);
  const out=[]; for (let v=Math.ceil(lo/step)*step; v<=hi+1e-9; v+=step) out.push(+v.toFixed(6)); return out;
}
// Monotone cubic path (Fritsch–Carlson), so smoothing never overshoots a real value.
function smooth(pts){
  const n=pts.length; if(n<3) return 'M'+pts.map(p=>p.join(',')).join('L');
  const dx=[],dy=[],m=[],t=[];
  for(let i=0;i<n-1;i++){dx[i]=pts[i+1][0]-pts[i][0];dy[i]=pts[i+1][1]-pts[i][1];m[i]=dy[i]/dx[i];}
  t[0]=m[0];t[n-1]=m[n-2];
  for(let i=1;i<n-1;i++) t[i]=m[i-1]*m[i]<=0?0:3*(dx[i-1]+dx[i])/((2*dx[i]+dx[i-1])/m[i-1]+(dx[i]+2*dx[i-1])/m[i]);
  let d=`M${pts[0][0]},${pts[0][1]}`;
  for(let i=0;i<n-1;i++){const h=dx[i]/3;d+=`C${pts[i][0]+h},${pts[i][1]+t[i]*h} ${pts[i+1][0]-h},${pts[i+1][1]-t[i+1]*h} ${pts[i+1][0]},${pts[i+1][1]}`;}
  return d;
}
let uid=0;

/* A line/area pane. opts: dates, series[{name,color,values,area,fmt,end}], height, yfmt, bands, levels, xlabels */
function linePane(el, o){
  const W = Math.max(280, el.clientWidth), H = o.height, padL = o.padL ?? 46, padR = o.padR ?? 12, padT = 10, padB = o.noX ? 6 : 24;
  el.querySelector('svg')?.remove(); const svg = mk('svg',{viewBox:`0 0 ${W} ${H}`,height:H,'aria-hidden':'true'}); el.prepend(svg);
  const n=o.dates.length, all=o.series.flatMap(s=>s.values.filter(v=>v!=null));
  let lo=Math.min(...all,...(o.levels||[]).map(l=>l.v)), hi=Math.max(...all,...(o.levels||[]).map(l=>l.v));
  if(o.range){lo=o.range[0];hi=o.range[1];} else {const pad=(hi-lo)*0.08;lo-=pad;hi+=pad;}
  const X=i=>padL+(W-padL-padR)*(n<2?0:i/(n-1)), Y=v=>padT+(H-padT-padB)*(1-(v-lo)/(hi-lo));
  for(const b of o.bands||[]) mk('rect',{x:padL,width:W-padL-padR,y:Y(b.to),height:Y(b.from)-Y(b.to),fill:b.fill},svg);
  for(const t of niceTicks(lo,hi,o.ticks||4)){ if(t<lo||t>hi) continue;
    mk('line',{x1:padL,x2:W-padR,y1:Y(t),y2:Y(t),stroke:css('--rule-soft'),'stroke-width':1},svg);
    mk('text',{x:padL-6,y:Y(t)+4,'text-anchor':'end'},svg).textContent=String(o.yfmt(t)).replace('-','−'); }
  for(const l of o.levels||[]){ mk('line',{x1:padL,x2:W-padR,y1:Y(l.v),y2:Y(l.v),stroke:l.color,'stroke-width':1,'stroke-dasharray':'3 4'},svg);
    const t=mk('text',{x:padL+4,y:Y(l.v)-5},svg); t.textContent=l.label; t.setAttribute('style',`fill:${l.color}`); }
  if(!o.noX){ const yrs=new Set(); const step=Math.max(1,Math.ceil(n/Math.max(2,Math.floor((W-padL-padR)/84))));
    let prevY=null, prevL=null;
    for(let i=0;i<n;i+=step){ const [y,m]=o.dates[i].split('-'); const lab=o.xfmt?o.xfmt(o.dates[i]):(y!==prevY?`${MON[+m-1]} ’${y.slice(2)}`:MON[+m-1]);
      if(lab===prevL||(!o.xfmt&&y===prevY&&MON[+m-1]===prevL)) continue; prevY=y; prevL=o.xfmt?lab:MON[+m-1];  // a month is named once
      const t=mk('text',{x:X(i),y:H-6,'text-anchor':i===0?'start':'middle'},svg); t.textContent=lab; } }
  for(const s of o.series){
    const pts=s.values.map((v,i)=>v==null?null:[X(i),Y(v)]).filter(Boolean);
    if(s.area){ const id='g'+(++uid); const g=mk('linearGradient',{id,x1:0,x2:0,y1:0,y2:1},mk('defs',{},svg));
      mk('stop',{offset:'0%','stop-color':s.color,'stop-opacity':.28},g); mk('stop',{offset:'100%','stop-color':s.color,'stop-opacity':0},g);
      const base=Y(o.areaBase??lo); mk('path',{d:smooth(pts)+`L${pts.at(-1)[0]},${base}L${pts[0][0]},${base}Z`,fill:`url(#${id})`},svg); }
    mk('path',{d:smooth(pts),fill:'none',stroke:s.color,'stroke-width':s.width||2,'stroke-linejoin':'round','stroke-linecap':'round','stroke-dasharray':s.dash||''},svg);
    const last=pts.at(-1); mk('circle',{cx:last[0],cy:last[1],r:4,fill:s.color,stroke:css('--bg'),'stroke-width':2},svg);
    if(s.end){ const t=mk('text',{x:last[0]+8,y:last[1]+4+(s.endDy||0),class:'lbl-end'},svg); t.textContent=s.end; t.setAttribute('style',`fill:${s.color}`); }
  }
  const cross=mk('line',{y1:padT,y2:H-padB,stroke:css('--muted'),'stroke-width':1,opacity:0},svg);
  const dots=o.series.map(s=>mk('circle',{r:5,fill:s.color,stroke:css('--bg'),'stroke-width':2,opacity:0},svg));
  return { n, X, padL, padR, W,
    show(i){ if(i==null){cross.setAttribute('opacity',0);dots.forEach(d=>d.setAttribute('opacity',0));return;}
      cross.setAttribute('x1',X(i));cross.setAttribute('x2',X(i));cross.setAttribute('opacity',.55);
      o.series.forEach((s,k)=>{const v=s.values[i]; if(v==null){dots[k].setAttribute('opacity',0);return;} dots[k].setAttribute('cx',X(i));dots[k].setAttribute('cy',Y(v));dots[k].setAttribute('opacity',1);}); },
    index(px){ return Math.max(0,Math.min(n-1,Math.round((px-padL)/(W-padL-padR)*(n-1)))); } };
}

/* A bar pane: labels, values; colours by sign; rounded ends; others dim under the pointer. */
function barPane(el,o){
  const W=Math.max(280,el.clientWidth),H=o.height,padL=6,padR=o.padR??52,padT=14,padB=o.valueLabels&&Math.min(...o.values)<0?36:24;
  el.querySelector('svg')?.remove(); const svg=mk('svg',{viewBox:`0 0 ${W} ${H}`,height:H,'aria-hidden':'true'}); el.prepend(svg);
  const v2=(o.values2||[]).filter(v=>v!=null);   // a second series beside the first, where it exists (domestic flows)
  // Stacked on one column: a second value of the same sign sits beyond the first; of the other sign it runs from zero.
  const ends=o.values.map((v,i)=>{ const u=o.values2?o.values2[i]:null; if(u==null) return [v]; return (u>=0)===(v>=0)?[v+u]:[v,u]; }).flat();
  const bnd=o.band||[];   // the usual range [low, high, label], shaded behind the bars (tipsheet benchmark, 21 Nov 2026)
  const dv=(o.dots||[]).filter(v=>v!=null), n=o.values.length, fx=o.valueLabels?1.22:1.08;
  let lo=Math.min(0,...o.values,...ends,...dv,...bnd.slice(0,2))*fx, hi=Math.max(0,...o.values,...ends,...dv,...bnd.slice(0,2))*fx;
  if(o.range){lo=o.range[0];hi=o.range[1];}
  const Y=v=>padT+(H-padT-padB)*(1-(v-lo)/(hi-lo)), bw=(W-padL-padR)/n, gap=Math.min(6,bw*.28);
  if(bnd.length){ mk('rect',{x:padL,width:W-padL-padR,y:Y(bnd[1]),height:Math.max(1,Y(bnd[0])-Y(bnd[1])),fill:css('--caution-soft')},svg);
    if(bnd[2]){ const t=mk('text',{x:padL+4,y:Y(bnd[1])+12,class:'lbl-band'},svg); t.textContent=bnd[2]; } }
  for(const t of niceTicks(lo,hi,4)){ mk('line',{x1:padL,x2:W-padR,y1:Y(t),y2:Y(t),stroke:t===0?css('--ink'):css('--rule-soft'),'stroke-width':1,opacity:t===0?.5:1},svg);
    mk('text',{x:W-padR+8,y:Y(t)+4},svg).textContent=String(o.yfmt(t)).replace('-','−'); }
  for(const l of o.levels||[]){ mk('line',{x1:padL,x2:W-padR,y1:Y(l.v),y2:Y(l.v),stroke:l.color,'stroke-dasharray':'3 4'},svg);
    if(l.label){ const t=mk('text',{x:padL+2,y:Y(l.v)+(l.below?13:-5)},svg); t.textContent=l.label; t.setAttribute('style',`fill:${l.color}`); } }
  const r=Math.min(3,bw/4), bars=[];
  const bar=(x,w,v,fill,base=0)=>{ const y0=Y(base), y1=Y(base+v), h=Math.abs(y1-y0), up=v>=0, top=up?y1:y0, rr=Math.min(r,h/2);
    const d=up?`M${x},${y0}V${top+rr}Q${x},${top} ${x+rr},${top}H${x+w-rr}Q${x+w},${top} ${x+w},${top+rr}V${y0}Z`
              :`M${x},${y0}V${y1-rr}Q${x},${y1} ${x+rr},${y1}H${x+w-rr}Q${x+w},${y1} ${x+w},${y1-rr}V${y0}Z`;
    return mk('path',{d,fill},svg); };
  o.values.forEach((v,i)=>{ const x=padL+i*bw+gap/2, w=Math.max(1,bw-gap), y0=Y(0), y1=Y(v), h=Math.abs(y1-y0);
    const up=v>=0, top=up?y1:y0, rr=Math.min(r,h/2);
    const d=up?`M${x},${y0}V${top+rr}Q${x},${top} ${x+rr},${top}H${x+w-rr}Q${x+w},${top} ${x+w},${top+rr}V${y0}Z`
              :`M${x},${y0}V${y1-rr}Q${x},${y1} ${x+rr},${y1}H${x+w-rr}Q${x+w},${y1} ${x+w},${y1-rr}V${y0}Z`;
    const last=i===n-1 && o.markLast;
    bars.push(mk('path',{d,fill:up?css('--up'):css('--down'),opacity:last||!o.markLast?1:.72},svg));
    const u=o.values2&&o.values2[i]; if(u!=null){ const same=(u>=0)===(v>=0), base=same?v:0, end=base+u; bar(x,w,u,css(o.color2||'--teal'),base);
      if(o.valueLabels){ const t=mk('text',{x:x+w/2,y:end>=0?Y(end)-5:Y(end)+13,'text-anchor':'middle',class:'lbl-v'},svg); t.textContent=o.valueLabels(u); t.setAttribute('style',`fill:${css(o.color2||'--teal')}`); } } });
  (o.dots||[]).forEach((v,i)=>{ if(v!=null) mk('circle',{cx:padL+i*bw+bw/2,cy:Y(v),r:Math.max(2.5,Math.min(4,bw/5)),fill:css('--ink')},svg); });
  const step=Math.max(1,Math.ceil(n/Math.min(o.xn||6,Math.max(2,Math.floor((W-padL-padR)/78)))));
  for(let i=0;i<n;i+=step){ const first=i===0&&bw<40; const t=mk('text',{x:first?padL:padL+i*bw+bw/2,y:H-6,'text-anchor':first?'start':'middle'},svg); t.textContent=o.xlab(i); }
  if(o.valueLabels){ o.values.forEach((v,i)=>{ const u=o.values2?o.values2[i]:null, inside=u!=null&&(u>=0)===(v>=0);
    const t=mk('text',{x:padL+i*bw+bw/2,y:inside?(v>=0?Y(v)+13:Y(v)-5):(v>=0?Y(v)-5:Y(v)+13),'text-anchor':'middle',class:'lbl-v'},svg); t.textContent=o.valueLabels(v);
    t.setAttribute('style',inside?`fill:${css('--bg')};stroke:none`:`fill:${v>=0?css('--up'):css('--down')}`); }); }
  if(o.markLast){ const i=n-1,v=o.values[i]; const t=mk('text',{x:padL+i*bw+bw/2,y:v>=0?Y(v)-5:Y(v)+13,'text-anchor':'end',class:'lbl-end'},svg); t.textContent=o.lastLabel; t.setAttribute('style',`fill:${v>=0?css('--up'):css('--down')}`); }
  return { n, W, X:i=>padL+i*bw+bw/2, show(i){ bars.forEach((b,k)=>b.style.opacity = i==null ? '' : (k===i?1:.3)); },
    index(px){ return Math.max(0,Math.min(n-1,Math.floor((px-padL)/bw))); } };
}

/* Pointer, touch and keyboard: one handler for every chart. On touch the tooltip is replaced by the readout above. */
function interact(card, panes, readout, rows, restIndex){
  const charts=[...card.querySelectorAll('.chart')], tip=document.createElement('div'); tip.className='tip'; charts[0].appendChild(tip);
  let cur=null;
  const render=(i,touch)=>{ cur=i; panes().forEach(p=>p.show(i)); const k=i??restIndex(); const r=rows(k);
    if(typeof readout==='function') readout(r,i); else readout.innerHTML=roHtml(r,i);
    if(i==null||touch){ tip.classList.remove('on'); return; }
    tip.innerHTML=`<div class="t-d">${r.date}</div>`+r.items.map(x=>`<div class="t-r"><span class="t-k"><i style="background:${x.color}"></i>${x.name}</span><b>${x.v}</b></div>`).join('');
    const p=panes()[0], x=p.X?p.X(i):(p.index&&null), cw=charts[0].clientWidth;
    const px = p.X ? p.X(i)/p.W*cw : (i+0.5)/p.n*(cw-52);
    tip.classList.add('on'); const tw=tip.offsetWidth; tip.style.left=Math.max(0,Math.min(cw-tw, px+14>cw-tw?px-tw-14:px+14))+'px'; tip.style.top='6px'; };
  for(const c of charts){
    const at=(e)=>{ const box=c.getBoundingClientRect(); const p=panes()[charts.indexOf(c)]||panes()[0]; const W=p.W||box.width; return p.index((e.clientX-box.left)/box.width*W); };
    c.addEventListener('pointermove',e=>render(at(e),e.pointerType==='touch'));
    c.addEventListener('pointerdown',e=>render(at(e),e.pointerType==='touch'));
    c.addEventListener('pointerleave',e=>{ if(e.pointerType!=='touch') render(null); });  // a lifted finger keeps its reading
  }
  charts[0].addEventListener('keydown',e=>{ const n=panes()[0].n; if(e.key==='ArrowLeft'||e.key==='ArrowRight'){ e.preventDefault(); render(Math.max(0,Math.min(n-1,(cur??n-1)+(e.key==='ArrowLeft'?-1:1)))); } if(e.key==='Escape') render(null); });
  charts[0].addEventListener('blur',()=>render(null));
  /* The readout keeps the height of its tallest reading, so a reading that wraps to a second line
     (a month in progress names its dates) never pushes the chart down as the pointer moves (owner, 21 Nov). */
  if(typeof readout!=='function'){ let w=0;
    const fit=()=>{ const n=panes()[0].n, step=Math.max(1,Math.floor(n/80)); readout.style.minHeight=''; let h=0;
      const ks=[]; for(let k=0;k<n;k+=step) ks.push(k); ks.push(n-1);
      for(const k of ks){ readout.innerHTML=roHtml(rows(k),k); h=Math.max(h,readout.offsetHeight); }
      readout.innerHTML=roHtml(rows(restIndex()),null); h=Math.max(h,readout.offsetHeight);
      readout.style.minHeight=h+'px'; render(cur); };
    if(window.ResizeObserver) new ResizeObserver(()=>{ const nw=readout.clientWidth; if(nw&&nw!==w){ w=nw; fit(); } }).observe(readout);
  }
  render(null);
}
const roHtml=(r,i)=>`<span class="d">${i==null?'Latest · ':''}${r.date}</span>`+r.items.map(x=>`<span class="ro"><i style="background:${x.color}"></i><b style="color:${x.vcolor||'inherit'}">${x.v}</b><span>${x.name}</span></span>`).join('');

function _unusedTable(card, head, rows){
  const btn=card.querySelector('[data-table]'), box=card.querySelector('.tbl');
  btn.addEventListener('click',()=>{ if(!box.innerHTML) box.innerHTML=`<table><thead><tr>${head.map(h=>`<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${rows().map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
    box.hidden=!box.hidden; btn.textContent=box.hidden?'Show the table':'Hide the table'; });
}
function chips(card, onPick){ card.querySelectorAll('.chip').forEach(b=>b.addEventListener('click',()=>{ card.querySelectorAll('.chip').forEach(x=>x.setAttribute('aria-pressed',x===b)); onPick(+b.dataset.range); })); }
const mlabel = s => { const [y,m]=s.split('-'); return `${MON[+m-1]} ${y}`; };

function track(v, o){
  // Straight lines in two colours: ink where filled, light grey where empty. A negative value
  // fills leftward from the zero line. The last line fills part of its height, so 5.4 and 5.6 differ.
  const N = Math.round((o.hi - o.lo) / o.step), z = Math.round((0 - o.lo) / o.step);
  const pos = v != null && v >= 0, reach = v == null ? 0 : Math.abs(v) / o.step;
  let out = '';
  for (let k = 0; k < N; k++){
    const d = pos ? k - z : z - 1 - k;
    let f = 0;
    if (v != null && ((pos && k >= z) || (!pos && k < z))) f = Math.max(0, Math.min(1, reach - d));
    if (f <= 0) { out += '<i></i>'; continue; }
    const p = Math.round(f * 100);
    out += f >= 1 ? '<i class="f"></i>' : `<i style="background:linear-gradient(to top, var(--ink) ${p}%, var(--rule) ${p}%)"></i>`;
  }
  const at = x => (x - o.lo) / (o.hi - o.lo) * 100;
  const extra = (o.lo < 0 ? `<span class="zero" style="left:${at(0)}%"></span>` : '')
    + (o.lines || []).map(x => `<span class="line" style="left:${at(x)}%"></span>`).join('')
    + (o.ago != null ? `<span class="ago" style="left:${at(o.ago)}%" title="A month ago"></span>` : '');
  return `<div class="tt" style="--n:${N}">${out}${extra}</div>`;
}

function rowsInteract(card, sel, read){
  const rows = [...card.querySelectorAll(sel)];
  rows.forEach((r, j) => { r.tabIndex = 0;
    const on = () => { rows.forEach(x => x.classList.toggle('on', x === r)); read(j); };
    r.addEventListener('pointerenter', on); r.addEventListener('pointerdown', on); r.addEventListener('focus', on);
    r.addEventListener('pointerleave', e => { if (e.pointerType !== 'touch') { r.classList.remove('on'); read(null); } });
    r.addEventListener('blur', () => { r.classList.remove('on'); read(null); }); });
  /* As in interact(): the readout holds its tallest reading, so moving down the rows never moves them
     (412 px, 21 Nov: the book's month went from two lines to four). A period switch redraws and can only
     raise the hold; a new width starts it again. */
  const box = $('.readout', card);
  if (box) { const fit = () => { const w = box.clientWidth; if (!w) return;
      if (box._w !== w) { box._w = w; box._h = 0; box.style.minHeight = ''; }
      let h = box._h; for (let j = 0; j < rows.length; j++) { read(j); h = Math.max(h, box.offsetHeight); }
      read(null); box._h = h = Math.max(h, box.offsetHeight); box.style.minHeight = h + 'px'; };
    fit(); if (window.ResizeObserver && !box._ro) { box._ro = new ResizeObserver(() => { if (box.clientWidth !== box._w) box._fit(); }); box._ro.observe(box); }
    box._fit = fit; return; }
  read(null);
}
const ro = (card, date, items) => { $('.readout', card).innerHTML = `<span class="d">${date}</span>` + items.map(x =>
  `<span class="ro">${x.color ? `<i style="background:${x.color}"></i>` : ''}<b class="${x.cls || ''}">${x.v}</b><span>${x.name}</span></span>`).join(''); };


const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const tone = v => v == null ? '' : v >= 0 ? 'up' : 'down';

const R = {};

/* The month: one row per series, straight-line bars, a period switch (a month that fell shows leftward). */
R.month = (card, s) => {
  const o = {lo: s.lo, hi: s.hi, step: s.step};
  let m = s.periods[0].key;
  const sw = $('.chips', card);
  sw.innerHTML = s.periods.map((p, i) => `<button class="chip" type="button" data-m="${p.key}" aria-pressed="${i === 0}">${esc(p.label)}</button>`).join('');
  const draw = () => { const v = s.values[m], label = s.periods.find(p => p.key === m).label;
    $('.seg-rows', card).innerHTML = s.rows.map((r, j) => `<div class="trow" role="listitem"><div class="nm"${r.bold ? ' style="font-weight:700"' : ''}>${esc(r.name)}<small>${esc(r.sub)}</small></div>${track(v[j], o)}<div class="vl ${tone(v[j])}">${v[j] == null ? '—' : sg(v[j]) + '%'}</div></div>`).join('');
    $('.seg-axis div', card).innerHTML = s.axis.map(t => `<span style="left:${(t - o.lo) / (o.hi - o.lo) * 100}%">${t > 0 ? '+' : t < 0 ? '−' : ''}${Math.abs(t)}%</span>`).join('');
    rowsInteract(card, '.trow', j => { const k = j ?? s.book, mk = v[s.market], bk = v[s.book];
      ro(card, (j == null ? 'Latest · ' : '') + label, [{v: sg(v[k], 2) + '%', cls: tone(v[k]), name: s.rows[k].name},
        {v: sg(v[k] - mk) + ' pts', cls: tone(v[k] - mk), name: 'against the market'},
        ...(k !== s.market && k !== s.book ? [{v: sg(bk - v[k]) + ' pts', cls: tone(bk - v[k]), name: 'the book against it'}] : [])]); }); };
  sw.querySelectorAll('.chip').forEach(b => b.addEventListener('click', () => { sw.querySelectorAll('.chip').forEach(x => x.setAttribute('aria-pressed', x === b)); m = b.dataset.m; draw(); }));
  draw();
};

/* Monthly bars from a zero line: momentum's lead, foreign flows. */
R.bars = (card, s) => {
  const el = $('.chart', card); let pane;
  const draw = () => { pane = barPane(el, {values: s.values, values2: s.also ? s.also.map(a => a && a[1]) : null, color2: s.color2, height: s.height || 220, yfmt: v => sg(v / (s.axisDiv || 1), 0).replace('+', ''), xlab: i => s.labels[i], xn: s.xn || 6,
    markLast: !!s.lastLabel, lastLabel: s.lastLabel, padR: 38, valueLabels: s.valueLabels ? v => sg(v / (s.axisDiv || 1), s.vdp ?? 0) : null,
    levels: (s.levels || []).map(l => ({v: l, color: css('--up')})), band: s.band, dots: s.dots, range: s.range}); };
  REDRAW.push(draw); draw(); new ResizeObserver(draw).observe(el);
  interact(card, () => [pane], $('.readout', card), k => { const v = s.values[k], c = v >= 0 ? css('--up') : css('--down');
    const lvl = s.levels && s.levels.length ? ' · ' + (v >= s.levels[0] ? s.above : v < 0 ? s.belowZero : s.between) : '';
    const items = [{name: s.unit + lvl, color: c, v: s.money ? inr(v) : sg(v, s.dp ?? 1), vcolor: c}];
    if (s.dots && s.dots[k] != null) items.push({name: s.dotName || '', color: css('--ink'), v: sg(s.dots[k], s.dp ?? 1), vcolor: css('--down')});
    const a = s.also && s.also[k]; if (a) items.push({name: a[0], color: css(s.color2 || '--teal'), v: s.money ? inr(a[1]) : sg(a[1], s.dp ?? 1), vcolor: a[1] >= 0 ? css('--up') : css('--down')});
    return {date: s.full[k] + (k === s.values.length - 1 && s.lastNote ? s.lastNote : ''), items}; }, () => s.values.length - 1);
};

/* Breadth by size list: bars plus the three readings. */
R.shared = (card, s) => {
  const nows = s.rows.map(r => r[3]), lo = Math.min(...nows), hi = Math.max(...nows);
  $('#rows', card).innerHTML = s.rows.map(([n, a3, a1, now]) => `<div class="shrow" role="listitem"><div class="nm"><b>${esc(n)}</b></div>${track(now, {lo: 0, hi: 100, step: s.step, ago: a1, lines: [40, 60]})}<span class="num muted">${a3 == null ? '—' : a3 + '%'}</span><span class="num muted">${a1 == null ? '—' : a1 + '%'}</span><span class="num b ${now === hi ? 'up' : now === lo ? 'down' : ''}">${now}%</span></div>`).join('');
  const best = nows.indexOf(hi);
  rowsInteract(card, '.shrow', j => { const [n, a3, a1, now] = s.rows[j ?? best];
    ro(card, j == null ? 'Latest · the broadest' : n, [{v: now + '%', name: 'now'}, {v: sg(now - a1, 0) + ' pts', cls: tone(now - a1), name: 'in a month'}, {v: sg(now - a3, 0) + ' pts', cls: tone(now - a3), name: 'in 3 months'}]); });
};

/* The book by industry: one segment per industry, labelled where it fits. */
R.segbar = (card, s) => {
  const bar = $('.segbar', card), G = {strong: 'Strong', turning: 'Turning', weak: 'Weak'};
  bar.innerHTML = s.segs.map(([n, h, w, , , , g], i) => `<i role="listitem" class="seg-${g}${i % 2 ? ' alt' : ''}" style="flex:${w} 1 0" data-i="${i}" tabindex="0" aria-label="${esc(n)} ${w}%"><span>${esc(n)} ${Math.round(w)}%</span></i>`).join('');
  const show = i => { bar.querySelectorAll('i').forEach(t => t.classList.toggle('dim', i != null && +t.dataset.i !== i));
    const [n, h, w, r6, r1, , g] = s.segs[i ?? 0];
    ro(card, i == null ? 'Latest · the largest' : G[g], [{v: w.toFixed(1) + '%', name: `${n}, ${h} holding${h > 1 ? 's' : ''}`}, {v: sg(r6) + ' · ' + sg(r1), cls: tone(r1), name: '6M · 1M'}]); };
  bar.querySelectorAll('i').forEach(t => { const i = +t.dataset.i; t.addEventListener('pointerenter', () => show(i)); t.addEventListener('pointerdown', () => show(i)); t.addEventListener('focus', () => show(i)); });
  bar.addEventListener('pointerleave', e => { if (e.pointerType !== 'touch') show(null); });
  const fit = () => bar.querySelectorAll('i').forEach(t => { const sp = t.querySelector('span'); sp.style.visibility = ''; if (sp.offsetWidth > t.clientWidth - 10) sp.style.visibility = 'hidden'; });
  if (s.totals) $('.seg-key', card).innerHTML = [['strong', 'Strong', 'ahead of the market on both windows'], ['turning', 'Turning', 'ahead on one'], ['weak', 'Weak', 'behind on both']]
    .filter(([k]) => s.totals[k] != null).map(([k, t, d]) => `<span><i class="seg-${k}"></i><b>${s.totals[k].toFixed(1)}%</b> ${t}, ${d}</span>`).join('');
  show(null); fit(); new ResizeObserver(fit).observe(bar);
};

/* The index and how many stocks carry it: two panes, one crosshair, 6M / 1Y / 3Y. */
R.breadth = (card, s) => {
  const top = $('[data-pane="top"]', card), bot = $('[data-pane="bottom"]', card);
  let from = 0, panes = [];
  const draw = () => { const dates = s.dates.slice(from), n5 = s.n500.slice(from), a = s.a200.slice(from);
    panes = [linePane(top, {dates, series: [{name: 'Nifty 500', color: css('--ink'), values: n5, area: true, width: 1.8}], height: 180, noX: true, yfmt: v => v.toLocaleString('en-IN')}),
             linePane(bot, {dates, series: [{name: 'Above their 200D EMA', color: css('--up'), values: a, area: true, width: 1.8}], height: 130, range: [0, 100], ticks: 4, yfmt: v => v + '%', areaBase: 0,
               bands: [{from: 60, to: 100, fill: css('--up-soft')}, {from: 0, to: 40, fill: css('--down-soft')}],
               levels: [{v: 60, label: 'Broad', color: css('--up')}, {v: 40, label: 'Narrow', color: css('--down')}]})]; };
  REDRAW.push(draw); draw(); new ResizeObserver(draw).observe(top);
  chips(card, r => { from = r ? Math.max(0, s.dates.length - r) : 0; draw(); });
  interact(card, () => panes, $('.readout', card), k => { const i = from + k; return {date: dlong(s.dates[i]), items: [
    {name: 'Nifty 500', color: css('--ink'), v: s.n500[i].toLocaleString('en-IN', {minimumFractionDigits: 1, maximumFractionDigits: 1})},
    {name: 'of the 750 above their 200D EMA', color: css('--up'), v: s.a200[i] == null ? '—' : s.a200[i].toFixed(0) + '%', vcolor: s.a200[i] >= 60 ? css('--up') : s.a200[i] <= 40 ? css('--down') : ''}]}; }, () => s.dates.length - 1 - from);
};

/* ₹100 since the start and how far below its peak, the book and the market: two panes, one crosshair (Portfolio).
   The values sit in each pane's heading and follow the pointer, so the lines use the frame's whole width (owner, 20 Nov). */
R.growth = (card, s) => {
  const top = $('[data-pane="top"]', card), bot = $('[data-pane="bottom"]', card);
  let panes = [];
  const draw = () => { const W = top.clientWidth, h = Math.round(Math.max(200, Math.min(340, W * 0.32)));
    panes = [linePane(top, {dates: s.dates, series: [
        {name: 'The book', color: css('--ink'), values: s.book, area: true, width: 2.4},
        {name: 'Nifty500 Momentum 50', color: css('--caution'), values: s.mom},
        {name: 'Nifty Total Market', color: css('--muted'), values: s.market, dash: '5 4'}],
        height: h, padL: 34, padR: 8, noX: true, yfmt: v => v.toFixed(0), areaBase: Math.min(...s.book) * 0.95}),
      linePane(bot, {dates: s.dates, series: [{name: 'The book', color: css('--down'), values: s.dd, area: true, width: 1.6},
        {name: 'Nifty Total Market', color: css('--muted'), values: s.ddm, dash: '4 3', width: 1.4}],
        height: Math.round(h * 0.5), padL: 34, padR: 8, yfmt: v => v.toFixed(0) + '%', areaBase: 0, ticks: 3})]; };
  REDRAW.push(draw); draw(); new ResizeObserver(draw).observe(top);
  const put = (k, v, c) => { const b = $(`[data-v="${k}"]`, card); b.textContent = v; b.className = c || ''; };
  interact(card, () => panes, (r, i) => { const k = i ?? s.dates.length - 1;
    $('.ph .d', card).textContent = (i == null ? 'Latest · ' : '') + r.date;
    put('book', '₹' + s.book[k].toFixed(1)); put('mom', s.mom[k] == null ? '—' : '₹' + s.mom[k].toFixed(1)); put('market', s.market[k] == null ? '—' : '₹' + s.market[k].toFixed(1));
    put('dd', sg(s.dd[k]) + '%', s.dd[k] < 0 ? 'down' : ''); put('ddm', s.ddm[k] == null ? '—' : sg(s.ddm[k]) + '%'); },
    k => ({date: dlong(s.dates[k]), items: []}), () => s.dates.length - 1);
};

/* The holdings, sortable by any column (Portfolio). */
R.holdings = (card, s) => {
  const el = $('.hold', card), inrf = v => (v < 0 ? '−' : '') + '₹' + Math.round(Math.abs(v)).toLocaleString('en-IN');
  const f2 = v => v.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const rk = r => r == null ? 'Out' : '#' + r;
  const MONS = MON;
  const ds = d => { const [y, m, dd] = d.split('-'); return `${+dd} ${MONS[+m - 1]} ’${y.slice(2)}`; };
  const cols = s.cols;
  let key = 'val', dir = -1;
  const draw = () => {
    const rows = s.rows.slice().sort((a, b) => { const va = a[key] ?? 999, vb = b[key] ?? 999; return (typeof va === 'string' ? va.localeCompare(vb) : va - vb) * dir; });
    const lab = (k, t) => { if (k !== 'rn') return esc(t); const [w, ...rest] = t.split(' '); return `${esc(w)}<span class="vh"> ${esc(rest.join(' '))}</span><span class="rk3" aria-hidden="true">${rest.join(' ').split(' · ').map(x => `<i>${esc(x)}</i>`).join('')}</span>`; };
    const head = cols.map(([k, t, n]) => `<th scope="col" data-k="${k}" tabindex="0" class="${n ? 'num' : ''}${k === 'rn' ? ' rk' : ''}" aria-sort="${k === key ? (dir < 0 ? 'descending' : 'ascending') : 'none'}">${lab(k, t)}</th>`).join('');
    const body = rows.map(h => {
      const emaC = h.ema != null && h.ema < 0 ? 'down b' : '', hiC = h.hi != null && h.hi <= -s.high_cut ? 'down b' : h.hi != null && h.hi <= -12 ? 'watch' : 'muted';
      const rC = h.rn == null || h.rn > s.rank_cut ? 'down' : '';
      return `<tr><th scope="row" title="${esc(h.co)}"><span class="sym">${esc(h.s)}</span><span class="ss co">${esc(h.co_short)}</span></th>`
        + `<td>${esc(h.ind)}<span class="ss"><span class="${h.tone}">${esc(h.status)}</span>${h.size ? ' · ' + esc(h.size) : ''}</span></td>`
        + `<td class="nw">${ds(h.since)}<span class="ss">${h.days} days</span></td>`
        + `<td class="num">${h.q.toLocaleString('en-IN')}</td><td class="num">${f2(h.ep)}</td><td class="num">${f2(h.px)}</td>`
        + `<td class="num">${inrf(h.val)}</td><td class="num">${h.w.toFixed(1)}%</td><td class="num ${tone(h.dayp)}">${sg(h.dayp)}%</td>`
        + `<td class="num ${tone(h.pnl)}">${h.pnl > 0 ? '+' : ''}${inrf(h.pnl)}</td><td class="num b ${tone(h.ret)}">${sg(h.ret)}%</td>`
        + `<td class="num ${emaC}">${h.ema == null ? '—' : sg(h.ema) + '%'}</td><td class="num ${hiC}">${h.hi == null ? '—' : sg(h.hi) + '%'}</td>`
        + `<td class="rk"><span class="rk3"><i>${rk(h.r3)}</i><i>${rk(h.r1)}</i><b class="${rC}">${rk(h.rn)}</b></span></td></tr>`; }).join('');
    const F = s.foot;
    const L = s.text;
    const foot = `<tr class="tot"><th scope="row">${esc(L.holdings)}</th><td></td><td></td><td></td><td></td><td></td><td class="num">${inrf(F.val)}</td><td class="num">${F.w.toFixed(1)}%</td>`
      + `<td class="num ${tone(F.day)}">${sg(F.day)}%<span class="ss">${F.dayr > 0 ? '+' : ''}${inrf(F.dayr)}</span></td><td class="num ${tone(F.pnl)}">${F.pnl > 0 ? '+' : ''}${inrf(F.pnl)}<span class="ss">${sg(F.since_fill)}% ${esc(L.before)}</span></td>`
      + `<td></td><td class="num ${F.below_ema ? 'down' : ''}">${F.below_ema} ${esc(L.below)}</td><td class="num ${F.past_high ? 'down' : ''}">${F.past_high} ${esc(L.past_high)}</td><td class="${F.past_rank ? 'down' : ''}">${F.past_rank} ${esc(L.past_rank)}</td></tr>`;
    el.innerHTML = `<table class="ht"><thead><tr>${head}</tr></thead><tbody>${body}</tbody><tfoot>${foot}</tfoot></table>`;
    el.querySelectorAll('thead th').forEach(th => { const go = () => { const k = th.dataset.k; dir = k === key ? -dir : (['s', 'ind', 'rn', 'since'].includes(k) ? 1 : -1); key = k; draw(); };
      th.addEventListener('click', go); th.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } }); });
  };
  draw();
};

/* Every trade and every rebalance line: two views, filters, the rebalance bars (Portfolio, hidden until opened). */
R.history = (card, s) => {
  const vsw = $('.views', card), fsw = $('.filters', card), body = $('.hbody', card), bars = $('.hbars', card);
  let view = 'trades', filt = 'all', pane = null;
  const ds = v => v ? dlong(v) : '—';
  const sets = s.filters;
  vsw.innerHTML = s.views.map(([k, t, a], i) => `<button class="chip" type="button" data-v="${k}" aria-pressed="${i === 0}" aria-label="${esc(a)}">${esc(t)}</button>`).join('');
  const chipsFor = () => { fsw.innerHTML = sets[view].map(([k, t], i) => `<button class="chip" type="button" data-f="${k}" aria-pressed="${k === filt}">${t}</button>`).join(''); };
  const draw = () => {
    bars.hidden = view !== 'lines';
    if (view === 'lines' && !pane) { const el = $('.chart', bars);
      const go = () => { pane = barPane(el, {values: s.rebal.map(r => r[1]), height: 150, yfmt: v => v.toFixed(0), xlab: i => s.rebal[i][0], xn: 12, valueLabels: v => String(v), padR: 30}); };
      REDRAW.push(go); go(); new ResizeObserver(go).observe(el);
      interact(bars, () => [pane], $('.readout', bars), k => ({date: 'Rebalance of ' + s.rebal[k][4], items: [
        {name: 'bought', v: String(s.rebal[k][1]), color: css('--up')}, {name: 'sold', v: String(s.rebal[k][2]), color: css('--down')}, {name: 'kept', v: String(s.rebal[k][3]), color: css('--muted')}]}), () => s.rebal.length - 1); }
    if (view === 'trades') {
      const r = s.trades.filter(x => filt === 'all' || (filt === 'open' ? x[14] === 'Open' : x[14] !== 'Open' && (filt === 'win' ? x[11] > 0 : x[11] <= 0)));
      body.innerHTML = `<table class="lt"><thead><tr><th>Stock</th><th>Signal</th><th>Bought</th><th class="num">Price</th><th class="num">Rank</th><th>Signal</th><th>Sold</th><th class="num">Price</th><th class="num">Return</th><th class="num">Days</th><th>Why it closed</th></tr></thead><tbody>`
        + r.map(x => `<tr><td><b>${esc(x[0])}</b></td><td>${ds(x[2])}</td><td>${ds(x[3])}</td><td class="num">${x[4].toFixed(2)}</td><td class="num">${x[5] == null ? '—' : '#' + x[5]}</td><td>${x[14] === 'Open' ? '—' : ds(x[7])}</td><td>${x[14] === 'Open' ? 'Held' : ds(x[8])}</td><td class="num">${x[9] == null ? '—' : x[9].toFixed(2)}</td><td class="num ${tone(x[11])}">${sg(x[11])}%</td><td class="num">${x[12]}</td><td>${esc(x[13])}</td></tr>`).join('') + '</tbody></table>';
    } else {
      const r = s.lines.filter(x => filt === 'all' || x[1] === filt);
      const A = {BUY: ['Buy', 'up'], SELL: ['Sell', 'down'], HOLD: ['Hold', 'muted']};
      body.innerHTML = `<table class="lt"><thead><tr><th>Month</th><th>Action</th><th>Stock</th><th class="num">Price</th><th class="num">Weight</th><th>Why</th></tr></thead><tbody>`
        + r.map(x => `<tr><td>${esc(x[0])}</td><td class="${A[x[1]][1]}">${A[x[1]][0]}</td><td><b>${esc(x[2])}</b></td><td class="num">${x[3] == null ? '—' : x[3].toFixed(2)}</td><td class="num">${x[4] == null ? '—' : x[4].toFixed(1) + '%'}</td><td>${esc(x[5])}</td></tr>`).join('') + '</tbody></table>';
    }
  };
  vsw.addEventListener('click', e => { const b = e.target.closest('.chip'); if (!b) return; vsw.querySelectorAll('.chip').forEach(c => c.setAttribute('aria-pressed', c === b)); view = b.dataset.v; filt = 'all'; chipsFor(); draw(); });
  fsw.addEventListener('click', e => { const b = e.target.closest('.chip'); if (!b) return; fsw.querySelectorAll('.chip').forEach(c => c.setAttribute('aria-pressed', c === b)); filt = b.dataset.f; draw(); });
  chipsFor(); draw();
};

/* Lines on one axis, values in the heading over the pane (Breadth, 21 Nov 2026). spec: dates, series[{name, values,
   color: token name, dash}], yfmt "num" | "pct" | "pts", levels [{v, label, color}], range [lo, hi], height, chips [[label, sessions]]. */
R.lines = (card, s) => {
  const el = $('.chart', card), head = $('.ph', card);
  const fmt = {num: v => v.toLocaleString('en-IN', {maximumFractionDigits: 0}), pct: v => v.toFixed(0) + '%', pts: v => sg(v, 1)}[s.yfmt || 'num'];
  const show = {num: v => v.toLocaleString('en-IN', {minimumFractionDigits: 1, maximumFractionDigits: 1}), pct: v => v.toFixed(0) + '%', pts: v => sg(v, 1)}[s.yfmt || 'num'];
  head.innerHTML = '<span class="d"></span>' + s.series.map((x, i) => `<span><i class="${x.dash ? 'dash' : ''}" style="color:${css('--' + x.color)}"></i>${esc(x.name)} <b data-v="${i}"></b></span>`).join('');
  let from = 0, pane;
  const draw = () => { const W = el.clientWidth, h = s.height || Math.round(Math.max(200, Math.min(320, W * 0.3)));
    pane = linePane(el, {dates: s.dates.slice(from), series: s.series.map(x => ({name: x.name, color: css('--' + x.color), values: x.values.slice(from), dash: x.dash ? '5 4' : '', width: x.width || 2})),
      height: h, padL: 44, padR: 8, yfmt: fmt, range: s.range, ticks: 4,
      levels: (s.levels || []).map(l => ({v: l.v, label: l.label, color: css('--' + (l.color || 'muted'))})),
      bands: (s.bands || []).map(b => ({from: b.from, to: b.to, fill: css('--' + (b.color || 'up-soft'))}))}); };
  REDRAW.push(draw); draw(); new ResizeObserver(draw).observe(el);
  if (s.chips) { const sw = $('.chips', card);
    sw.innerHTML = s.chips.map(([t, n], i) => `<button class="chip" type="button" data-range="${n}" aria-pressed="${i === s.chips.length - 1}">${esc(t)}</button>`).join('');
    chips(card, r => { from = r ? Math.max(0, s.dates.length - r) : 0; draw(); }); }
  interact(card, () => [pane], (r, i) => { const k = from + (i ?? (s.dates.length - 1 - from));
    $('.d', head).textContent = (i == null ? 'Latest · ' : '') + dlong(s.dates[k]);
    s.series.forEach((x, j) => { const v = x.values[k]; $(`[data-v="${j}"]`, head).textContent = v == null ? '—' : show(v); }); },
    k => ({date: dlong(s.dates[from + k]), items: []}), () => s.dates.length - 1 - from);
};

/* Rows of readings with a line bar (Indices, S170): a name and its note, the bar on one scale for
   every row, then the readings as numbers. spec: head [label...], rows [{name, sub, bar, ago, vals:[...], cls:[...]}],
   lo, hi, step, lines, unit (the bar's), dp. */
R.trows = (card, s) => {
  const nv = s.head.length;
  card.style.setProperty('--nv', nv);
  card.style.setProperty('--tn', Math.round((s.hi - s.lo) / s.step));
  $('.tr-head', card).innerHTML = '<span>' + esc(s.label || '') + '</span><span>' + esc(s.barHead || '') + '</span>' + s.head.map(h => `<span class="num">${esc(h)}</span>`).join('');
  /* A row with `heading` is a group heading (Sectors, 21 Nov 2026: groups as heading rows, not colour alone);
     a row with `ref` is a reference row, ruled off from the rest. */
  const data = s.rows.filter(r => !r.heading);
  $('#rows', card).innerHTML = s.rows.map(r => r.heading ? `<div class="trgrp" role="presentation"><b>${esc(r.heading)}</b>${r.sub ? ` <span>${esc(r.sub)}</span>` : ''}</div>`
    : `<div class="trrow${r.ref ? ' ref' : ''}" role="listitem"><div class="nm"><b>${esc(r.name)}</b>${r.sub ? `<small>${esc(r.sub)}</small>` : ''}</div>`
    + track(r.bar, {lo: s.lo, hi: s.hi, step: s.step, ago: r.ago, lines: s.lines || []})
    + r.vals.map((v, j) => `<span class="num ${(r.cls || [])[j] || ''}">${esc(v)}</span>`).join('') + '</div>').join('');
  rowsInteract(card, '.trrow', j => { const r = data[j ?? 0];
    ro(card, j == null ? s.rest || 'Latest' : r.name, (r.read || []).map(x => ({v: x[0], name: x[1], cls: x[2] || ''}))); });
};

/* A style against its parent: the relative line (100 at launch) and how far it sits below its best,
   two panes, one crosshair, one chip per style (Indices, S170). */
R.rel = (card, s) => {
  const top = $('[data-pane="top"]', card), bot = $('[data-pane="bottom"]', card), sw = $('.chips', card);
  let k = 0, panes = [];
  sw.innerHTML = s.styles.map((x, i) => `<button class="chip" type="button" data-range="${i}" aria-pressed="${i === 0}">${esc(x.style)}</button>`).join('');
  const draw = () => { const x = s.styles[k], W = top.clientWidth, h = Math.round(Math.max(190, Math.min(300, W * 0.3)));
    panes = [linePane(top, {dates: x.dates, series: [{name: x.label, color: css('--ink'), values: x.rel, area: true, width: 1.8}],
               height: h, padL: 44, padR: 8, noX: true, yfmt: v => v.toFixed(0), levels: [{v: 100, label: '', color: css('--muted')}]}),
             linePane(bot, {dates: x.dates, series: [{name: 'Below its best', color: css('--down'), values: x.dd, area: true, width: 1.4}],
               height: Math.round(h * 0.5), padL: 44, padR: 8, yfmt: v => v.toFixed(0) + '%', areaBase: 0, ticks: 3})]; };
  REDRAW.push(draw); draw(); new ResizeObserver(draw).observe(top);
  chips(card, i => { k = i; draw(); });
  interact(card, () => panes, $('.readout', card), i => { const x = s.styles[k]; return {date: dlong(x.dates[i]), items: [
    {name: x.label, color: css('--ink'), v: x.rel[i].toFixed(1)},
    {name: 'below its best', color: css('--down'), v: sg(x.dd[i]) + '%', vcolor: x.dd[i] < 0 ? css('--down') : ''}]}; },
    () => s.styles[k].dates.length - 1);
};

/* A sector and its NSE index over a year, both 100 on the first shared session; one chip per sector
   (Sectors, 21 Nov 2026). spec: pairs [{short, ours_name, index, dates, ours, nse}], start, text {gap, latest, month_end}. */
R.pairs = (card, s) => {
  const el = $('.chart', card), head = $('.ph', card), sw = $('.chips', card), tb = $('.ptab', card), T = s.text || {};
  let k = s.start || 0, pane;
  sw.innerHTML = s.pairs.map((x, i) => `<button class="chip" type="button" data-range="${i}" aria-pressed="${i === k}">${esc(x.short)}</button>`).join('');
  const table = x => { const ends = x.dates.map((d, i) => [d, i]).filter(([d, i]) => i === x.dates.length - 1 || d.slice(0, 7) !== x.dates[i + 1].slice(0, 7));
    tb.innerHTML = `<table class="lt"><thead><tr><th>${esc(T.month_end || 'Month end')}</th><th class="num">${esc(x.ours_name)}</th><th class="num">${esc(x.index)}</th></tr></thead><tbody>`
      + ends.map(([d, i]) => `<tr><td>${dlong(d)}</td><td class="num">${x.ours[i].toFixed(1)}</td><td class="num">${x.nse[i].toFixed(1)}</td></tr>`).join('') + '</tbody></table>'; };
  const draw = () => { const x = s.pairs[k], W = el.clientWidth, h = Math.round(Math.max(200, Math.min(320, W * 0.3)));
    pane = linePane(el, {dates: x.dates, series: [{name: x.ours_name, color: css('--ink'), values: x.ours, area: true, width: 1.8},
      {name: x.index, color: css('--up'), values: x.nse, width: 1.6}], height: h, padL: 44, padR: 8, yfmt: v => v.toFixed(0),
      levels: [{v: 100, label: '', color: css('--muted')}]}); table(x); };
  REDRAW.push(draw); draw(); new ResizeObserver(draw).observe(el);
  sw.addEventListener('click', e => { const b = e.target.closest('.chip'); if (!b) return;
    sw.querySelectorAll('.chip').forEach(c => c.setAttribute('aria-pressed', c === b)); k = +b.dataset.range; draw(); el.dispatchEvent(new Event('blur')); });
  interact(card, () => [pane], (r, i) => { const x = s.pairs[k], j = Math.min(i ?? x.dates.length - 1, x.dates.length - 1);
    head.innerHTML = `<span class="d">${i == null ? esc(T.latest || 'Latest') + ' · ' : ''}${dlong(x.dates[j])}</span>`
      + `<span><i style="color:${css('--ink')}"></i>${esc(x.ours_name)} <b>${x.ours[j].toFixed(1)}</b></span>`
      + `<span><i style="color:${css('--up')}"></i>${esc(x.index)} <b>${x.nse[j].toFixed(1)}</b></span>`
      + `<span>${esc(T.gap || 'gap')} <b class="${x.ours[j] - x.nse[j] < 0 ? 'down' : ''}">${sg(x.ours[j] - x.nse[j])}</b></span>`; },
    () => ({date: '', items: []}), () => s.pairs[k].dates.length - 1);
};

/* The sector leadership map (kept, owner 21 Nov 2026): across, the lead over the 750 over the period; up, the share
   above the EMA; a hollow dot then, a filled dot now. The EMA and period switch inside the frame (no page rerun),
   a picker, values under the pointer, and the worked example for the picked sector, or the first ahead on narrow
   breadth, or the leader. spec: views {"<span>-<months>": rows}, spans, periods, start, short {name: short}, text {...}. */
R.lmap = (card, s) => {
  const el = $('.chart', card), T = s.text, sh = n => (s.short || {})[n] || n;
  const esw = $('.ema', card), psw = $('.per', card), pick = $('.pick', card);
  let span = s.start[0], per = s.start[1], focus = '', hover = null, geo = null;
  esw.innerHTML = s.spans.map(n => `<button class="chip" type="button" data-v="${n}" aria-pressed="${n === span}">${n}${esc(T.ema)}</button>`).join('');
  psw.innerHTML = s.periods.map(n => `<button class="chip" type="button" data-v="${n}" aria-pressed="${n === per}">${n}M</button>`).join('');
  const rows = () => s.views[`${span}-${per}`] || [];
  const pts1 = v => sg(v) + ' ' + T.pts;
  const fillPick = () => { const v = pick.value; pick.innerHTML = `<option value="">${esc(T.all)}</option>` + rows().slice().sort((a, b) => sh(a.name).localeCompare(sh(b.name)))
      .map(r => `<option value="${esc(r.name)}">${esc(sh(r.name))}</option>`).join(''); pick.value = rows().some(r => r.name === v) ? v : ''; focus = pick.value; };
  const ends = () => { const R = rows(); return R.length ? [R.reduce((a, r) => r.x1 > a.x1 ? r : a), R.reduce((a, r) => r.x1 < a.x1 ? r : a)] : [null, null]; };
  const col = r => { const [lead, lag] = ends(); return r === lead ? css('--up') : r === lag ? css('--down') : css('--muted'); };
  const read = () => { const R = rows(), [lead] = ends(); const r = hover || R.find(q => q.name === focus) || lead; if (!r) return;
    $('.readout', card).innerHTML = `<span class="d">${hover ? '' : esc(T.latest) + ' · '}${esc(sh(r.name))} · ${r.stocks} ${esc(T.stocks)}</span>`
      + `<span class="ro"><span>${esc(r.then)}</span><b>${pts1(r.x0)}</b><span>${Math.round(r.y0)}% ${esc(T.above)}</span></span>`
      + `<span class="ro"><span>${esc(r.now)}</span><b class="${tone(r.x1)}">${pts1(r.x1)}</b><span>${Math.round(r.y1)}% ${esc(T.above)}</span></span>`; };
  const example = () => { const R = rows(); if (!R.length) { $('.mex', card).innerHTML = ''; return; }
    const [lead] = ends(), narrow = R.filter(r => r.x1 > 0 && r.y1 < 50);
    const ex = R.find(r => r.name === focus) || narrow[0] || lead, n = ex.stocks, per1 = per === 1 ? T.month : `${per} ${T.months}`;
    const dx = ex.x1 - ex.x0, dy = ex.y1 - ex.y0, flat = Math.abs(dy) < 0.5, side = ex.x1 >= 0 ? T.right_of : T.left_of, half = ex.y1 >= 50 ? T.above_w : T.below_w;
    // "Same share" when breadth did not move (found for the Sectors build, 21 Nov 2026: it read "more of its stocks").
    const reading = flat ? (dx >= 0 ? T.r_flat_up : T.r_flat_down) : dx >= 0 && dy >= 0 ? T.r_ru : dx >= 0 ? T.r_rd : dy >= 0 ? T.r_lu : T.r_ld;
    const lifts = ex.leaders.map(([sym, v]) => `${esc(sym)} ${sg(v)}%, ${T.adds} ${sg(v / n, 2)} ${T.pts}`).join('; ');
    $('.mex', card).innerHTML = `<p class="mh">${esc(T.how)}: ${esc(sh(ex.name))}</p>`
      + `<p><b>${esc(T.q_across.replace('{p}', per1))}</b> ${esc(T.a_across.replace('{n}', n).replace('{name}', sh(ex.name)).replace('{then}', ex.then).replace('{now}', ex.now))} <b>${sg(ex.ret, 2)}%</b>. ${esc(T.a_market)} <b>${sg(ex.bench, 2)}%</b>. ${esc(T.a_diff)} <b>${pts1(ex.x1)}</b>, ${esc(side)}. ${esc(T.a_hollow)} ${pts1(ex.x0)}.</p>`
      + `<p><b>${esc(T.q_up)}</b> ${esc(T.a_up.replace('{span}', span))} ${ex.a1} / ${ex.o1} = <b>${Math.round(ex.y1)}%</b>; ${esc(T.ago_word)} ${ex.a0} / ${ex.o0} = ${Math.round(ex.y0)}%. ${esc(T.a_up2.replace('{need}', Math.round(span * 0.8)))}</p>`
      + `<p><b>${esc(T.q_lift)}</b> ${esc(T.a_lift.replace('{n}', n))} ${lifts}.</p>`
      + `<p><b>${esc(T.q_line)}</b> ${esc(T.a_line)} ${Math.abs(dx).toFixed(1)} ${T.pts} ${dx >= 0 ? T.right : T.left}, ${flat ? T.no_move : Math.abs(dy).toFixed(0) + ' ' + T.pts + ' ' + (dy >= 0 ? T.up : T.down)}: ${esc(reading)} ${esc(T.today.replace('{side}', side).replace('{half}', half))} ${esc(T.four)}</p>`;
    const fell = R.filter(r => Math.round(r.y1) < Math.round(r.y0)).length;
    $('.mcap', card).textContent = `${R[0].then} → ${R[0].now}: ${T.fell.replace('{n}', fell).replace('{of}', R.length)}`
      + (narrow.length ? ` ${T.narrow.replace('{span}', span)} ${narrow.map(r => sh(r.name)).join(', ')}.` : '');
    $('.mtab', card).innerHTML = `<table class="lt"><thead><tr><th>${esc(T.sector)}</th><th class="num">${esc(T.lead)} ${esc(R[0].then)}</th><th class="num">${esc(T.lead)} ${esc(R[0].now)}</th><th class="num">${esc(T.share)} ${esc(R[0].then)}</th><th class="num">${esc(T.share)} ${esc(R[0].now)}</th></tr></thead><tbody>`
      + R.slice().sort((a, b) => b.x1 - a.x1).map(r => `<tr><td>${esc(sh(r.name))}</td><td class="num">${sg(r.x0)}</td><td class="num ${tone(r.x1)}">${sg(r.x1)}</td><td class="num">${Math.round(r.y0)}%</td><td class="num">${Math.round(r.y1)}%</td></tr>`).join('') + '</tbody></table>'; };
  const draw = () => { const R = rows(), W = Math.max(280, el.clientWidth), phone = W < 560, H = Math.min(520, Math.max(300, Math.round(W * (phone ? 0.95 : 0.5))));
    const L = 40, Rp = phone ? 8 : 16, Tp = 12, B = 30;
    el.querySelector('svg')?.remove(); const svg = mk('svg', {viewBox: `0 0 ${W} ${H}`, height: H, 'aria-hidden': 'true'}); el.prepend(svg);
    if (!R.length) return;
    const lim = Math.ceil(Math.max(2, ...R.flatMap(r => [Math.abs(r.x0), Math.abs(r.x1)])) / 2) * 2 + 1;
    const X = v => L + (W - L - Rp) * (v + lim) / (2 * lim), Y = v => Tp + (H - Tp - B) * (100 - v) / 100;
    for (let v = 0; v <= 100; v += 25) { mk('line', {x1: L, x2: W - Rp, y1: Y(v), y2: Y(v), stroke: css(v === 50 ? '--rule' : '--rule-soft'), 'stroke-width': v === 50 ? 1.2 : 1}, svg);
      mk('text', {x: L - 6, y: Y(v) + 4, 'text-anchor': 'end'}, svg).textContent = v + '%'; }
    const st = lim > 12 ? 5 : lim > 6 ? 4 : 2;
    for (let v = -Math.floor(lim / st) * st; v <= lim; v += st) { mk('line', {x1: X(v), x2: X(v), y1: Tp, y2: H - B, stroke: v === 0 ? css('--ink') : css('--rule-soft'), 'stroke-width': v === 0 ? 1.2 : 1, opacity: v === 0 ? .6 : 1}, svg);
      mk('text', {x: X(v), y: H - B + 14, 'text-anchor': 'middle'}, svg).textContent = v === 0 ? '0' : sg(v, 0); }
    mk('text', {x: W - Rp, y: H - 2, 'text-anchor': 'end'}, svg).textContent = T.x_axis;
    mk('text', {x: L + 4, y: Tp + 10}, svg).textContent = T.y_axis.replace('{span}', span);
    const [lead, lag] = ends(), on = r => !focus || r.name === focus;
    const order = R.slice().sort((a, b) => (a === lead || a === lag || a.name === focus) - (b === lead || b === lag || b.name === focus));
    for (const r of order) { const c = col(r), g = mk('g', {opacity: on(r) ? 1 : .22}, svg);
      mk('line', {x1: X(r.x0), y1: Y(r.y0), x2: X(r.x1), y2: Y(r.y1), stroke: c, 'stroke-width': 1.4}, g);
      mk('circle', {cx: X(r.x0), cy: Y(r.y0), r: 3.5, fill: css('--bg'), stroke: c, 'stroke-width': 1.4}, g);
      mk('circle', {cx: X(r.x1), cy: Y(r.y1), r: 4.5, fill: c}, g); }
    // Labels beside the filled dot, reading leftward near the right edge, nudged apart; on a phone only the leader,
    // the laggard, the picked and the touched sector are named (PAGE_DESIGN 8: labels that do not fit are named on tap).
    const placed = [];
    for (const r of R.filter(r => on(r) && (!phone || r === lead || r === lag || r.name === focus || (hover && hover.name === r.name))).sort((a, b) => Y(a.y1) - Y(b.y1))) {
      const left = X(r.x1) > W - 110, tx = X(r.x1) + (left ? -8 : 8); let ty = Y(r.y1) + 4;
      for (const q of placed) if (Math.abs(q.ty - ty) < 13 && Math.abs(q.tx - tx) < 110) ty = q.ty + 13;
      placed.push({tx, ty});
      const t = mk('text', {x: tx, y: ty, 'text-anchor': left ? 'end' : 'start', class: 'lbl-end'}, svg); t.textContent = sh(r.name);
      t.setAttribute('style', `fill:${r === lead || r === lag ? col(r) : css('--text2')}`); }
    if (hover) mk('circle', {cx: X(hover.x1), cy: Y(hover.y1), r: 8, fill: 'none', stroke: css('--ink'), 'stroke-width': 1.2}, svg);
    geo = {X, Y, W}; read(); };
  const near = e => { if (!geo) return; const b = el.getBoundingClientRect(), k = geo.W / b.width, px = (e.clientX - b.left) * k, py = (e.clientY - b.top) * k;
    let best = null, d = 1e12; for (const r of rows()) { const dd = (geo.X(r.x1) - px) ** 2 + (geo.Y(r.y1) - py) ** 2; if (dd < d) { d = dd; best = r; } }
    hover = best; draw(); };
  el.addEventListener('pointermove', near); el.addEventListener('pointerdown', near);
  el.addEventListener('pointerleave', e => { if (e.pointerType !== 'touch') { hover = null; draw(); } });
  el.addEventListener('keydown', e => { if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return; e.preventDefault();
    const srt = rows().slice().sort((a, b) => a.x1 - b.x1), i = srt.indexOf(hover || ends()[0]);
    hover = srt[Math.max(0, Math.min(srt.length - 1, i + (e.key === 'ArrowLeft' ? -1 : 1)))]; draw(); });
  const sw = (box, set) => box.addEventListener('click', e => { const b = e.target.closest('.chip'); if (!b) return;
    box.querySelectorAll('.chip').forEach(c => c.setAttribute('aria-pressed', c === b)); set(+b.dataset.v); hover = null; fillPick(); draw(); example(); });
  sw(esw, v => { span = v; }); sw(psw, v => { per = v; });
  pick.addEventListener('change', () => { focus = pick.value; hover = null; draw(); example(); });
  fillPick(); REDRAW.push(draw); draw(); example(); new ResizeObserver(draw).observe(el);
};

/* A sortable table with a line-bar column (Sectors' "Inside each sector", 21 Nov 2026). spec: cols [{k, label, num,
   bar}], rows [{name, sub, ref, v: {k: value}, t: {k: text}, c: {k: class}}], sort, bar {lo, hi, step, lines, ago}.
   The reference row stays first; a heading sorts on a click, Enter or Space. */
R.stable = (card, s) => {
  const el = $('.stab', card), B = s.bar || {};
  let key = s.sort, dir = -1;
  const draw = () => {
    const ref = s.rows.filter(r => r.ref), rest = s.rows.filter(r => !r.ref).sort((a, b) => {
      const va = key === 'name' ? a.name : a.v[key], vb = key === 'name' ? b.name : b.v[key];
      if (va == null) return 1; if (vb == null) return -1;
      return (typeof va === 'string' ? va.localeCompare(vb) : va - vb) * dir; });
    const head = s.cols.map(c => `<th scope="col" data-k="${c.k}" tabindex="0" class="${c.num ? 'num' : ''}" aria-sort="${c.k === key ? (dir < 0 ? 'descending' : 'ascending') : 'none'}">${esc(c.label)}</th>`).join('');
    const cell = (r, c) => { if (c.k === 'name') return `<th scope="row">${esc(r.name)}${r.sub ? `<span class="ss">${esc(r.sub)}</span>` : ''}</th>`;
      const t = (r.t || {})[c.k] ?? (r.v[c.k] == null ? '—' : String(r.v[c.k])), cls = (r.c || {})[c.k] || '';
      if (c.bar) return `<td class="bar"><div class="bw">${track(r.v[c.k], {lo: B.lo, hi: B.hi, step: B.step, lines: B.lines || [], ago: r.v[B.ago]})}<span class="num ${cls}">${esc(t)}</span></div></td>`;
      return `<td class="${c.num ? 'num ' : ''}${cls}">${esc(t)}</td>`; };
    const row = r => `<tr${r.ref ? ' class="ref"' : ''}>${s.cols.map(c => cell(r, c)).join('')}</tr>`;
    el.innerHTML = `<table class="ht st"><thead><tr>${head}</tr></thead><tbody>${ref.map(row).join('')}${rest.map(row).join('')}</tbody></table>`;
    el.querySelectorAll('thead th').forEach(th => { const go = () => { const k = th.dataset.k; dir = k === key ? -dir : (k === 'name' ? 1 : -1); key = k; draw(); };
      th.addEventListener('click', go); th.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } }); });
  };
  draw();
};

window.DashCharts = {render(kind, spec) { R[kind](document.getElementById('c'), spec); }};

})();
