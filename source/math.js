// Local typesetting only. Stored answers, numerical grading and citations stay unchanged.
(() => {
  const escape=text=>String(text??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const greek={eta:'\\eta',alpha:'\\alpha',beta:'\\beta',theta:'\\theta',lambda:'\\lambda'};
  function legacyTex(text){
    return text.replace(/(?<![A-Za-z0-9_α-ωΑ-Ωℓ])([A-Za-zα-ωΑ-Ωℓ∇∂])_(new|old)\b/g,(_,v,label)=>`${v}^{\\mathrm{${label}}}`)
      .replace(/(?<![A-Za-z0-9_α-ωΑ-Ωℓ])([A-Za-zα-ωΑ-Ωℓ∇∂])_([A-Za-zα-ωΑ-Ω]|\d+)\b/g,(_,v,i)=>`${v}_{${i}}`)
      .replace(/gradient\(L\(([A-Za-z])\)\)/g,(_,v)=>`\\nabla L(${v})`)
      .replace(/\b(eta|alpha|beta|theta|lambda)\b/g,name=>greek[name])
      .replace(/\b(sin|cos|tan|log|ln|exp)\b/g,name=>'\\'+name)
      .replace(/\bgradient\b/g,'\\operatorname{gradient}')
      .replace(/([A-Za-z0-9])\^([+-]?\d+)/g,'$1^{$2}')
      .replace(/([A-Za-z])([²³])/g,(_,v,p)=>`${v}^{${p==='²'?2:3}}`)
      .replace(/\b(\d+(?:\.\d+)?)[eE]([+-]?\d+)\b/g,'$1\\times 10^{$2}')
      .replace(/−/g,'-').replace(/×/g,'\\times ').replace(/÷/g,'\\div ')
      .replace(/∇/g,'\\nabla ').replace(/η/g,'\\eta ').replace(/α/g,'\\alpha ').replace(/β/g,'\\beta ').replace(/θ/g,'\\theta ').replace(/λ/g,'\\lambda ')
      .replace(/\*/g,'\\cdot ');
  }
  function legacyFormula(text){
    if(text.length>1200||/[?:\n]/.test(text)||!/[=_^+*/∇ηαβθλ²³×÷]|\s[-−]\s|^\[[\d\s.,−-]+\]$/.test(text))return false;
    return (text.match(/[A-Za-z]+/g)||[]).every(w=>w.length===1||/^(new|old|eta|alpha|beta|theta|lambda|gradient|sin|cos|tan|log|ln|exp)$/.test(w));
  }
  function statusLabels(tex){
    return tex.replace(/(\\(?:mathbf|boldsymbol|mathsf|mathrm)\{[A-Za-z]\}|[A-Za-zα-ωΑ-Ωℓ])_\{(?:\\(?:mathrm|text)\{(new|old)\}|(new|old))\}/g,
      (_,base,label,plainLabel)=>`${base}^{\\mathrm{${label||plainLabel}}}`);
  }
  function render(tex,display,original){
    if(!window.katex)return escape(original);
    tex=statusLabels(tex);
    try{
      if(tex.length>16000)throw Error('Expression too long');
      return '<span class="math-expression'+(display?' math-display':'')+'">'+window.katex.renderToString(tex,{displayMode:display,output:'htmlAndMathml',throwOnError:true,trust:false,strict:'ignore',maxExpand:500,maxSize:10,macros:{}})+'</span>';
    }catch{return '<span class="math-error" title="Math formatting could not be rendered">'+escape(original)+'</span>';}
  }
  function plain(text,formula=false){
    if(formula||legacyFormula(text))return render(legacyTex(text),formula,text);
    // Conservative conversion of old variable labels, never whole prose or identifiers.
    const tokens=/(?<![A-Za-z0-9_α-ωΑ-Ωℓ])[∇∂]_[A-Za-zα-ωΑ-Ω]\s+[A-Za-zα-ωΑ-Ωℓ](?:_[A-Za-zα-ωΑ-Ω])?\([^()\n]{1,40}\)|(?<![A-Za-z0-9_α-ωΑ-Ωℓ])[A-Za-zα-ωΑ-Ωℓ∇∂]_(?:new|old|[A-Za-zα-ωΑ-Ω]|\d+)(?![A-Za-z0-9_α-ωΑ-Ωℓ])(?:\^(?:[A-Za-z]|\d+))?(?:\([^()\n]{1,40}\))?|\b[A-Za-z]\^(?:\{[^{}\n]{1,30}\}|[+-]?\d+|[A-Za-z])|\b[A-Za-z][²³]|(?<![A-Za-z0-9_])\d+(?:\.\d+)?\^(?:\{[+-]?\d+\}|[+-]?\d+)|(?<![A-Za-z0-9_])\d+(?:\.\d+)?[eE][+-]?\d+\b/g;
    let result='',at=0;
    for(const match of text.matchAll(tokens)){result+=escape(text.slice(at,match.index))+render(legacyTex(match[0]),false,match[0]);at=match.index+match[0].length;}
    return result+escape(text.slice(at));
  }
  function toHtml(value,{formula=false,literal=false}={}){
    const text=String(value??'');if(literal)return escape(text);
    // Some saved model output escapes the delimiters twice after JSON decoding.
    // Consume complete delimiter runs without changing commands or matrix row breaks.
    const expressions=/(\\+)\(([\s\S]*?)(\\+)\)|(\\+)\[([\s\S]*?)(\\+)\]|\$\$([\s\S]*?)\$\$|(?<!\\)\$([^$\n]+?)\$/g;
    let result='',at=0,found=false;
    for(const match of text.matchAll(expressions)){
      let tex=match[2]??match[5]??match[7]??match[8];
      const opening=match[1]??match[4],closing=match[3]??match[6];
      if(opening&&closing.length>opening.length)tex+=closing.slice(opening.length);
      if(match[8]!==undefined&&!/\\/.test(tex)&&!legacyFormula(tex)&&!/^[-+]?\d+(?:\.\d+)?$/.test(tex.trim())&&!/^[A-Za-zα-ωΑ-Ωℓ](?:\([^()]*\))?$/.test(tex.trim()))continue;
      result+=plain(text.slice(at,match.index))+render(tex,match[5]!==undefined||match[7]!==undefined,match[0]);at=match.index+match[0].length;found=true;
    }
    if(!found){
      if(formula&&/\\(?:frac|sqrt|sum|int|partial|nabla|mathrm|mathbb|begin)\b/.test(text))return render(text,true,text);
      return plain(text,formula);
    }
    return result+plain(text.slice(at));
  }
  window.LectureMath={toHtml,legacyTex};
})();
