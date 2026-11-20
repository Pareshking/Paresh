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
  const n=o.values.length, fx=o.valueLabels?1.22:1.08, lo=Math.min(0,...o.values)*fx, hi=Math.max(0,...o.values)*fx;
  const Y=v=>padT+(H-padT-padB)*(1-(v-lo)/(hi-lo)), bw=(W-padL-padR)/n, gap=Math.min(6,bw*.28);
  for(const t of niceTicks(lo,hi,4)){ mk('line',{x1:padL,x2:W-padR,y1:Y(t),y2:Y(t),stroke:t===0?css('--ink'):css('--rule-soft'),'stroke-width':1,opacity:t===0?.5:1},svg);
    mk('text',{x:W-padR+8,y:Y(t)+4},svg).textContent=String(o.yfmt(t)).replace('-','−'); }
  for(const l of o.levels||[]){ mk('line',{x1:padL,x2:W-padR,y1:Y(l.v),y2:Y(l.v),stroke:l.color,'stroke-dasharray':'3 4'},svg);
    if(l.label){ const t=mk('text',{x:padL+2,y:Y(l.v)+(l.below?13:-5)},svg); t.textContent=l.label; t.setAttribute('style',`fill:${l.color}`); } }
  const r=Math.min(3,bw/4), bars=[];
  o.values.forEach((v,i)=>{ const x=padL+i*bw+gap/2, w=Math.max(1,bw-gap), y0=Y(0), y1=Y(v), h=Math.abs(y1-y0);
    const up=v>=0, top=up?y1:y0, rr=Math.min(r,h/2);
    const d=up?`M${x},${y0}V${top+rr}Q${x},${top} ${x+rr},${top}H${x+w-rr}Q${x+w},${top} ${x+w},${top+rr}V${y0}Z`
              :`M${x},${y0}V${y1-rr}Q${x},${y1} ${x+rr},${y1}H${x+w-rr}Q${x+w},${y1} ${x+w},${y1-rr}V${y0}Z`;
    const last=i===n-1 && o.markLast;
    bars.push(mk('path',{d,fill:up?css('--up'):css('--down'),opacity:last||!o.markLast?1:.72},svg)); });
  const step=Math.max(1,Math.ceil(n/Math.min(o.xn||6,Math.max(2,Math.floor((W-padL-padR)/78)))));
  for(let i=0;i<n;i+=step){ const t=mk('text',{x:padL+i*bw+bw/2,y:H-6,'text-anchor':'middle'},svg); t.textContent=o.xlab(i); }
  if(o.valueLabels){ o.values.forEach((v,i)=>{ const t=mk('text',{x:padL+i*bw+bw/2,y:v>=0?Y(v)-5:Y(v)+13,'text-anchor':'middle',class:'lbl-v'},svg); t.textContent=o.valueLabels(v); t.setAttribute('style',`fill:${v>=0?css('--up'):css('--down')}`); }); }
  if(o.markLast){ const i=n-1,v=o.values[i]; const t=mk('text',{x:padL+i*bw+bw/2,y:v>=0?Y(v)-5:Y(v)+13,'text-anchor':'end',class:'lbl-end'},svg); t.textContent=o.lastLabel; t.setAttribute('style',`fill:${v>=0?css('--up'):css('--down')}`); }
  return { n, W, X:i=>padL+i*bw+bw/2, show(i){ bars.forEach((b,k)=>b.style.opacity = i==null ? '' : (k===i?1:.3)); },
    index(px){ return Math.max(0,Math.min(n-1,Math.floor((px-padL)/bw))); } };
}

