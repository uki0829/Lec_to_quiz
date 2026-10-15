// The agent plans requests; the existing server pipeline retrieves lecture evidence.
let agentMessages=[],agentFolder=null,agentSending=false,agentWatching=false,agentOwnsBusy=false;
let agentLoadEpoch=0,agentPlanTimer=null,agentRenderKey='',agentOptionKey='';
let agentRequestKey=null,agentRequestText=null;

function resetAgentSession(){
  clearTimeout(agentPlanTimer);agentLoadEpoch++;
  agentMessages=[];agentFolder=null;agentRenderKey='';agentOptionKey='';agentRequestKey=null;agentRequestText=null;
  $('#agent-input').value='';$('#agent-messages').innerHTML='';$('#agent-error').textContent='';
}
function syncAgentState(){
  const rows=typeof collectionRows==='undefined'?[]:collectionRows;
  const key=JSON.stringify(rows.map(c=>[c.id,c.name]));
  if(key!==agentOptionKey){
    agentOptionKey=key;
    $('#agent-collection').innerHTML='<option value="" disabled>Choose a study folder</option>'+rows.map(c=>
      '<option value="'+esc(c.id)+'">'+esc(folderName(c.name))+'</option>').join('');
  }
  $('#agent-collection').value=collectionId||'';
  const ready=currentCollection?.id===collectionId?currentCollection.materials.filter(m=>m.searchReady).length:0;
  const pending=agentFolder===collectionId&&agentMessages.some(m=>['planning','pending'].includes(m.state));
  const locked=busy||agentSending||pending;
  $('#agent-collection').disabled=locked;
  $('#agent-input').disabled=locked;
  $('#agent-send').disabled=locked||!collectionId||!ready||!$('#agent-input').value.trim();
  $('#agent-add').disabled=locked;
  $('#agent-ready').textContent=ready?ready+' lecture'+(ready===1?'':'s')+' ready':'Add lectures to begin';
  document.querySelectorAll('[data-agent-suggestion]').forEach(b=>b.disabled=locked||!ready);
  if(typeof syncMenus==='function')syncMenus();
}
function renderAgentConversation(){
  const key=JSON.stringify(agentMessages);
  $('#agent-empty').hidden=Boolean(agentMessages.length);
  if(key!==agentRenderKey){
    agentRenderKey=key;
    $('#agent-messages').innerHTML=agentMessages.map(m=>{
      const pending=['planning','pending'].includes(m.state),set=m.set;
      let content='<p>'+mathHtml(pending?(m.stage||m.text):m.text)+'</p>';
      if(set){
        content+='<div class="agent-result"><span class="agent-result-kind">'+flashIcon(formatIcon(set.format))+esc(formatName(set.format))+' · '+set.count+' '+(set.format==='cheatsheet'?'sections':'questions')+'</span><h2>'+mathHtml(set.title)+'</h2><button class="primary" data-agent-open="'+esc(set.id)+'">'+(set.format==='cheatsheet'?'Open guide':'Start practice')+flashIcon('arrow-right')+'</button>'+
          (set.sources.length?'<details class="agent-sources"><summary>'+set.sources.length+' lecture source'+(set.sources.length===1?'':'s')+'</summary>'+set.sources.map(s=>'<button class="agent-source" data-agent-source="'+esc(s.id)+'">'+flashIcon('file-text')+'<span>'+esc(s.name)+'<small>'+esc(s.locator)+'</small></span></button>').join('')+'</details>':'')+'</div>';
      }
      if(m.state==='failed')content+='<button class="secondary" data-agent-retry="'+esc(m.id)+'">Try again</button>';
      if(m.state==='pending'&&m.jobId)content+='<button class="quiet" data-agent-cancel="'+esc(m.jobId)+'">Cancel</button>';
      return '<article class="agent-message '+(m.role==='user'?'from-user':'from-agent')+(pending?' is-pending':'')+'"><span class="agent-speaker">'+(m.role==='user'?'You':flashIcon('sparkles')+'Agent')+'</span>'+content+'</article>';
    }).join('');
    $('#agent-messages').querySelectorAll('[data-agent-open]').forEach(b=>b.onclick=()=>openAgentSet(b.dataset.agentOpen));
    $('#agent-messages').querySelectorAll('[data-agent-source]').forEach(b=>b.onclick=()=>openSource(b.dataset.agentSource));
    $('#agent-messages').querySelectorAll('[data-agent-retry]').forEach(b=>b.onclick=()=>retryAgentMessage(b.dataset.agentRetry));
    $('#agent-messages').querySelectorAll('[data-agent-cancel]').forEach(b=>b.onclick=async()=>{
      try{await api('/api/jobs/'+b.dataset.agentCancel+'/cancel',{method:'POST'});b.disabled=true;b.textContent='Cancelling…';}
      catch(error){$('#agent-error').textContent=error.message;}
    });
    $('#agent-messages').scrollTop=$('#agent-messages').scrollHeight;
  }
  syncAgentState();
}
async function loadAgentConversation(){
  clearTimeout(agentPlanTimer);
  const cid=collectionId,epoch=++agentLoadEpoch;
  if(!cid){agentMessages=[];agentFolder=null;renderAgentConversation();return;}
  if(agentFolder!==cid){agentMessages=[];agentFolder=cid;agentRenderKey='';renderAgentConversation();}
  const data=await api('/api/collections/'+encodeURIComponent(cid)+'/agent');
  if(epoch!==agentLoadEpoch||cid!==collectionId)return;
  agentMessages=data.messages;agentFolder=cid;renderAgentConversation();
  const pending=agentMessages.find(m=>['planning','pending'].includes(m.state));
  if(pending?.jobId&&!agentWatching&&!agentSending&&!activeJob){
    void watchAgentJob(pending.jobId).catch(error=>{$('#agent-error').textContent=error.message;});
  }else if(pending?.jobId&&!agentWatching&&!agentSending&&activeJob===pending.jobId){
    agentPlanTimer=setTimeout(()=>watchAgentJob(pending.jobId).catch(error=>{$('#agent-error').textContent=error.message;}),2000);
  }else if(pending?.state==='planning'&&currentView==='agent'){
    if(!busy){agentOwnsBusy=true;setBusy(true);}
    agentPlanTimer=setTimeout(()=>loadAgentConversation().catch(error=>{$('#agent-error').textContent=error.message;}),2000);
  }else if(!pending&&agentOwnsBusy&&!agentSending&&!agentWatching&&!activeJob){
    agentOwnsBusy=false;setBusy(false);
  }
}
async function openStudyAgent(){
  showView('agent');$('#agent-error').textContent='';
  try{await loadAgentConversation();if(!busy)$('#agent-input').focus();saveSnapshot();}
  catch(error){$('#agent-error').textContent=error.message;}
}
async function watchAgentJob(id){
  if(agentWatching)return;
  agentWatching=true;agentOwnsBusy=true;
  try{await watchJob(id);}catch(error){$('#agent-error').textContent=error.message;}
  finally{
    agentWatching=false;agentOwnsBusy=false;
    if(!activeJob)setBusy(false);
    await loadAgentConversation();
    if(currentView==='agent'&&!busy)$('#agent-input').focus();
  }
}
async function sendAgentMessage(){
  const text=$('#agent-input').value.trim(),cid=collectionId;
  if(!text||!cid||busy||agentSending)return;
  if(!currentCollection?.materials.some(m=>m.searchReady)){
    $('#agent-error').textContent='Add lecture material to this folder first.';return;
  }
  agentSending=true;agentOwnsBusy=true;$('#agent-error').textContent='';
  if(agentRequestText!==text||!agentRequestKey){
    agentRequestKey=window.crypto?.randomUUID?.()||Date.now().toString(36)+Math.random().toString(36).slice(2);
    agentRequestText=text;
  }
  setBusy(true);
  // Display a local placeholder while the server plans the request.
  agentMessages=[...agentMessages,{id:'sending-user',role:'user',state:'ready',text},
    {id:'sending-agent',role:'assistant',state:'planning',text:'Understanding your request…'}];
  renderAgentConversation();saveSnapshot();
  try{
    const data=await api('/api/collections/'+encodeURIComponent(cid)+'/agent/messages',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text,requestId:agentRequestKey})});
    if(cid!==collectionId)return;
    agentMessages=data.messages;agentRequestKey=null;agentRequestText=null;$('#agent-input').value='';
    agentSending=false;renderAgentConversation();
    const pending=data.messages.find(m=>m.id===data.messageId&&m.state==='pending');
    if(pending?.jobId)await watchAgentJob(pending.jobId);
    else await loadAgentConversation();
  }catch(error){$('#agent-error').textContent=error.message;await loadAgentConversation().catch(()=>{});}
  finally{agentSending=false;if(!activeJob){agentOwnsBusy=false;setBusy(false);}syncAgentState();saveSnapshot();}
}
async function retryAgentMessage(id){
  if(busy||agentSending)return;
  const m=agentMessages.find(m=>m.id===id);if(!m)return;
  if(!m.jobId){
    const position=agentMessages.indexOf(m);
    $('#agent-input').value=[...agentMessages.slice(0,position)].reverse().find(x=>x.role==='user')?.text||'';
    return sendAgentMessage();
  }
  try{
    agentSending=true;setBusy(true);$('#agent-error').textContent='';
    const data=await api('/api/collections/'+encodeURIComponent(collectionId)+'/agent/messages/'+encodeURIComponent(id)+'/retry',{method:'POST'});
    agentMessages=data.messages;agentSending=false;renderAgentConversation();
    const pending=data.messages.find(m=>m.id===id);
    if(pending?.jobId)await watchAgentJob(pending.jobId);
  }catch(error){$('#agent-error').textContent=error.message;}
  finally{agentSending=false;if(!activeJob)setBusy(false);syncAgentState();}
}
async function openAgentSet(id){
  try{await flushPracticeProgress();const q=validateImported(await api('/api/quizzes/'+id));startQuiz(q);saveSnapshot();}
  catch(error){$('#agent-error').textContent=error.message;}
}
$('#nav-agent').onclick=openStudyAgent;
$('#agent-collection').onchange=async event=>{if(busy)return;try{await selectCollection(event.target.value);}catch(error){$('#agent-error').textContent=error.message;}};
$('#agent-form').onsubmit=event=>{event.preventDefault();sendAgentMessage();};
$('#agent-input').oninput=syncAgentState;
$('#agent-input').onkeydown=event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing&&!event.repeat){event.preventDefault();sendAgentMessage();}};
$('#agent-add').onclick=()=>{if(!collectionId)$('#create-collection').click();else openUpload();};
document.querySelectorAll('[data-agent-suggestion]').forEach(b=>b.onclick=()=>{$('#agent-input').value=b.dataset.agentSuggestion;syncAgentState();$('#agent-input').focus();});
