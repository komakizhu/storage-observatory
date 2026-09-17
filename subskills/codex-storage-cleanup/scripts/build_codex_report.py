#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the Codex-specific report with the main skill's visual grammar."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


SKILL_ROOT = Path(__file__).resolve().parents[1]
MAIN_SKILL_ROOT = SKILL_ROOT.parents[1]
PARENT_BUILDER = MAIN_SKILL_ROOT / "scripts" / "build_storage_report.py"


def parent_css() -> str:
    spec = importlib.util.spec_from_file_location("storage_observatory_report", PARENT_BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法载入主 skill 报告模板：{PARENT_BUILDER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    template = module.TEMPLATE
    return template.split("<style>", 1)[1].split("</style>", 1)[0]


CUSTOM_CSS = r"""
.cleanup-hero{grid-template-columns:1.2fr .8fr}.cleanup-hero .hero-number{color:var(--ink)}
.cleanup-hero .hero-number .accent{color:var(--safe)}.cleanup-hero .hero-side strong{font-size:25px}
.cleanup-hero .hero-side .accent{color:var(--bad)}
.eyebrow{margin-bottom:9px}.scope-note{max-width:960px}.scope-note code{font:10px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--ink)}
.report-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:0;border-top:1px solid var(--ink);border-bottom:1px solid var(--grid);margin:0 0 44px}
.report-stat{padding:16px 18px 15px 0;border-right:1px solid var(--grid);margin-right:18px}.report-stat:last-child{border-right:0;margin-right:0}
.report-stat b{display:block;font-size:24px;letter-spacing:-.045em;color:var(--ink)}.report-stat span{display:block;color:var(--muted);font-size:11px;margin-top:2px}
.report-stat.green b{color:var(--safe)}.report-stat.orange b{color:var(--bad)}
.chart-caption{display:flex;justify-content:space-between;gap:12px;color:var(--muted);font-size:11px;margin-top:8px}.chart-caption strong{color:var(--ink)}
.ledger-summary{display:grid;grid-template-columns:1.1fr .9fr;gap:28px;border-top:1px solid var(--ink);border-bottom:1px solid var(--grid);padding:22px 0;margin:22px 0 34px}.ledger-summary h2{font-size:19px;margin-bottom:7px}.ledger-summary p{color:var(--muted);font-size:12px;max-width:720px}.ledger-summary ul{padding-left:19px;color:var(--muted);font-size:12px}.ledger-summary li{margin:4px 0}
.scope-table{min-width:920px}.scope-table td,.scope-table th{padding-top:13px;padding-bottom:13px}.user-pill{font-weight:700}.user-home{display:block;color:var(--muted);font:10px ui-monospace,SFMono-Regular,Menlo,monospace;margin-top:2px;max-width:270px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.status-ok{color:var(--safe);font-weight:700}.status-warn{color:var(--bad);font-weight:700}.status-muted{color:var(--muted)}
.root-list{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px}.root-chip{display:inline-block;border:1px solid var(--faint);border-radius:999px;padding:2px 7px;color:var(--muted);font:9px ui-monospace,SFMono-Regular,Menlo,monospace;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tier.regenerable{border-left:3px solid var(--safe);padding-left:18px}.tier.manual{border-left:3px solid var(--bad);padding-left:18px}.tier.protected{border-left:3px solid var(--faint);padding-left:18px}.tier .item:last-child{border-bottom:0}
.tier-kicker{font-size:9px;letter-spacing:.12em;color:var(--muted);text-transform:uppercase;margin-bottom:3px}.tier-kicker.green{color:var(--safe)}.tier-kicker.orange{color:var(--bad)}
.ledger-tag{display:inline-block;margin-left:8px;border:1px solid var(--faint);border-radius:999px;padding:1px 6px;font-size:9px;line-height:1.45;color:var(--muted);vertical-align:2px;font-weight:600}.ledger-tag.green{color:var(--safe);border-color:var(--safe)}.ledger-tag.orange{color:var(--bad);border-color:var(--bad)}
.compact-group{border-bottom:1px solid var(--grid)}.compact-group summary{cursor:pointer;list-style:none;display:flex;gap:10px;align-items:baseline;padding:13px 0}.compact-group summary::-webkit-details-marker{display:none}.compact-group summary:before{content:"＋";font-size:14px;color:var(--muted);width:16px}.compact-group[open] summary:before{content:"−"}.compact-group-title{font-weight:700;flex:1;min-width:180px}.compact-group-sub{display:block;color:var(--muted);font-size:11px;font-weight:400;line-height:1.45;margin-top:3px}.compact-group-total{flex:0 0 auto;text-align:right;font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap}.compact-group-body{padding:0 0 0 26px;border-left:1px solid var(--faint);margin-left:7px}.compact-group-body>.compact-group{margin-left:0}
.item-body .meta-grid{display:grid;grid-template-columns:120px 1fr;gap:4px 12px;margin:11px 0 2px}.meta-grid dt{color:var(--faint);font-size:10px;text-transform:uppercase;letter-spacing:.08em}.meta-grid dd{color:var(--muted);font-size:12px;word-break:break-word}.meta-grid dd.path{font-size:11px}
.issue-panel{border-top:1px solid var(--ink);border-bottom:1px solid var(--grid);padding:17px 0;margin:30px 0}.issue-panel h2{font-size:18px;margin-bottom:7px}.issue-panel p,.issue-panel li{color:var(--muted);font-size:12px}.issue-panel ul{padding-left:19px;margin-top:8px}.issue-panel li{margin:4px 0}.protected-note{background:rgba(31,30,28,.04);padding:12px 14px;color:var(--muted);font-size:11px;margin-top:12px}
.empty-state{padding:30px 0;border-bottom:1px solid var(--grid);color:var(--muted);font-size:13px}
@media(max-width:760px){.report-strip{grid-template-columns:1fr 1fr}.report-stat{border-bottom:1px solid var(--grid);padding:13px 10px 12px 0}.ledger-summary{grid-template-columns:1fr;gap:16px}.item-body .meta-grid{grid-template-columns:1fr;gap:2px}.meta-grid dd{margin-bottom:6px}.tier.regenerable,.tier.manual,.tier.protected{padding-left:12px}.compact-group summary{flex-wrap:wrap}.compact-group-title{min-width:140px}.compact-group-total{flex:0 0 76px}}
"""


TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Codex 文件清理检查</title>
<style>__CSS__
/* Child skill additions: same tokens and chart grammar, Codex-only content. */
__CUSTOM_CSS__</style>
</head>
<body>
<main class="page">
<header class="masthead">
  <div class="eyebrow">CODEX STORAGE CLEANUP · CROSS-USER / CROSS-PLATFORM</div>
  <h1>Codex 里有哪些文件可以清理？</h1>
  <p>这里只看 Codex 生成或管理的文件：归档会话、应用缓存、临时文件、工作区里的旧构建文件和历史任务输出。工作区本身、源代码和你自己的输出不会被当成删除对象。</p>
</header>
<div id="app"></div>
</main>
<script>
const DATA=__DATA__;
const ACTION_CONFIG=window.__ACTION_CONFIG__||{enabled:false};
const NS='http://www.w3.org/2000/svg',INK='#22211F',MUTED='#8F8E86',FAINT='#C0BFB7',GRID='rgba(31,30,28,.16)',SAFE='#43593B',BAD='#F5572F';
const esc=s=>String(s==null?'':s).replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));
const bytes=v=>{if(typeof v==='number')return Number.isFinite(v)?v:0;const m=String(v==null?'':v).replace(/,/g,'').match(/([-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*(B|KB|MB|GB|TB)?/i);if(!m)return 0;return Number(m[1])*({B:1,KB:1e3,MB:1e6,GB:1e9,TB:1e12}[String(m[2]||'GB').toUpperCase()]||1e9)};
const fmtBytes=v=>{let n=bytes(v);for(const unit of ['B','KB','MB','GB','TB']){if(n<1000||unit==='TB')return unit==='B'?Math.round(n)+' B':unit==='KB'?Math.round(n)+' KB':n.toFixed(1)+' '+unit;n/=1000}return n.toFixed(1)+' TB'};
const fmt=v=>bytes(v)>0?fmtBytes(v):'0 B';
const svgEl=(p,t,a={})=>{const x=document.createElementNS(NS,t);for(const k in a)x.setAttribute(k,a[k]);p.appendChild(x);return x};
const svgText=(p,a,s)=>{const x=svgEl(p,'text',a);x.textContent=s;return x};
const tip=(node,s)=>{const t=document.createElementNS(NS,'title');t.textContent=s;node.appendChild(t)};
const reveal=node=>{node.classList.add('reveal','motion-loaded');return node};
const encodePaths=paths=>btoa(unescape(encodeURIComponent(JSON.stringify(paths||[]))));
const actionButton=(label,mode,paths,danger=false)=>'<button class="action-btn'+(danger?' danger':'')+'" data-action="'+mode+'" data-paths="'+encodePaths(paths)+'">'+label+'</button>';
function drawCandidateGauge(svg){
  const s=DATA.summary||{},total=Math.max(bytes(s.codex_bytes),1),candidate=bytes(s.candidate_bytes),pct=Math.min(100,candidate/total*100),cx=190,cy=158,R=103,A0=-195,SW=210;
  svg.setAttribute('viewBox','0 0 380 300');
  [0,25,50,75,100].forEach(m=>{const a=A0+m/100*SW,r=R-19,x=cx+r*Math.cos(a*Math.PI/180),y=cy+r*Math.sin(a*Math.PI/180);svgText(svg,{x,y:y+3,'text-anchor':'middle','font-size':9,'font-weight':600,fill:MUTED},m+'%')});
  svgText(svg,{x:cx,y:cy-8,'text-anchor':'middle','font-size':27,'font-weight':800,fill:INK},pct.toFixed(1)+'%');
  svgText(svg,{x:cx,y:cy+14,'text-anchor':'middle','font-size':13,'font-weight':700,fill:INK},'初步判断可以清理');
  for(let k=0;k<100;k++){const a=A0+k/100*SW,inked=k<pct,len=inked?13:5,x1=cx+R*Math.cos(a*Math.PI/180),y1=cy+R*Math.sin(a*Math.PI/180),x2=cx+(R+len)*Math.cos(a*Math.PI/180),y2=cy+(R+len)*Math.sin(a*Math.PI/180);reveal(svgEl(svg,'line',{x1,y1,x2,y2,stroke:inked?SAFE:FAINT,'stroke-width':inked?1:.6,opacity:inked?1:.72}))}
  svgText(svg,{x:cx,y:cy+52,'text-anchor':'middle','font-size':12,'font-weight':700,fill:SAFE},fmtBytes(candidate)+' / '+fmtBytes(total));
}
function drawUserLens(svg){
  const users=(DATA.users||[]).filter(u=>bytes(u.codex_bytes)>0||bytes(u.candidate_bytes)>0),max=Math.max(...users.map(u=>Math.max(bytes(u.codex_bytes),bytes(u.candidate_bytes))),1),W=520,H=390;
  svg.setAttribute('viewBox','0 0 '+W+' '+H);
  if(!users.length){svgText(svg,{x:W/2,y:H/2,'text-anchor':'middle','font-size':14,fill:MUTED},'没有找到 Codex 文件');return}
  const left=42,right=477,top=42,row=Math.min(78,(H-88)/Math.max(users.length,1));
  users.slice(0,5).forEach((u,i)=>{const y=top+i*row+24,total=bytes(u.codex_bytes),candidate=bytes(u.candidate_bytes),visualTotal=Math.max(total,candidate),radius=18+30*Math.sqrt(visualTotal/max),x=left+radius+5;svgEl(svg,'line',{x1:left,y1:y+35,x2:right,y2:y+35,stroke:GRID,'stroke-width':1});const c=reveal(svgEl(svg,'circle',{cx:x,cy:y,r:Math.min(radius,47),fill:'none',stroke:INK,'stroke-width':1.2}));tip(c,u.user+' · '+fmtBytes(total||candidate));svgText(svg,{x:x,y:y+4,'text-anchor':'middle','font-size':11,'font-weight':800,fill:INK},u.user);svgText(svg,{x:left,y:y+59,'font-size':11,'font-weight':700,fill:INK},u.user);svgText(svg,{x:left+72,y:y+59,'font-size':10,fill:MUTED},fmtBytes(total||candidate)+' · 初步判断可以清理 '+fmtBytes(candidate));const barWidth=Math.max((candidate/max)*340,3);reveal(svgEl(svg,'rect',{x:left+72,y:y+66,width:barWidth,height:7,rx:4,fill:SAFE}))});
}
function drawTimeline(svg){
  const data=DATA.timeline||[],W=520,H=390;svg.setAttribute('viewBox','0 0 '+W+' '+H);
  if(!data.length){svgText(svg,{x:W/2,y:H/2,'text-anchor':'middle','font-size':14,fill:MUTED},'没有可用的修改时间');return}
  const max=Math.max(...data.map(d=>bytes(d.size_bytes)),1),left=46,right=478,base=250,step=data.length===1?0:(right-left)/(data.length-1);
  svgEl(svg,'line',{x1:left,y1:base,x2:right,y2:base,stroke:INK,'stroke-width':1.2});
  data.forEach((d,i)=>{const x=data.length===1?262:left+i*step,size=bytes(d.size_bytes),h=26+142*(size/max),bar=reveal(svgEl(svg,'rect',{x:x-10,y:base-h,width:20,height:h,rx:10,fill:i%2?MUTED:INK}));tip(bar,d.date+' · '+fmtBytes(size));svgText(svg,{x,y:base+22,'text-anchor':'middle','font-size':9,fill:MUTED},String(d.date).slice(5));svgText(svg,{x,y:base-h-10,'text-anchor':'middle','font-size':10,'font-weight':700,fill:INK},fmtBytes(size))});
  svgText(svg,{x:left,y:44,'font-size':12,'font-weight':700,fill:INK},'按文件夹最近修改时间统计');
}
function drawPaths(svg){
  const data=(DATA.top_paths||[]).slice(0,9),W=520,H=390;svg.setAttribute('viewBox','0 0 '+W+' '+H);
  if(!data.length){svgText(svg,{x:W/2,y:H/2,'text-anchor':'middle','font-size':14,fill:MUTED},'没有找到可以展示的文件夹');return}
  const max=Math.max(...data.map(d=>bytes(d.size_bytes)),1),x0=190,x1=460,row=Math.min(35,(H-70)/data.length);
  data.forEach((d,i)=>{const y=58+i*row,size=bytes(d.size_bytes),width=Math.max(4,size/max*(x1-x0)),color=d.tier==='regenerable'?SAFE:d.tier==='manual'?BAD:MUTED;svgText(svg,{x:4,y:y+5,'font-size':11,'font-weight':700,fill:INK},String(d.name).slice(0,22));const bar=reveal(svgEl(svg,'rect',{x:x0,y:y-9,width,height:18,rx:9,fill:'#C0BFB7'}));const fill=reveal(svgEl(svg,'rect',{x:x0,y:y-9,width,height:18,rx:9,fill:color}));tip(fill,d.path+' · '+fmtBytes(size));svgText(svg,{x:x1+10,y:y+5,'font-size':10,'font-weight':700,fill:color},fmtBytes(size))});
}
function renderCard(title,sub,chart,tag){return '<article class="card square"><div class="eyebrow">'+tag+'</div><h2>'+title+'</h2><p class="sub">'+sub+'</p>'+chart+'</article>'}
function renderHero(){
  const s=DATA.summary||{},scope=DATA.scope||{},p=DATA.platform||{};
  return '<section class="hero cleanup-hero"><div class="hero-main"><div class="hero-label">初步判断可以清理的 Codex 文件</div><div class="hero-number"><span class="accent">'+fmtBytes(s.candidate_bytes)+'</span></div><div class="hero-meta">'+(s.candidate_count||0)+' 项 · 只包含 Codex 生成或管理的文件 · 生成报告不会改变文件</div></div><div class="hero-side"><strong>已检查 '+(scope.readable_user_count||0)+' 个用户</strong><div class="rule"></div><p>'+esc(p.name||'当前平台')+' · '+esc(p.arch||'')+' · 当前账号 '+esc(p.current_user||'未知')+'</p><p>找到了 '+(scope.codex_root_count||0)+' 个 Codex 文件夹；得到你的同意后才会移动或删除。</p></div></section><div class="report-strip"><div class="report-stat green"><b>'+fmtBytes(s.regenerable_bytes)+'</b><span>缓存和临时文件 · '+(s.regenerable_count||0)+' 项</span></div><div class="report-stat orange"><b>'+fmtBytes(s.manual_bytes)+'</b><span>需要你先看 · '+(s.manual_count||0)+' 项</span></div><div class="report-stat"><b>'+fmtBytes(s.codex_bytes)+'</b><span>Codex 文件总量</span></div><div class="report-stat"><b>'+fmtBytes(s.protected_bytes)+'</b><span>建议保留的文件</span></div></div>';
}
function renderCharts(){
  return '<section class="chart-grid">'+renderCard('初步判断可以清理的文件有多少？','F11 · 只计算已经找到的 Codex 文件夹和待处理文件','<svg id="candidate-gauge" class="chart-square" data-chart="candidate-gauge" aria-label="初步判断可以清理的文件占 Codex 文件比例"></svg>','SCOPE / RATIO')+renderCard('哪个用户占用最多？','每个圆环代表一个找到 Codex 文件的用户','<svg id="user-lens" class="chart-lens" data-chart="user-lens" aria-label="各用户的 Codex 文件占用"></svg>','USERS / LENS')+renderCard('这些文件是什么时候留下的？','F2 · 按文件夹最近修改时间统计','<svg id="codex-timeline" class="chart-history" data-chart="codex-timeline" aria-label="Codex 文件时间线"></svg>','AGE / TIMELINE')+renderCard('具体是哪些文件夹？','G10 · 条形只代表初步判断可以清理的部分，不代表整个工作区','<svg id="codex-paths" class="chart-wide" data-chart="codex-paths" aria-label="初步判断可以清理的 Codex 文件夹"></svg>','PATHS / LEDGER')+'</section>';
}
function renderScope(){
  const users=DATA.users||[];if(!users.length)return '<section class="section"><div class="empty-state">没有发现可读取的本地用户目录。</div></section>';
  const rows=users.map(u=>{const roots=(u.codex_roots||[]).map(r=>'<span class="root-chip" title="'+esc(r.path)+'">'+esc(r.label||r.kind)+' · '+esc(r.size||'—')+'</span>').join('');const status=u.status==='已读取'?'<span class="status-ok">已读取</span>':u.status==='部分受限'?'<span class="status-warn">部分受限</span>':'<span class="status-muted">不可读取</span>';return '<tr><td><span class="user-pill">'+esc(u.user)+'</span><span class="user-home">'+esc(u.home)+'</span></td><td>'+esc(u.platform||'—')+'</td><td>'+status+'</td><td>'+((u.codex_roots||[]).length?roots:'<span class="status-muted">没有找到 Codex 文件夹</span>')+'</td><td class="num">'+esc(u.codex_size||'0 B')+'</td><td class="num">'+esc(u.candidate_size||'0 B')+'<br><span class="status-muted">'+(u.candidate_count||0)+' 项</span></td></tr>'}).join('');
  return '<section class="section"><div class="section-head"><h2>检查了哪些用户和文件夹？</h2><div class="source">DISCOVERY / PROVENANCE</div></div><p class="scope-note">逐个检查每个用户实际存在的 <code>.codex</code> 文件夹、Documents/Codex 工作区和 Codex 应用数据。不会把整个用户文件夹、Documents 或 C:\\Users 当成清理目标。</p><div class="table-wrap"><table class="table scope-table"><thead><tr><th>用户 / 文件夹</th><th>平台</th><th>检查结果</th><th>找到的 Codex 文件夹</th><th>Codex 占用</th><th>初步判断可以清理</th></tr></thead><tbody>'+rows+'</tbody></table></div></section>';
}
function itemActions(it){
  const out=[];const opens=it.open_paths||[];const trash=it.trash_paths||[];
  if(opens.length)out.push(actionButton('打开位置','open',opens));
  if(trash.length)out.push(actionButton('移到废纸篓/回收站','trash',trash));
  if(!ACTION_CONFIG.enabled&&out.length)out.push('<span class="action-note">启动本地服务后启用</span>');
  return out.length?'<div class="action-row">'+out.join('')+'</div>':'';
}
function renderItem(it,tier,maxSize){
  const size=bytes(it.size_bytes),pct=Math.min(100,size/Math.max(maxSize,1)*100),tag=tier==='regenerable'?'<span class="ledger-tag green">初步判断可以清理</span>':tier==='manual'?'<span class="ledger-tag orange">先看一下</span>':'<span class="ledger-tag">建议保留</span>';
  const meter='<span class="item-meter" title="相对本组最大占用：'+pct.toFixed(1)+'%"><span class="item-meter-fill" style="width:'+pct.toFixed(1)+'%"></span></span>';
  const meta='<dl class="meta-grid"><dt>文件位置</dt><dd class="path">'+esc(it.path)+'</dd><dt>为什么算作 Codex 文件</dt><dd>'+esc(it.provenance)+'</dd><dt>为什么现在列出来</dt><dd>'+esc(it.reason)+'</dd><dt>是否正在使用</dt><dd>'+esc(it.activity||'没有找到相关信息')+'</dd><dt>项目状态</dt><dd>'+esc(it.git_state||'不适用')+'</dd><dt>怎么恢复</dt><dd>'+esc(it.recovery||'请先确认')+'</dd><dt>建议怎么处理</dt><dd>'+esc(it.recommendation||'保留')+'</dd></dl>';
  const extra=it.file_count!=null?'<p><span class="label">归档文件数量</span> '+esc(it.file_count)+(it.file_count_note?' · '+esc(it.file_count_note):'')+'</p>':'';
  return '<details class="item"><summary><span class="item-name">'+esc(it.name)+' '+tag+'<span class="item-explainer">'+esc(it.artifact_type)+' · '+esc(it.user)+' · 最后修改于 '+esc(it.modified_at||'未读取')+'</span></span>'+meter+'<span class="item-size">'+esc(it.size||fmtBytes(size))+'</span></summary><div class="item-body">'+meta+extra+itemActions(it)+'</div></details>';
}
const COMPACT_START=100*1000*1000;
const COMPACT_MIN_VISIBLE=5;
const compactThresholdLabel=threshold=>fmtBytes(threshold).replace(/\.0 (?=[A-Z])/, ' ');
function renderCompactGroup(items,tier,maxSize,upperThreshold,groupLabel='',groupSub=''){
  const ordered=items.slice().sort((a,b)=>bytes(b.size_bytes)-bytes(a.size_bytes)),nextThreshold=upperThreshold/10;
  const shown=ordered.filter(item=>bytes(item.size_bytes)>=nextThreshold),smaller=ordered.filter(item=>bytes(item.size_bytes)<nextThreshold);
  const shownHtml=shown.map(item=>renderItem(item,tier,maxSize)).join('');
  const smallerHtml=smaller.length?(nextThreshold>=1000?renderCompactGroup(smaller,tier,maxSize,nextThreshold):smaller.map(item=>renderItem(item,tier,maxSize)).join('')):'';
  const total=ordered.reduce((sum,item)=>sum+bytes(item.size_bytes),0);
  const pct=Math.min(100,total/Math.max(maxSize,1)*100),meter='<span class="item-meter compact-meter" title="其他合计 '+fmtBytes(total)+'，相对本组最大项目 '+pct.toFixed(1)+'%"><span class="item-meter-fill" style="width:'+pct.toFixed(1)+'%"></span></span>';
  return '<details class="compact-group"><summary><span class="compact-group-title">其他 · '+(groupLabel||'小于 '+compactThresholdLabel(upperThreshold))+'<span class="compact-group-sub">'+(groupSub||'展开后继续按 10 倍大小查看')+'</span></span>'+meter+'<span class="compact-group-total item-size">'+fmtBytes(total)+' · '+ordered.length+' 项</span></summary><div class="compact-group-body">'+shownHtml+smallerHtml+'</div></details>';
}
function renderCompactItems(ordered,tier,maxSize){
  if(ordered.length<=COMPACT_MIN_VISIBLE)return ordered.map(item=>renderItem(item,tier,maxSize)).join('');
  const shown=ordered.filter(item=>bytes(item.size_bytes)>=COMPACT_START),smaller=ordered.filter(item=>bytes(item.size_bytes)<COMPACT_START);
  if(shown.length<COMPACT_MIN_VISIBLE){
    const top=ordered.slice(0,COMPACT_MIN_VISIBLE),rest=ordered.slice(COMPACT_MIN_VISIBLE);
    return top.map(item=>renderItem(item,tier,maxSize)).join('')+renderCompactGroup(rest,tier,maxSize,COMPACT_START,'其余项目','前 5 项已单独显示，展开查看剩余项目');
  }
  return shown.map(item=>renderItem(item,tier,maxSize)).join('')+(smaller.length?renderCompactGroup(smaller,tier,maxSize,COMPACT_START):'');
}
function renderTier(title,kicker,intro,items,tier){
  if(!items.length)return '';
  const ordered=items.slice().sort((a,b)=>bytes(b.size_bytes)-bytes(a.size_bytes)),max=Math.max(...ordered.map(item=>bytes(item.size_bytes)),1),total=ordered.reduce((sum,item)=>sum+bytes(item.size_bytes),0);
  return '<div class="tier '+tier+'"><div class="tier-head"><div><div class="tier-kicker '+(tier==='regenerable'?'green':tier==='manual'?'orange':'')+'">'+kicker+'</div><h3>'+title+' · '+ordered.length+' 项</h3><p class="tier-intro">'+intro+'</p></div><div class="tier-head-meta"><div class="tier-total">'+fmtBytes(total)+'</div></div></div>'+renderCompactItems(ordered,tier,max)+'</div>';
}
function renderDecision(){
  const s=DATA.summary||{};return '<section class="section"><div class="section-head"><h2>Codex 清理决策清单</h2><div class="source">OBSERVATION → AUTHORIZATION</div></div><div class="ledger-summary"><div><h2>先看清楚，再决定要不要处理</h2><p>这个页面只看 Codex 生成或管理的文件，主页面仍然负责查看整台电脑的磁盘占用。工作区文件夹本身不会直接操作，只有具体文件夹得到你的同意后才会处理。</p><p>列表先显示 100 MB 以上的项目；小于 100 MB 的项目会收进“其他”，展开后继续按 10 倍大小查看。</p></div><ul><li>缓存和临时文件：'+esc(s.regenerable_size)+'，关闭相关程序后可以考虑移到废纸篓/回收站。</li><li>需要你先看：'+esc(s.manual_size)+'，包括归档会话、崩溃报告和工作区里的旧产物。</li><li>建议保留：'+esc(s.protected_size)+'，包括当前会话、源代码、你自己的输出、设置和数据库。</li></ul></div>'+renderTier('初步判断可以清理 · 缓存和临时文件','CACHE / TEMP','这些文件通常会在需要时重新生成。请先关闭正在使用它们的程序，再决定是否移走。',DATA.green||[],'regenerable')+renderTier('需要你先看 · 会话和旧产物','REVIEW / YOUR DECISION','这些内容可能包含聊天、诊断信息或你自己的文件。请先打开位置、检查备份，再决定是否移走。',DATA.yellow||[],'manual')+renderTier('建议保留 · 当前数据','KEEP / PROTECTED','这些文件夹里可能有当前任务、源代码、附件、登录信息或设置，不在本次清理范围内。',DATA.red||[],'protected')+'</section>';
}
function renderIssues(){
  const meta=DATA.ledger_meta||{},issues=meta.issues||[],scope=DATA.scope||{};if(!issues.length&&!((scope.unreadable_homes||[]).length))return '';
  const rows=issues.slice(0,24).map(issue=>'<li>'+esc(issue.user||'未知用户')+' · '+esc(issue.path||'')+' · '+esc(issue.reason||'无法读取')+'</li>').join('');const unread=(scope.unreadable_homes||[]).map(home=>'<li>无法完整读取的用户文件夹：'+esc(home)+'</li>').join('');return '<section class="issue-panel"><h2>没有完整读取的地方</h2><p>权限不足或无法完整读取的内容不会被列为可以清理的文件。</p><ul>'+unread+rows+'</ul></section>';
}
function renderFooter(){const p=DATA.platform||{},s=DATA.scope||{};return '<footer class="footer">CODEX STORAGE CLEANUP · '+esc(p.name||'平台未识别')+' · '+esc(DATA.generated_at||'')+' · 已检查 '+(s.user_count||0)+' 个用户 · 找到 '+(s.codex_root_count||0)+' 个 Codex 文件夹 · 只查看，尚未操作</footer>'}
const app=document.getElementById('app');
app.innerHTML=renderHero()+renderCharts()+'<div id="below-fold-sentinel" class="deferred-sentinel" aria-hidden="true"></div>';
const chartFns={'candidate-gauge':drawCandidateGauge,'user-lens':drawUserLens,'codex-timeline':drawTimeline,'codex-paths':drawPaths};
const initCharts=()=>{Object.entries(chartFns).forEach(([id,fn])=>{const node=document.getElementById(id);if(node&&node.dataset.ready!=='1'){fn(node);node.dataset.ready='1'}})};
requestAnimationFrame(()=>requestAnimationFrame(initCharts));
let belowLoaded=false;const loadBelow=()=>{if(belowLoaded)return;belowLoaded=true;const sentinel=document.getElementById('below-fold-sentinel');if(sentinel)sentinel.remove();app.insertAdjacentHTML('beforeend',renderScope()+renderDecision()+renderIssues()+renderFooter());app.querySelectorAll('.reveal').forEach(node=>node.classList.add('motion-loaded'))};
const observer='IntersectionObserver' in window?new IntersectionObserver(entries=>{if(entries.some(entry=>entry.isIntersecting)){loadBelow();observer.disconnect()}},{root:null,rootMargin:'360px 0px',threshold:.01}):null;const sentinel=document.getElementById('below-fold-sentinel');if(observer)observer.observe(sentinel);if(window.requestIdleCallback)requestIdleCallback(loadBelow,{timeout:900});else setTimeout(loadBelow,400);
async function performAction(button){const mode=button.dataset.action,paths=JSON.parse(decodeURIComponent(escape(atob(button.dataset.paths)))),label=mode==='trash'?'移到废纸篓/回收站':'打开位置';if(!ACTION_CONFIG.enabled){alert('请通过 Codex 清理页面操作。');return}if(mode==='trash'&&!confirm('确认'+label+'？\n\n'+paths.join('\n')))return;button.disabled=true;try{const result=await fetch(ACTION_CONFIG.endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:ACTION_CONFIG.token,mode,paths})}),body=await result.json();if(!result.ok||!body.ok)throw new Error(body.error||'操作失败');button.textContent=mode==='open'?'已打开':'已移入废纸篓/回收站'}catch(error){button.disabled=false;alert(error.message||'操作失败')}}
document.addEventListener('click',event=>{const action=event.target.closest('.action-btn');if(action){event.stopPropagation();performAction(action)}});
</script>
</body>
</html>
"""


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: build_codex_report.py <data.json> <report.html>")
        return 2
    data_path, report_path = map(Path, sys.argv[1:3])
    data = json.loads(data_path.read_text(encoding="utf-8"))
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.replace("__CSS__", parent_css()).replace("__CUSTOM_CSS__", CUSTOM_CSS).replace("__DATA__", payload)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(html, encoding="utf-8")
    print(f"Codex 清理报告已生成: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
