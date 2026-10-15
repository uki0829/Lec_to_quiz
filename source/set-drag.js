// Saved library cards: native drag, long-press touch drag, and keyboard pickup.
let setDrag=null,setTouch=null,setDragSuppress=null;
function beginSetDrag(id,card,mode='native',kind='set'){
  const material=kind==='material',shared=kind==='shared';
  if(!['set','material','shared'].includes(kind))return false;
  const available=shared?currentGroupDetail?.owner_id===currentUser?.id&&currentGroupDetail?.sets.some(s=>s.id===id):material?currentCollection?.materials.some(m=>m.id===id):savedSets.some(q=>q.id===id);
  const visible=shared?currentView==='groups'&&!$('#group-detail').hidden&&currentGroupDetail?.id===currentGroupId:currentView==='library'&&activeLibraryTab===(material?'materials':'sets');
  if(busy||setActionsBusy||!visible||!available)return false;
  endSetDrag();setDrag={id,collectionId,card,mode,kind,groupId:shared?currentGroupId:null,userId:shared?currentUser.id:null};
  $('#set-trash').setAttribute('aria-label',shared?'Remove set from group':material?'Permanently delete material':'Permanently delete study set');
  $('#set-trash span').textContent='Delete permanently';
  card.classList.add('is-dragging');$('#set-trash').hidden=false;
  $('#set-drag-status').textContent='Drop to delete permanently. Escape cancels.';
  return true;
}
function endSetDrag(){
  if(setTouch){clearTimeout(setTouch.timer);setTouch.ghost?.remove();setTouch=null;}
  if(setDrag){setDrag.card.classList.remove('is-dragging');setDragSuppress={id:setDrag.id,kind:setDrag.kind,until:Date.now()+500};}
  setDrag=null;$('#set-trash').hidden=true;$('#set-trash').classList.remove('is-over');
  $('#set-drag-status').textContent='';
}
function trashContains(x,y){
  const r=$('#set-trash').getBoundingClientRect();return x>=r.left&&x<=r.right&&y>=r.top&&y<=r.bottom;
}
function bindMaterialDrag(card){bindLibraryDrag(card,'material');}
function bindSetDrag(card){bindLibraryDrag(card,'set');}
function bindSharedSetDrag(card){bindLibraryDrag(card,'shared');}
function bindLibraryDrag(card,kind){
  const id=kind==='shared'?card.dataset.dragShare:kind==='material'?card.dataset.dragMaterial:card.dataset.dragSet;
  const control=kind==='material'?'.material-actions':'[data-rename-set]';
  card.addEventListener('click',event=>{
    if(setDrag||setDragSuppress?.id===id&&setDragSuppress.kind===kind&&Date.now()<setDragSuppress.until){event.preventDefault();event.stopPropagation();}
  },true);
  card.addEventListener('dragstart',event=>{
    if(event.target.closest(control)||!beginSetDrag(id,card,'native',kind)){event.preventDefault();return;}
    event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('application/x-lecture-lab-'+kind,id);
  });
  card.addEventListener('dragend',()=>endSetDrag());
  card.addEventListener('keydown',event=>{
    if(event.target.closest(control)||!['Delete','Backspace'].includes(event.key))return;
    event.preventDefault();if(beginSetDrag(id,card,'keyboard',kind))$('#set-trash').focus();
  });
  card.addEventListener('touchstart',event=>{
    if(event.touches.length!==1||event.target.closest(control))return;
    endSetDrag();const p=event.touches[0];
    const touch={id,card,x:p.clientX,y:p.clientY,timer:null,ghost:null};setTouch=touch;
    touch.timer=setTimeout(()=>{
      if(setTouch!==touch)return;
      setTouch=null;if(!beginSetDrag(id,card,'touch',kind))return;setTouch=touch;
      const r=card.getBoundingClientRect(),ghost=card.cloneNode(true);
      ghost.removeAttribute('draggable');ghost.removeAttribute('data-drag-set');ghost.removeAttribute('data-drag-material');ghost.removeAttribute('data-drag-share');
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
async function deleteDraggedCard(selection){
  if(selection?.kind==='shared')await deleteDraggedSharedSet(selection);
  else if(selection?.kind==='material')await deleteDraggedMaterial(selection);
  else await deleteDraggedSet(selection);
}
async function deleteDraggedMaterial(selection){
  if(!selection||busy||setActionsBusy||selection.collectionId!==collectionId||!currentCollection?.materials.some(m=>m.id===selection.id))return;
  setActionsBusy=true;updateSetActions();
  try{await removeMaterial(selection.id,selection.collectionId);}
  finally{setActionsBusy=false;updateSetActions();}
}
$('#set-trash').addEventListener('dragover',event=>{
  if(!setDrag||(setDrag.kind==='shared'?(setDrag.groupId!==currentGroupId||setDrag.userId!==currentUser?.id):setDrag.collectionId!==collectionId))return;
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
  endSetDrag();await deleteDraggedCard(picked);
});
$('#set-trash').addEventListener('click',async()=>{
  if(setDrag?.mode!=='keyboard')return;const picked=setDrag;endSetDrag();await deleteDraggedCard(picked);
});
document.addEventListener('keydown',event=>{
  if(event.key==='Escape'&&(setDrag||setTouch)){
    event.preventDefault();const card=setDrag?.card;endSetDrag();(card?.querySelector('.set-open')||card)?.focus();
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
  if(picked)event.preventDefault();endSetDrag();if(dropped)await deleteDraggedCard(picked);
},{passive:false});
document.addEventListener('touchcancel',()=>endSetDrag());
document.addEventListener('visibilitychange',()=>{if(document.hidden)endSetDrag();});
window.addEventListener('blur',()=>endSetDrag());
