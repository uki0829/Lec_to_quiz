// Growing study collections, source retrieval, and durable practice state.
let materialId=null, materialDirty=true, collectionId=null, parentQuizId=null, parentQuizTitle='';
let activeJob=null, lastFailedJob=null, saveTimer=null, pollToken=0;
let connection={connected:false}, pendingGeneration=null, currentCollection=null, collectionAction='create';
let renderedMaterialsKey='', renderedQuizzesKey='', renderedCollectionsKey='';
let composerStep='upload',composerMaterialId=null,composerLoadedTitle='',composerReady=false,composerJobId=null;
let bankRows=[],bankKey='';
let savedSets=[],collectionRows=[],currentView='library',activeLibraryTab='sets',pendingEntry=null,toastTimer=null;
async function api(url,options={}) {
  const response=await fetch(url,options);let body;
  try {body=await response.json();}catch{throw Error('The local server returned an unreadable response.');}
  if(!response.ok)throw Error(body.error||body.detail||'The request could not be completed.');
  return body;
}
function saveSnapshot(review=$('#summary').hidden===false) {
  try {const q=quiz?{...quiz,progress:{index,answers:structuredClone(answers),review}}:null;
    localStorage.setItem('lecture-lab-state',JSON.stringify({collectionId,parentQuizId,parentQuizTitle,materialId,activeJob,pendingGeneration,
      view:currentView,libraryTab:activeLibraryTab,lastFailedJob,creator:{open:$('#composer-dialog').open,step:composerStep,materialId:composerMaterialId,title:composerLoadedTitle,jobId:composerJobId,heading:$('#composer-title').textContent},quiz:q?.id?{id:q.id,mode:q.mode,progress:q.progress}:q,format,request:$('#request').value,count:$('#count').value,difficulty:$('#difficulty').value}));
  }catch{}
}
function scheduleSave(review=false) {
  clearTimeout(saveTimer);saveSnapshot(review);if(!quiz?.id||quiz.mode!=='generated'||quiz.format==='cheatsheet')return;
  const id=quiz.id,progress={index,answers:structuredClone(answers),review};
  const saved=savedSets.find(q=>q.id===id);
  if(saved)saved.answeredCount=Object.values(answers).filter(a=>a.submitted).length;
  saveTimer=setTimeout(()=>api('/api/quizzes/'+id+'/progress',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(progress)})
    .catch(()=>message('Progress could not be saved. Your quiz remains available.',true)),250);
}
function setBusy(value) {
  busy=value;$('#composer-processing').hidden=!value;
  for(const id of ['generate','process-material','files','composer-files','notes','composer-notes','request','difficulty','composer-collection','composer-parent','reset-material','saved-materials','create-collection','rename-collection','build-followup','saved-quizzes','header-create','open-composer','open-upload','materials-add','collection-filter','upload-continue','use-saved-materials','composer-back','composer-retry'])$('#'+id).disabled=value;
  document.querySelectorAll('[data-module],[data-format],[data-count],.collection-button,.folder-delete,.material-actions button').forEach(b=>b.disabled=value);
  $('#rename-collection').disabled=value||!collectionId;
  $('#generate').textContent=value?'Creating…':generationLabel();
  $('#process-material').textContent=value?'Adding materials…':'Add materials';
  $('#job-actions').hidden=!(value||lastFailedJob);$('#cancel-job').hidden=!activeJob;
  if(!value){$('#job-panel').hidden=!activeJob&&!lastFailedJob;if(lastFailedJob){$('#retry-job').hidden=false;$('#edit-failed').hidden=false;}}
  if(value){$('#edit-failed').hidden=true;$('#job-panel').hidden=false;$('#job-panel').classList.remove('failed');}
  updateComposerState();renderQuestionBank();
}
async function checkConnection() {
  try {connection=await api('/api/config');$('#connection-status').textContent=connection.connected?'OpenAI connected':'Add OPENAI_API_KEY to .env, then restart.';

  }catch(err){$('#connection-status').textContent=err.message;}
}
$('#refresh-connection').onclick=checkConnection;
$('#notes').addEventListener('input',()=>materialDirty=true);
for(const id of ['request','count','difficulty'])$('#'+id).addEventListener('change',()=>saveSnapshot());
function updateFollowup() {
  $('#followup-context').hidden=!parentQuizId;$('#followup-label').textContent='Building on: '+parentQuizTitle;$('#composer-parent').value=parentQuizId||'';
  if(typeof syncMenus==='function')syncMenus();
}
function updateQuizContext(q) {
  const live=q.id&&q.mode==='generated';$('#quiz-context').hidden=!live;$('#build-followup').hidden=!live;showView('study');
  $('#original-request').textContent=q.request?.submitted?.prompt||q.request?.resolved?.prompt||'The original request was not recorded for this older quiz.';
}
$('#clear-followup').onclick=()=>{parentQuizId=null;parentQuizTitle='';updateFollowup();saveSnapshot();};
$('#build-followup').onclick=async()=>{
  if(!quiz?.id||quiz.mode!=='generated'||busy)return;
  try {const q=await api('/api/quizzes/'+quiz.id);if(q.collectionId!==collectionId)await selectCollection(q.collectionId);
    const settings=q.request?.resolved||{};parentQuizId=q.id;parentQuizTitle=q.title;
    $('#request').value=settings.prompt||q.title;$('#count').value=String(settings.count||q.questions.length);
    $('#difficulty').value=settings.difficulty||'intermediate';document.querySelector('[data-format="'+(settings.format||q.format)+'"]').click();
    updateFollowup();openComposer(null,true);saveSnapshot();$('#request').focus();
    message('Edit your next request.');
  }catch(err){message(err.message,true);}
};
async function refreshLibrary() {
  const data=await api('/api/collections');collectionRows=data.collections;
  const key=JSON.stringify(data.collections);
  if(key!==renderedCollectionsKey){renderedCollectionsKey=key;
    const options='<option value="" disabled>Choose a study folder</option>'+data.collections.map(c=>'<option value="'+esc(c.id)+'" data-meta="'+esc(folderContents(c))+'">'+esc(folderName(c.name))+'</option>').join('');
    $('#saved-materials').innerHTML=options;$('#composer-collection').innerHTML=options;$('#collection-filter').innerHTML=options;
  }
  $('#saved-materials').value=collectionId||'';$('#composer-collection').value=collectionId||'';$('#collection-filter').value=collectionId||'';
  $('#rename-collection').disabled=busy||!collectionId;
  renderCollectionNav();await refreshCollection();return data.collections;
}
function folderName(name){
  if(!/\.(pdf|png|jpe?g|webp|mp3|wav|ogg|flac|m4a|mp4|webm|txt)$/i.test(name))return name;
  const text=name.replace(/\.[^.]+$/,'').replace(/[-_]+/g,' ');return text.charAt(0).toUpperCase()+text.slice(1);
}
function folderContents(c){
  const parts=[];
  if(c.fileCount)parts.push(c.fileCount+' file'+(c.fileCount===1?'':'s'));
  if(c.noteCount)parts.push(c.noteCount+' note'+(c.noteCount===1?'':'s'));
  const extension=c.name?.match(/\.(pdf|png|jpe?g|webp|mp3|wav|ogg|flac|m4a|mp4|webm|txt)$/i)?.[1];
  if(extension&&c.fileCount)parts.push(extension.toUpperCase());
  return parts.join(' · ')||(c.materialCount?c.materialCount+' upload'+(c.materialCount===1?'':'s'):'Empty');
}
function renderCollectionNav(){
  const markup=collectionRows.map(c=>'<div class="folder-row"><button class="collection-button" data-collection="'+esc(c.id)+'" aria-current="'+String(c.id===collectionId)+'" title="'+esc(c.name)+'">'+icon('folder')+'<span class="folder-copy"><strong class="folder-name">'+esc(folderName(c.name))+'</strong><small class="folder-count">'+esc(folderContents(c))+'</small></span>'+icon('chevron-right')+'</button><button class="folder-delete icon-button" data-delete-folder="'+esc(c.id)+'" aria-label="Delete folder '+esc(folderName(c.name))+'" title="Delete folder">'+icon('trash-2')+'</button></div>').join('');
  if($('#collection-nav').innerHTML!==markup){$('#collection-nav').innerHTML=markup;$('#collection-nav').querySelectorAll('[data-collection]').forEach(b=>b.onclick=()=>selectCollection(b.dataset.collection).catch(err=>message(err.message,true)));}
  $('#collection-nav').querySelectorAll('[data-delete-folder]').forEach(b=>b.onclick=()=>previewFolderDeletion(b.dataset.deleteFolder,b));
  $('#collection-nav').querySelectorAll('button').forEach(b=>b.disabled=busy);
}
function renderQuizGrid(){
  const search=$('#search-sets').value.trim().toLowerCase();
  const selectedType=$('#set-format-filter').value;
  const sets=savedSets.filter(q=>(!selectedType||q.format===selectedType)&&(q.title+' '+formatName(q.format)).toLowerCase().includes(search));
  $('#sets-count').textContent=savedSets.length;
  $('#quiz-grid').innerHTML=sets.map(q=>'<button class="quiz-card" data-quiz="'+esc(q.id)+'"><span class="card-top"><span class="card-format">'+icon(formatIcon(q.format))+esc(formatName(q.format))+'</span><span class="card-count">'+(q.format==='cheatsheet'?q.sectionCount+' sections':q.questionCount+' questions')+'</span></span><h3>'+esc(q.title)+'</h3><span class="card-cta"><span>'+ (q.format==='cheatsheet'?'Open sheet':q.answeredCount?'Continue · '+q.answeredCount+'/'+q.questionCount:'Study')+'</span>'+icon('arrow-right')+'</span></button>').join('')+
    (!search?'<button class="quiz-card new-set-card" id="new-set-card">'+icon('plus')+'<strong>Create study set</strong></button>':!sets.length?'<p class="empty-results">No study sets match that search.</p>':'');
  $('#quiz-grid').querySelectorAll('[data-quiz]').forEach(b=>b.onclick=()=>openQuiz(b.dataset.quiz));
  $('#new-set-card')?.addEventListener('click',()=>openComposer());
}
async function refreshCollection() {
  if(!collectionId){currentCollection=null;savedSets=[];bankRows=[];bankKey='';renderQuestionBank();renderedMaterialsKey='';renderedQuizzesKey='';$('#library-title').textContent='Create new';$('#collection-breadcrumb').textContent='Collections';$('#collection-overview').textContent='Create a study folder.';$('#collection-materials').innerHTML='<p class="empty-results">Create a study folder.</p>';$('#materials-count').textContent='0';$('#saved-quizzes').innerHTML='<option value="">Choose a set</option>';$('#composer-parent').innerHTML='<option value="">No previous set</option>';renderQuizGrid();updateComposerState();return;}
  const cid=collectionId;const [c,saved,bank]=await Promise.all([api('/api/collections/'+cid),api('/api/quizzes?collectionId='+encodeURIComponent(cid)),api('/api/collections/'+cid+'/question-bank')]);
  if(cid!==collectionId)return;currentCollection=c;savedSets=saved.quizzes;bankRows=bank.questions;const newBankKey=JSON.stringify(bankRows);if(newBankKey!==bankKey){bankKey=newBankKey;renderQuestionBank();syncCardStar();}
  $('#library-title').textContent='Create new';$('#collection-breadcrumb').textContent=c.name;
  const ready=c.materials.filter(m=>m.searchReady).length;
  $('#collection-overview').textContent=ready+' ready lecture'+(ready===1?'':'s')+' · '+savedSets.length+' study sets'+(ready<c.materials.length?' · '+(c.materials.length-ready)+' materials still need processing':'');
  $('#materials-count').textContent=c.materials.length;
  const materialsKey=cid+JSON.stringify(c.materials);
  if(materialsKey!==renderedMaterialsKey){renderedMaterialsKey=materialsKey;
    $('#collection-materials').innerHTML=c.materials.map(m=>'<article class="material-card" data-material-title="'+esc(m.title.toLowerCase())+'"><div class="material-title">'+icon('file-text')+'<strong>'+esc(m.title)+'</strong></div><div class="material-state">'+esc(m.searchReady?'Ready for practice':m.status==='ready'?'Indexing: '+(m.jobStatus||'pending'):m.status)+' · '+m.sourceCount+' source sections</div><div class="material-actions"><button class="quiet" data-view="'+esc(m.id)+'">'+icon('book-open')+'View sources</button>'+(!m.searchReady?'<button class="quiet" data-process="'+esc(m.id)+'">'+icon('rotate-ccw')+(['queued','running'].includes(m.jobStatus)?'Check progress':'Process / retry')+'</button>':'')+'<button class="quiet danger" data-delete="'+esc(m.id)+'" aria-label="Remove '+esc(m.title)+'">'+icon('trash-2')+'</button></div></article>').join('')||'<p class="empty-results">Add your first lecture.</p>';
    $('#collection-materials').querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>loadMaterial(b.dataset.view).catch(err=>message(err.message,true)));
    $('#collection-materials').querySelectorAll('[data-process]').forEach(b=>b.onclick=()=>resumeMaterial(b.dataset.process));
    $('#collection-materials').querySelectorAll('[data-delete]').forEach(b=>b.onclick=()=>removeMaterial(b.dataset.delete));
  }
  const quizzesKey=cid+JSON.stringify(saved.quizzes.map(q=>({id:q.id,title:q.title,format:q.format,count:q.questionCount,sections:q.sectionCount,answered:q.answeredCount})));
  if(quizzesKey!==renderedQuizzesKey){renderedQuizzesKey=quizzesKey;
    $('#saved-quizzes').innerHTML='<option value="">Choose a set</option>'+saved.quizzes.map(q=>'<option value="'+esc(q.id)+'">'+esc(formatName(q.format))+' · '+esc(q.title)+'</option>').join('');
    const parentOptions='<option value="">No previous set</option>'+savedSets.map(q=>'<option value="'+esc(q.id)+'">Build on: '+esc(q.title)+'</option>').join('');
    $('#composer-parent').innerHTML=parentOptions;$('#composer-parent').value=parentQuizId||'';renderQuizGrid();
  }
  $('#saved-quizzes').value=quiz?.collectionId===collectionId?quiz.id||'':'';
  if(busy)document.querySelectorAll('.material-actions button').forEach(b=>b.disabled=true);
  filterMaterials();updateComposerState();
}
function clearUpload() {attachments=[];$('#notes').value='';$('#composer-notes').value='';materialId=null;materialDirty=true;listFiles();$('#material-summary').innerHTML='';}
async function selectCollection(id) {collectionId=id||null;parentQuizId=null;parentQuizTitle='';updateFollowup();showView('library');await refreshLibrary();saveSnapshot();}
$('#collection-filter').onchange=$('#saved-materials').onchange=e=>selectCollection(e.target.value).catch(err=>message(err.message,true));
$('#reset-material').onclick=()=>{if(busy)return;clearUpload();saveSnapshot();message('Upload cleared.');};
function collectionDialog(action) {collectionAction=action;$('#collection-dialog-title').textContent=action==='rename'?'Rename folder':'New study folder';$('#collection-name').value=action==='rename'?currentCollection?.name||'':'';$('#collection-error').textContent='';$('#collection-dialog').showModal();$('#collection-name').focus();}
$('#create-collection').onclick=()=>collectionDialog('create');$('#rename-collection').onclick=()=>collectionDialog('rename');
$('#close-collection').onclick=()=>{pendingEntry=null;$('#collection-dialog').close();};
$('#collection-form').onsubmit=async e=>{e.preventDefault();const name=$('#collection-name').value.trim();if(!name)return;
  const button=e.currentTarget.querySelector('[type="submit"]');button.disabled=true;
  try {const c=await api('/api/collections'+(collectionAction==='rename'?'/'+collectionId:''),{method:collectionAction==='rename'?'PATCH':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});
    $('#collection-dialog').close();await selectCollection(c.id);message('Folder saved.');if(pendingEntry){const entry=pendingEntry;pendingEntry=null;if(entry.kind==='composer')openComposer(entry.format);else openUpload();}
  }catch(err){$('#collection-error').textContent=err.message;}finally{button.disabled=false;}
};
async function loadMaterial(id) {
  const m=await api('/api/materials/'+id);materialId=id;
  const preview=m.sources.map(s=>'<button type="button" data-source="'+esc(s.id)+'">'+esc(s.name)+' · '+esc(s.locator)+'</button>').join('');
  $('#material-summary').innerHTML='<strong>'+esc(m.title)+'</strong><br>'+m.sources.length+' source sections'+
    (m.files.some(f=>f.kind==='video')?'<br>Video visuals are sampled once per minute; brief content may be missed.':'')+'<div class="source-preview">'+preview+'</div>';
  $('#material-summary').querySelectorAll('[data-source]').forEach(b=>b.onclick=()=>{$('#material-dialog').close();openSource(b.dataset.source);});$('#material-title').textContent=m.title;$('#material-dialog').showModal();saveSnapshot();return m;
}
$('#saved-quizzes').onchange=async e=>{if(!e.target.value)return;
  try {const q=validateImported(await api('/api/quizzes/'+e.target.value));startQuiz(q);if(q.progress?.review)showSummary();message('Saved quiz restored.');}
  catch(err){message(err.message,true);}
};
let folderDeletion=null,folderDeleting=false,folderDeleteTrigger=null;
async function previewFolderDeletion(id,trigger) {
  try {
    const impact=await api('/api/collections/'+id+'/deletion-impact');
    folderDeletion={id,revision:impact.revision};folderDeleteTrigger=trigger;
    $('#delete-folder-title').textContent='Delete “'+folderName(impact.name)+'”?';
    const list=(title,items)=>'<div class="deletion-group"><strong>'+title+' · '+items.length+'</strong>'+(items.length?'<ul>'+items.map(item=>'<li>'+esc(item.title)+'</li>').join('')+'</ul>':'')+'</div>';
    $('#delete-folder-impact').innerHTML=list('Materials',impact.materials)+list('Saved sets',impact.quizzes);
    $('#delete-folder-error').textContent=impact.blocked?'Stop active processing before deleting this folder.':'';
    $('#confirm-delete-folder').disabled=impact.blocked;
    $('#delete-folder-dialog').showModal();$('#cancel-delete-folder').focus();
  }catch(err){message(err.message,true);}
}
function closeFolderDeletion(){if(folderDeleting)return;$('#delete-folder-dialog').close();folderDeletion=null;folderDeleteTrigger?.focus();}
$('#close-delete-folder').onclick=$('#cancel-delete-folder').onclick=closeFolderDeletion;
$('#delete-folder-dialog').addEventListener('cancel',e=>{if(folderDeleting)e.preventDefault();});
$('#confirm-delete-folder').onclick=async()=>{
  if(!folderDeletion||folderDeleting)return;
  const {id,revision}=folderDeletion;folderDeleting=true;
  $('#confirm-delete-folder').disabled=true;$('#cancel-delete-folder').disabled=true;$('#close-delete-folder').disabled=true;
  $('#delete-folder-error').textContent='';
  try {
    const result=await api('/api/collections/'+id+'?expectedRevision='+encodeURIComponent(revision),{method:'DELETE'});
    if(result.deletedQuizIds.includes(quiz?.id)||(quiz?.mode==='bank'&&quiz.questions.some(q=>result.deletedQuizIds.includes(q.originQuizId)))){
      clearTimeout(saveTimer);quiz=null;answers={};index=0;
      for(const key of ['cheatsheet','study','summary','quiz-context','build-followup'])$('#'+key).hidden=true;
      $('#empty').hidden=false;$('#mode-badge').textContent='Ready when you are';showView('library');
    }
    if(result.deletedQuizIds.includes(parentQuizId)){parentQuizId=null;parentQuizTitle='';updateFollowup();}
    if(result.deletedMaterialIds.includes(materialId)){materialId=null;$('#material-summary').innerHTML='';}
    if(result.deletedMaterialIds.includes(composerMaterialId)){
      composerMaterialId=null;composerLoadedTitle='';composerReady=false;composerJobId=null;composerStep='upload';
    }
    if(result.deletedJobIds.includes(lastFailedJob)){lastFailedJob=null;$('#job-panel').hidden=true;$('#retry-job').hidden=true;}
    if(collectionId===id){collectionId=collectionRows.find(c=>c.id!==id)?.id||null;pendingGeneration=null;showView('library');}
    folderDeletion=null;$('#delete-folder-dialog').close();await refreshLibrary();saveSnapshot();message('Folder deleted.');
    $('#create-collection').focus();
  }catch(err){$('#delete-folder-error').textContent=err.message;}
  finally{folderDeleting=false;$('#confirm-delete-folder').disabled=false;$('#cancel-delete-folder').disabled=false;$('#close-delete-folder').disabled=false;}
};

