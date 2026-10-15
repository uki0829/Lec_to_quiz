// Saved-set names and permanent drag-to-trash deletion.
let setActionsBusy=false,setRenameId=null;
function resetSetActions(){if(typeof endSetDrag==='function')endSetDrag();setRenameId=null;}
function updateSetActions(){
  document.querySelectorAll('.managed-set button,.material-actions button,.group-card button,.group-set-card,#group-leave,#group-share,#create-group,#join-group').forEach(b=>b.disabled=busy||setActionsBusy);
  for(const id of ['set-name','save-set-name','cancel-rename-set','close-rename-set'])$('#'+id).disabled=setActionsBusy;
}
function renderSetCards(sets,search){
  if(typeof endSetDrag==='function')endSetDrag();
  $('#quiz-grid').innerHTML=sets.map(q=>'<article class="quiz-card managed-set" draggable="true" data-drag-set="'+esc(q.id)+'"><button class="set-open" aria-keyshortcuts="Delete" aria-description="Drag to the trash to delete. Press Delete for keyboard controls." data-quiz="'+esc(q.id)+'"><span class="card-top"><span class="card-format">'+icon(formatIcon(q.format))+esc(formatName(q.format))+'</span><span class="card-count">'+(q.format==='cheatsheet'?q.sectionCount+' sections':q.questionCount+' questions')+'</span></span><h3>'+mathHtml(q.title)+'</h3><span class="card-cta"><span>'+(q.format==='cheatsheet'?'Open sheet':q.answeredCount?'Continue · '+q.answeredCount+'/'+q.questionCount:'Study')+'</span>'+icon('arrow-right')+'</span></button><div class="set-card-actions"><button class="quiet set-rename" data-rename-set="'+esc(q.id)+'" aria-label="Rename '+esc(q.title)+'">'+icon('pencil')+'Rename</button></div></article>').join('')+(!search?'<button class="quiz-card new-set-card" id="new-set-card">'+icon('plus')+'<strong>Create study set</strong></button>':!sets.length?'<p class="empty-results">No study sets match.</p>':'');
  $('#quiz-grid').querySelectorAll('[data-quiz]').forEach(b=>b.onclick=()=>openQuiz(b.dataset.quiz));
  $('#quiz-grid').querySelectorAll('[data-rename-set]').forEach(b=>b.onclick=()=>openSetRename(b.dataset.renameSet));
  $('#new-set-card')?.addEventListener('click',()=>openComposer());
  if(typeof bindSetDrag==='function')$('#quiz-grid').querySelectorAll('[data-drag-set]').forEach(bindSetDrag);
  updateSetActions();
}
function openSetRename(id){
  if(busy||setActionsBusy)return;const found=savedSets.find(q=>q.id===id);if(!found)return;
  if(typeof endSetDrag==='function')endSetDrag();
  setRenameId=id;$('#set-name').value=found.title;$('#rename-set-error').textContent='';$('#rename-set-dialog').showModal();$('#set-name').focus();$('#set-name').select();
}
async function deleteDraggedSet(selection){
  if(!selection||busy||setActionsBusy||selection.collectionId!==collectionId||!savedSets.some(q=>q.id===selection.id))return;
  const {id,collectionId:cid}=selection;
  setActionsBusy=true;updateSetActions();
  try{
    await api('/api/collections/'+encodeURIComponent(cid)+'/quizzes/remove',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({quizIds:[id]})});
    savedSets=savedSets.filter(q=>q.id!==id);
    bankRows=bankRows.filter(q=>q.originQuizId!==id);bankKey='';renderedQuizzesKey='';
    if(parentQuizId===id){parentQuizId=null;parentQuizTitle='';updateFollowup();}
    if((quiz?.id===id&&quiz.mode==='generated')||(quiz?.mode==='bank'&&quiz.questions.some(q=>q.originQuizId===id))){
      clearTimeout(saveTimer);cancelQuizAdvance();closeQuizExplanation();quiz=null;answers={};
      $('#study').hidden=true;$('#summary').hidden=true;$('#cheatsheet').hidden=true;$('#empty').hidden=false;
      showView('library');
    }
    renderQuizGrid();renderQuestionBank();saveSnapshot();await refreshCollection();
    if(currentView==='library'&&collectionId===cid)$('#new-set-card')?.focus();
  }catch(err){message(err.message,true);}
  finally{setActionsBusy=false;updateSetActions();}
}
$('#rename-set-form').onsubmit=async event=>{
  event.preventDefault();if(setActionsBusy||busy||!setRenameId)return;
  const title=$('#set-name').value.trim();if(!title){$('#rename-set-error').textContent='Enter a name.';return;}
  const id=setRenameId;setActionsBusy=true;updateSetActions();
  try{
    const result=await api('/api/quizzes/'+encodeURIComponent(id),{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({title})});
    savedSets=savedSets.map(q=>q.id===id?{...q,title:result.title}:q);
    if(quiz?.id===id&&quiz.mode==='generated'){quiz.title=result.title;$('#quiz-title').innerHTML=mathHtml(result.title);$('#sheet-title').innerHTML=mathHtml(result.title);}
    if(parentQuizId===id){parentQuizTitle=result.title;updateFollowup();}
    $('#rename-set-dialog').close();renderQuizGrid();saveSnapshot();await refreshCollection();
  }catch(err){$('#rename-set-error').textContent=err.message;message(err.message,true);}
  finally{setActionsBusy=false;updateSetActions();}
};
for(const id of ['close-rename-set','cancel-rename-set'])$('#'+id).onclick=()=>{if(!setActionsBusy)$('#rename-set-dialog').close();};
$('#rename-set-dialog').addEventListener('cancel',event=>{if(setActionsBusy)event.preventDefault();});
