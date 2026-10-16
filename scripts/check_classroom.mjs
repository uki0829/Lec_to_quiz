import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const elements=new Map(),calls=[],opened=[],timers=new Map();let timer=0;
const element=()=>({value:'',textContent:'',innerHTML:'',className:'',hidden:false,disabled:false,open:false,
  style:{},dataset:{},scrollHeight:500,scrollTop:500,clientHeight:300,
  classList:{toggle(){},add(){},remove(){}},querySelectorAll(){return []},
  addEventListener(){},showModal(){this.open=true},close(){this.open=false},focus(){}});
const $=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id)};
const escape=value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const agents=[{id:'alice',name:'Sage',avatar:'fox',style:'guide',ownerName:'Alice'},
              {id:'bob',name:'Mochi',avatar:'cloud',style:'coach',ownerName:'Bob'}];
let data={agents,turns:[],sharedCount:1},fail=false,nonce=0;
const context=vm.createContext({$,console,Math,Date,document:{},currentUser:{id:'alice'},currentGroupId:'g1',currentView:'groups',
  currentGroupDetail:{id:'g1',sets:[]},window:{crypto:{randomUUID:()=>`classroom-request-${++nonce}`}},
  esc:escape,mathHtml:escape,flashIcon:x=>`<i>${x}</i>`,syncMenus(){},message(){},renderGroupSets(){},
  openSharedSet:id=>opened.push(id),setTimeout(fn){timers.set(++timer,fn);return timer},clearTimeout(id){timers.delete(id)},
  async api(path,options){
    calls.push({path,options});
    if(path==='/api/agents/me')return options?.method==='PATCH'?{agent:{...agents[0],...JSON.parse(options.body)}}:{agent:agents[0],avatars:[{id:'fox',name:'Sage',description:'Scholar'},{id:'pig',name:'Pip',description:'Inventor'}]};
    if(path.endsWith('/classroom')&&options?.method==='POST'){
      if(fail)throw Error('Network unavailable');
      data={...data,turns:[{id:'turn1',userId:'alice',userName:'Alice',prompt:'Explain',action:'mcq',status:'running',stage:'Sage is teaching',jobId:'job1',activeAgentId:'alice',replies:[]}]};
      return {jobId:'job1',turnId:'turn1'};
    }
    if(path.endsWith('/classroom'))return data;
    if(path==='/api/jobs/job1/cancel'){data={...data,turns:[{...data.turns[0],status:'cancelled',error:'Cancelled'}]};return {accepted:true};}
    if(path==='/api/groups/g1')return {id:'g1',sets:[{id:'new-set'}]};
    throw Error(path);
  }});
vm.runInContext(readFileSync('source/classroom.js','utf8'),context);
const run=code=>vm.runInContext(code,context);
await run('openAgentLibrary()');
assert.equal($('#agent-profile-dialog').open,true);
assert.match($('#agent-avatar-library').innerHTML,/avatar-fox/);
$('#agent-name').value='Professor Pip';$('#agent-style').value='analyst';run("chosenAvatar='pig'");
await $('#agent-profile-form').onsubmit({preventDefault(){}});
assert.equal($('#agent-profile-name').textContent,'Professor Pip');
assert.equal($('#agent-profile-avatar').className,'pixel-avatar avatar-pig');
assert.equal($('#agent-profile-dialog').open,false);
await run("openClassroom({id:'g1'})");
assert.deepEqual(Array.from(run('roomSelected')),['alice','bob']);
assert.match($('#classroom-teachers').innerHTML,/avatar-fox/);
$('#classroom-input').value='Explain momentum';$('#classroom-action').value='mcq';run('syncClassroomControls()');
assert.equal($('#classroom-send').disabled,false);
fail=true;await run('sendClassroom()');
assert.equal($('#classroom-input').value,'Explain momentum');
const first=JSON.parse(calls.filter(c=>c.options?.method==='POST'&&c.path.endsWith('/classroom')).at(-1).options.body);
fail=false;await run('sendClassroom()');
const second=JSON.parse(calls.filter(c=>c.options?.method==='POST'&&c.path.endsWith('/classroom')).at(-1).options.body);
assert.equal(first.requestId,second.requestId);
assert.deepEqual(second.agentIds,['alice','bob']);assert.equal(second.action,'mcq');
assert.equal($('#classroom-send').disabled,true);assert.equal($('#classroom-cancel').hidden,false);
assert.match($('#classroom-teachers').innerHTML,/is-teaching/);
await $('#classroom-cancel').onclick();
assert.match($('#classroom-messages').innerHTML,/Cancelled/);
data={agents,sharedCount:1,turns:[{id:'turn2',userName:'Alice',status:'completed',prompt:'Explain',grounding:'shared',takeaway:'Use the correct rule',shareId:'new-set',
  replies:[{agent:agents[0],text:'Here is the reasoning.',sources:[{shareId:'shared1',name:'Lecture practice',locator:'Question 1'}]}]}]};