async function removeMaterial(id) {
  try {const impact=await api('/api/materials/'+id+'/deletion-impact');const title=currentCollection?.materials.find(m=>m.id===id)?.title||'this material';
    if(!confirm('Remove '+title+' and its source files? '+(impact.quizzes.length?'This also deletes '+impact.quizzes.length+' quizzes that cite it: '+impact.quizzes.map(q=>q.title).join(', '):'No saved quizzes cite it.')))return;
    const result=await api('/api/materials/'+id,{method:'DELETE'});
    if(result.deletedQuizIds.includes(quiz?.id)||(quiz?.mode==='bank'&&quiz.questions.some(q=>result.deletedQuizIds.includes(q.originQuizId)))){quiz=null;answers={};$('#cheatsheet').hidden=true;$('#study').hidden=true;$('#summary').hidden=true;$('#empty').hidden=false;$('#quiz-context').hidden=true;$('#build-followup').hidden=true;$('#mode-badge').textContent='Ready when you are';showView('library');}
    if(result.deletedQuizIds.includes(parentQuizId)){$('#clear-followup').click();}
    if(materialId===id){materialId=null;$('#material-summary').innerHTML='';}
    saveSnapshot();await refreshLibrary();message('Material and dependent quizzes removed.');
  }catch(err){message(err.message,true);}
}
function showJob(job) {$('#job-panel').hidden=false;const fraction=job.total?Math.min(1,job.completed/job.total):null;$('#job-status').innerHTML='<span>'+esc(['failed','cancelled','interrupted'].includes(job.status)?friendlyJobError(job):job.stage)+'</span>'+(fraction!==null?'<progress class="job-meter" value="'+fraction+'" max="1" aria-label="Processing progress"></progress><span class="tiny">'+job.completed+' of '+job.total+' units</span>':'');$('#composer-job-status').innerHTML=$('#job-status').innerHTML;}
function pause(ms){return new Promise(resolve=>setTimeout(resolve,ms));}
async function watchJob(jobId) {
  const token=++pollToken;activeJob=jobId;lastFailedJob=null;$('#retry-job').hidden=true;setBusy(true);saveSnapshot();
  while(token===pollToken){let job;
    try {job=await api('/api/jobs/'+jobId);}catch(err){setBusy(false);lastFailedJob=jobId;$('#job-actions').hidden=false;$('#cancel-job').hidden=true;$('#retry-job').hidden=false;$('#retry-job').textContent='Resume checking';throw err;}
    showJob(job);
    if(['completed','failed','cancelled','interrupted'].includes(job.status)){activeJob=null;setBusy(false);saveSnapshot();await refreshLibrary();
      if(job.status!=='completed'){$('#job-panel').classList.add('failed');lastFailedJob=jobId;$('#job-actions').hidden=false;$('#cancel-job').hidden=true;$('#retry-job').hidden=false;$('#edit-failed').hidden=job.kind!=='quiz';saveSnapshot();throw Error(friendlyJobError(job));}$('#job-panel').hidden=true;return job;
    }await pause(2000);
  }throw Error('Stopped following this job.');
}
async function resumeMaterial(id) {
  if(busy)return;
  try {const m=currentCollection.materials.find(m=>m.id===id);let next;
    const old=m.jobId?await api('/api/jobs/'+m.jobId):null;
    if(old&&['queued','running'].includes(old.status))next={jobId:old.id};
    else if(old&&['failed','cancelled','interrupted'].includes(old.status))next=await api('/api/jobs/'+old.id+'/retry',{method:'POST'});
    else next=await api('/api/materials/'+id+'/index',{method:'POST'});
    await watchJob(next.jobId);await loadMaterial(id);message('Material ready.');
  }catch(err){message(err.message,true);}finally{if(!activeJob)setBusy(false);}
}
async function finishComposerMaterial(id) {
  const m=await api('/api/materials/'+id);
  if(!m.searchReady)throw Error('Lecture not ready. Finish processing or retry.');
  collectionId=m.collectionId;composerMaterialId=id;composerLoadedTitle=m.title;composerReady=true;composerJobId=null;
  await refreshLibrary();composerStep='options';updateComposerState();saveSnapshot();
  if($('#composer-dialog').open)$('#request').focus();
}
async function ensureMaterial(forComposer=false) {
  if(!collectionId&&!forComposer)throw Error('Create or choose a study folder.');
  const notes=(forComposer?$('#composer-notes').value:$('#notes').value).trim();if(!notes&&!attachments.length)throw Error('Choose lecture files or paste new notes to add.');
  const body=new FormData();body.append('notes',notes);if(collectionId)body.append('collectionId',collectionId);attachments.forEach(f=>body.append('files',f));
  setBusy(true);$('#job-status').textContent='Uploading your lecture…';$('#composer-job-status').textContent='Uploading your lecture…';
  const result=await api('/api/materials',{method:'POST',body});materialId=result.materialId;materialDirty=false;
  // Uploads are durable before extraction starts; retries reuse this material.
  if(forComposer){composerMaterialId=result.materialId;composerJobId=result.jobId;composerReady=false;composerLoadedTitle=attachments.map(f=>f.name).join(', ')||'Pasted lecture notes';}
  attachments=[];$('#notes').value='';$('#composer-notes').value='';listFiles();saveSnapshot();
  if($('#upload-dialog').open)$('#upload-dialog').close();await watchJob(result.jobId);
  if(forComposer)await finishComposerMaterial(result.materialId);
  return result.materialId;
}
$('#upload-continue').onclick=async()=>{
  if(busy)return;
  try {
    if(!attachments.length&&!$('#composer-notes').value.trim()&&composerReady){composerStep='options';updateComposerState();saveSnapshot();$('#request').focus();return;}
    await checkConnection();if(!connection.connected)throw Error('Connect OpenAI to process lectures.');
    await ensureMaterial(true);message('Lecture ready.');
  }catch(err){message(err.message,true);}finally{if(!activeJob)setBusy(false);saveSnapshot();}
};
$('#use-saved-materials').onclick=()=>{
  if(busy||!currentCollection?.materials.some(m=>m.searchReady))return;
  // A deliberate choice: discard only unsent inputs, never stored lectures.
  clearUpload();composerMaterialId=null;composerJobId=null;composerLoadedTitle='Your saved lectures';composerReady=true;composerStep='options';
  updateComposerState();saveSnapshot();$('#request').focus();
};
$('#composer-back').onclick=()=>{if(busy)return;composerStep='upload';updateComposerState();saveSnapshot();$('#composer-files').focus();};
$('#process-material').onclick=async()=>{if(busy)return;pendingGeneration=null;
  try {await checkConnection();if(!connection.connected)throw Error('Connect OpenAI to process lectures.');await ensureMaterial();message('Materials added.');setLibraryTab('materials');}
  catch(err){message(err.message,true);}finally{if(!activeJob)setBusy(false);saveSnapshot();}
};
async function generateQuiz(params) {
  const result=await api('/api/quizzes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(params)});pendingGeneration=null;if($('#composer-dialog').open)$('#composer-dialog').close();
  const job=await watchJob(result.jobId);if(job.result.status!=='ready'){message(job.result.message||'Add clearer material or choose another topic.',true);return;}
  const q=validateImported(await api('/api/quizzes/'+job.result.quizId));parentQuizId=null;updateFollowup();$('#search-sets').value='';$('#set-format-filter').value='';startQuiz(q);
  message('Study set ready.');
}
$('#generate').onclick=async()=>{
  if(busy)return;const prompt=$('#request').value.trim();if(!prompt)return message('Add a topic or instructions for your study set.',true);
  if(composerStep!=='options'||!composerReady||!currentCollection?.materials.some(m=>m.searchReady))return message('Load your lecture before choosing practice settings.',true);
  if(!collectionId)return message('Choose a study folder.',true);
  const params={collectionId,parentQuizId:parentQuizId||undefined,prompt,format,count:Number($('#count').value),difficulty:$('#difficulty').value};pendingGeneration=params;setBusy(true);
  try {await checkConnection();if(!connection.connected)throw Error('Add OPENAI_API_KEY to .env, then restart.');await generateQuiz(params);}
  catch(err){message(err.message,true);}finally{pendingGeneration=null;if(!activeJob)setBusy(false);saveSnapshot();}
};
$('#cancel-job').onclick=async()=>{if(!activeJob)return;try{await api('/api/jobs/'+activeJob+'/cancel',{method:'POST'});message('Cancelling after the current request.');}catch(err){message(err.message,true);}};
$('#retry-job').onclick=async()=>{if(!lastFailedJob||busy)return;
  try {const old=await api('/api/jobs/'+lastFailedJob);const next=['failed','interrupted','cancelled'].includes(old.status)?await api('/api/jobs/'+lastFailedJob+'/retry',{method:'POST'}):{jobId:old.id};
    $('#retry-job').textContent='Retry job';const job=await watchJob(next.jobId);
    if(job.kind==='quiz'&&job.result?.status==='ready')startQuiz(await api('/api/quizzes/'+job.result.quizId));else if(job.result?.message)message(job.result.message,true);else if(composerMaterialId&&job.material_id===composerMaterialId)await finishComposerMaterial(composerMaterialId);else await loadMaterial(job.material_id);
  }catch(err){message(err.message,true);}finally{if(!activeJob)setBusy(false);}
};
async function openSource(id) {
  $('#source-dialog').showModal();$('#source-content').textContent='Loading source…';
  try {
    if(id==='sample'){$('#source-title').textContent='Sample gradient-descent lecture';$('#source-content').innerHTML='<p class="dialog-note">Included sample lecture. </p><div class="extracted-text">'+esc(lecture)+'</div>';return;}
    const s=await api('/api/sources/'+encodeURIComponent(id));$('#source-title').textContent=s.name+' · '+s.locator;
    let html='';
    if(s.kind==='pdf')html='<img alt="Original lecture PDF page '+s.page+'" src="'+esc(s.previewUrl)+'"><p><a href="'+esc(s.fileUrl)+'" download="'+esc(s.name)+'">Download original PDF</a></p>';
    else if(s.kind==='image')html='<img alt="Original lecture image" src="'+esc(s.fileUrl)+'">';
    else if(['audio','video'].includes(s.kind))html='<'+s.kind+' id="source-player" controls preload="metadata" src="'+esc(s.fileUrl)+'"></'+s.kind+'>'+(s.frameUrl?'<p class="dialog-note">Sampled slide frame</p><img alt="Slide frame at the cited timestamp" src="'+esc(s.frameUrl)+'">':'');
    if(s.uncertainty)html+='<details><summary>Source notes</summary><p>'+esc(s.uncertainty)+'</p></details>';
    html+='<details open><summary>Extracted content</summary><div class="extracted-text">'+esc(s.text)+'</div></details>';
    $('#source-content').innerHTML=html;
    const player=$('#source-player');if(player)player.addEventListener('loadedmetadata',()=>{player.currentTime=s.start||0;},{once:true});
  }catch(err){$('#source-content').textContent=err.message;}
}
$('#close-source').onclick=()=>{$('#source-player')?.pause();$('#source-dialog').close();};
$('#source-dialog').addEventListener('close',()=>$('#source-player')?.pause());

function icon(name){return '<img class="icon" src="/static/icons/'+name+'.svg" alt="" aria-hidden="true">';}
function formatName(type){return ({mcq:'Quiz',flashcard:'Flashcards',calculation:'Calculation',cheatsheet:'Cheat Sheet'})[type]||'Study set';}
function formatIcon(type){return ({mcq:'clipboard-list',flashcard:'layers',calculation:'calculator',cheatsheet:'file-text'})[type]||'book-open';}
function applyToast(text,error){
  clearTimeout(toastTimer);
  for(const id of ['composer-message','upload-message']){const el=$('#'+id);el.className=text?'notice'+(error?' error':''):'';el.textContent=text;}
  if(text&&!error)toastTimer=setTimeout(()=>{for(const id of ['setup-message','composer-message','upload-message'])$('#'+id).textContent='';},7000);
}
function showView(view){currentView=view;$('#library-view').hidden=view!=='library';$('#study-view').hidden=view!=='study';}
function filterMaterials(){
  const search=$('#search-sets').value.trim().toLowerCase();
  const cards=Array.from($('#collection-materials').querySelectorAll('[data-material-title]'));
  cards.forEach(card=>card.hidden=!card.dataset.materialTitle.includes(search));
  $('#materials-empty').hidden=!cards.length||cards.some(card=>!card.hidden);
}
function setLibraryTab(tab){
  activeLibraryTab=['sets','materials','bank'].includes(tab)?tab:'sets';
  for(const name of ['sets','materials','bank']){
    $('#'+name+'-panel').hidden=activeLibraryTab!==name;
    $('#'+name+'-tab').setAttribute('aria-selected',String(activeLibraryTab===name));
  }
  const sets=activeLibraryTab==='sets';$('#set-format-filter').hidden=!sets;$('#set-format-label').hidden=!sets;
  $('#search-sets').disabled=false;$('#search-sets').placeholder=sets?'Search sets':activeLibraryTab==='bank'?'Search starred cards':'Search materials';
  $('#library-search-label').textContent=$('#search-sets').placeholder;
  renderQuizGrid();filterMaterials();renderQuestionBank();if(typeof syncMenus==='function')syncMenus();saveSnapshot();
}

function cardOrigin(q){return {quizId:q.originQuizId||quiz?.id,questionId:q.originQuestionId||q.id};}
function isQuestionStarred(q){const origin=cardOrigin(q);const found=bankRows.some(row=>row.originQuizId===origin.quizId&&row.originQuestionId===origin.questionId);return currentCollection&&quiz?.collectionId===collectionId?found:found||Boolean(q.starred);}
function syncCardStar(){
  const q=quiz?.questions?.[index],button=$('#flash-star');if(!q||!button)return;
  const starred=isQuestionStarred(q);button.setAttribute('aria-pressed',String(starred));button.setAttribute('aria-label',starred?'Unstar card':'Star card');button.classList.toggle('is-starred',starred);const img=button.querySelector?.('img');if(img)img.src='/static/icons/'+(starred?'star-filled':'star')+'.svg';
}
async function toggleQuestionStar(q){
  const origin=cardOrigin(q);if(!origin.quizId||q.starLoading)return;
  q.starLoading=true;const visibleQuiz=quiz;render();
  try{
    const result=await api('/api/quizzes/'+origin.quizId+'/questions/'+origin.questionId+'/star',{
      method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({starred:!isQuestionStarred(q)})});
    q.starred=result.starred;
    bankRows=bankRows.filter(row=>!(row.originQuizId===origin.quizId&&row.originQuestionId===origin.questionId));
    if(result.starred)bankRows.unshift({...q,originQuizId:origin.quizId,originQuestionId:origin.questionId,quizTitle:visibleQuiz.title});
    renderQuestionBank();saveSnapshot();
  }catch(err){message(err.message,true);}
  finally{q.starLoading=false;if(quiz===visibleQuiz&&quiz.questions[index]===q)render();}
}
async function requestFlashcardHint(q){
  if(q.hintLoading)return;
  const a=answers[q.id]||{};
  if(q.hint){answers[q.id]={...a,hintVisible:!a.hintVisible};render();return;}
  const origin=cardOrigin(q);if(!origin.quizId)return;
  const visibleQuiz=quiz;q.hintLoading=true;render();
  try{
    const result=await api('/api/quizzes/'+origin.quizId+'/questions/'+origin.questionId+'/hint',{method:'POST'});
    q.hint=result.hint;
    if(quiz===visibleQuiz){answers[q.id]={...answers[q.id],hintVisible:true};saveSnapshot();}
  }catch(err){message(err.message,true);}
  finally{q.hintLoading=false;if(quiz===visibleQuiz&&quiz.questions[index]===q)render();}
}
function renderQuestionBank(){
  const search=$('#search-sets').value.trim().toLowerCase();
  const rows=bankRows.filter(q=>(q.prompt+' '+q.quizTitle).toLowerCase().includes(search));
  $('#bank-count').textContent=bankRows.length;$('#practice-bank').disabled=!rows.length||busy;
  $('#bank-grid').innerHTML=rows.map(q=>'<button class="bank-card" data-bank-quiz="'+esc(q.originQuizId)+'" data-bank-question="'+esc(q.originQuestionId)+'">'+icon('star')+'<span><strong>'+esc(q.prompt)+'</strong><small>'+esc(q.quizTitle)+'</small></span>'+icon('arrow-right')+'</button>').join('')||'<p class="empty-results">'+(search?'No starred cards match.':'Star cards to practise later.')+'</p>';
  $('#bank-grid').querySelectorAll('[data-bank-quiz]').forEach(b=>b.onclick=()=>practiceQuestionBank(b.dataset.bankQuiz,b.dataset.bankQuestion));
}
function practiceQuestionBank(quizId=null,questionId=null){
  if(busy)return;
  const search=$('#search-sets').value.trim().toLowerCase();
  const rows=bankRows.filter(q=>quizId?q.originQuizId===quizId&&q.originQuestionId===questionId:(q.prompt+' '+q.quizTitle).toLowerCase().includes(search));
  if(!rows.length)return;
  startQuiz({title:'Question bank',format:'flashcard',mode:'bank',collectionId,questions:rows.map(q=>({...q,id:q.originQuizId+':'+q.originQuestionId,starred:true}))});
  saveSnapshot();
}
$('#practice-bank').onclick=()=>practiceQuestionBank();
function generationLabel(){return format==='cheatsheet'?'Create cheat sheet':'Create '+$('#count').value+' '+(format==='flashcard'?'flashcards':format==='mcq'?'quiz questions':'calculations');}
function updateComposerState(){
  const count=Number($('#count').value)||6;
  const ready=currentCollection?.materials.filter(m=>m.searchReady).length||0;
  // SQLite's ready/indexed status determines when practice may begin.
  const bound=composerMaterialId&&currentCollection?.materials.find(m=>m.id===composerMaterialId);
  const eligible=composerReady&&ready>0&&(!composerMaterialId||Boolean(bound?.searchReady));
  const options=composerStep==='options';
  $('#composer-upload-step').hidden=options;$('#composer-options-step').hidden=!options;
  $('#upload-step-label').setAttribute('aria-current',options?'false':'step');$('#options-step-label').setAttribute('aria-current',options?'step':'false');
  const hasInput=Boolean(attachments.length||$('#composer-notes').value.trim());
  $('#upload-continue').disabled=busy||(!hasInput&&!eligible);
  $('#upload-continue').textContent=busy?'Reading your lecture…':hasInput?'Upload and continue':eligible?'Continue to settings':'Upload and continue';
  $('#use-saved-materials').hidden=!ready||Boolean(composerMaterialId);$('#use-saved-materials').disabled=busy;
  $('#use-saved-materials').textContent='Use '+ready+' saved lecture'+(ready===1?'':'s')+' instead';
  
  $('#composer-uploaded').hidden=!composerMaterialId;
  $('#composer-uploaded').textContent=(eligible?'Ready: ':'Saved upload: ')+composerLoadedTitle+(eligible?'':' · Processing required.');
  $('#loaded-title').textContent=composerLoadedTitle||'Your lectures are ready';
  
  $('#composer-collection').disabled=busy||Boolean(composerMaterialId);
  
  $('#generate').disabled=busy||!options||!eligible||!$('#request').value.trim();
  if(!busy)$('#generate').textContent=generationLabel();
  $('#count-label').textContent=format==='cheatsheet'?'Sections':'Questions';$('#difficulty-field').hidden=format==='cheatsheet';
  document.querySelectorAll('[data-count]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.count)===count)));
  $('#composer-sources').textContent=ready?ready+' saved lecture'+(ready===1?'':'s')+' ready.':'No ready lectures.';
  $('#composer-retry').hidden=!composerJobId||!lastFailedJob||busy;$('#composer-retry').disabled=busy;
  const mentioned=inferRequestedFormat($('#request').value),mismatch=mentioned&&mentioned!==format;
  $('#format-conflict').hidden=!mismatch;
  if(typeof syncMenus==='function')syncMenus();
  if(mismatch){$('#format-conflict-text').textContent='Requested: '+formatName(mentioned).toLowerCase()+'. Selected: '+formatName(format).toLowerCase()+'.';$('#use-mentioned-format').textContent='Switch to '+formatName(mentioned).toLowerCase();$('#use-mentioned-format').dataset.formatTarget=mentioned;}
}
function openComposer(type=null,followup=false){
  if(busy)return;
  if(type)document.querySelector('[data-format="'+type+'"]').click();
  if(type==='cheatsheet'&&!followup)$('#request').value='Summarize key concepts and formulas.';
  composerMaterialId=null;composerJobId=null;composerLoadedTitle='';composerReady=false;composerStep='upload';
  if(!followup){parentQuizId=null;parentQuizTitle='';updateFollowup();}
  else if(currentCollection?.materials.some(m=>m.searchReady)){composerStep='options';composerReady=true;composerLoadedTitle='Your saved lectures';}
  for(const id of ['upload-dialog','material-dialog'])if($('#'+id).open)$('#'+id).close();
  message('');$('#composer-collection').value=collectionId||'';$('#composer-parent').value=parentQuizId||'';updateComposerState();
  $('#composer-title').textContent=type==='flashcard'?'Create flashcards':type==='calculation'?'Create calculation practice':type==='mcq'?'Create a quiz':type==='cheatsheet'?'Create cheat sheet':'Create study set';
  if(!$('#composer-dialog').open)$('#composer-dialog').showModal();
  $(composerStep==='upload'?'#composer-files':'#request').focus();saveSnapshot();
}
function openUpload(){
  if(busy)return;
  if(!collectionId){pendingEntry={kind:'upload'};collectionDialog('create');return;}
  if($('#composer-dialog').open)$('#composer-dialog').close();
  message('');$('#upload-collection').textContent='Study folder: '+folderName(currentCollection.name);
  $('#upload-dialog').showModal();
}
async function openQuiz(id){try{const q=validateImported(await api('/api/quizzes/'+id));startQuiz(q);if(q.progress?.review)showSummary();saveSnapshot();window.scrollTo({top:0,behavior:'smooth'});}catch(err){message(err.message,true);}}
function friendlyJobError(job){
  if((job.error||'').includes('Question IDs or formats'))return 'Format conflict. Choose a format and retry.';
  if(/source references|reference does not belong|selected evidence|supporting excerpt|selected excerpt/.test(job.error||''))return 'Source check failed. Retry using your saved lecture.';
  if(/generated (?:quiz|study set) failed validation/.test(job.error||''))return (job.error||'').replace(/^The generated (?:quiz|study set) failed validation: /,'')+'. Retry.';
  return job.error||'Processing was '+job.status+'. Retry to reuse completed work.';
}
$('#brand-home').onclick=()=>{const fromStudy=currentView==='study';showView('library');if(fromStudy)setLibraryTab('sets');saveSnapshot();};
$('#back-library').onclick=()=>{showView('library');setLibraryTab('sets');saveSnapshot($('#summary').hidden===false);};
for(const id of ['header-create','open-composer'])$('#'+id).onclick=()=>openComposer();
for(const id of ['open-upload','materials-add'])$('#'+id).onclick=openUpload;
document.querySelectorAll('[data-module]').forEach(b=>b.onclick=()=>openComposer(b.dataset.module));
$('#sidebar-sample').onclick=()=>{if(busy)return;document.querySelector('[data-format="flashcard"]').click();sampleQuiz();};
$('#composer-cancel').onclick=()=>$('#cancel-job').click();
$('#composer-retry').onclick=()=>{if(composerJobId){lastFailedJob=composerJobId;$('#retry-job').click();}};
$('#composer-notes').addEventListener('input',()=>{materialDirty=true;updateComposerState();});
$('#composer-dialog').addEventListener('close',()=>saveSnapshot());
$('#close-composer').onclick=()=>{$('#composer-dialog').close();saveSnapshot();};
$('#close-upload').onclick=()=>$('#upload-dialog').close();$('#close-material').onclick=()=>$('#material-dialog').close();
for(const name of ['sets','materials','bank'])$('#'+name+'-tab').onclick=()=>setLibraryTab(name);
for(const name of ['sets','materials','bank'])$('#'+name+'-tab').onkeydown=e=>{
  if(['ArrowLeft','ArrowRight'].includes(e.key)){
    e.preventDefault();const tabs=['sets','materials','bank'];const direction=e.key==='ArrowRight'?1:-1;
    setLibraryTab(tabs[(tabs.indexOf(activeLibraryTab)+direction+tabs.length)%tabs.length]);$('#'+activeLibraryTab+'-tab').focus();
  }
};
$('#search-sets').oninput=()=>{renderQuizGrid();filterMaterials();renderQuestionBank();};
$('#set-format-filter').onchange=renderQuizGrid;
$('#request').addEventListener('input',()=>{updateComposerState();saveSnapshot();});
document.querySelectorAll('[data-count]').forEach(b=>b.onclick=()=>{$('#count').value=b.dataset.count;updateComposerState();saveSnapshot();});
$('#use-mentioned-format').onclick=()=>document.querySelector('[data-format="'+$('#use-mentioned-format').dataset.formatTarget+'"]').click();
$('#composer-collection').onchange=async e=>{if(!e.target.value)return;try{await selectCollection(e.target.value);composerReady=Boolean(currentCollection?.materials.some(m=>m.searchReady));updateComposerState();}catch(err){message(err.message,true);}};
$('#composer-parent').onchange=async e=>{
  if(!e.target.value){$('#clear-followup').click();return;}
  try {const p=await api('/api/quizzes/'+e.target.value);if(p.collectionId!==collectionId)throw Error('Choose a set from this collection.');parentQuizId=p.id;parentQuizTitle=p.title;updateFollowup();if(!$('#request').value.trim())$('#request').value=p.request?.resolved?.prompt||p.title;updateComposerState();saveSnapshot();}
  catch(err){message(err.message,true);}
};
$('#composer-materials').onclick=()=>{$('#composer-dialog').close();showView('library');setLibraryTab('materials');};
$('#composer-files').onchange=e=>{addFiles(e.target.files);e.target.value='';};
['dragenter','dragover'].forEach(t=>$('#composer-drop').addEventListener(t,e=>{e.preventDefault();$('#composer-drop').classList.add('drag');}));
['dragleave','drop'].forEach(t=>$('#composer-drop').addEventListener(t,e=>{e.preventDefault();$('#composer-drop').classList.remove('drag');if(t==='drop')addFiles(e.dataTransfer.files);}));
$('#edit-failed').onclick=async()=>{try{if(!lastFailedJob)return openComposer();const job=await api('/api/jobs/'+lastFailedJob);const p=(await api('/api/jobs/'+lastFailedJob+'/request')).request||{};$('#request').value=p.prompt||$('#request').value;if(p.format)document.querySelector('[data-format="'+p.format+'"]').click();$('#count').value=String(p.count||6);$('#difficulty').value=p.difficulty||'intermediate';parentQuizId=p.parentQuizId||null;parentQuizTitle=parentQuizId?savedSets.find(q=>q.id===parentQuizId)?.title||'Previous set':'';updateFollowup();openComposer(null,true);}catch(err){message(err.message,true);}};

async function boot() {
  setBusy(true);
  let state;try{state=JSON.parse(localStorage.getItem('lecture-lab-state')||'null');}catch{}
  try {await checkConnection();
    if(state?.collectionId)collectionId=state.collectionId;
    else if(state?.materialId){try{collectionId=(await api('/api/materials/'+state.materialId)).collectionId;}catch{}}
    const collections=await api('/api/collections');if(!collections.collections.some(c=>c.id===collectionId))collectionId=collections.collections[0]?.id||null;
    await refreshLibrary();
    if(state){$('#request').value=state.request||'';$('#count').value=state.count||'6';$('#difficulty').value=state.difficulty||'intermediate';
      format=['mcq','flashcard','calculation','cheatsheet'].includes(state.format)?state.format:'mcq';
      document.querySelectorAll('[data-format]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.format===format)));
      if(state.quiz){try{let q=state.quiz.id?await api('/api/quizzes/'+state.quiz.id):state.quiz;q=validateImported(q);if(state.quiz.progress)q.progress=state.quiz.progress;startQuiz(q);if(q.progress?.review)showSummary();}catch{message('Quiz unavailable. Choose another saved set.',true);}}
      if(state.parentQuizId){try{const p=await api('/api/quizzes/'+state.parentQuizId);if(p.collectionId===collectionId){parentQuizId=p.id;parentQuizTitle=p.title;updateFollowup();}}catch{}}
      showView(state.view||'library');setLibraryTab(state.libraryTab||'sets');
      if(state.creator?.open){const c=state.creator;$('#composer-title').textContent=c.heading||'Create study set';composerMaterialId=c.materialId||null;composerJobId=c.jobId||null;composerLoadedTitle=c.title||'';
        if(composerMaterialId){try{const m=await api('/api/materials/'+composerMaterialId);composerReady=m.collectionId===collectionId&&m.searchReady;}catch{composerMaterialId=null;composerJobId=null;}}
        else composerReady=Boolean(currentCollection?.materials.some(m=>m.searchReady));
        composerStep=c.step==='options'&&composerReady?'options':'upload';$('#composer-dialog').showModal();updateComposerState();
      }
      if(state.activeJob){pendingGeneration=state.pendingGeneration;const job=await watchJob(state.activeJob);
        if(['material','index'].includes(job.kind)){if(composerMaterialId&&job.material_id===composerMaterialId)await finishComposerMaterial(composerMaterialId);else if(pendingGeneration)await generateQuiz({...pendingGeneration,collectionId});}
        else if(job.result?.status==='ready')startQuiz(await api('/api/quizzes/'+job.result.quizId));else if(job.result?.message)message(job.result.message,true);
      }
    }
    if(state?.creator?.open&&composerJobId&&!activeJob){const j=await api('/api/jobs/'+composerJobId);if(['failed','cancelled','interrupted'].includes(j.status))lastFailedJob=j.id;else if(j.status==='completed')await finishComposerMaterial(composerMaterialId);}
    updateComposerState();
    if(!activeJob&&currentCollection?.latestQuizJob&&['failed','cancelled','interrupted'].includes(currentCollection.latestQuizJob.status)){lastFailedJob=currentCollection.latestQuizJob.id;const old=await api('/api/jobs/'+lastFailedJob);showJob(old);$('#job-panel').classList.add('failed');$('#job-actions').hidden=false;$('#cancel-job').hidden=true;$('#retry-job').hidden=false;$('#edit-failed').hidden=false;}
  }catch(err){message(err.message,true);}finally{pendingGeneration=null;if(!activeJob)setBusy(false);if(lastFailedJob){$('#job-actions').hidden=false;$('#retry-job').hidden=false;$('#cancel-job').hidden=true;$('#edit-failed').hidden=false;}}
}
window.addEventListener('pagehide',()=>saveSnapshot(!$('#summary').hidden));
setInterval(()=>{if(!busy&&collectionId)refreshCollection().catch(()=>{});},4000);
boot();
