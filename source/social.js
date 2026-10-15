// Accounts, group membership, and explicit set sharing for the local demo.
let currentUser=null,currentGroupId=null,authMode='login',groupFormMode='create';
function studyStateKey(){return 'lecture-lab-state:'+ (currentUser?.id||'signed-out');}
function showSignIn(){
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
  showView('groups');$('#group-message').textContent='';$('#group-detail').hidden=true;$('#group-list').hidden=false;
  try{const data=await api('/api/groups');$('#group-list').innerHTML=data.groups.map(g=>'<button class="group-card" data-group="'+esc(g.id)+'"><span class="group-card-icon">'+flashIcon('users')+'</span><span><strong>'+esc(g.name)+'</strong><small>'+g.memberCount+' members · '+g.setCount+' sets'+(g.demo?' · Demo':'')+'</small></span>'+flashIcon('chevron-right')+'</button>').join('')||'<div class="group-empty">'+flashIcon('users')+'<h2>Bring your study circle together.</h2><p>Create a group or join with an invite code.</p></div>';
    $('#group-list').querySelectorAll('[data-group]').forEach(b=>b.onclick=()=>openGroup(b.dataset.group));saveSnapshot();
  }catch(err){$('#group-message').textContent=err.message;}
}
async function openGroup(id){
  try{const g=await api('/api/groups/'+id);currentGroupId=id;showView('groups');$('#group-list').hidden=true;$('#group-detail').hidden=false;
    $('#group-title').textContent=g.name;$('#group-demo-label').hidden=!g.demo;$('#group-invite-code').value=g.invite_code;
    $('#group-members').innerHTML=g.members.map(m=>'<span class="member-chip"><i>'+esc(m.name.slice(0,1).toUpperCase())+'</i>'+esc(m.name)+(m.demo?' <small>Demo</small>':'')+'</span>').join('');
    $('#group-sets').innerHTML=g.sets.map(s=>'<button class="quiz-card group-set-card" data-share="'+esc(s.id)+'"><span class="card-top"><span class="card-format">'+flashIcon(formatIcon(s.format))+esc(formatName(s.format))+'</span><span class="card-count">'+s.count+' '+(s.format==='cheatsheet'?'sections':'questions')+'</span></span><h3>'+mathHtml(s.title)+'</h3><span class="shared-by">'+esc(s.authorName)+(s.demo?' · Demo set':'')+'</span><span class="card-cta">'+(s.format==='cheatsheet'?'Open sheet':'Practice')+flashIcon('arrow-right')+'</span></button>').join('')||'<p class="empty-results">Share your first study set.</p>';
    $('#group-sets').querySelectorAll('[data-share]').forEach(b=>b.onclick=()=>openSharedSet(b.dataset.share));$('#group-message').textContent='';saveSnapshot();
  }catch(err){$('#group-message').textContent=err.message;}
}
async function openSharedSet(id){try{const q=validateImported(await api('/api/shared-sets/'+id));startQuiz(q);if(q.progress?.review)showSummary();saveSnapshot();window.scrollTo({top:0,behavior:'smooth'});}catch(err){$('#group-message').textContent=err.message;}}
function updateSocialQuiz(q){$('#share-current').hidden=!(q.id&&q.mode==='generated');}
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
async function openShareDialog(quizId=null){
  try{const [groups,sets]=await Promise.all([api('/api/groups'),api('/api/quizzes')]);
    if(!groups.groups.length){await showGroups();$('#group-message').textContent='Create or join a group first.';return;}
    if(!sets.quizzes.length){$('#group-message').textContent='Create a study set before sharing.';message('Create a study set before sharing.',true);return;}
    $('#share-group').innerHTML=groups.groups.map(g=>'<option value="'+esc(g.id)+'">'+esc(g.name)+'</option>').join('');
    $('#share-set').innerHTML=sets.quizzes.map(q=>'<option value="'+esc(q.id)+'" data-format="'+esc(q.format)+'">'+esc(formatName(q.format)+' · '+q.title)+'</option>').join('');
    if(currentGroupId)$('#share-group').value=currentGroupId;if(quizId)$('#share-set').value=quizId;$('#share-error').textContent='';$('#share-dialog').showModal();if(typeof syncMenus==='function')syncMenus();
  }catch(err){message(err.message,true);}
}
$('#group-share').onclick=()=>openShareDialog();$('#share-current').onclick=()=>openShareDialog(quiz?.id);$('#close-share-dialog').onclick=()=>$('#share-dialog').close();
$('#share-form').onsubmit=async event=>{event.preventDefault();$('#confirm-share').disabled=true;
  try{const result=await api('/api/groups/'+$('#share-group').value+'/share',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({quizId:$('#share-set').value})});$('#share-dialog').close();await openGroup(result.groupId);$('#group-message').textContent='Shared with your group.';}
  catch(err){$('#share-error').textContent=err.message;}finally{$('#confirm-share').disabled=false;}
};