/* Pointer, touch and keyboard: one handler for every chart. On touch the tooltip is replaced by the readout above. */
function interact(card, panes, readout, rows, restIndex){
  const charts=[...card.querySelectorAll('.chart')], tip=document.createElement('div'); tip.className='tip'; charts[0].appendChild(tip);
  let cur=null;
  const render=(i,touch)=>{ cur=i; panes().forEach(p=>p.show(i)); const k=i??restIndex(); const r=rows(k);
    if(typeof readout==='function') readout(r,i); else
    readout.innerHTML=`<span class="d">${i==null?'Latest · ':''}${r.date}</span>`+r.items.map(x=>`<span class="ro"><i style="background:${x.color}"></i><b style="color:${x.vcolor||'inherit'}">${x.v}</b><span>${x.name}</span></span>`).join('');
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
  render(null);
}

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
  const draw = () => { pane = barPane(el, {values: s.values, height: s.height || 220, yfmt: v => sg(v / (s.axisDiv || 1), 0).replace('+', ''), xlab: i => s.labels[i], xn: s.xn || 6,
    markLast: !!s.lastLabel, lastLabel: s.lastLabel, padR: 38, valueLabels: s.valueLabels ? v => sg(v / (s.axisDiv || 1), s.vdp ?? 0) : null,
    levels: (s.levels || []).map(l => ({v: l, color: css('--up')}))}); };
  REDRAW.push(draw); draw(); new ResizeObserver(draw).observe(el);
  interact(card, () => [pane], $('.readout', card), k => { const v = s.values[k], c = v >= 0 ? css('--up') : css('--down');
    const lvl = s.levels && s.levels.length ? ' · ' + (v >= s.levels[0] ? s.above : v < 0 ? s.belowZero : s.between) : '';
    const items = [{name: s.unit + lvl, color: c, v: s.money ? inr(v) : sg(v, s.dp ?? 1), vcolor: c}];
    const a = s.also && s.also[k]; if (a) items.push({name: a[0], color: css('--caution'), v: inr(a[1]), vcolor: a[1] >= 0 ? css('--up') : css('--down')});
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
  const bar = $('.segbar', card), Q = {Leading: 'up', Improving: 'up', Weakening: 'watch', Lagging: 'down'}, G = {strong: 'Strong', turning: 'Turning', weak: 'Weak'};
  bar.innerHTML = s.segs.map(([n, h, w, , , , g], i) => `<i role="listitem" class="seg-${g}${i % 2 ? ' alt' : ''}" style="flex:${w} 1 0" data-i="${i}" tabindex="0" aria-label="${esc(n)} ${w}%"><span>${esc(n)} ${Math.round(w)}%</span></i>`).join('');
  const show = i => { bar.querySelectorAll('i').forEach(t => t.classList.toggle('dim', i != null && +t.dataset.i !== i));
    const [n, h, w, r6, r1, q, g] = s.segs[i ?? 0];
    ro(card, i == null ? 'Latest · the largest' : G[g], [{v: w.toFixed(1) + '%', name: `${n}, ${h} holding${h > 1 ? 's' : ''}`}, {v: sg(r6) + ' · ' + sg(r1), cls: tone(r1), name: '6M · 1M'}, {v: q, cls: Q[q] || '', name: 'on the RRG'}]); };
  bar.querySelectorAll('i').forEach(t => { const i = +t.dataset.i; t.addEventListener('pointerenter', () => show(i)); t.addEventListener('pointerdown', () => show(i)); t.addEventListener('focus', () => show(i)); });
  bar.addEventListener('pointerleave', e => { if (e.pointerType !== 'touch') show(null); });
  const fit = () => bar.querySelectorAll('i').forEach(t => { const sp = t.querySelector('span'); sp.style.visibility = ''; if (sp.offsetWidth > t.clientWidth - 10) sp.style.visibility = 'hidden'; });
  if (s.totals) $('.seg-key', card).innerHTML = [['strong', 'Strong', 'ahead of the market on both windows'], ['turning', 'Turning', 'ahead on one'], ['weak', 'Weak', 'behind on both']]
    .filter(([k]) => s.totals[k] != null).map(([k, t, d]) => `<span><i class="seg-${k}"></i><b>${s.totals[k].toFixed(1)}%</b> ${t}, ${d}</span>`).join('');
  show(null); fit(); new ResizeObserver(fit).observe(bar);
};

/* Relative rotation: every industry, the book's holdings filled and sized. */
R.rrg = (card, s) => {
  const P = [...s.points].sort((a, b) => b[3] - a[3]), el = $('.chart', card);
  const quad = (r, m) => r >= 100 ? (m >= 100 ? 'Leading' : 'Weakening') : (m >= 100 ? 'Improving' : 'Lagging');
  const xs = P.map(p => p[1]), ys = P.map(p => p[2]);
  const xlo = Math.min(97, ...xs) - 2, xhi = Math.max(103, ...xs) + 2, ylo = Math.min(97, ...ys) - 2.5, yhi = Math.max(103, ...ys) + 2;
  let sel = null;
  const short = n => n.replace('Automobile and Auto Components', 'Auto').replace('Media Entertainment & Publication', 'Media').replace('Fast Moving Consumer Goods', 'FMCG').replace('Oil Gas & Consumable Fuels', 'Oil & Gas').replace('Information Technology', 'IT').replace('Consumer ', 'Cons. ');
  const draw = () => { const W = Math.max(300, el.clientWidth), H = Math.round(W / 1.45), pad = 30;
    el.querySelector('svg')?.remove(); const svg = mk('svg', {viewBox: `0 0 ${W} ${H}`, height: H, 'aria-hidden': 'true'}); el.prepend(svg);
    const X = v => pad + (W - 2 * pad) * (v - xlo) / (xhi - xlo), Y = v => pad + (H - 2 * pad) * (1 - (v - ylo) / (yhi - ylo));
    [[100, xhi, 100, yhi, css('--up-soft')], [100, xhi, ylo, 100, css('--caution-soft')], [xlo, 100, ylo, 100, css('--down-soft')]]
      .forEach(([a, b, c, d, f]) => mk('rect', {x: X(a), y: Y(d), width: X(b) - X(a), height: Y(c) - Y(d), fill: f}, svg));
    mk('line', {x1: X(100), x2: X(100), y1: pad, y2: H - pad, stroke: css('--muted'), 'stroke-width': 1}, svg);
    mk('line', {x1: pad, x2: W - pad, y1: Y(100), y2: Y(100), stroke: css('--muted'), 'stroke-width': 1}, svg);
    [['Leading', X(xhi) - 6, pad + 14, 'end', '--up'], ['Improving', X(xlo) + 6, pad + 14, 'start', '--muted'], ['Weakening', X(xhi) - 6, H - pad - 8, 'end', '--caution'], ['Lagging', X(xlo) + 6, H - pad - 8, 'start', '--down']]
      .forEach(([t, x, y, a, c]) => { const e = mk('text', {x, y, 'text-anchor': a, class: 'lbl-end'}, svg); e.textContent = t; e.setAttribute('style', `fill:${css(c)}`); });
    niceTicks(xlo, xhi, 6).forEach(t => { const e = mk('text', {x: X(t), y: H - 8, 'text-anchor': 'middle'}, svg); e.textContent = t; });
    niceTicks(ylo, yhi, 4).forEach(t => { const e = mk('text', {x: 4, y: Y(t) + 4}, svg); e.textContent = t; });
    const placed = [];
    P.forEach((p, i) => { const cx = X(p[1]), cy = Y(p[2]), held = p[3] > 0, on = sel === i;
      mk('circle', {cx, cy, r: held ? 5 + Math.min(p[3], 6) : 4.5, fill: held ? css('--caution') : css('--bg'), stroke: held ? css('--bg') : css('--muted'), 'stroke-width': 1.5, opacity: sel == null || on ? 1 : .35}, svg);
      const clash = placed.some(([x, y]) => Math.abs(x - cx) < 90 && Math.abs(y - cy) < 14);
      if (on || (sel == null && !clash && (held || p[1] === Math.max(...xs) || p[1] === Math.min(...xs)))) { placed.push([cx, cy]);
        const e = mk('text', {x: cx + 9, y: cy + 4, class: 'lbl-end'}, svg); e.textContent = short(p[0]); e.setAttribute('style', `fill:${css('--ink')};font-weight:${on ? 700 : 500}`);
        if (cx > W - 120) { e.setAttribute('x', cx - 9); e.setAttribute('text-anchor', 'end'); } } });
    el._m = {X, Y, W, H}; };
  REDRAW.push(draw); draw(); new ResizeObserver(draw).observe(el);
  const Qc = {Leading: 'up', Improving: 'up', Weakening: 'watch', Lagging: 'down'};
  const read = i => { if (i == null) { ro(card, 'Tap a dot', [{v: s.heldLeaders, name: 'leaders held by the book'}]); return; }
    const p = P[i], q = quad(p[1], p[2]); ro(card, p[0], [{v: p[1].toFixed(1), name: 'RS ratio'}, {v: p[2].toFixed(1), name: 'RS momentum'}, {v: q, cls: Qc[q], name: `was ${p[4]}`}, {v: p[3] || '—', name: 'held'}]); };
  const pick = e => { const b = el.getBoundingClientRect(), m = el._m, sx = (e.clientX - b.left) / b.width * m.W, sy = (e.clientY - b.top) / b.height * m.H;
    let best = null, bd = 1e9; P.forEach((p, i) => { const d = Math.hypot(m.X(p[1]) - sx, m.Y(p[2]) - sy); if (d < bd) { bd = d; best = i; } });
    sel = bd < 40 ? best : null; draw(); read(sel); };
  el.addEventListener('pointermove', pick); el.addEventListener('pointerdown', pick);
  el.addEventListener('pointerleave', e => { if (e.pointerType === 'touch') return; sel = null; draw(); read(null); });
  el.addEventListener('keydown', e => { if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); sel = ((sel ?? -1) + (e.key === 'ArrowRight' ? 1 : P.length - 1)) % P.length; draw(); read(sel); } });
  read(null);
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

window.DashCharts = {render(kind, spec) { R[kind](document.getElementById('c'), spec); }};

})();
