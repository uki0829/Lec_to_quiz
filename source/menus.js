// Styled single-choice menus retain native values and existing change handlers.
(() => {
  const controls=[];let openControl=null,typeBuffer='',typeTime=0;
  const asset=name=>'<img class="icon" src="/static/icons/'+name+'.svg" alt="" aria-hidden="true">';
  function optionIcon(control,option){
    if(control.select.id==='share-group')return 'users';
    if(control.select.id==='share-set')return ({flashcard:'layers',mcq:'clipboard-list',calculation:'calculator',cheatsheet:'file-text'})[option.dataset.format]||'book-open';
    if(control.select.id==='language-select')return 'languages';
    if(['collection-filter','composer-collection','agent-collection','share-collection'].includes(control.select.id))return 'folder';
    if(control.select.id==='set-format-filter')return ({flashcard:'layers',mcq:'clipboard-list',calculation:'calculator',cheatsheet:'file-text'})[option.value]||'layers';
    return control.select.id==='composer-parent'?'book-open':'sparkles';
  }
  function choices(control){return Array.from(control.select.options).map((o,i)=>({option:o,index:i,disabled:o.disabled||Boolean(o.closest('optgroup')?.disabled)}));}
  function closeMenu(){
    if(!openControl)return;
    openControl.panel.hidden=true;openControl.trigger.setAttribute('aria-expanded','false');openControl.trigger.removeAttribute('aria-activedescendant');
    openControl=null;typeBuffer='';
  }
  function position(control){
    const rect=control.trigger.getBoundingClientRect(),width=Math.min(Math.max(rect.width,control.select.id==='language-select'?180:control.select.id==='set-format-filter'?200:280),innerWidth-24);
    control.panel.style.width=width+'px';
    const height=Math.min(control.panel.scrollHeight,300,innerHeight-24);
    const below=innerHeight-rect.bottom-12,above=rect.top-12;
    const top=below>=Math.min(height,140)||below>=above?rect.bottom+7:Math.max(12,rect.top-height-7);
    control.panel.style.left=Math.max(12,Math.min(rect.left,innerWidth-width-12))+'px';
    control.panel.style.top=top+'px';
    control.panel.style.maxHeight=Math.max(80,Math.min(300,top>rect.top?innerHeight-top-12:height))+'px';
  }
  function activate(control,index){
    control.active=index;
    control.panel.querySelectorAll('[role="option"]').forEach((el,i)=>el.classList.toggle('menu-active',i===index));
    const option=control.panel.querySelector('#'+control.select.id+'-option-'+index);
    if(option){
      control.trigger.setAttribute('aria-activedescendant',option.id);
      const top=option.offsetTop,bottom=top+option.offsetHeight;
      if(top<control.panel.scrollTop)control.panel.scrollTop=top;
      else if(bottom>control.panel.scrollTop+control.panel.clientHeight)control.panel.scrollTop=bottom-control.panel.clientHeight;
    }
  }
  function openMenu(control){
    if(control.select.disabled||control.wrapper.hidden||!control.trigger.getClientRects().length)return;
    closeMenu();sync(control);openControl=control;control.panel.hidden=false;control.trigger.setAttribute('aria-expanded','true');
    position(control);
    const first=choices(control).find(c=>!c.disabled)?.index??-1;
    const selected=control.select.selectedIndex;
    activate(control,selected>=0&&!control.select.options[selected].disabled?selected:first);
  }
  function choose(control,index){
    const choice=choices(control)[index];if(!choice||choice.disabled||control.select.disabled)return;
    control.select.value=choice.option.value;closeMenu();control.trigger.focus();
    control.select.dispatchEvent(new Event('change',{bubbles:true}));syncAll();
  }
  function move(control,direction,edge=false){
    const enabled=choices(control).filter(c=>!c.disabled).map(c=>c.index);if(!enabled.length)return;
    const current=enabled.indexOf(control.active);
    const next=edge?(direction>0?enabled[enabled.length-1]:enabled[0]):enabled[(current+direction+enabled.length)%enabled.length];
    activate(control,next);
  }
  function keydown(control,event){
    const key=event.key,isOpen=openControl===control;
    if(key==='Tab'){closeMenu();return;}
    if(key==='Escape'&&isOpen){event.preventDefault();event.stopPropagation();closeMenu();return;}
    if(['ArrowDown','ArrowUp','Home','End'].includes(key)){
      event.preventDefault();if(!isOpen)openMenu(control);
      if(key==='Home'||key==='End')move(control,key==='End'?1:-1,true);
      else if(isOpen)move(control,key==='ArrowDown'?1:-1);
      return;
    }
    if(key==='Enter'||key===' '){event.preventDefault();if(isOpen)choose(control,control.active);else openMenu(control);return;}
    if(key.length===1&&!event.metaKey&&!event.ctrlKey&&!event.altKey){
      event.preventDefault();if(!isOpen)openMenu(control);
      typeBuffer=Date.now()-typeTime>600?key:typeBuffer+key;typeTime=Date.now();
      const enabled=choices(control).filter(c=>!c.disabled);
      let match=enabled.find(c=>c.option.textContent.trim().toLowerCase().startsWith(typeBuffer.toLowerCase()));
      if(!match&&typeBuffer.split('').every(c=>c===key)){typeBuffer=key;const start=enabled.findIndex(c=>c.index===control.active)+1;match=[...enabled.slice(start),...enabled.slice(0,start)].find(c=>c.option.textContent.trim().toLowerCase().startsWith(key.toLowerCase()));}
      if(match)activate(control,match.index);
    }
  }
  function sync(control){
    const select=control.select,option=select.selectedOptions[0]||select.options[0];
    control.wrapper.hidden=select.hidden;control.trigger.disabled=select.disabled;
    control.trigger.setAttribute('aria-disabled',String(select.disabled));
    if(!option){control.trigger.innerHTML='<span>Choose an option</span>'+asset('chevron-right');}
    else control.trigger.innerHTML=asset(optionIcon(control,option))+'<span class="select-value">'+esc(option.textContent)+'</span><span class="select-chevron">'+asset('chevron-right')+'</span>';
    const label=document.querySelector('label[for="'+select.id+'"]');
    if(label){if(!label.id)label.id=select.id+'-label';control.trigger.setAttribute('aria-labelledby',label.id);control.panel.setAttribute('aria-labelledby',label.id);}
    else control.trigger.setAttribute('aria-label',select.getAttribute('aria-label')||'Choose an option');
    const signature=JSON.stringify(choices(control).map(c=>[c.option.value,c.option.textContent,c.option.dataset.meta,c.disabled,select.value===c.option.value]));
    if(signature!==control.signature){
      control.signature=signature;
      control.panel.innerHTML=choices(control).map(c=>'<div id="'+select.id+'-option-'+c.index+'" role="option" aria-selected="'+String(select.value===c.option.value)+'" aria-disabled="'+String(c.disabled)+'" data-index="'+c.index+'">'+asset(optionIcon(control,c.option))+'<span class="menu-option-copy"><span>'+esc(c.option.textContent)+'</span>'+(c.option.dataset.meta?'<small>'+esc(c.option.dataset.meta)+'</small>':'')+'</span><span class="menu-check">'+asset('check')+'</span></div>').join('');
      control.panel.querySelectorAll('[role="option"]').forEach(el=>{el.onpointerdown=e=>e.preventDefault();el.onclick=()=>choose(control,Number(el.dataset.index));el.onpointermove=()=>{if(el.getAttribute('aria-disabled')!=='true')activate(control,Number(el.dataset.index));};});
    }
    if(openControl===control){if(select.hidden||select.disabled||!control.trigger.getClientRects().length)closeMenu();else {position(control);activate(control,control.active);}}
  }
  function enhance(select){
    const wrapper=document.createElement('div');wrapper.className='select-control';wrapper.dataset.select=select.id;
    select.before(wrapper);wrapper.append(select);select.classList.add('select-native');select.setAttribute('aria-hidden','true');select.tabIndex=-1;
    const trigger=document.createElement('button');trigger.type='button';trigger.className='select-trigger';trigger.id=select.id+'-trigger';trigger.setAttribute('role','combobox');trigger.setAttribute('aria-haspopup','listbox');trigger.setAttribute('aria-expanded','false');trigger.setAttribute('aria-controls',select.id+'-menu');
    wrapper.append(trigger);
    const panel=document.createElement('div');panel.className='select-menu';panel.id=select.id+'-menu';panel.setAttribute('role','listbox');panel.hidden=true;
    (select.closest('dialog')||document.body).append(panel);
    const control={select,wrapper,trigger,panel,active:-1,signature:''};controls.push(control);
    trigger.onclick=()=>openControl===control?closeMenu():openMenu(control);
    trigger.onkeydown=e=>keydown(control,e);
    select.addEventListener('change',()=>sync(control));
    const label=document.querySelector('label[for="'+select.id+'"]');if(label)label.addEventListener('click',e=>{e.preventDefault();trigger.focus();});
    new MutationObserver(()=>sync(control)).observe(select,{childList:true,subtree:true,attributes:true,characterData:true});
    sync(control);
  }
  function syncAll(){controls.forEach(sync);}
  document.querySelectorAll('[data-styled-select]').forEach(enhance);
  document.addEventListener('pointerdown',event=>{if(openControl&&!openControl.wrapper.contains(event.target)&&!openControl.panel.contains(event.target))closeMenu();});
  document.addEventListener('scroll',event=>{
    if(!openControl||openControl.panel.contains(event.target))return;
    const rect=openControl.trigger.getBoundingClientRect();
    if(!openControl.trigger.getClientRects().length||rect.bottom<0||rect.top>innerHeight)closeMenu();else position(openControl);
  },true);
  document.querySelectorAll('dialog').forEach(dialog=>dialog.addEventListener('close',closeMenu));
  window.addEventListener('resize',()=>{if(openControl)position(openControl);});
  window.syncMenus=syncAll;
})();
