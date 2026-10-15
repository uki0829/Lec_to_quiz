import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const elements=new Map(),memory=new Map(),domEvents={},timers=new Map();let timerId=0;
const element=()=>{const classes=new Set();return {value:'',dataset:{},events:{},hidden:false,open:false,disabled:false,textContent:'',innerHTML:'',style:{},classList:{toggle(n,on){on?classes.add(n):classes.delete(n)},add(n){classes.add(n)},remove(n){classes.delete(n)},contains(n){return classes.has(n)}},querySelectorAll(){return []},querySelector(){return null},closest(){return null},contains(){return false},removeAttribute(){},remove(){},cloneNode(){return element()},setAttribute(){},addEventListener(n,fn){this.events[n]=fn},focus(){},select(){},click(){this.onclick?.()},showModal(){this.open=true},close(){this.open=false}}};
const document={body:{appendChild(){}},addEventListener(n,fn){domEvents[n]=fn},querySelector(s){if(!elements.has(s))elements.set(s,element());return elements.get(s)},querySelectorAll(){return []}};
const context=vm.createContext({document,window:{addEventListener(){}},localStorage:{getItem:k=>memory.get(k),setItem:(k,v)=>memory.set(k,v)},structuredClone,console,setTimeout(fn){timers.set(++timerId,fn);return timerId},clearTimeout(id){timers.delete(id)},setInterval(){}});
for(const file of ['source/app.js','source/social.js','source/set-actions.js','source/set-drag.js','source/local.js'])vm.runInContext(fs.readFileSync(file,'utf8').replace(/\nboot\(\);\s*$/,''),context);
const run=s=>vm.runInContext(s,context),page=fs.readFileSync('source/page.html','utf8');
run("studyStateKey=()=> 'lecture-lab-state'");
for(const match of fs.readFileSync('source/set-actions.js','utf8').matchAll(/\$\('#([a-z-]+)'\)/g))if(match[1]!=='new-set-card')assert.ok(page.includes('id="'+match[1]+'"'),match[1]);
run(`collectionId='c1';currentCollection={name:'Course',materials:[]};savedSets=[{id:'q1',title:'First quiz',format:'mcq',questionCount:6,answeredCount:1},{id:'q2',title:'Flashcards',format:'flashcard',questionCount:4,answeredCount:0}];activeLibraryTab='sets';renderQuizGrid();`);
assert.match(document.querySelector('#quiz-grid').innerHTML,/data-rename-set="q1"/);
assert.doesNotMatch(document.querySelector('#quiz-grid').innerHTML,/data-select-set/);
assert.doesNotMatch(page,/id="manage-sets"|id="remove-selected-sets"|id="set-selection-bar"/);
run("openSetRename('q1');$('#set-name').value='   ';");
await run("$('#rename-set-form').onsubmit({preventDefault(){}})");
assert.equal(document.querySelector('#rename-set-error').textContent,'Enter a name.');
run("$('#set-name').value='Renamed quiz';api=async()=>{throw Error('Fixture network failure')};");
await run("$('#rename-set-form').onsubmit({preventDefault(){}})");
assert.equal(run('savedSets[0].title'),'First quiz');assert.equal(document.querySelector('#rename-set-dialog').open,true);
run("startQuiz({id:'q1',collectionId:'c1',title:'First quiz',mode:'generated',format:'mcq',questions:structuredClone(samples.mcq)});answers.m1={submitted:true,correct:true};parentQuizId='q1';parentQuizTitle='First quiz';let requests=[];api=async(url,options)=>{requests.push({url,body:JSON.parse(options.body)});return {title:'Renamed quiz'}};refreshCollection=async()=>{};");
await run("$('#rename-set-form').onsubmit({preventDefault(){}})");
assert.equal(run('savedSets[0].title'),'Renamed quiz');assert.equal(run('quiz.title'),'Renamed quiz');assert.equal(run('parentQuizTitle'),'Renamed quiz');
assert.equal(run('answers.m1.correct'),true);assert.equal(document.querySelector('#rename-set-dialog').open,false);
run('saveSnapshot()');
assert.equal(JSON.parse(memory.get('lecture-lab-state')).removedSets,undefined);
assert.doesNotMatch(page,/undo-set-removal|set-undo-bar/);
console.log('Saved-set checks passed: Rename preserves progress and context; Undo controls and persisted recovery state are absent.');

