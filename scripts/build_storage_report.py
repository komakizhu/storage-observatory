#!/usr/bin/env python3
"""Build the Lieflat-style, read-only storage report."""

from __future__ import annotations

import json
from pathlib import Path
import sys


TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>存储快照</title>
<style>
:root{--paper:#F0F0EE;--ink:#1F1E1C;--muted:#8F8E86;--faint:#C0BFB7;--grid:rgba(31,30,28,.16);--soft:#DBDAD3;--safe:#43593B;--bad:#F5572F}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--paper);color:var(--ink);font-family:Inter,-apple-system,BlinkMacSystemFont,"SF Pro SC","PingFang SC",sans-serif;
  -webkit-font-smoothing:antialiased;line-height:1.55;padding:48px 28px 90px}
.page{max-width:1320px;margin:auto}
.masthead{margin-bottom:42px;padding:0 4px}
.eyebrow,.source,.tag{font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.masthead h1{font-size:42px;line-height:1.08;letter-spacing:-.055em;font-weight:800}
.masthead p{max-width:720px;color:var(--muted);font-size:13px;margin-top:10px}
.hero{display:grid;grid-template-columns:1.35fr .65fr;gap:34px;margin-bottom:48px}
.hero-main,.hero-side{padding:25px 0;border-top:1px solid var(--ink);border-bottom:1px solid var(--grid)}
.hero-label{font-size:18px;color:var(--ink);font-weight:700;letter-spacing:-.02em}
.hero-number{font-size:82px;font-weight:800;letter-spacing:-.075em;line-height:.98;margin-top:8px;color:var(--safe)}
.hero-number small{font-size:22px;letter-spacing:-.02em;margin-left:5px}
.hero-meta{font-size:12px;color:var(--muted);margin-top:10px}
.hero-side{display:flex;flex-direction:column;justify-content:center}
.hero-side strong{font-size:29px;letter-spacing:-.045em}
.good{color:var(--safe)}.bad{color:var(--bad)}
.hero-side p{font-size:12px;color:var(--muted);margin-top:6px}
.hero-side .rule{height:1px;background:var(--grid);margin:14px 0}
.chart-grid{display:grid;grid-template-columns:1fr 1fr;gap:34px;margin-bottom:48px}
.card{padding:34px 34px 28px;background:rgba(255,255,255,.18);border-radius:24px}
.card.wide{grid-column:1/-1}
.card.square{aspect-ratio:1/1;display:flex;flex-direction:column}
.card.square>svg{flex:1;height:auto;min-height:0}
.card h2{font-size:21px;line-height:1.2;letter-spacing:-.03em;font-weight:700;margin:8px 0 12px}
.sub{font-size:11.5px;color:var(--muted);margin-bottom:12px}
.src{font-size:9.5px;color:var(--faint);letter-spacing:.1em;font-weight:600;margin-top:8px}
svg{width:100%;display:block;overflow:visible}
.chart-wide{height:380px}.chart-square{height:390px}.chart-history{height:390px}.chart-lens{height:390px}
svg text{font-family:Inter,-apple-system,BlinkMacSystemFont,"SF Pro SC","PingFang SC",sans-serif}
.rule-line{stroke:var(--grid);stroke-width:1}
.hair{stroke:var(--ink);stroke-width:.8;fill:none}
.hair-muted{stroke:var(--faint);stroke-width:.8;fill:none}
.ink{stroke:var(--ink);fill:var(--ink)}.muted{stroke:var(--muted);fill:var(--muted)}
.dash{stroke-dasharray:2.5 3}
.reveal{animation:rise var(--reveal-duration,2.1s) var(--reveal-ease,cubic-bezier(.2,.7,.3,1)) both;animation-play-state:paused}
.reveal.motion-loaded{animation-play-state:running}
.delay-1{animation-delay:.24s}.delay-2{animation-delay:.48s}.delay-3{animation-delay:.72s}
.lens-card .reveal{animation-duration:var(--reveal-duration,6.3s)}
.gauge-tick-path{fill:none;stroke-linecap:butt;stroke-linejoin:round}
.gauge-tick.reveal{animation-name:gauge-fade;animation-duration:.9s;animation-timing-function:ease;transform:none}
@keyframes gauge-fade{from{opacity:0}to{opacity:1}}
@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;animation-delay:0!important;scroll-behavior:auto!important}}
.section{margin:34px 0}.section-head{display:flex;align-items:baseline;justify-content:space-between;border-bottom:1px solid var(--ink);padding-bottom:9px;margin-bottom:12px}
.section h2{font-size:18px;letter-spacing:-.025em}.section-head .source{font-size:9px}
.scope-visual{border-top:1px solid var(--grid);border-bottom:1px solid var(--grid);padding:16px 0 12px;margin:12px 0 14px}.scope-row{display:grid;grid-template-columns:128px 1fr 76px;align-items:center;gap:12px;margin:12px 0}.scope-name{font-size:11px;font-weight:700}.scope-path{display:block;color:var(--muted);font:9px ui-monospace,SFMono-Regular,Menlo,monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:2px}.scope-track{height:16px;background:rgba(31,30,28,.08);border-radius:999px;overflow:hidden}.scope-fill{height:100%;border-radius:999px;background:var(--ink);min-width:7px}.scope-row.other .scope-fill{background:var(--muted)}.scope-row.shared .scope-fill{background:var(--faint)}.scope-row.free .scope-fill{background:var(--safe)}.scope-value{text-align:right;font-size:11px;font-variant-numeric:tabular-nums;font-weight:700}.scope-legend{display:flex;justify-content:space-between;color:var(--muted);font-size:10px;margin-top:10px}.scope-legend b{color:var(--ink)}.scope-note{color:var(--muted);font-size:11px;margin-top:8px}
.scope-fill.reveal{animation-name:scope-grow;animation-duration:var(--scope-duration,2.1s);animation-timing-function:cubic-bezier(.16,1,.3,1);transform-origin:left center}
@keyframes scope-grow{from{opacity:0;transform:scaleX(0)}to{opacity:1;transform:scaleX(1)}}
.diverge-bar.reveal{animation-name:diverge-grow;animation-duration:var(--diverge-duration,2.1s);animation-timing-function:cubic-bezier(.16,1,.3,1);transform-box:fill-box;transform-origin:var(--diverge-origin,left center)}
.diverge-bar.negative{--diverge-origin:right center}
@keyframes diverge-grow{from{opacity:0;transform:scaleX(0)}to{opacity:1;transform:scaleX(1)}}
.history-segment.reveal{animation-name:history-draw;animation-duration:var(--history-segment-duration,.84s);animation-timing-function:cubic-bezier(.22,.82,.35,1);stroke-dasharray:1;stroke-dashoffset:1}
.history-node.reveal{animation-name:history-node-in;animation-duration:.12s;animation-timing-function:ease-out;transform:none}
@keyframes history-draw{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}
@keyframes history-node-in{from{opacity:0}to{opacity:1}}
.table-wrap{overflow-x:auto}.table{width:100%;border-collapse:collapse;min-width:760px}
.table th,.table td{padding:11px 10px;border-bottom:1px solid var(--grid);text-align:left;font-size:12px;vertical-align:top}
.table th{font-size:9px;letter-spacing:.1em;color:var(--muted);text-transform:uppercase}.table-action{text-align:right!important;white-space:nowrap}
.table td.num{font-variant-numeric:tabular-nums;font-weight:700;white-space:nowrap}.path{font:11px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted);word-break:break-all}
.insight{font-size:14px;max-width:850px;margin-bottom:13px}.list{padding-left:20px;color:var(--muted);font-size:13px}.list li{margin:5px 0}
.tier{margin:24px 0}.tier-head{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;border-bottom:1px solid var(--grid);padding-bottom:9px;margin-bottom:9px}.tier-head h3{font-size:15px;margin:0}.tier-intro{color:var(--muted);font-size:12px;line-height:1.5;margin:5px 0 0;max-width:780px}.tier-head-meta{display:flex;flex-direction:column;align-items:flex-end;gap:8px}.tier-total{font-size:13px;font-weight:700;color:var(--ink);white-space:nowrap}.tier-actions{display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-end}.tier-actions .action-btn{white-space:nowrap}.tier-actions .action-note{white-space:nowrap}.item{border-bottom:1px solid var(--grid);padding:13px 0}.item summary{cursor:pointer;list-style:none;display:flex;gap:10px;align-items:baseline}.item summary::-webkit-details-marker{display:none}
.item{border-bottom:1px solid var(--grid);padding:13px 0}.item summary{cursor:pointer;list-style:none;display:flex;gap:10px;align-items:baseline}.item summary::-webkit-details-marker{display:none}
.item summary:before{content:"＋";font-size:14px;color:var(--muted);width:16px}.item[open] summary:before{content:"−"}
.item-name{font-weight:700;flex:1;min-width:180px}.item-explainer{display:block;color:var(--muted);font-size:11px;font-weight:400;line-height:1.45;margin-top:3px;max-width:900px}.item-meter{display:flex;justify-content:flex-end;flex:0 0 260px;width:260px;min-width:260px;height:9px;background:transparent;border-radius:999px;overflow:hidden;align-self:center}.item-meter-fill{display:block;height:100%;min-width:3px;border-radius:999px;background:#8F8E86}.item-size{flex:0 0 88px;text-align:right;font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap}
.item-body{padding:12px 0 0 26px;color:var(--muted);font-size:13px}.item-body p{margin:7px 0}.label{font-size:10px;color:var(--faint);font-weight:700;letter-spacing:.1em;text-transform:uppercase;margin-top:12px}
.code{position:relative;background:var(--ink);color:var(--paper);padding:13px 48px 13px 13px;border-radius:10px;font:11px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace;overflow:auto;margin-top:6px;white-space:pre-wrap;word-break:break-word}
.copy{position:absolute;right:8px;top:8px;border:0;border-radius:7px;background:var(--paper);color:var(--ink);padding:4px 8px;font-size:10px;cursor:pointer}
.action-row{display:flex;gap:7px;flex-wrap:wrap;margin:12px 0 5px}.action-btn{border:1px solid var(--faint);background:transparent;color:var(--ink);border-radius:999px;padding:6px 10px;font-size:11px;cursor:pointer}.action-btn:hover,.action-btn.danger{border-color:var(--ink);color:var(--ink)}.action-btn:disabled{opacity:.45;cursor:not-allowed}.action-btn:disabled:hover{border-color:var(--faint);color:var(--ink)}.action-note{font-size:11px;color:var(--muted);padding:7px 0}
.note{color:var(--muted);font-size:12px}.denied{border-top:1px solid var(--ink);padding-top:13px;color:var(--muted);font-size:12px;word-break:break-all}
.permission-panel{border-top:1px solid var(--ink);border-bottom:1px solid var(--grid);padding:18px 0;margin:28px 0}.permission-panel h2{font-size:18px;margin:0 0 7px}.permission-summary{font-size:13px;font-weight:700}.permission-panel ol{padding-left:22px;margin:12px 0;color:var(--ink);font-size:12px}.permission-panel li{margin:6px 0}.permission-note{color:var(--muted);font-size:12px;max-width:920px}.permission-paths{margin-top:12px;color:var(--muted);font-size:11px}.permission-paths summary{cursor:pointer;font-weight:700;color:var(--ink)}.permission-paths code{display:block;margin-top:6px;font:10px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;word-break:break-all}
.footer{margin-top:46px;padding-top:12px;border-top:1px solid var(--grid);color:var(--faint);font-size:10px;letter-spacing:.08em;text-transform:uppercase}
.deferred-sentinel{height:1px;width:100%;pointer-events:none}
@media(max-width:760px){body{padding:30px 16px 60px}.masthead h1{font-size:31px}.hero{grid-template-columns:1fr;gap:0}.hero-side{border-top:0}.chart-grid{grid-template-columns:1fr}.card.wide{grid-column:auto}.hero-number{font-size:64px}.scope-row{grid-template-columns:96px 1fr 60px;gap:7px}.scope-path{font-size:8px}.tier-head{display:block}.tier-head-meta{align-items:flex-start;margin-top:10px}.tier-actions{justify-content:flex-start}.item summary{flex-wrap:wrap}.item-name{min-width:140px}.item-meter{flex:1 1 150px;min-width:130px}.item-size{flex:0 0 76px}}
@media(prefers-color-scheme:dark){.item-meter{background:transparent;box-shadow:none}.item-meter-fill{background:#C0C0B7}}
</style>
</head>
<body>
<main class="page">
<header class="masthead">
  <h1>你的硬盘，还剩多容量？</h1>
</header>
<div id="app"></div>
</main>
<script>
const DATA=__DATA__;
const ACTION_CONFIG=window.__ACTION_CONFIG__||{enabled:false};
const scrollStateKey='storage-observatory-scroll:'+location.pathname+location.search;
let restoredScrollY=0;
try{restoredScrollY=Math.max(0,Number(sessionStorage.getItem(scrollStateKey)||0))}catch(_error){restoredScrollY=0}
if('scrollRestoration' in history)history.scrollRestoration='manual';
const rememberScroll=()=>{try{sessionStorage.setItem(scrollStateKey,String(Math.max(0,Math.round(window.scrollY))))}catch(_error){}};
window.addEventListener('scroll',rememberScroll,{passive:true});
window.addEventListener('pagehide',rememberScroll);
const restoreScrollPosition=()=>{if(restoredScrollY<=0)return;const target=restoredScrollY;requestAnimationFrame(()=>requestAnimationFrame(()=>window.scrollTo(0,target)))};
const NS='http://www.w3.org/2000/svg';
const INK='#22211F',MUTED='#8F8E86',FAINT='#C0BFB7',GRID='rgba(31,30,28,.16)',PAPER='#F0F0EE',SAFE='#43593B',BAD='#F5572F';
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const n=v=>{
  if(typeof v==='number')return Number.isFinite(v)?v:0;
  const m=String(v==null?'':v).replace(/,/g,'').match(/([-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*(B|KB|MB|GB|TB)?/i);
  if(!m)return 0;
  const unit=(m[2]||'GB').toUpperCase();
  return Number(m[1])*({B:1e-9,KB:1e-6,MB:1e-3,GB:1,TB:1000}[unit]||1);
};
const fmt=v=>n(v).toFixed(1);
const svgEl=(p,t,a={})=>{const x=document.createElementNS(NS,t);for(const k in a)x.setAttribute(k,a[k]);p.appendChild(x);return x};
const svgText=(p,a,s)=>{const x=svgEl(p,'text',a);x.textContent=s;return x};
const svgRichText=(p,a,parts)=>{const x=svgEl(p,'text',a);parts.forEach(part=>{const t=svgEl(x,'tspan',{fill:part.fill||a.fill});t.textContent=part.text});return x};
const tip=(node,s)=>{const t=document.createElementNS(NS,'title');t.textContent=s;node.appendChild(t)};
const rnd=(i,k)=>Math.abs(((i*73856093)^(k*19349663))%1000)/1000;
const pol=(cx,cy,r,deg)=>{const a=deg*Math.PI/180;return[cx+r*Math.cos(a),cy+r*Math.sin(a)]};
const copyText=async text=>{try{await navigator.clipboard.writeText(text)}catch(e){const t=document.createElement('textarea');t.value=text;document.body.appendChild(t);t.select();document.execCommand('copy');t.remove()}};
function drawDumbbell(svg,sd){
  const W=980,H=360,x0=215,x1=930,y0=i=>105+i*145;
  svg.setAttribute('viewBox','0 0 '+W+' '+H);
  const before=n(sd.used_before_gb),after=n(sd.used_after_gb),delta=n(sd.used_delta_gb),currentColor=delta<0?SAFE:delta>0?BAD:INK;
  const span=Math.max(Math.abs(delta),1),rows=[
    {label:'已用空间',before,after,min:0,max:Math.max(after*1.02,1)},
    {label:'变化',before:0,after:delta,displayBefore:before,displayAfter:after,min:delta<0?delta*1.25:-span*.2,max:delta>0?delta*1.25:span*.2}
  ];
  rows.forEach((row,i)=>{
    const y=y0(i),range=Math.max(row.max-row.min,.001),scale=v=>x0+(v-row.min)/range*(x1-x0),xa=scale(row.before),xb=scale(row.after);
    svgText(svg,{x:188,y:y+5,'text-anchor':'end','font-size':18,'font-weight':700,fill:INK},row.label);
    svgEl(svg,'line',{x1:x0-10,y1:y,x2:x1+10,y2:y,stroke:GRID,'stroke-width':1});
    for(let k=0;k<=8;k++){const x=x0+k/8*(x1-x0);svgEl(svg,'line',{x1:x,y1:y-6,x2:x,y2:y+6,stroke:FAINT,'stroke-width':.8,class:'reveal',style:'animation-delay:'+(k*.06)+'s'})}
    svgEl(svg,'line',{x1:xa,y1:y,x2:xb,y2:y,stroke:currentColor,'stroke-width':2,class:'reveal'});
    svgEl(svg,'circle',{cx:xa,cy:y,r:8,fill:MUTED,stroke:MUTED,'stroke-width':1,class:'reveal'});
    const now=svgEl(svg,'circle',{cx:xb,cy:y,r:9,fill:currentColor,class:'reveal delay-2'});tip(now,row.label+' · '+fmt(row.after)+' GB');
    const beforeLabel=row.displayBefore==null?(row.before===0?'0':fmt(row.before)):fmt(row.displayBefore),afterLabel=row.displayAfter==null?(row.after===0?'0':fmt(row.after)):fmt(row.displayAfter);
    svgText(svg,{x:xa,y:y-20,'text-anchor':'middle','font-size':16,'font-weight':700,fill:MUTED},beforeLabel);
    svgText(svg,{x:xb,y:y-20,'text-anchor':'middle','font-size':18,'font-weight':800,fill:currentColor},afterLabel);
    if(i===1)svgText(svg,{x:xb,y:y+32,'text-anchor':'middle','font-size':18,'font-weight':800,fill:currentColor},(row.after>0?'+':'')+fmt(row.after));
  });
}
function drawGauge(svg,system){
  const total=Math.max(n(system.disk_total),1),used=n(system.disk_used),pct=Math.min(100,used/total*100);
  const cx=190,cy=164,R=102,A0=-195,SW=210;svg.setAttribute('viewBox','0 0 380 300');
  [0,25,50,75,100].forEach(m=>{const a=A0+m/100*SW,[x,y]=pol(cx,cy,R-19,a);svgText(svg,{x,y:y+3,'text-anchor':'middle','font-size':9,'font-weight':600,fill:MUTED},String(m))});
  svgText(svg,{x:cx,y:cy-4,'text-anchor':'middle','font-size':34,'font-weight':800,fill:INK},pct.toFixed(1)+'%');
  svgText(svg,{x:cx,y:cy+17,'text-anchor':'middle','font-size':15,'font-weight':700,fill:INK},'已用');
  // F11 · Tick Gauge 原版动效：100 个刻度沿弧线按顺序轻微错峰淡入。
  // 刻度长度使用原版的确定性微抖动；仅把 inked 颜色映射到当前“已用/剩余”语义。
  for(let k=0;k<100;k++){
    const a=A0+k/100*SW,inked=k<pct;
    const len=inked?13+rnd(k+1,3)*6:5+rnd(k+1,7)*2.5;
    const [x1,y1]=pol(cx,cy,R,a),[x2,y2]=pol(cx,cy,R+len,a);
    svgEl(svg,'line',{x1,y1,x2,y2,stroke:inked?INK:SAFE,'stroke-width':inked?1:.6,opacity:inked?1:.72,class:'reveal gauge-tick',style:'animation-delay:'+(k*.012)+'s'});
  }
}
function drawDiverging(svg,sd){
  svg.setAttribute('viewBox','0 0 520 390');
  const data=(sd.changes||[]).slice(0,9);
  if(!sd.path_comparison_available){svgText(svg,{x:260,y:175,'text-anchor':'middle','font-size':14,'font-weight':700,fill:INK},'下一次快照后显示');return}
  if(!data.length){svgText(svg,{x:260,y:175,'text-anchor':'middle','font-size':14,'font-weight':700,fill:INK},'没有目录变化');return}
  const x0=320,y0=72,row=Math.min(120,(330-y0)/Math.max(data.length,1)),localMax=Math.max(...data.map(d=>Math.abs(n(d.delta_gb))),0.1),max=localMax*1.15,scale=v=>Math.abs(v)/max*160;
  svgRichText(svg,{x:x0-54,y:22,'text-anchor':'end','font-size':13,'font-weight':700,fill:INK},[{text:'占用',fill:INK},{text:'减少',fill:SAFE},{text:' ←',fill:SAFE}]);svgRichText(svg,{x:x0+54,y:22,'text-anchor':'start','font-size':13,'font-weight':700,fill:INK},[{text:'→ ',fill:BAD},{text:'占用',fill:INK},{text:'增加',fill:BAD}]);
  svgEl(svg,'line',{x1:x0,y1:38,x2:x0,y2:y0+row*(data.length-1)+34,stroke:INK,'stroke-width':1.2});
  data.forEach((d,i)=>{const v=n(d.delta_gb),y=y0+i*row,len=scale(v),barLen=Math.max(len,4),positive=v>=0,x=positive?x0:x0-len;
    svgText(svg,{x:18,y:y+5,'font-size':14,'font-weight':700,fill:INK},String(d.name).slice(0,18));
    const divergeDuration=.35+1.75*Math.pow(Math.min(barLen/160,1),.62),bar=svgEl(svg,'rect',{x:positive?x:x-barLen+len,y:y-10,width:barLen,height:20,rx:10,fill:positive?BAD:SAFE,class:'reveal diverge-bar '+(positive?'positive':'negative'),style:'--diverge-duration:'+divergeDuration.toFixed(2)+'s;animation-delay:'+(i*.24)+'s'});tip(bar,d.path+' · '+(v>0?'+':'')+v.toFixed(1)+' GB');
    const label=(v>0?'+':'')+v.toFixed(1)+' GB';
    // Positive values sit to the right of their bar; negative values sit to
    // the left. Scale the label with the rendered bar while keeping it legible.
    const valueX=positive?x+barLen+12:x-12;
    const valueAnchor=positive?'start':'end';
    const valueFontSize=(10.5+3.5*Math.pow(Math.min(barLen/160,1),.62)).toFixed(1);
    svgText(svg,{x:valueX,y:y+5,'text-anchor':valueAnchor,'font-size':valueFontSize,'font-weight':800,fill:positive?BAD:SAFE},label);
  });
}
function drawHistory(svg,history,totalCapacity){
  svg.setAttribute('viewBox','0 0 520 390');const data=(history||[]).slice(-6),capacity=Math.max(n(totalCapacity),1),values=(history||[]).slice(-6).map(d=>n(d.used_gb)),minValue=Math.min(...values),maxValue=Math.max(...values),span=Math.max(maxValue-minValue,1),padding=Math.max(span*.18,2.5),yMin=Math.max(0,minValue-padding),yMax=Math.min(capacity,maxValue+padding);
  if(!data.length){svgText(svg,{x:260,y:195,'text-anchor':'middle','font-size':12,fill:MUTED},'执行一次快照后开始记录');return}
  const left=56,right=484,top=64,bottom=296,x=i=>data.length===1?270:left+i/(data.length-1)*(right-left),y=v=>bottom-(Math.max(yMin,Math.min(v,yMax))-yMin)/Math.max(yMax-yMin,.001)*(bottom-top);
  [yMax,(yMin+yMax)/2,yMin].forEach(v=>{const yy=y(v);svgEl(svg,'line',{x1:left,y1:yy,x2:right,y2:yy,stroke:GRID,'stroke-width':1});svgText(svg,{x:2,y:yy+3,'font-size':9,fill:MUTED},v.toFixed(1)+' GB')});
  // 固定方案：总时长 2.1s，按线段几何长度分配非线性时长，节点随对应线段完成后出现。
  const pts=data.map((d,i)=>[x(i),y(n(d.used_gb))]),historyDrawDuration=2.1,segmentLengths=pts.slice(1).map(([x2,y2],i)=>Math.hypot(x2-pts[i][0],y2-pts[i][1])),segmentWeights=segmentLengths.map(length=>Math.pow(Math.max(length,1),.68)),minimumSegmentDuration=.14,weightTotal=Math.max(segmentWeights.reduce((sum,weight)=>sum+weight,0),.001),remainingDuration=Math.max(historyDrawDuration-minimumSegmentDuration*segmentWeights.length,.2),segmentDurations=segmentWeights.map(weight=>minimumSegmentDuration+remainingDuration*weight/weightTotal),segmentOffsets=[];let segmentOffset=0;segmentDurations.forEach(duration=>{segmentOffsets.push(segmentOffset);segmentOffset+=duration});
  for(let i=0;i<pts.length-1;i++){const [x1,y1]=pts[i],[x2,y2]=pts[i+1],duration=segmentDurations[i]||historyDrawDuration;svgEl(svg,'line',{x1,y1,x2,y2,'pathLength':1,fill:'none',stroke:INK,'stroke-width':2.2,class:'reveal history-segment',style:'--history-segment-duration:'+duration.toFixed(3)+'s;animation-delay:'+(segmentOffsets[i]||0).toFixed(3)+'s'})}
  const laterMaxDelta=Math.max(...data.slice(1).map((d,i)=>Math.abs(n(d.used_gb)-n(data[i].used_gb))),.001);
  data.forEach((d,i)=>{const current=n(d.used_gb),previous=i? n(data[i-1].used_gb):current,delta=current-previous,pointColor=i===0?INK:delta<0?SAFE:delta>0?BAD:INK,pointY=y(current),labelY=pointY<top+34?pointY+24:pointY-14,label=i===0?current.toFixed(1)+' GB':(delta>0?'+':'')+delta.toFixed(1)+' GB',pointRadius=i===0?4:3+Math.min(1,Math.abs(delta)/laterMaxDelta)*4,nodeDelay=i===0?0:(segmentOffsets[i-1]||0)+(segmentDurations[i-1]||0),c=svgEl(svg,'circle',{cx:x(i),cy:pointY,r:pointRadius,fill:pointColor,class:'reveal history-node',style:'animation-delay:'+nodeDelay.toFixed(3)+'s'});tip(c,d.at+' · 已用空间 '+current.toFixed(2)+' GB');svgText(svg,{x:x(i),y:labelY,'text-anchor':'middle','font-size':i===data.length-1?13:11,'font-weight':800,fill:pointColor},label)});
  data.forEach((d,i)=>{if(i===0||i===data.length-1)svgText(svg,{x:x(i),y:348,'text-anchor':i===0?'start':i===data.length-1?'end':'middle','font-size':9,fill:MUTED},d.at)});
}
function drawLens(svg,entries){
  svg.setAttribute('viewBox','0 0 680 680');
  const data=(entries||[]).filter(d=>n(d.size_gb)>0).slice(0,10),total=data.reduce((sum,d)=>sum+n(d.size_gb),0);
  if(!data.length){svgText(svg,{x:340,y:330,'text-anchor':'middle','font-size':14,'font-weight':700,fill:INK},'暂无目录数据');return}
  const colors=['#22211F','#3F3E3A','#5D5C55','#77766F','#8F8E86','#A4A39B','#B6B5AD','#C0BFB7','#D0CFC7','#DFDED7'];
  const localized={Desktop:'桌面',Library:'资源库',Documents:'文稿',Music:'音乐',Downloads:'下载',Movies:'影片',Pictures:'图片',Public:'公共'};
  // Keep the panel size fixed while giving the pie a larger share of it.
  // Leaders read from the label as horizontal first, then diagonal into the pie.
  const cx=340,cy=340,R=179,leaderGap=30;let angle=-Math.PI/2,slices=[];
  data.forEach((d,i)=>{const value=n(d.size_gb),start=angle,next=angle+value/total*Math.PI*2,large=next-start>Math.PI?1:0,[x1,y1]=[cx+R*Math.cos(start),cy+R*Math.sin(start)],[x2,y2]=[cx+R*Math.cos(next),cy+R*Math.sin(next)];const path=svgEl(svg,'path',{d:'M '+cx+' '+cy+' L '+x1+' '+y1+' A '+R+' '+R+' 0 '+large+' 1 '+x2+' '+y2+' Z',fill:colors[i],class:'reveal',style:'animation-delay:'+(i*.45)+'s'});tip(path,d.path+' · '+value.toFixed(2)+' GB · '+(value/total*100).toFixed(1)+'%');slices.push({mid:(start+next)/2});angle=next});
  const sides={left:[],right:[]},measure=document.createElement('canvas').getContext('2d');
  if(measure)measure.font='700 13px Inter,-apple-system,BlinkMacSystemFont,"SF Pro SC","PingFang SC",sans-serif';
  data.forEach((d,i)=>{const mid=slices[i].mid,anchorX=cx+(R+6)*Math.cos(mid),anchorY=cy+(R+6)*Math.sin(mid),side=Math.cos(mid)>=0?'right':'left';sides[side].push({d,i,anchorX,anchorY})});
  const minGap=30,minY=44,maxY=596,labelY=new Map();
  const applyY=(items,desired)=>{let ys=desired.map(v=>Math.max(minY,Math.min(maxY,v)));for(let i=1;i<ys.length;i++)ys[i]=Math.max(ys[i],ys[i-1]+minGap);if(ys.length&&ys[ys.length-1]>maxY){const shift=ys[ys.length-1]-maxY;ys=ys.map(v=>v-shift)}if(ys.length&&ys[0]<minY){const shift=minY-ys[0];ys=ys.map(v=>v+shift)}items.forEach((item,i)=>labelY.set(item,Math.max(minY,Math.min(maxY,ys[i]))))};
  const placeLabels=(side,list)=>{list.sort((a,b)=>a.anchorY-b.anchorY);const upper=list.filter(item=>item.anchorY<cy),lower=list.filter(item=>item.anchorY>=cy);if(side==='left'){let start=0;while(start<upper.length){let end=start;while(end+1<upper.length&&upper[end+1].anchorY-upper[end].anchorY<42)end++;const run=upper.slice(start,end+1);if(run.length>1){const endY=Math.min(run[run.length-1].anchorY-28,205);applyY(run,run.map((item,i)=>endY-(run.length-1-i)*minGap))}else applyY(run,[run[0].anchorY-28]);start=end+1}applyY(lower,lower.map(item=>item.anchorY+28))}else{applyY(upper,upper.map(item=>item.anchorY-38));applyY(lower,lower.map(item=>item.anchorY+38))}};
  Object.entries(sides).forEach(([side,list])=>{
    placeLabels(side,list);
    list.forEach(item=>{
      const {d,i,anchorX,anchorY}=item;
      const value=n(d.size_gb),share=value/total*100,y=labelY.get(item),lineY=y-5;
      const rightSide=side==='right',edgeX=rightSide?cx+R+leaderGap:cx-R-leaderGap,labelX=rightSide?662:18,textAnchor=rightSide?'end':'start';
      const textDelay=(i*.45+.22).toFixed(3),labelMotion={class:'reveal lens-label',style:'animation-delay:'+textDelay+'s'},labelText=String(localized[d.name]||d.name).slice(0,20);
      svgText(svg,{x:labelX,y:y,'text-anchor':textAnchor,'font-size':13,'font-weight':700,fill:INK,...labelMotion},labelText);
      const measuredWidth=measure?measure.measureText(labelText).width:labelText.length*13;
      const lineEnd=rightSide?labelX-measuredWidth-24:labelX+measuredWidth+24,baseLineEndX=Math.max(36,Math.min(644,lineEnd));
      const points=anchorX+','+anchorY+' '+edgeX+','+lineY+' '+baseLineEndX+','+lineY;
      svgEl(svg,'polyline',{points,fill:'none',stroke:colors[i],'stroke-width':1.25,'stroke-linecap':'round','stroke-linejoin':'round',opacity:.9,class:'reveal',style:'animation-delay:'+(i*.45)+'s'});
      svgText(svg,{x:labelX,y:y+16,'text-anchor':textAnchor,'font-size':11,'font-weight':600,fill:MUTED,...labelMotion},value.toFixed(1)+' GB · '+share.toFixed(1)+'%');
    });
  });
}
function renderCard(tag,title,sub,body,src,wide=false,square=false,extra=''){return '<article class="card '+extra+(wide?' wide':'')+(square?' square':'')+'"><h2>'+title+'</h2>'+body+'</article>'}
function renderSnapshot(){
  const s=DATA.system||{},sd=DATA.snapshot_diff||{},total=n(s.disk_total),used=n(s.disk_used),free=n(s.disk_free),pct=total?used/total*100:0,fd=n(sd.free_delta_gb);
  const movement=sd.has_previous?('和上次相比的空间变化： '+(fd<0?'<span class="bad">-'+Math.abs(fd).toFixed(1)+' GB</span>':'<span class="good">+'+Math.abs(fd).toFixed(1)+' GB</span>')):'已建立第一份基线';
  const history='<svg id="history" data-chart="history" class="chart-history" aria-label="存储空间变化趋势"></svg>';
  const gauge='<svg id="gauge" data-chart="gauge" class="chart-square" aria-label="已用空间"></svg>';
  const div='<svg id="diverge" data-chart="diverge" class="chart-wide" aria-label="变化落在哪些目录"></svg>';
  return '<section class="hero"><div class="hero-main"><div class="hero-label">当前可用空间</div><div class="hero-number">'+free.toFixed(1)+'<small>GB</small></div></div><div class="hero-side"><strong>'+movement+'</strong></div></section>' +
    '<section class="chart-grid">'+
      renderCard('','已用空间','',gauge,'',false,true,'gauge-card')+
      renderLens()+
      renderCard('','存储空间变化趋势','',history,'',false,true)+
      renderCard('','变化落在哪些目录','',div,'',false,true)+
    '</section>';
}
function renderLens(){return renderCard('','内存透镜','', '<svg id="lens" data-chart="lens" class="chart-lens" aria-label="内存透镜"></svg>','',false,true,'lens-card')}
function renderTop5(){const used=n((DATA.system||{}).disk_used);const rows=(DATA.top5||[]).map(r=>{const share=used?n(r.size)/used*100:0;const open=actionButton('一键打开','open',[r.path]);return '<tr><td class="num">'+esc(r.rank)+'</td><td>'+esc(r.name)+'</td><td class="num">'+esc(r.size)+'</td><td class="num">'+share.toFixed(1)+'%</td><td class="path">'+esc(r.path)+'</td><td class="table-action">'+open+'</td></tr>'}).join('');return '<section class="section"><div class="section-head"><h2>现在，最大的占用在哪里？</h2></div><div class="table-wrap"><table class="table"><thead><tr><th>排名</th><th>项目</th><th>大小</th><th>占已用</th><th>路径</th><th class="table-action">操作</th></tr></thead><tbody>'+rows+'</tbody></table></div></section>'}
function renderUsers(){const s=DATA.system||{},a=DATA.storage_accounting||{},roots=(DATA.root_directories||[]).filter(r=>Number(r.size_kb||0)>0);const total=n(s.disk_total),used=n(s.disk_used),free=Number.isFinite(a.disk_free_gb)?a.disk_free_gb:n(s.disk_free),visible=Number.isFinite(a.root_visible_gb)?a.root_visible_gb:roots.reduce((sum,r)=>sum+n(r.size_h),0),unexpanded=Number.isFinite(a.root_unexpanded_gb)?a.root_unexpanded_gb:Math.max(used-visible,0);const entries=roots.map(r=>({...r,size:n(r.size_h),kind:'root'}));if(unexpanded>0.01)entries.push({name:'系统/权限未展开',path:'已用空间与顶层目录可见合计之间的差额',size:unexpanded,size_h:unexpanded.toFixed(2)+' GB',kind:'other'});if(free>0.01)entries.push({name:'未使用空间',path:'当前文件系统可用空间',size:free,size_h:free.toFixed(2)+' GB',kind:'free'});entries.sort((a,b)=>b.size-a.size);const scale=total>0?total:Math.max(...entries.map(r=>r.size),1),shadeRows=entries.filter(r=>r.kind!=='free'),shadeFor=index=>{const t=shadeRows.length<=1?0:index/(shadeRows.length-1),mix=(a,b)=>Math.round(a+(b-a)*t),hex=v=>v.toString(16).padStart(2,'0');return '#'+hex(mix(34,192))+hex(mix(33,191))+hex(mix(31,183))};const visual=entries.map(r=>{const fillPct=Math.max(r.size/scale,0.0025),fillDuration=.38+2.1*Math.pow(Math.min(fillPct,1),.68),shadeIndex=shadeRows.indexOf(r),fillStyle='width:'+(fillPct*100).toFixed(2)+'%;--scope-duration:'+fillDuration.toFixed(2)+'s'+(shadeIndex>=0?';background:'+shadeFor(shadeIndex):'');return '<div class="scope-row '+esc(r.kind)+'"><div class="scope-name">'+esc(r.name||'其他目录')+'<span class="scope-path">'+esc(r.path||'')+'</span></div><div class="scope-track"><div class="scope-fill reveal" style="'+fillStyle+'"></div></div><div class="scope-value">'+esc(r.size_h||'—')+'</div></div>'}).join('');const accounted=Number.isFinite(a.accounted_gb)?a.accounted_gb:(visible+unexpanded+free);const legend='<div class="scope-legend"><span>总容量 <b>'+fmt(total)+' GB</b></span><span>已核算 <b>'+fmt(accounted)+' GB</b> · 已用 '+fmt(used)+' GB</span></div>';return entries.length?'<section class="section"><div class="section-head"><h2>本机目录与空间构成</h2></div><div class="scope-visual">'+visual+legend+'</div></section>':''}
function renderDeltaDetails(){const sd=DATA.snapshot_diff||{},data=(sd.changes||[]);const rows=data.map(d=>{const v=n(d.delta_gb),cls=v>0?'bad':v<0?'good':'';return '<tr><td>'+esc(d.name)+'</td><td class="num '+cls+'">'+(v>0?'+':'')+fmt(v)+' GB</td></tr>'}).join('');return rows?'<section class="section"><div class="section-head"><h2>目录变化明细</h2></div><div class="table-wrap"><table class="table"><thead><tr><th>目录</th><th>变化</th></tr></thead><tbody>'+rows+'</tbody></table></div></section>':''}
function codeBlock(cmd){return '<div class="code">'+esc(cmd)+'<button class="copy" data-copy="'+btoa(unescape(encodeURIComponent(cmd)))+'">复制</button></div>'}
function encodePaths(paths){return btoa(unescape(encodeURIComponent(JSON.stringify(paths||[]))))}
function actionButton(label,mode,paths,danger=false){const disabled=ACTION_CONFIG.enabled?'':' disabled';return '<button class="action-btn'+(danger?' danger':'')+'" data-action="'+mode+'" data-paths="'+encodePaths(paths)+'"'+disabled+'>'+label+'</button>'}
function actionButtons(it,kind){const out=[];if(kind==='green'&&(it.trash_paths||[]).length){out.push(actionButton('移到废纸篓','trash',it.trash_paths));out.push(actionButton('直接删除（不可逆）','rm',it.trash_paths,true))}else if(kind==='yellow'){if(it.path)out.push(actionButton('打开位置','open',[it.path]));if((it.trash_paths||[]).length)out.push(actionButton('移到废纸篓','trash',it.trash_paths))}else if(kind==='red'){const paths=(it.app_paths||[]).length?it.app_paths:(it.path?[it.path]:[]);if(paths.length)out.push(actionButton('打开位置（去卸载）','open',paths))}if(!ACTION_CONFIG.enabled&&out.length)out.push('<span class="action-note">启动本地服务后启用按钮</span>');return out.length?'<div class="action-row">'+out.join('')+'</div>':''}
function explainItem(it,kind){const name=String(it.name||'');if(kind==='green'){if(it.description)return it.description;if(/下载缓存|更新缓存|下载源缓存/.test(name))return '安装包或更新包的本地副本，用于重复安装或更新；删除后需要时会重新下载。';if(/pip|npm|uv|Cargo|node-gyp/.test(name))return '开发工具保存的包下载或编译中间文件；不会卸载已安装的软件，之后需要时会重新生成。';if(/Homebrew/.test(name))return 'Homebrew 保存的安装包和构建中间文件；不会删除已安装的软件，之后安装时会重新下载。';if(/Ollama/.test(name))return '本地模型运行或下载过程中的缓存；删除后可能需要重新下载模型。';if(/Playwright/.test(name))return '浏览器测试运行时下载的浏览器文件；删除后测试时会重新下载。';if(/Siri TTS/.test(name))return '语音合成生成的音频与模型缓存；再次使用时会重新生成或下载。';if(/Zotero/.test(name))return '文献附件、缩略图和同步过程中的可再生缓存；删除后会按需重建。';if(/网易云音乐/.test(name))return '音乐播放和下载的本地缓存，用于减少重复加载；删除后会按需重新缓存。';if(/Ableton/.test(name))return '音乐软件生成的索引、波形和临时渲染文件；删除后会重新扫描或生成。';return '应用运行产生的可再生临时文件，用于加快启动、搜索或媒体加载；删除后会按需重建。'}if(kind==='yellow')return it.content_profile||'个人项目、媒体、素材或应用数据，可能被其他工程引用；清理前先确认备份和使用情况。';return it.why_keep||'应用本体或附属组件，清理前要确认长期不用，并采用正规的卸载路径。'}
function tierActions(items,kind){const out=[];if(kind==='green'){const paths=[...new Set(items.flatMap(it=>it.trash_paths||[]))];if(paths.length){out.push(actionButton('一键移到废纸篓','trash',paths));out.push(actionButton('一键直接删除（不可逆）','rm',paths,true))}}else{const paths=[...new Set(items.flatMap(it=>kind==='red'?(it.app_paths||[]):(it.path?[it.path]:[])))];if(paths.length)out.push(actionButton(kind==='yellow'?'批量打开人工判断位置':'批量打开应用位置','open',paths))}if(!ACTION_CONFIG.enabled&&out.length)out.push('<span class="action-note">启动本地服务后启用按钮</span>');return out.join('')}
function renderTier(title,items,kind,scaleMax){if(!items||!items.length)return '';const ordered=items.slice().sort((a,b)=>n(b.size_estimate||b.size)-n(a.size_estimate||a.size));const intro=kind==='green'?'这些是可以重新生成的应用缓存、下载包或编译中间文件；清理不会卸载软件，之后需要时可能重新下载或生成。':kind==='yellow'?'这些是个人项目、媒体、素材和应用数据；可能被工程或应用引用，请先确认备份与使用情况。':'这些是应用本体或大型运行组件；清理前请确认长期不用，并使用正规的卸载路径。';const total=ordered.reduce((sum,it)=>sum+n(it.size_estimate||it.size),0);const totalLabel=total>0?'总占用 '+total.toFixed(1)+' GB':'总占用 未读取';const cards=ordered.map(it=>{const inner=[];if(it.content_profile)inner.push('<div class="label">内容画像</div><p>'+esc(it.content_profile)+'</p>');if(it.why_manual||it.why_keep)inner.push('<div class="label">判断</div><p>'+esc(it.why_manual||it.why_keep)+'</p>');if(it.disposal||it.indirect_release)inner.push('<div class="label">处置路径</div><p>'+esc(it.disposal||it.indirect_release)+'</p>');if(it.risk)inner.push('<div class="label">风险</div><p>'+esc(it.risk)+'</p>');inner.push(actionButtons(it,kind));if(it.commands)inner.push('<div class="label">自行确认后执行</div>'+it.commands.map(c=>codeBlock(c.cmd)).join(''));const itemSize=it.size_estimate||it.size||'',itemValue=n(itemSize),barPct=itemValue>0?Math.min(100,itemValue/Math.max(scaleMax,1)*100):0,meter='<span class="item-meter" title="相对本组最大占用：'+barPct.toFixed(1)+'%"><span class="item-meter-fill" style="width:'+barPct.toFixed(1)+'%"></span></span>';return '<details class="item"><summary><span class="item-name">'+esc(it.name)+'<span class="item-explainer">'+esc(explainItem(it,kind))+'</span></span>'+meter+'<span class="item-size">'+esc(itemSize)+'</span></summary><div class="item-body"><div class="path">'+esc(it.path)+'</div>'+inner.join('')+'</div></details>'}).join('');return '<div class="tier"><div class="tier-head"><div><h3>'+title+' · '+ordered.length+' 项</h3><p class="tier-intro">'+intro+'</p></div><div class="tier-head-meta"><div class="tier-total">'+totalLabel+'</div><div class="tier-actions">'+tierActions(ordered,kind)+'</div></div></div>'+cards+'</div>'}
function renderExecution(){const sm=DATA.summary||{};return '<section class="section"><div class="section-head"><h2>执行建议</h2><div class="source">OBSERVATION → DECISION</div></div><p class="insight">'+esc(sm.overview||'')+'</p><ul class="list">'+(sm.priority||[]).map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul></section>'}
function renderLongTerm(){const a=(DATA.summary&&DATA.summary.long_term)||[];return '<section class="section"><div class="section-head"><h2>长期优化</h2><div class="source">PREVENTION</div></div><ul class="list">'+a.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul></section>'}
function renderPermissions(){const p=DATA.permission_status||{};if(!p.needs_attention)return '';const counts=[];if(p.denied_count)counts.push('拒绝读取 '+p.denied_count+' 项');if(p.cleanup_issue_count)counts.push('缓存路径未完整测量 '+p.cleanup_issue_count+' 项');if(p.timeout_count)counts.push('扫描超时 '+p.timeout_count+' 项');const steps=(p.steps||[]).map(step=>'<li>'+esc(step)+'</li>').join('');const paths=(p.sample_paths||[]).map(path=>'<code>'+esc(path)+'</code>').join('');return '<section class="permission-panel"><h2>需要补充扫描权限</h2><p class="permission-summary">'+esc(p.platform||'当前平台')+' · '+esc(counts.join(' · ')||'部分目录未完整读取')+'</p><ol>'+steps+'</ol><p class="permission-note">'+esc(p.note||'权限只用于补全只读统计，不会扩大删除白名单。')+'</p>'+(paths?'<details class="permission-paths"><summary>查看受限路径示例</summary>'+paths+'</details>':'')+'</section>'}
const tierScaleMax=items=>Math.max(...(items||[]).map(it=>n(it.size_estimate||it.size)),1);
const app=document.getElementById('app');
const renderBelowFold=()=>renderUsers()+renderTop5()+renderPermissions()+'<section class="section"><div class="section-head"><h2>清理决策清单</h2></div>'+renderTier('可自动清理 · 纯缓存',DATA.green,'green',tierScaleMax(DATA.green))+renderTier('需人工判断 · 用户数据',DATA.yellow,'yellow',tierScaleMax(DATA.yellow))+renderTier('谨慎清理 · 正规卸载',DATA.red,'red',tierScaleMax(DATA.red))+'</section>';
const perfEnabled=new URLSearchParams(window.location.search).has('perf'),perfMark=label=>{if(perfEnabled&&window.performance&&typeof performance.mark==='function')performance.mark('storage-'+label)};
// Phase 1: put only the masthead, summary and chart shells in the DOM. No SVG
// children are created before the browser has a chance to paint this frame.
perfMark('shell-start');
app.innerHTML=renderSnapshot()+'<div id="below-fold-sentinel" class="deferred-sentinel" aria-hidden="true"></div>';
perfMark('shell-ready');
const markMotionLoaded=node=>{if(node.dataset.motionLoaded==='1')return;node.dataset.motionLoaded='1';node.classList.add('motion-loaded')};
const revealObserver='IntersectionObserver' in window?new IntersectionObserver(entries=>{entries.forEach(entry=>{if(!entry.isIntersecting)return;markMotionLoaded(entry.target);revealObserver.unobserve(entry.target)})},{root:null,rootMargin:'0px',threshold:.01}):null;
const observeReveals=root=>{const nodes=root.querySelectorAll('.reveal:not(.motion-loaded)');if(!revealObserver){nodes.forEach(markMotionLoaded);return}nodes.forEach(node=>revealObserver.observe(node))};
window.__storageRevealObserver=revealObserver;
const chartInitializers={
  gauge:svg=>drawGauge(svg,DATA.system||{}),
  diverge:svg=>drawDiverging(svg,DATA.snapshot_diff||{}),
  history:svg=>drawHistory(svg,DATA.snapshot_history||[],(DATA.system||{}).disk_total),
  lens:svg=>drawLens(svg,DATA.top10||[])
};
const chartPriority={gauge:0,lens:1,history:2,diverge:3},chartQueue=[],prePaintCharts=[],queuedCharts=new WeakSet();let chartFlushPending=false,firstPaintDone=false;
const scheduleIdle=callback=>window.requestIdleCallback?window.requestIdleCallback(callback,{timeout:700}):window.setTimeout(()=>callback({timeRemaining:()=>0}),140);
const scheduleChartFlush=callback=>scheduleIdle(callback);
const flushChartQueue=()=>{const svg=chartQueue.shift();if(svg&&svg.dataset.chartReady!=='1'){const initializer=chartInitializers[svg.dataset.chart];if(initializer){perfMark('chart-'+svg.dataset.chart+'-start');initializer(svg);svg.dataset.chartReady='1';perfMark('chart-'+svg.dataset.chart+'-ready');requestAnimationFrame(()=>svg.querySelectorAll('.reveal').forEach(markMotionLoaded))}}if(chartQueue.length)scheduleChartFlush(flushChartQueue);else chartFlushPending=false};
const startChartFlush=()=>{chartQueue.sort((a,b)=>(chartPriority[a.dataset.chart]??9)-(chartPriority[b.dataset.chart]??9));if(chartQueue.length&&!chartFlushPending){chartFlushPending=true;scheduleChartFlush(flushChartQueue)}};
const queueChart=svg=>{if(!svg||svg.dataset.chartReady==='1'||queuedCharts.has(svg))return;queuedCharts.add(svg);if(!firstPaintDone){prePaintCharts.push(svg);return}chartQueue.push(svg);startChartFlush()};
const chartObserver='IntersectionObserver' in window?new IntersectionObserver(entries=>{entries.forEach(entry=>{if(!entry.isIntersecting)return;queueChart(entry.target);chartObserver.unobserve(entry.target)})},{root:null,rootMargin:'0px',threshold:.01}):null;
requestAnimationFrame(()=>requestAnimationFrame(()=>{perfMark('first-paint-gate');firstPaintDone=true;prePaintCharts.splice(0).forEach(svg=>chartQueue.push(svg));startChartFlush()}));
const chartNodes=app.querySelectorAll('[data-chart]');
if(chartObserver)chartNodes.forEach(node=>chartObserver.observe(node));else chartNodes.forEach(queueChart);
let belowFoldLoaded=false;
const loadBelowFold=()=>{if(belowFoldLoaded)return;belowFoldLoaded=true;perfMark('below-fold-start');const sentinel=document.getElementById('below-fold-sentinel');if(sentinel)sentinel.remove();app.insertAdjacentHTML('beforeend',renderBelowFold());observeReveals(app);perfMark('below-fold-ready');restoreScrollPosition()};
const sentinel=document.getElementById('below-fold-sentinel');
const belowFoldObserver='IntersectionObserver' in window?new IntersectionObserver(entries=>{if(entries.some(entry=>entry.isIntersecting)){loadBelowFold();belowFoldObserver.disconnect()}},{root:null,rootMargin:'360px 0px',threshold:.01}):null;
if(belowFoldObserver)belowFoldObserver.observe(sentinel);else loadBelowFold();
scheduleIdle(loadBelowFold);
async function performAction(button){const mode=button.dataset.action;const paths=JSON.parse(decodeURIComponent(escape(atob(button.dataset.paths))));const label=mode==='rm'?'直接删除（不可逆）':mode==='trash'?'移到废纸篓':'打开位置';if(!ACTION_CONFIG.enabled){alert('请用存储观察站的本地服务打开报告后再使用此按钮。');return}if(mode!=='open'&&!confirm('确认'+label+'？\n\n'+paths.join('\n')))return;button.disabled=true;try{const r=await fetch(ACTION_CONFIG.endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:ACTION_CONFIG.token,mode,paths})});const body=await r.json();if(!r.ok||!body.ok)throw new Error(body.error||'操作失败');button.textContent=mode==='open'?'已打开':'已完成';}catch(error){button.disabled=false;alert(error.message||'操作失败')}}
document.addEventListener('click',e=>{const a=e.target.closest('.action-btn');if(a){e.stopPropagation();performAction(a);return}const b=e.target.closest('.copy');if(!b)return;e.stopPropagation();const text=decodeURIComponent(escape(atob(b.dataset.copy)));copyText(text).then(()=>{b.textContent='已复制';setTimeout(()=>b.textContent='复制',1200)})});
</script>
</body>
</html>
"""


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: build_storage_report.py <data.json> <report.html>")
        return 2
    data_path, report_path = map(Path, sys.argv[1:3])
    data = json.loads(data_path.read_text(encoding="utf-8"))
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    report_path.write_text(TEMPLATE.replace("__DATA__", payload), encoding="utf-8")
    print(f"Lieflat 报告已生成: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
