// Saved library cards: native drag, long-press touch drag, and keyboard pickup.
let setDrag=null,setTouch=null,setDragSuppress=null;
function beginSetDrag(id,card,mode='native'){
  if(busy||setActionsBusy||currentView!=='library'||activeLibraryTab!=='sets'||!savedSets.some(q=>q.id===id))return false;
  endSetDrag();setDrag={id,collectionId,card,mode};
  card.classList.add('is-dragging');$('#set-trash').hidden=false;
  $('#set-drag-status').textContent='Drop to delete permanently. Escape cancels.';
  return true;
}
function endSetDrag(){
  if(setTouch){clearTimeout(setTouch.timer);setTouch.ghost?.remove();setTouch=null;}
  if(setDrag){setDrag.card.classList.remove('is-dragging');setDragSuppress={id:setDrag.id,until:Date.now()+500};}
  setDrag=null;$('#set-trash').hidden=true;$('#set-trash').classList.remove('is-over');
  $('#set-drag-status').textContent='';
}
function trashContains(x,y){
  const r=$('#set-trash').getBoundingClientRect();return x>=r.left&&x<=r.right&&y>=r.top&&y<=r.bottom;
}
function bindSetDrag(card){
  const id=card.dataset.dragSet;
  card.addEventListener('click',event=>{
    if(setDrag||setDragSuppress?.id===id&&Date.now()<setDragSuppress.until){event.preventDefault();event.stopPropagation();}
  },true);
  card.addEventListener('dragstart',event=>{
    if(event.target.closest('[data-rename-set]')||!beginSetDrag(id,card)){event.preventDefault();return;}
    event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('application/x-lecture-lab-set',id);
  });
  card.addEventListener('dragend',()=>endSetDrag());
  card.addEventListener('keydown',event=>{
    if(event.target.closest('[data-rename-set]')||!['Delete','Backspace'].includes(event.key))return;
    event.preventDefault();if(beginSetDrag(id,card,'keyboard'))$('#set-trash').focus();
  });
  card.addEventListener('touchstart',event=>{
    if(event.touches.length!==1||event.target.closest('[data-rename-set]'))return;
    endSetDrag();const p=event.touches[0];
    const touch={id,card,x:p.clientX,y:p.clientY,timer:null,ghost:null};setTouch=touch;
    touch.timer=setTimeout(()=>{
      if(setTouch!==touch)return;
      setTouch=null;if(!beginSetDrag(id,card,'touch'))return;setTouch=touch;
      const r=card.getBoundingClientRect(),ghost=card.cloneNode(true);
      ghost.removeAttribute('draggable');ghost.removeAttribute('data-drag-set');
      ghost.setAttribute('aria-hidden','true');ghost.classList.add('set-drag-ghost');
      ghost.style.width=Math.min(r.width,280)+'px';document.body.appendChild(ghost);touch.ghost=ghost;
      moveSetTouch(touch.x,touch.y);
    },350);
  },{passive:true});
  card.addEventListener('contextmenu',event=>{if(setDrag?.mode==='touch')event.preventDefault();});
}
function moveSetTouch(x,y){
  if(!setTouch?.ghost)return;
  setTouch.ghost.style.left=x+'px';setTouch.ghost.style.top=y+'px';
  $('#set-trash').classList.toggle('is-over',trashContains(x,y));
}
$('#set-trash').addEventListener('dragover',event=>{
  if(!setDrag||setDrag.collectionId!==collectionId)return;
  event.preventDefault();event.dataTransfer.dropEffect='move';$('#set-trash').classList.add('is-over');
});
$('#set-trash').addEventListener('dragleave',event=>{
  if(!event.currentTarget.contains(event.relatedTarget))$('#set-trash').classList.remove('is-over');
});
$('#set-trash').addEventListener('drop',async event=>{
  event.preventDefault();
  const picked=setDrag;
  // External dragged content never supplies the ID to delete.
  if(!picked||picked.mode!=='native')return;
  endSetDrag();await deleteDraggedSet(picked);
});
$('#set-trash').addEventListener('click',async()=>{
  if(setDrag?.mode!=='keyboard')return;const picked=setDrag;endSetDrag();await deleteDraggedSet(picked);
});
document.addEventListener('keydown',event=>{
  if(event.key==='Escape'&&(setDrag||setTouch)){
    event.preventDefault();const card=setDrag?.card;endSetDrag();card?.querySelector('.set-open')?.focus();
  }
});
document.addEventListener('touchmove',event=>{
  if(!setTouch)return;
  if(event.touches.length!==1){endSetDrag();return;}
  const p=event.touches[0];
  if(setDrag?.mode==='touch'){event.preventDefault();moveSetTouch(p.clientX,p.clientY);}
  else if(Math.hypot(p.clientX-setTouch.x,p.clientY-setTouch.y)>10)endSetDrag();
},{passive:false});
document.addEventListener('touchend',async event=>{
  if(!setTouch)return;
  const picked=setDrag,p=event.changedTouches[0];
  const dropped=picked?.mode==='touch'&&p&&trashContains(p.clientX,p.clientY);
  if(picked)event.preventDefault();endSetDrag();if(dropped)await deleteDraggedSet(picked);
},{passive:false});
document.addEventListener('touchcancel',()=>endSetDrag());
document.addEventListener('visibilitychange',()=>{if(document.hidden)endSetDrag();});
window.addEventListener('blur',()=>endSetDrag());