assert.match(document.querySelector('#quiz-grid').innerHTML,/draggable="true" data-drag-set="q1"/);
const card=element();card.dataset.dragSet='q1';context.dragCard=card;
run("currentView='library';collectionId='c1';bindSetDrag(dragCard);api=async(url,options)=>{requests.push({url,body:JSON.parse(options.body)});return {removedQuizIds:['q1']}};");
const trash=document.querySelector('#set-trash');trash.getBoundingClientRect=()=>({left:100,right:300,top:600,bottom:720});
let prevented=false;
card.events.dragstart({target:card,dataTransfer:{setData(){}},preventDefault(){prevented=true}});
assert.equal(prevented,false);assert.equal(trash.hidden,false);
let stopped=false;card.events.click({preventDefault(){},stopPropagation(){stopped=true}});assert.equal(stopped,true);
const beforeCancel=run('requests.length');
domEvents.keydown({key:'Escape',preventDefault(){}});assert.equal(trash.hidden,true);assert.equal(run('requests.length'),beforeCancel);
card.events.dragstart({target:card,dataTransfer:{setData(){}},preventDefault(){}});
trash.events.dragover({preventDefault(){},dataTransfer:{}});assert.equal(trash.classList.contains('is-over'),true);
await trash.events.drop({preventDefault(){}});
assert.equal(trash.hidden,true);assert.equal(run('savedSets.some(q=>q.id==="q1")'),false);
assert.equal(run('savedSets.some(q=>q.id==="q2")'),true);
assert.equal(run('quiz'),null);assert.equal(run('parentQuizId'),null);
assert.equal(run('requests.at(-1).url'),'/api/collections/c1/quizzes/remove');
assert.deepEqual(JSON.parse(run('JSON.stringify(requests.at(-1).body)')),{quizIds:['q1']});
assert.equal(JSON.parse(memory.get('lecture-lab-state')).removedSets,undefined);
const beforeExternal=run('requests.length');await trash.events.drop({preventDefault(){}});
assert.equal(run('requests.length'),beforeExternal);
// Failed deletion leaves the card intact.
run("api=async()=>{throw Error('Cannot delete right now')};");
const second=element();second.dataset.dragSet='q2';context.secondCard=second;run('bindSetDrag(secondCard)');
second.events.dragstart({target:second,dataTransfer:{setData(){}},preventDefault(){}});
await trash.events.drop({preventDefault(){}});
assert.equal(run('savedSets.some(q=>q.id==="q2")'),true);assert.equal(run('setActionsBusy'),false);
// A held touch can drop a card; scrolling before the hold cancels pickup.
run("api=async(url,options)=>{requests.push({url,body:JSON.parse(options.body)});return {removedQuizIds:['q2']}};");
second.getBoundingClientRect=()=>({width:260});
second.events.touchstart({target:second,touches:[{clientX:50,clientY:50}]});
domEvents.touchmove({touches:[{clientX:50,clientY:80}],preventDefault(){throw Error('Scrolling should remain available')}});
assert.equal(run('setTouch'),null);assert.equal(trash.hidden,true);
second.events.touchstart({target:second,touches:[{clientX:50,clientY:50}]});
timers.get(run('setTouch.timer'))();assert.equal(trash.hidden,false);
domEvents.touchmove({touches:[{clientX:150,clientY:650}],preventDefault(){}});
assert.equal(trash.classList.contains('is-over'),true);
await domEvents.touchend({changedTouches:[{clientX:150,clientY:650}],preventDefault(){}});
assert.equal(run('savedSets.length'),0);assert.equal(trash.hidden,true);
assert.equal(JSON.parse(memory.get('lecture-lab-state')).removedSets,undefined);
// Keyboard pickup is explicit; a changed folder cancels deletion eligibility.
run("savedSets=[{id:'q2',title:'Cards',format:'flashcard',questionCount:4,answeredCount:0}];");
second.events.keydown({target:second,key:'Delete',preventDefault(){}});assert.equal(trash.hidden,false);
const beforeSwitch=run('requests.length');run("collectionId='other'");await trash.events.click();
assert.equal(run('requests.length'),beforeSwitch);assert.equal(run('savedSets.length'),1);assert.equal(trash.hidden,true);
run("collectionId='c1';quiz={mode:'bank',questions:[{originQuizId:'q2'}]};");
await run("deleteDraggedSet({id:'q2',collectionId:'c1'})");
assert.equal(run('quiz'),null);assert.equal(run('savedSets.length'),0);
console.log('Drag-to-trash passed: mouse drop, Escape cancellation, no accidental open, foreign-drop rejection, deletion failure, touch hold/drop, scrolling, keyboard pickup, folder isolation, and no recovery controls.');

