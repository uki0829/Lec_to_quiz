// Render trusted layout from plain generated content; never execute generated HTML.
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname,join} from 'node:path';
import vm from 'node:vm';
import katex from 'katex';

const root=join(dirname(fileURLToPath(import.meta.url)),'..');
const sheet=JSON.parse(readFileSync(0,'utf8'));
const context=vm.createContext({window:{katex}});
vm.runInContext(readFileSync(join(root,'source/math.js'),'utf8'),context);
const math=context.window.LectureMath.toHtml;
const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const vendor=join(root,'source/vendor/katex');
const fonts=new Map();
const mathCss=readFileSync(join(vendor,'katex.min.css'),'utf8').replace(/url\((?:["']?)(fonts\/[^)'" ]+)(?:["']?)\)/g,(_,font)=>{
  if(!fonts.has(font))fonts.set(font,'data:font/'+(font.endsWith('.woff2')?'woff2':font.endsWith('.woff')?'woff':'ttf')+';base64,'+readFileSync(join(vendor,font)).toString('base64'));
  return 'url('+fonts.get(font)+')';
});
const sections=sheet.sections.map((s,i)=>`<section id="section-${i}"><h2>${math(s.heading)}</h2>
${s.points.length?'<ul>'+s.points.map(p=>'<li>'+math(p)+'</li>').join('')+'</ul>':''}
${s.formulas.map(f=>'<div class="formula">'+math(f,{formula:true})+'</div>').join('')}
<p class="source">${escape(s.source.name)} · ${escape(s.source.locator)}</p></section>`).join('');
process.stdout.write(`<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(sheet.title)}</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; font-src data:; img-src data:; base-uri 'none'; form-action 'none'">
<style>${mathCss}
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#fff;color:#263344;font:15px/1.7 'Avenir Next','Segoe UI',Arial,sans-serif}
main{max-width:980px;margin:0 auto;padding:48px 42px}header{border-bottom:3px solid #7866c4;margin-bottom:28px;padding-bottom:20px}header p{font-size:12px;color:#63518f;margin:0 0 8px}h1{font-size:30px;line-height:1.25;margin:0;overflow-wrap:anywhere}
.description{margin:14px 0 0;color:#52607b;font-size:14px}section{padding:0 0 22px;margin:0 0 22px;border-bottom:1px solid #dce2ee}h2{font-size:19px;line-height:1.4;margin:0 0 12px;break-after:avoid;overflow-wrap:anywhere}ul{padding-left:21px;margin:0}li{padding-left:3px;margin-bottom:9px;white-space:pre-wrap;overflow-wrap:anywhere;orphans:3;widows:3}.formula{background:#f2f4fa;border-left:3px solid #8977c8;border-radius:4px;padding:12px 16px;margin:15px 0;break-inside:avoid;overflow-wrap:anywhere}.katex-display{margin:.4em 0;overflow-x:auto;overflow-y:hidden}.katex{font-size:1.05em}.source{font-size:11px;color:#64718a;margin:14px 0 0}.math-error{color:#263344;font-family:monospace;overflow-wrap:anywhere}
@media(max-width:600px){main{padding:28px 20px}h1{font-size:25px}}
@page{size:A4;margin:17mm 16mm 19mm} @media print{body{font-size:10.5pt}main{max-width:none;padding:0}header{margin-bottom:19px;padding-bottom:15px}h1{font-size:23pt}h2{font-size:14pt}section{margin-bottom:17px;padding-bottom:17px;break-inside:avoid}.formula{background:#f2f4fa;overflow:visible}.katex-display{overflow:visible}.source{font-size:8pt}}
</style></head><body><main><header><p>Lecture Lab · Study guide</p><h1>${math(sheet.title)}</h1>${sheet.description?'<p class="description">'+math(sheet.description)+'</p>':''}</header>${sections}</main></body></html>`);