await run("fetchClassroom('g1',roomEpoch)");
assert.match($('#classroom-messages').innerHTML,/Open study set/);
assert.match($('#classroom-messages').innerHTML,/Lecture practice/);
assert.equal($('#classroom-board-text').innerHTML,'Use the correct rule');
// A late group response must not replace another classroom or another account.
let release;
const originalApi=context.api;
context.api=()=>new Promise(resolve=>release=resolve);
const stale=run("fetchClassroom('g1',roomEpoch)");
run('closeClassroom()');context.currentGroupId='g2';
release({agents,turns:[{prompt:'OLD PRIVATE GROUP'}],sharedCount:1});await stale;
assert.doesNotMatch($('#classroom-messages').innerHTML,/OLD PRIVATE GROUP/);
context.api=originalApi;run('resetClassroomSession()');
assert.equal(run('myAgent'),null);assert.equal(run('roomId'),null);assert.equal(timers.size,0);
const page=readFileSync('source/page.html','utf8'),css=readFileSync('source/classroom.css','utf8');
assert.match(page,/id="classroom"/);assert.match(page,/id="agent-avatar-library"/);
assert.match(page,/classroom.js/);assert.match(css,/prefers-reduced-motion/);
assert.match(css,/image-rendering:pixelated/);
console.log('Classroom checks passed: saved avatar/name, two-teacher selection, teaching state, idempotent retry, cancellation, shared results, stale-group isolation, and session cleanup.');

// Classroom motion cycles between walking, reading at desks, and teaching.
let time=1000;
context.Date={now:()=>time};context.Math=Object.assign(Object.create(Math),{random:()=>.1});
const occupants=['alice','bob'].map(id=>({dataset:{roomActor:id},style:{setProperty(){}},classList:{toggle(){}},
  querySelector(){return {textContent:''}}}));
$('#classroom-actors').querySelectorAll=()=>occupants;
context.currentGroupId='g1';run("roomId='g1';roomTeachingId=null;updateClassroomMotion()");
assert.equal(run("roomActorStates.get('bob').mode"),'studying');
assert.equal(run("roomActorStates.get('alice').mode"),'idle');
time+=3000;run('updateClassroomMotion()');
assert.equal(run("roomActorStates.get('alice').mode"),'walking');
assert.equal(run("roomActorStates.get('alice').after"),'studying');
time+=4500;run('updateClassroomMotion()');
assert.equal(run("roomActorStates.get('alice').mode"),'studying');
run("roomTeachingId='alice';updateClassroomMotion()");
assert.equal(run("roomActorStates.get('alice').after"),'teaching');
time+=2000;run('updateClassroomMotion()');
assert.equal(run("roomActorStates.get('alice').mode"),'teaching');
run('roomTeachingId=null;updateClassroomMotion()');
assert.equal(run("roomActorStates.get('alice').mode"),'walking');
run('closeClassroom()');assert.equal(run('roomActorStates.size'),0);
context.window.matchMedia=()=>({matches:true});
run("roomId='g1';updateClassroomMotion()");
assert.equal(run('roomMoveTimer'),null);
const destination=run('floorDestination()');assert.ok(destination.x>=18&&destination.x<=82&&destination.y>=77&&destination.y<=93);
run('closeClassroom()');
console.log('Classroom movement passed: random floor targets, occupied-desk avoidance, study pauses, teaching transitions, cleanup, and reduced motion.');
