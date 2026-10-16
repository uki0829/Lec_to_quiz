// Persistent tutor identity; classroom content is scoped to explicit group sharing.
let myAgent=null,agentAvatars=[],chosenAvatar='explorer',agentProfileBusy=false;
let roomId=null,roomEpoch=0,roomTimer=null,roomAgents=[],roomTurns=[],roomSelected=[];
let roomMoveTimer=null,roomActorKey='',roomActorStates=new Map(),roomTeachingId=null;
let roomSending=false,roomRequestKey=null,roomRequestText=null,roomRenderKey='',roomRosterKey='',roomSelectionInitialized=false;
const avatarIds=['explorer','cloud','fox','pig'];
function avatarClass(avatar){return avatarIds.includes(avatar)?avatar:'explorer';}
function avatarHtml(agent,extra=''){return '<span class="pixel-avatar avatar-'+avatarClass(agent?.avatar)+' '+extra+'" aria-hidden="true"></span>';}
function resetClassroomSession(){
  closeClassroom();myAgent=null;agentAvatars=[];
  $('#classroom-input').value='';$('#classroom-error').textContent='';
}
function pauseClassroom(){clearTimeout(roomTimer);clearTimeout(roomMoveTimer);roomMoveTimer=null;}
function closeClassroom(){
  pauseClassroom();roomEpoch++;roomId=null;roomAgents=[];roomTurns=[];roomSelected=[];roomSending=false;
  roomRequestKey=null;roomRequestText=null;roomRenderKey='';roomRosterKey='';roomSelectionInitialized=false;roomActorKey='';roomActorStates.clear();roomTeachingId=null;
}
function syncAgentIdentity(){
  if(!myAgent)return;
  $('#agent-profile-avatar').className='pixel-avatar avatar-'+avatarClass(myAgent.avatar);
  $('#agent-profile-name').textContent=myAgent.name;
}
async function loadAgentProfile(){
  const userId=currentUser?.id;
  const data=await api('/api/agents/me');
  if(userId!==currentUser?.id)return;
  myAgent=data.agent;agentAvatars=data.avatars;syncAgentIdentity();
}
async function openAgentLibrary(){
  if(agentProfileBusy)return;
  try{
    await loadAgentProfile();if(!myAgent)return;
    chosenAvatar=myAgent.avatar;$('#agent-name').value=myAgent.name;$('#agent-style').value=myAgent.style;
    $('#agent-profile-error').textContent='';renderAvatarLibrary();
    if(!$('#agent-profile-dialog').open)$('#agent-profile-dialog').showModal();
    if(typeof syncMenus==='function')syncMenus();
  }catch(error){message(error.message,true);}
}
function renderAvatarLibrary(){
  $('#agent-avatar-library').innerHTML=agentAvatars.map(a=>'<button type="button" class="avatar-choice" data-avatar="'+esc(a.id)+'" aria-pressed="'+(chosenAvatar===a.id)+'">'+avatarHtml({avatar:a.id})+'<strong>'+esc(a.name)+'</strong><small>'+esc(a.description)+'</small></button>').join('');
  $('#agent-avatar-library').querySelectorAll('[data-avatar]').forEach(button=>button.onclick=()=>{chosenAvatar=button.dataset.avatar;renderAvatarLibrary();});
}
$('#agent-profile-open').onclick=openAgentLibrary;
$('#classroom-avatar-open').onclick=openAgentLibrary;
$('#agent-profile-close').onclick=()=>{if(!agentProfileBusy)$('#agent-profile-dialog').close();};
$('#agent-profile-dialog').addEventListener('cancel',event=>{if(agentProfileBusy)event.preventDefault();});
$('#agent-profile-form').onsubmit=async event=>{
  event.preventDefault();if(agentProfileBusy)return;
  const userId=currentUser?.id;agentProfileBusy=true;$('#agent-profile-save').disabled=true;
  $('#agent-profile-error').textContent='';
  try{
    const data=await api('/api/agents/me',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:$('#agent-name').value.trim(),avatar:chosenAvatar,style:$('#agent-style').value})});
    if(userId!==currentUser?.id)return;
    myAgent=data.agent;syncAgentIdentity();$('#agent-profile-dialog').close();
    if(roomId)await fetchClassroom(roomId,roomEpoch);
  }catch(error){if(userId===currentUser?.id)$('#agent-profile-error').textContent=error.message;}
  finally{agentProfileBusy=false;$('#agent-profile-save').disabled=false;}
};
function roomActive(){return roomId&&currentView==='groups'&&currentGroupId===roomId&&!$('#group-detail').hidden;}
async function openClassroom(group){
  closeClassroom();roomId=group.id;const epoch=roomEpoch;
  $('#classroom-error').textContent='';$('#classroom-input').value='';
  $('#classroom-board-text').textContent='What shall we explore?';
  $('#classroom-messages').innerHTML='<p class="classroom-empty">Your teachers are arriving…</p>';
  try{await fetchClassroom(group.id,epoch);}catch(error){if(epoch===roomEpoch)$('#classroom-error').textContent=error.message;}
}
async function fetchClassroom(gid,epoch){
  const data=await api('/api/groups/'+encodeURIComponent(gid)+'/classroom');
  if(epoch!==roomEpoch||gid!==roomId||!roomActive())return;
  roomAgents=[...data.agents].sort((a,b)=>Number(b.id===currentUser?.id)-Number(a.id===currentUser?.id));roomTurns=data.turns;
  roomSelected=roomSelected.filter(id=>roomAgents.some(a=>a.id===id));
  if(!roomSelectionInitialized){
    roomSelectionInitialized=true;
    const own=roomAgents.find(a=>a.id===currentUser?.id)||roomAgents[0];
    roomSelected=[own?.id,roomAgents.find(a=>a.id!==own?.id)?.id].filter(Boolean);
  }
  renderClassroom(data.sharedCount);
  clearTimeout(roomTimer);roomTimer=setTimeout(()=>fetchClassroom(gid,epoch).catch(error=>{
    if(epoch===roomEpoch&&roomActive()){$('#classroom-error').textContent=error.message;roomTimer=setTimeout(()=>fetchClassroom(gid,epoch).catch(()=>{}),5000);}
  }),2500);
}
function classroomPending(){return roomTurns.find(t=>['queued','running'].includes(t.status));}
function floorDestination(){return {x:18+Math.random()*64,y:77+Math.random()*16};}
function roomDeskPosition(index){
  const room=$('#pixel-room'),desk=room.querySelectorAll('.pixel-desks i')[index];
  if(room.getBoundingClientRect&&desk?.getBoundingClientRect){
    const bounds=room.getBoundingClientRect(),seat=desk.getBoundingClientRect();
    if(bounds.width&&bounds.height)return {x:(seat.left+seat.width/2-bounds.left)/bounds.width*100,y:(seat.top+13-bounds.top)/bounds.height*100};
  }
  return {x:[22,50,78][index],y:90};
}
function applyActorState(actor,state){
  actor.style.left=state.x+'%';actor.style.top=state.y+'%';
  actor.style.setProperty('--walk-duration',(state.duration||0)+'ms');
  actor.classList.toggle('is-walking',state.mode==='walking');
  actor.classList.toggle('is-studying',state.mode==='studying');
  actor.classList.toggle('is-teaching',state.mode==='teaching');
  actor.style.setProperty('--facing',state.facing||1);
  actor.querySelector('.actor-activity').textContent=state.mode==='studying'?'Studying':state.mode==='teaching'?'Teaching':state.mode==='walking'?'Exploring':'Thinking';
}
function updateClassroomMotion(){
  roomMoveTimer=null;if(!roomActive())return;
  const reduced=window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const now=Date.now();
  $('#classroom-actors').querySelectorAll('[data-room-actor]').forEach((actor,index)=>{
    const id=actor.dataset.roomActor;let state=roomActorStates.get(id);
    if(!state){
      const desk=index===1?0:null;
      state={...(desk!==null?roomDeskPosition(desk):{x:32+index*18%50,y:80}),mode:desk!==null?'studying':'idle',
        desk,due:now+(desk!==null?6500:800+Math.random()*1400),duration:0};
      roomActorStates.set(id,state);applyActorState(actor,state);
    }
    if(reduced)return;
    if(id===roomTeachingId){
      if(state.mode!=='teaching'&&state.after!=='teaching'){
        state={...state,x:roomSelected.indexOf(id)===1?63:37,y:74,desk:null,mode:'walking',after:'teaching',duration:1800,due:now+1800};
      }else if(state.mode==='walking'&&now>=state.due){state={...state,mode:'teaching',after:null,duration:0,due:Infinity};}
      roomActorStates.set(id,state);applyActorState(actor,state);return;
    }
    if(state.mode==='teaching'||state.after==='teaching')state={...state,due:0,after:null};
    if(now<state.due)return;
    if(state.mode==='walking'){
      state={...state,mode:state.after==='studying'?'studying':'idle',after:null,duration:0,
        due:now+(state.desk!==null?6500+Math.random()*5000:1500+Math.random()*2500)};
    }else{
      const occupied=new Set([...roomActorStates.entries()].filter(([other])=>other!==id).map(([,value])=>value.desk).filter(desk=>desk!==null));
      const available=[0,1,2].filter(desk=>!occupied.has(desk));
      const desk=state.mode!=='studying'&&available.length&&Math.random()<.55?available[Math.floor(Math.random()*available.length)]:null;
      const target=desk!==null?roomDeskPosition(desk):floorDestination();
      const duration=1800+Math.random()*2200;
      state={...state,...target,mode:'walking',after:desk!==null?'studying':'idle',desk,duration,due:now+duration,
        facing:target.x<state.x?-1:1};
    }
    roomActorStates.set(id,state);applyActorState(actor,state);
  });
  if(!reduced)roomMoveTimer=setTimeout(updateClassroomMotion,450);
}
function renderClassroomActors(active){
  roomTeachingId=active||null;
  const visible=[...roomAgents].sort((a,b)=>Number(roomSelected.includes(b.id))-Number(roomSelected.includes(a.id))).slice(0,8);
  const key=JSON.stringify(visible.map(a=>[a.id,a.avatar,a.name]));
  if(key!==roomActorKey){
    roomActorKey=key;
    $('#classroom-actors').innerHTML=visible.map(a=>'<div class="classroom-actor" data-room-actor="'+esc(a.id)+'"><span class="actor-label">'+esc(a.name)+'<small class="actor-activity">Thinking</small></span><span class="actor-facing">'+avatarHtml(a)+'<i class="actor-book"></i><i class="actor-pencil"></i></span><span class="actor-shadow"></span></div>').join('');
    const keep=new Set(visible.map(a=>a.id));for(const id of roomActorStates.keys())if(!keep.has(id))roomActorStates.delete(id);
    $('#classroom-actors').querySelectorAll('[data-room-actor]').forEach(actor=>{const state=roomActorStates.get(actor.dataset.roomActor);if(state)applyActorState(actor,state);});
  }
  if(!roomMoveTimer)updateClassroomMotion();
}
function syncClassroomControls(){
  const pending=classroomPending(),locked=roomSending||Boolean(pending);
  $('#classroom-send').disabled=locked||!roomSelected.length||!$('#classroom-input').value.trim();
  $('#classroom-input').disabled=locked;$('#classroom-action').disabled=locked;
  $('#classroom-cancel').hidden=!pending?.jobId;
  $('#classroom-avatar-open').disabled=roomSending;
  $('#classroom-status').textContent=roomSending?'Preparing…':pending?'Teaching…':'Ready';
  if(typeof syncMenus==='function')syncMenus();
}
function renderClassroom(sharedCount){
  const pending=classroomPending();
  const active=pending?.activeAgentId;
  const rosterKey=JSON.stringify([roomAgents,roomSelected,active,Boolean(pending),roomSending]);
  if(rosterKey!==roomRosterKey){
    roomRosterKey=rosterKey;
    $('#classroom-teachers').innerHTML=roomAgents.map((agent,i)=>'<button type="button" class="room-teacher '+(roomSelected.includes(agent.id)?'is-selected ':'')+(active===agent.id?'is-teaching':'')+'" style="--seat:'+i+'" data-teacher="'+esc(agent.id)+'" aria-label="'+esc(agent.name+' by '+agent.ownerName)+'" aria-pressed="'+roomSelected.includes(agent.id)+'" '+(pending||roomSending?'disabled':'')+'><span class="teacher-bubble">'+(active===agent.id?'Teaching…':roomSelected.includes(agent.id)?'Ready':'Join in')+'</span>'+avatarHtml(agent)+'<strong>'+esc(agent.name)+'</strong><small>'+esc(agent.ownerName)+(agent.id===currentUser?.id?' · You':'')+'</small></button>').join('');
    $('#classroom-teachers').querySelectorAll('[data-teacher]').forEach(button=>button.onclick=()=>{
      const id=button.dataset.teacher;
      if(roomSelected.includes(id))roomSelected=roomSelected.filter(x=>x!==id);
      else if(roomSelected.length<2)roomSelected.push(id);
      else{$('#classroom-error').textContent='Choose up to two teachers.';return;}
      $('#classroom-error').textContent='';renderClassroom(sharedCount);
    });
  }
  const latest=roomTurns.at(-1);
  $('#pixel-room').classList.toggle('is-busy',Boolean(pending));
  $('#classroom-board-label').textContent=pending?.stage||'Today’s takeaway';
  $('#classroom-board-text').innerHTML=mathHtml(latest?.takeaway||latest?.prompt||'What shall we explore?');
  $('#classroom-scope').textContent=latest?.grounding==='general'?'General knowledge':sharedCount+' shared set'+(sharedCount===1?'':'s');
  const renderKey=JSON.stringify(roomTurns);
  if(renderKey!==roomRenderKey){
    roomRenderKey=renderKey;
    const log=$('#classroom-messages'),nearBottom=log.scrollHeight-log.scrollTop-log.clientHeight<100;
    log.innerHTML=roomTurns.map(turn=>'<article class="classroom-turn"><div class="classroom-student"><strong>'+esc(turn.userName)+'</strong><p>'+mathHtml(turn.prompt)+'</p></div>'+(turn.replies||[]).map(reply=>'<div class="teacher-reply">'+avatarHtml(reply.agent)+'<div><strong>'+esc(reply.agent.name)+'</strong><p>'+mathHtml(reply.text)+'</p>'+(reply.sources.length?'<div class="classroom-sources">'+reply.sources.map(s=>'<button class="quiet" type="button" data-room-source="'+esc(s.shareId)+'">'+flashIcon('book-open')+esc(s.name)+' · '+esc(s.locator)+'</button>').join('')+'</div>':'<small class="general-label">General knowledge</small>')+'</div></div>').join('')+(turn.shareId?'<button class="secondary classroom-result" data-room-set="'+esc(turn.shareId)+'">'+flashIcon('layers')+'Open study set'+flashIcon('arrow-right')+'</button>':'')+(turn.error?'<p class="classroom-error">'+esc(turn.error)+'</p>':'')+(['queued','running'].includes(turn.status)?'<p class="classroom-thinking">'+esc(turn.stage)+'</p>':'')+'</article>').join('')||'<div class="classroom-empty">'+flashIcon('users')+'<strong>Bring a question to class.</strong><p>Your teachers will work through it together.</p></div>';
    log.querySelectorAll('[data-room-source]').forEach(b=>b.onclick=()=>openSharedSet(b.dataset.roomSource));
    log.querySelectorAll('[data-room-set]').forEach(b=>b.onclick=()=>openSharedSet(b.dataset.roomSet));
    if(nearBottom||roomSending)log.scrollTop=log.scrollHeight;
    // Refresh the group library after a newly created classroom artifact appears.
    const newIds=roomTurns.map(t=>t.shareId).filter(Boolean);
    if(currentGroupDetail&&newIds.some(id=>!currentGroupDetail.sets.some(s=>s.id===id))){
      const gid=roomId,epoch=roomEpoch;
      void api('/api/groups/'+encodeURIComponent(gid)).then(g=>{
        if(epoch===roomEpoch&&gid===currentGroupId){currentGroupDetail=g;renderGroupSets(g);}
      }).catch(()=>{});
    }
  }
  renderClassroomActors(active);syncClassroomControls();
}
async function sendClassroom(){
  const text=$('#classroom-input').value.trim(),gid=roomId,epoch=roomEpoch;
  if(!text||!roomActive()||roomSending||classroomPending()||!roomSelected.length)return;
  roomSending=true;$('#classroom-error').textContent='';syncClassroomControls();
  const signature=JSON.stringify([text,roomSelected,$('#classroom-action').value]);
  if(roomRequestText!==signature||!roomRequestKey){roomRequestKey=window.crypto?.randomUUID?.()||Date.now().toString(36)+Math.random().toString(36).slice(2);roomRequestText=signature;}
  try{
    await api('/api/groups/'+encodeURIComponent(gid)+'/classroom',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text,agentIds:roomSelected,action:$('#classroom-action').value,count:4,requestId:roomRequestKey})});
    if(epoch!==roomEpoch)return;
    roomRequestKey=null;roomRequestText=null;$('#classroom-input').value='';
    await fetchClassroom(gid,epoch);
  }catch(error){if(epoch===roomEpoch)$('#classroom-error').textContent=error.message;}
  finally{if(epoch===roomEpoch){roomSending=false;syncClassroomControls();}}
}
$('#classroom-form').onsubmit=event=>{event.preventDefault();void sendClassroom();};
$('#classroom-input').oninput=syncClassroomControls;
$('#classroom-input').onkeydown=event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing&&!event.repeat){event.preventDefault();void sendClassroom();}};
$('#classroom-cancel').onclick=async()=>{
  const pending=classroomPending(),epoch=roomEpoch,gid=roomId;
  if(!pending?.jobId)return;
  try{await api('/api/jobs/'+encodeURIComponent(pending.jobId)+'/cancel',{method:'POST'});if(epoch===roomEpoch)await fetchClassroom(gid,epoch);}
  catch(error){if(epoch===roomEpoch)$('#classroom-error').textContent=error.message;}
};
