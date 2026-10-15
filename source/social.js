// Accounts, group membership, and explicit set sharing for the local demo.
let currentUser=null,currentGroupId=null,authMode='login',groupFormMode='create';
let groupRows=[],groupListToken=0,currentGroupDetail=null;
let shareAddedIds=[],shareStatusGroupId=null;
let shareGroups=[],shareSets=[],shareCollectionId=null,shareTargetGroupId=null,sharePreferredQuizId=null,shareUserId=null,shareLoadToken=0,shareBusy=false;
function studyStateKey(){return 'lecture-lab-state:'+ (currentUser?.id||'signed-out');}
function showSignIn(){
  groupRows=[];groupListToken++;currentGroupDetail=null;
  setAuthMode('login');if(typeof resetSetActions==='function')resetSetActions();$('#authenticated-app').classList.remove('practice-page');$('#authenticated-app').hidden=true;$('#auth-screen').hidden=false;
  $('#auth-password').value='';$('#auth-email').focus();
}
function setAuthMode(mode){
  authMode=mode;const create=mode==='register';
  $('#auth-title').textContent=create?'Your next chapter':'Welcome back';
  $('#auth-subtitle').textContent=create?'Create your personal study space.':'Keep learning where you left off.';
  $('#auth-name-field').hidden=!create;$('#auth-name').required=create;
  $('#auth-password').autocomplete=create?'new-password':'current-password';
  $('#auth-submit').textContent=create?'Create account':'Sign in';
  $('#auth-mode').textContent=create?'Already have an account? Sign in':'Create an account';$('#auth-error').textContent='';
}
async function enterSession(user){
  currentUser=user;
  if(new URLSearchParams(location.search).has('authError'))history.replaceState(null,'','/');
  if(user.id==='demo-hefeng'){
    try{const legacy=localStorage.getItem('lecture-lab-state');if(legacy&&!localStorage.getItem(studyStateKey()))localStorage.setItem(studyStateKey(),legacy);localStorage.removeItem('lecture-lab-state');}catch{}
  }
  $('#account-name').textContent=user.name+(user.demo?' · Demo':'');
  $('#auth-password').value='';$('#auth-screen').hidden=true;$('#authenticated-app').hidden=false;
  await boot();
}
async function startSession(){
  try{const state=await api('/api/auth/me');if(state.user){await enterSession(state.user);return;}
    showSignIn();const error=new URLSearchParams(location.search).get('authError');
    if(error)$('#auth-error').textContent=({'google-setup':'Google sign-in needs setup. Use email or demo.','google-link':'Sign in with email first to link Google.','google-signin':'Google sign-in could not complete. Try again.'})[error]||'Sign-in could not complete.';
  }catch(err){showSignIn();$('#auth-error').textContent=err.message;}
}
$('#auth-mode').onclick=()=>setAuthMode(authMode==='login'?'register':'login');
$('#auth-form').onsubmit=async event=>{
  event.preventDefault();$('#auth-submit').disabled=true;$('#auth-error').textContent='';
  try{const result=await api('/api/auth/'+authMode,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:$('#auth-email').value,name:$('#auth-name').value,password:$('#auth-password').value})});await enterSession(result.user);}
  catch(err){$('#auth-error').textContent=err.message;}finally{$('#auth-submit').disabled=false;}
};
$('#auth-demo').onclick=async()=>{if($('#auth-demo').disabled)return;$('#auth-demo').disabled=true;try{await enterSession((await api('/api/auth/demo',{method:'POST'})).user);}catch(err){$('#auth-error').textContent=err.message;}finally{$('#auth-demo').disabled=false;}};
$('#sign-out').onclick=async()=>{
  cancelQuizAdvance();closeQuizExplanation();
  try{if(busy||activeJob){message('Finish or cancel processing before signing out.',true);return;}
    await flushPracticeProgress();await api('/api/auth/logout',{method:'POST'});
    if(typeof resetAgentSession==='function')resetAgentSession();currentUser=null;currentGroupId=null;if(typeof syncPracticePage==='function')syncPracticePage('library');quiz=null;answers={};index=0;collectionId=null;currentCollection=null;savedSets=[];bankRows=[];attachments=[];parentQuizId=null;parentQuizTitle='';materialId=null;lastFailedJob=null;pendingGeneration=null;
    $('#notes').value='';$('#composer-notes').value='';$('#request').value='';
    $('#summary').hidden=true;$('#study').hidden=true;$('#cheatsheet').hidden=true;$('#empty').hidden=false;$('#job-panel').hidden=true;
    for(const dialog of document.querySelectorAll('dialog[open]'))dialog.close();
    showSignIn();
  }catch(err){message(err.message,true);}
};
$('#nav-home').onclick=()=>{showView('library');setLibraryTab('sets');saveSnapshot();};
$('#nav-groups').onclick=()=>showGroups();
async function showGroups(){
  const token=++groupListToken,userId=currentUser?.id;
  if(typeof endSetDrag==='function')endSetDrag();currentGroupId=null;currentGroupDetail=null;
  showView('groups');$('#group-message').textContent='';setGroupDetail(false);
  try{const data=await api('/api/groups');if(token!==groupListToken||currentUser?.id!==userId||currentView!=='groups')return;
    groupRows=data.groups;renderGroupCards();saveSnapshot();
  }catch(err){$('#group-message').textContent=err.message;}
}
function setGroupDetail(open){
  $('#groups-overview-header').hidden=open;$('#groups-description').hidden=open;
  $('#group-detail').hidden=!open;$('#group-list').hidden=open;
}
function renderGroupCards(){
  if(typeof endSetDrag==='function')endSetDrag();
  $('#group-list').innerHTML=groupRows.map(g=>'<article class="group-card" aria-label="'+esc(g.name)+'"><button class="group-open" data-open-group="'+esc(g.id)+'"><span class="group-card-icon">'+flashIcon('users')+'</span><span><strong>'+esc(g.name)+'</strong><small>'+g.memberCount+' members · '+g.setCount+' sets'+(g.demo?' · Demo':'')+'</small></span>'+flashIcon('chevron-right')+'</button></article>').join('')||'<div class="group-empty">'+flashIcon('users')+'<h2>Bring your study circle together.</h2><p>Create a group or join with an invite code.</p></div>';
  $('#group-list').querySelectorAll('[data-open-group]').forEach(b=>b.onclick=()=>openGroup(b.dataset.openGroup));
  if(typeof updateSetActions==='function')updateSetActions();
}
async function leaveGroup(id){
  if(!id||!currentUser||busy||setActionsBusy||currentView!=='groups'||currentGroupId!==id||$('#group-detail').hidden)return;
  const userId=currentUser.id;
  if(typeof endSetDrag==='function')endSetDrag();
  groupListToken++;setActionsBusy=true;updateSetActions();
  try{
    await api('/api/groups/'+encodeURIComponent(id)+'/leave',{method:'POST'});
    if(userId!==currentUser?.id)return;
    groupRows=groupRows.filter(g=>g.id!==id);
    if(currentGroupId===id){currentGroupId=null;currentGroupDetail=null;setGroupDetail(false);}
    if(quiz?.mode==='shared'&&quiz.groupId===id){
      clearTimeout(saveTimer);cancelQuizAdvance();closeQuizExplanation();quiz=null;answers={};index=0;
      for(const key of ['study','summary','cheatsheet','quiz-context','build-followup'])$('#'+key).hidden=true;
      $('#empty').hidden=false;
    }
    renderGroupCards();saveSnapshot();$('#group-message').textContent='You left the group.';
    if(currentView==='groups')$('#create-group').focus();
  }catch(err){$('#group-message').textContent=err.message;}
  finally{setActionsBusy=false;updateSetActions();}
}
$('#group-leave').onclick=()=>leaveGroup(currentGroupId);
async function openGroup(id){
  const token=++groupListToken,userId=currentUser?.id;if(typeof endSetDrag==='function')endSetDrag();
  try{const g=await api('/api/groups/'+id);if(token!==groupListToken||userId!==currentUser?.id)return;
    currentGroupId=id;currentGroupDetail=g;showView('groups');setGroupDetail(true);
    $('#group-title').textContent=g.name;$('#group-demo-label').hidden=!g.demo;$('#group-invite-code').value=g.invite_code;
    $('#group-members').innerHTML=g.members.map(m=>'<span class="member-chip"><i>'+esc(m.name.slice(0,1).toUpperCase())+'</i>'+esc(m.name)+(m.id===g.owner_id?' <small>Owner</small>':'')+(m.demo?' <small>Demo</small>':'')+'</span>').join('');
    renderGroupSets(g);$('#group-message').textContent='';saveSnapshot();return true;
  }catch(err){$('#group-message').textContent=err.message;return false;}
}
function renderGroupSets(g){
  const owner=g.owner_id===currentUser?.id;
  $('#group-sets').innerHTML=g.sets.map(s=>'<button class="quiz-card group-set-card" data-share="'+esc(s.id)+'"'+(owner?' draggable="true" data-drag-share="'+esc(s.id)+'" aria-keyshortcuts="Delete" aria-description="Drag to the trash to remove this shared copy."':'')+'><span class="card-top"><span class="card-format">'+flashIcon(formatIcon(s.format))+esc(formatName(s.format))+'</span><span class="card-count">'+s.count+' '+(s.format==='cheatsheet'?'sections':'questions')+'</span></span><h3>'+mathHtml(s.title)+'</h3><span class="shared-by">'+esc(s.authorName)+(s.demo?' · Demo set':'')+'</span><span class="card-cta">'+(s.format==='cheatsheet'?'Open sheet':'Practice')+flashIcon('arrow-right')+'</span></button>').join('')||'<p class="empty-results">Share your first study set.</p>';
  $('#group-sets').querySelectorAll('[data-share]').forEach(b=>b.onclick=()=>openSharedSet(b.dataset.share));
  if(typeof bindSharedSetDrag==='function')$('#group-sets').querySelectorAll('[data-drag-share]').forEach(bindSharedSetDrag);
  if(typeof updateSetActions==='function')updateSetActions();
}
async function deleteDraggedSharedSet(selection){
  if(!selection||busy||setActionsBusy||selection.userId!==currentUser?.id||selection.groupId!==currentGroupId||currentView!=='groups'||$('#group-detail').hidden||currentGroupDetail?.owner_id!==currentUser?.id||!currentGroupDetail.sets.some(s=>s.id===selection.id))return;
  setActionsBusy=true;updateSetActions();
  try{
    await api('/api/groups/'+encodeURIComponent(selection.groupId)+'/sets/'+encodeURIComponent(selection.id),{method:'DELETE'});
    if(selection.userId!==currentUser?.id)return;
    if(quiz?.mode==='shared'&&quiz.shareId===selection.id){
      clearTimeout(saveTimer);cancelQuizAdvance();closeQuizExplanation();quiz=null;answers={};index=0;
      for(const key of ['study','summary','cheatsheet','quiz-context','build-followup'])$('#'+key).hidden=true;
      $('#empty').hidden=false;
    }
    if(currentView==='groups'&&currentGroupId===selection.groupId){await openGroup(selection.groupId);$('#group-message').textContent='Set removed from group.';}
    saveSnapshot();
  }catch(err){$('#group-message').textContent=err.message;}
  finally{setActionsBusy=false;updateSetActions();}
}
async function openSharedSet(id){try{const q=validateImported(await api('/api/shared-sets/'+id));startQuiz(q);if(q.progress?.review)showSummary();saveSnapshot();window.scrollTo({top:0,behavior:'smooth'});}catch(err){$('#group-message').textContent=err.message;}}
function updateSocialQuiz(q){$('#share-current').hidden=!(q.id&&q.mode==='generated');if(typeof syncStudyReturn==='function')syncStudyReturn();}
function openGroupForm(mode){
  groupFormMode=mode;const join=mode==='join';$('#group-dialog-title').textContent=join?'Join group':'Create group';$('#group-input-label').textContent=join?'Invite code':'Group name';$('#group-form-submit').textContent=join?'Join group':'Create group';$('#group-input').value='';$('#group-form-error').textContent='';$('#group-dialog').showModal();$('#group-input').focus();
}
$('#create-group').onclick=()=>openGroupForm('create');$('#join-group').onclick=()=>openGroupForm('join');$('#close-group-dialog').onclick=()=>$('#group-dialog').close();$('#back-groups').onclick=showGroups;
$('#group-form').onsubmit=async event=>{
  event.preventDefault();$('#group-form-submit').disabled=true;
  try{const join=groupFormMode==='join';const g=await api('/api/groups'+(join?'/join':''),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(join?{code:$('#group-input').value.trim()}:{name:$('#group-input').value.trim()})});$('#group-dialog').close();await openGroup(g.id);}
  catch(err){$('#group-form-error').textContent=err.message;}finally{$('#group-form-submit').disabled=false;}
};
$('#copy-group-code').onclick=async()=>{try{await navigator.clipboard.writeText($('#group-invite-code').value);$('#group-message').textContent='Invite code copied.';}catch{$('#group-invite-code').select();$('#group-message').textContent='Copy the selected invite code.';}};
function syncSharePicker(){
  const validGroup=shareGroups.some(g=>g.id===(shareTargetGroupId||$('#share-group').value));
  const validSet=shareStatusGroupId===(shareTargetGroupId||$('#share-group').value)&&shareCollectionId===$('#share-collection').value&&shareSets.some(q=>q.id===$('#share-set').value&&!shareAddedIds.includes(q.id));
  $('#confirm-share').disabled=shareBusy||!validGroup||!validSet||shareUserId!==currentUser?.id;
  for(const id of ['share-group','share-collection','close-share-dialog'])$('#'+id).disabled=shareBusy;
  $('#share-set').disabled=shareBusy||!shareCollectionId||!shareSets.length;
  if(typeof syncMenus==='function')syncMenus();
}
async function openShareDialog(quizId=null){
  if(shareBusy)return;
  const token=++shareLoadToken,userId=currentUser?.id;
  const target=currentView==='groups'?currentGroupId:null;
  try{const [groups,collections]=await Promise.all([api('/api/groups'),api('/api/collections')]);
    if(token!==shareLoadToken||userId!==currentUser?.id)return;
    if(!groups.groups.length){await showGroups();$('#group-message').textContent='Create or join a group first.';return;}
    if(target&&!groups.groups.some(g=>g.id===target))throw Error('Study group not found.');
    shareGroups=groups.groups;shareSets=[];shareAddedIds=[];shareStatusGroupId=null;shareCollectionId=null;shareTargetGroupId=target;sharePreferredQuizId=quizId;shareUserId=userId;
    $('#share-dialog-title').textContent=target?'Add study set':'Share a set';
    $('#confirm-share').textContent=target?'Add to group':'Share with group';
    $('#share-group-field').hidden=Boolean(target);
    $('#share-group').innerHTML='<option value="" disabled>Choose a group</option>'+shareGroups.map(g=>'<option value="'+esc(g.id)+'">'+esc(g.name)+'</option>').join('');
    $('#share-group').value=target||'';
    $('#share-collection').innerHTML='<option value="" disabled>Choose a collection</option>'+collections.collections.map(c=>'<option value="'+esc(c.id)+'">'+esc(c.name)+'</option>').join('');
    $('#share-collection').value='';$('#share-set').innerHTML='<option value="" disabled>Choose a set</option>';$('#share-set').value='';$('#share-set-step').hidden=true;
    $('#share-error').textContent=collections.collections.length?'':'Create a collection first.';
    $('#share-dialog').showModal();syncSharePicker();
  }catch(err){message(err.message,true);}
}
$('#share-collection').onchange=async()=>{
  const cid=$('#share-collection').value,token=++shareLoadToken,userId=currentUser?.id;
  const gid=shareTargetGroupId||$('#share-group').value;
  shareSets=[];shareAddedIds=[];shareStatusGroupId=null;shareCollectionId=null;$('#share-error').textContent='';$('#share-set-step').hidden=!cid;
  $('#share-set').innerHTML='<option value="" disabled>Loading sets…</option>';$('#share-set').value='';syncSharePicker();
  if(!cid)return;
  try{const result=await api('/api/quizzes?collectionId='+encodeURIComponent(cid)+(gid?'&groupId='+encodeURIComponent(gid):''));
    if(token!==shareLoadToken||userId!==currentUser?.id||!$('#share-dialog').open||$('#share-collection').value!==cid)return;
    if(gid&&result.quizzes.some(q=>typeof q.alreadyShared!=='boolean'))throw Error('Refresh the app to check group availability.');
    shareSets=result.quizzes.filter(q=>q.collectionId===cid);shareCollectionId=cid;shareAddedIds=shareSets.filter(q=>q.alreadyShared).map(q=>q.id);shareStatusGroupId=gid||null;
    $('#share-set').innerHTML='<option value="" disabled>Choose a set</option>'+shareSets.map(q=>'<option value="'+esc(q.id)+'" data-format="'+esc(q.format)+'"'+(shareAddedIds.includes(q.id)?' disabled':'')+'>'+esc(formatName(q.format)+' · '+q.title+(shareAddedIds.includes(q.id)?' · Already added':''))+'</option>').join('');
    $('#share-set').value=shareSets.some(q=>q.id===sharePreferredQuizId&&!shareAddedIds.includes(q.id))?sharePreferredQuizId:'';
    $('#share-error').textContent=shareSets.length?'':'No saved sets in this collection.';
  }catch(err){if(token===shareLoadToken&&userId===currentUser?.id)$('#share-error').textContent=err.message;}
  finally{if(token===shareLoadToken)syncSharePicker();}
};
$('#share-set').onchange=syncSharePicker;
$('#share-group').onchange=()=>$('#share-collection').value?$('#share-collection').onchange():syncSharePicker();
function closeShareDialog(){if(shareBusy)return;shareLoadToken++;$('#share-dialog').close();}
$('#group-share').onclick=()=>openShareDialog();$('#share-current').onclick=()=>openShareDialog(quiz?.id);$('#close-share-dialog').onclick=closeShareDialog;
$('#share-dialog').addEventListener('cancel',event=>{if(shareBusy)event.preventDefault();else shareLoadToken++;});
$('#share-form').onsubmit=async event=>{
  event.preventDefault();syncSharePicker();if($('#confirm-share').disabled)return;
  const groupId=shareTargetGroupId||$('#share-group').value,quizId=$('#share-set').value,userId=currentUser?.id;
  shareBusy=true;syncSharePicker();$('#share-error').textContent='';
  try{const result=await api('/api/groups/'+encodeURIComponent(groupId)+'/share',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({quizId})});
    if(userId!==currentUser?.id)return;
    $('#share-dialog').close();shareLoadToken++;await openGroup(result.groupId);$('#group-message').textContent='Added to group.';
  }catch(err){if(userId===currentUser?.id){if(/already in the group/i.test(err.message)){await $('#share-collection').onchange();return;}$('#share-error').textContent=err.message;}}
  finally{shareBusy=false;syncSharePicker();}
};