// Materials share the same trash target, but keep the source-dependency preview.
context.confirm=()=>true;
run(`
collectionId='c1';activeLibraryTab='materials';currentView='library';busy=false;
currentCollection={id:'c1',materials:[{id:'m1',title:'Lecture one'},{id:'m2',title:'Lecture two'}]};
let materialRequests=[],previewText='';
confirm=text=>{previewText=text;return true};
refreshLibrary=async()=>{};
api=async(url,options={})=>{
  materialRequests.push({url,method:options.method||'GET'});
  if(url.endsWith('/deletion-impact'))return {quizzes:[{id:'dependent',title:'Dependent quiz'}]};
  currentCollection.materials=currentCollection.materials.filter(m=>m.id!=='m1');
  return {deletedQuizIds:['dependent']};
};
quiz={id:'dependent',mode:'generated'};answers={old:{submitted:true}};
composerMaterialId='m1';composerReady=true;composerStep='options';materialId='m1';
`);
const material=element();material.dataset.dragMaterial='m1';context.materialCard=material;
run('bindMaterialDrag(materialCard)');
material.events.dragstart({target:material,dataTransfer:{setData(){}},preventDefault(){throw Error('Material should be draggable')}});
assert.equal(trash.hidden,false);assert.equal(run('setDrag.kind'),'material');
await trash.events.drop({preventDefault(){}});
assert.equal(trash.hidden,true);assert.equal(run('setActionsBusy'),false);
assert.deepEqual(JSON.parse(run('JSON.stringify(materialRequests)')),[{url:'/api/materials/m1/deletion-impact',method:'GET'},{url:'/api/materials/m1',method:'DELETE'}]);
assert.match(run('previewText'),/Dependent quiz/);
assert.equal(run('quiz'),null);assert.equal(run('materialId'),null);
assert.equal(run('composerMaterialId'),null);assert.equal(run('composerReady'),false);
assert.equal(run('currentCollection.materials[0].id'),'m2');
const remaining=element();remaining.dataset.dragMaterial='m2';context.remainingMaterial=remaining;
run('bindMaterialDrag(remainingMaterial)');
// Cancelling the preview or receiving an active-job error keeps the material.
run("materialRequests=[];confirm=()=>false;api=async(url,options={})=>{materialRequests.push({url,method:options.method||'GET'});return {quizzes:[{id:'related',title:'Related quiz'}]}};");
remaining.events.dragstart({target:remaining,dataTransfer:{setData(){}},preventDefault(){}});
await trash.events.drop({preventDefault(){}});
assert.equal(run('materialRequests.length'),1);assert.equal(run('currentCollection.materials.length'),1);
run("materialRequests=[];confirm=()=>true;api=async(url,options={})=>{materialRequests.push({url,method:options.method||'GET'});if(options.method==='DELETE')throw Error('Cancel the dependent active job');return {quizzes:[]}};");
remaining.events.dragstart({target:remaining,dataTransfer:{setData(){}},preventDefault(){}});
await trash.events.drop({preventDefault(){}});
assert.equal(run('currentCollection.materials.length'),1);assert.equal(run('setActionsBusy'),false);
// Escape, changing folders during the preview, external drops, and busy states cannot delete.
run('materialRequests=[]');
remaining.events.dragstart({target:remaining,dataTransfer:{setData(){}},preventDefault(){}});
domEvents.keydown({key:'Escape',preventDefault(){}});
await trash.events.drop({preventDefault(){}});assert.equal(run('materialRequests.length'),0);
run("api=async(url,options={})=>{materialRequests.push({url,method:options.method||'GET'});collectionId='other';return {quizzes:[]}};");
remaining.events.keydown({target:remaining,key:'Delete',preventDefault(){}});await trash.events.click();
assert.equal(run('materialRequests.length'),1);assert.equal(run('currentCollection.materials.length'),1);
run("collectionId='c1';busy=true");let busyPrevented=false;
remaining.events.dragstart({target:remaining,dataTransfer:{setData(){}},preventDefault(){busyPrevented=true}});
assert.equal(busyPrevented,true);assert.equal(trash.hidden,true);run('busy=false');
// Clicking View sources or Process does not start a drag.
const action={closest:selector=>selector==='.material-actions'?{}:null};let actionPrevented=false;
remaining.events.dragstart({target:action,dataTransfer:{setData(){}},preventDefault(){actionPrevented=true}});
assert.equal(actionPrevented,true);assert.equal(trash.hidden,true);
// Touch scrolling stays available; long-press/drop dispatches to materials, not quizzes.
remaining.getBoundingClientRect=()=>({width:260});
remaining.events.touchstart({target:remaining,touches:[{clientX:50,clientY:50}]});
domEvents.touchmove({touches:[{clientX:50,clientY:90}],preventDefault(){throw Error('Keep scrolling')}});
assert.equal(run('setTouch'),null);
run("materialRequests=[];confirm=()=>{throw Error('No confirmation needed without dependent quizzes')};api=async(url,options={})=>{materialRequests.push({url,method:options.method||'GET'});return options.method==='DELETE'?{deletedQuizIds:[]}:{quizzes:[]}};");
remaining.events.touchstart({target:remaining,touches:[{clientX:50,clientY:50}]});timers.get(run('setTouch.timer'))();
await domEvents.touchend({changedTouches:[{clientX:150,clientY:650}],preventDefault(){}});
assert.equal(run('materialRequests.at(-1).url'),'/api/materials/m2');
assert.equal(run('materialRequests.at(-1).method'),'DELETE');assert.equal(trash.hidden,true);
assert.doesNotMatch(fs.readFileSync('source/local.js','utf8'),/data-delete="/);
console.log('Material drag-to-trash passed: mouse, touch, keyboard, dependency preview, cancellation, busy/active-job failures, source controls, folder isolation, and dependent practice cleanup.');

// Leave group is available only in the selected group detail, preserving private practice.
run(`currentUser={id:'owner'};currentView='groups';currentGroupId=null;groupRows=[{id:'g1',name:'Course circle',memberCount:2,setCount:1}];setGroupDetail(false);renderGroupCards();let groupRequests=[];api=async(url,options)=>{groupRequests.push({url,method:options.method});return {left:true}};quiz={id:'private',mode:'generated'};answers={q0:{submitted:true}};`);
assert.doesNotMatch(document.querySelector('#group-list').innerHTML,/Leave group|draggable=/);
assert.match(document.querySelector('#group-list').innerHTML,/data-open-group="g1"/);
await run("leaveGroup('g1')");assert.equal(run('groupRequests.length'),0);
run("currentGroupId='g1';setGroupDetail(true)");await run("$('#group-leave').onclick()");
assert.equal(run('groupRequests[0].url'),'/api/groups/g1/leave');assert.equal(run('groupRequests[0].method'),'POST');
assert.equal(run('currentGroupId'),null);assert.equal(document.querySelector('#group-detail').hidden,true);
assert.equal(document.querySelector('#groups-overview-header').hidden,false);assert.equal(run('quiz.id'),'private');
run(`currentGroupId='retry-detail';setGroupDetail(true);api=async()=>{throw Error('Please retry')};`);
await run("$('#group-leave').onclick()");assert.equal(run('currentGroupId'),'retry-detail');
assert.equal(document.querySelector('#group-detail').hidden,false);assert.equal(run('setActionsBusy'),false);
console.log('Group detail leave checks passed: no exit on listing, explicit detail-only action, restored overview, failed-request retry, and preserved private practice.');

// Only group owners can drag shared quiz copies to the existing trash target.
run(`
currentUser={id:'owner'};currentGroupId='group-1';currentView='groups';setGroupDetail(true);busy=false;
currentGroupDetail={id:'group-1',owner_id:'owner',name:'Study circle',invite_code:'CODE',members:[],sets:[{id:'shared-1',title:'Shared quiz',format:'mcq',count:4,authorName:'Member'},{id:'shared-2',title:'Shared cards',format:'flashcard',count:4,authorName:'Member'}]};
renderGroupSets(currentGroupDetail);let copyRequests=[];
api=async(url,options={})=>{copyRequests.push({url,method:options.method||'GET'});if(options.method==='DELETE'){currentGroupDetail.sets=currentGroupDetail.sets.filter(s=>!url.endsWith('/'+s.id));return {deleted:true}}return currentGroupDetail};
quiz={id:'shared-shared-1',shareId:'shared-1',mode:'shared',groupId:'group-1'};answers={q0:{submitted:true}};
`);
assert.match(document.querySelector('#group-sets').innerHTML,/data-drag-share="shared-1"/);
const sharedCard=element();sharedCard.dataset.dragShare='shared-1';context.sharedCard=sharedCard;run('bindSharedSetDrag(sharedCard)');
sharedCard.events.dragstart({target:sharedCard,dataTransfer:{setData(){}},preventDefault(){throw Error('Owner can drag')}});
assert.equal(trash.hidden,false);domEvents.keydown({key:'Escape',preventDefault(){}});assert.equal(run('copyRequests.length'),0);
sharedCard.events.dragstart({target:sharedCard,dataTransfer:{setData(){}},preventDefault(){}});await trash.events.drop({preventDefault(){}});
assert.equal(run('copyRequests[0].url'),'/api/groups/group-1/sets/shared-1');assert.equal(run('copyRequests[0].method'),'DELETE');
assert.equal(run('quiz'),null);assert.equal(run('currentGroupDetail.sets.length'),1);assert.equal(trash.hidden,true);
// Author/member identity does not grant group-owner deletion rights.
run("currentUser={id:'member'};renderGroupSets(currentGroupDetail)");
assert.doesNotMatch(document.querySelector('#group-sets').innerHTML,/data-drag-share|draggable=/);
const sharedSecond=element();sharedSecond.dataset.dragShare='shared-2';context.sharedSecond=sharedSecond;run('bindSharedSetDrag(sharedSecond)');let memberBlocked=false;
sharedSecond.events.dragstart({target:sharedSecond,dataTransfer:{setData(){}},preventDefault(){memberBlocked=true}});assert.equal(memberBlocked,true);
// Failed deletion preserves the copy and private practice. Keyboard pickup uses the same endpoint.
run("currentUser={id:'owner'};quiz={id:'original',mode:'generated'};answers={q0:{submitted:true}};api=async()=>{throw Error('Owner changed or network failure')}");
sharedSecond.events.keydown({target:sharedSecond,key:'Delete',preventDefault(){}});await trash.events.click();
assert.equal(run('currentGroupDetail.sets.length'),1);assert.equal(run('quiz.id'),'original');assert.equal(run('setActionsBusy'),false);
// Changing groups or ownership after pickup invalidates the operation.
run("copyRequests=[];api=async(url)=>{copyRequests.push(url);return {deleted:true}}");
sharedSecond.events.dragstart({target:sharedSecond,dataTransfer:{setData(){}},preventDefault(){}});run("currentGroupId='different'");await trash.events.drop({preventDefault(){}});
assert.equal(run('copyRequests.length'),0);run("currentGroupId='group-1'");
sharedSecond.events.dragstart({target:sharedSecond,dataTransfer:{setData(){}},preventDefault(){}});run("currentGroupDetail.owner_id='new-owner'");await trash.events.drop({preventDefault(){}});
assert.equal(run('copyRequests.length'),0);
// A long-press touch drop removes only the shared copy and preserves the original.
run("currentGroupDetail.owner_id='owner';api=async(url,options={})=>{copyRequests.push(url);if(options.method==='DELETE'){currentGroupDetail.sets=[];return {deleted:true}}return currentGroupDetail}");
sharedSecond.getBoundingClientRect=()=>({width:260});sharedSecond.events.touchstart({target:sharedSecond,touches:[{clientX:50,clientY:50}]});timers.get(run('setTouch.timer'))();
await domEvents.touchend({changedTouches:[{clientX:150,clientY:650}],preventDefault(){}});
assert.equal(run('copyRequests[0]'),'/api/groups/group-1/sets/shared-2');assert.equal(run('quiz.id'),'original');assert.equal(run('answers.q0.submitted'),true);
assert.equal(run('currentGroupDetail.sets.length'),0);assert.equal(trash.hidden,true);
console.log('Shared-set drag deletion passed: owner-only mouse/touch/keyboard, Escape, API failures, group/ownership changes, refreshed group, and preserved private quiz/progress.');
