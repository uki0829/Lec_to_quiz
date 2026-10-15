import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const page=readFileSync('source/page.html','utf8'),social=readFileSync('source/social.js','utf8');
for(const match of social.matchAll(/\$\('#([^']+)'\)/g))assert.ok(page.includes('id="'+match[1]+'"'),`Missing social control ${match[1]}`);
const elements=new Map(),memory=new Map();
function element(){return {value:'',dataset:{},open:false,hidden:false,disabled:false,textContent:'',innerHTML:'',style:{},classList:{add(){},remove(){},toggle(){}},addEventListener(){},querySelectorAll(){return []},setAttribute(){},focus(){},click(){this.onclick?.()},showModal(){this.open=true},close(){this.open=false}};}
const document={querySelector(s){if(!elements.has(s))elements.set(s,element());return elements.get(s)},querySelectorAll(){return []}};
const context=vm.createContext({document,window:{addEventListener(){},scrollTo(){}},localStorage:{getItem:key=>memory.get(key)||null,setItem:(key,value)=>memory.set(key,value),removeItem:key=>memory.delete(key)},structuredClone,console,setTimeout,clearTimeout,setInterval(){},URLSearchParams,location:{search:''}});
for(const file of ['source/app.js','source/social.js','source/local.js'])vm.runInContext(readFileSync(file,'utf8').replace(/\nboot\(\);\s*$/,''),context);
const run=code=>vm.runInContext(code,context);
run("setAuthMode('register')");
assert.equal(document.querySelector('#auth-name-field').hidden,false);
assert.equal(document.querySelector('#auth-name').required,true);
assert.equal(document.querySelector('#auth-submit').textContent,'Create account');
run('showSignIn()');
assert.equal(document.querySelector('#auth-name-field').hidden,true);
assert.equal(document.querySelector('#auth-submit').textContent,'Sign in');
run("currentUser={id:'student-a'};quiz=null;saveSnapshot();");
assert.ok(memory.has('lecture-lab-state:student-a'));
run("currentUser={id:'student-b'};saveSnapshot();");
assert.ok(memory.has('lecture-lab-state:student-b'));
assert.notEqual(run('studyStateKey()'),'lecture-lab-state:student-a');
run("quiz={id:'shared-s1',shareId:'s1',title:'Shared cards',mode:'shared',format:'flashcard',questions:structuredClone(samples.flashcard)};index=0;answers={f1:{reviewed:true,submitted:true,correct:true}};let captured=null;api=async(url,options)=>{captured={url,body:JSON.parse(options.body)};return {saved:true}};");
await run('flushPracticeProgress()');
assert.equal(run('captured.url'),'/api/shared-sets/s1/progress');
assert.equal(run('captured.body.answers.f1.correct'),true);
assert.doesNotMatch(run('sourceHtml(quiz.questions[0])'),/Open source material/);
run("startQuiz(quiz);");
assert.equal(document.querySelector('#share-current').hidden,true);
assert.match(document.querySelector('#mode-badge').textContent,/Shared set/);
run("quiz={id:'private',mode:'generated',title:'Private',format:'mcq',questions:structuredClone(samples.mcq)};updateSocialQuiz(quiz);");
assert.equal(document.querySelector('#share-current').hidden,false);
assert.ok(page.includes('Original files stay private.'));
console.log('Social UI checks passed: real control IDs, register/sign-in fields, user-scoped browser state, shared progress, source privacy, and explicit sharing.');

// Group details have their own heading; leaving is available only inside a group.
run(`
currentUser={id:'student-b'};currentView='groups';
let socialCalls=[],sharedCall=null,openedGroup=null;
let groupFixture={id:'study-circle',name:'Study circle',owner_id:'student-b',invite_code:'CIRCLE',members:[],sets:[]};
api=async(url,options)=>{
  socialCalls.push(url);
  if(url==='/api/groups')return {groups:[groupFixture]};
  if(url==='/api/groups/study-circle')return groupFixture;
  if(url==='/api/collections')return {collections:[{id:'c1',name:'Computer science'},{id:'c2',name:'Psychology'},{id:'empty',name:'Empty course'}]};
  if(url.startsWith('/api/quizzes?')){
    const params=new URLSearchParams(url.split('?')[1]);
    const cid=params.get('collectionId'),gid=params.get('groupId');
    const sets=cid==='c1'?[{id:'saved-quiz',collectionId:'c1',title:'Gradient descent',format:'mcq'},{id:'cards',collectionId:'c1',title:'Terms',format:'flashcard'},{id:'guide',collectionId:'c1',title:'Guide',format:'cheatsheet'}]:cid==='c2'?[{id:'psych',collectionId:'c2',title:'Memory',format:'mcq'}]:[];
    return {quizzes:sets.map(q=>({...q,alreadyShared:gid==='study-circle'&&Boolean(groupFixture.addedQuizIds?.includes(q.id))}))};
  }
  if(options?.method==='POST'){sharedCall={url,body:JSON.parse(options.body)};return {groupId:'study-circle',shareId:'new-copy'}};
  throw Error(url);
};
let fixtureSocialApi=api;
`);
await run("openGroup('study-circle')");
assert.equal(document.querySelector('#groups-overview-header').hidden,true);
assert.equal(document.querySelector('#groups-description').hidden,true);
assert.equal(document.querySelector('#group-detail').hidden,false);
await run('showGroups()');
assert.equal(document.querySelector('#groups-overview-header').hidden,false);
assert.equal(document.querySelector('#group-detail').hidden,true);
assert.doesNotMatch(document.querySelector('#group-list').innerHTML,/Leave group|data-leave-group|draggable=/);
await run("openGroup('study-circle')");await run('openShareDialog()');
assert.equal(document.querySelector('#share-group-field').hidden,true);
assert.equal(document.querySelector('#share-dialog-title').textContent,'Add study set');
assert.equal(document.querySelector('#share-set-step').hidden,true);
assert.equal(document.querySelector('#confirm-share').disabled,true);
assert.equal(run("socialCalls.includes('/api/quizzes')"),false);
run("$('#share-collection').value='c1'");await run("$('#share-collection').onchange()");
assert.equal(document.querySelector('#share-set-step').hidden,false);
assert.match(document.querySelector('#share-set').innerHTML,/Gradient descent/);
assert.match(document.querySelector('#share-set').innerHTML,/Flashcards/);
assert.match(document.querySelector('#share-set').innerHTML,/Cheat Sheet/);
assert.doesNotMatch(document.querySelector('#share-set').innerHTML,/Memory/);
assert.equal(document.querySelector('#confirm-share').disabled,true);
run("$('#share-set').value='saved-quiz';$('#share-set').onchange();let realOpenGroup=openGroup;openGroup=async id=>openedGroup=id");
assert.equal(document.querySelector('#confirm-share').disabled,false);
await run("$('#share-form').onsubmit({preventDefault(){}})");
assert.equal(run('sharedCall.url'),'/api/groups/study-circle/share');
assert.equal(run('sharedCall.body.quizId'),'saved-quiz');assert.equal(run('openedGroup'),'study-circle');
assert.equal(document.querySelector('#share-dialog').open,false);
assert.equal(document.querySelector('#confirm-share').disabled,false);
// A new collection resets the previous choice and cannot submit an old set.
await run('openShareDialog()');run("$('#share-collection').value='empty'");await run("$('#share-collection').onchange()");
assert.equal(document.querySelector('#share-error').textContent,'No saved sets in this collection.');
assert.equal(document.querySelector('#confirm-share').disabled,true);
assert.equal(document.querySelector('#share-set').disabled,true);
run("$('#share-collection').value='c2'");await run("$('#share-collection').onchange()");
assert.doesNotMatch(document.querySelector('#share-set').innerHTML,/Gradient descent/);
run("$('#share-set').value='saved-quiz';$('#share-set').onchange()");assert.equal(document.querySelector('#confirm-share').disabled,true);
// Late responses from a previous collection cannot replace the current options.
run(`
let resolveFirst,resolveSecond;
api=url=>url.startsWith('/api/groups/')?Promise.resolve(groupFixture):new Promise(resolve=>{if(url.includes('collectionId=c1'))resolveFirst=resolve;else resolveSecond=resolve});
$('#share-collection').value='c1';let firstLoad=$('#share-collection').onchange();
$('#share-collection').value='c2';let secondLoad=$('#share-collection').onchange();
resolveSecond({quizzes:[{id:'psych',collectionId:'c2',format:'mcq',title:'Memory',alreadyShared:false}]});
`);
await run('secondLoad');run("resolveFirst({quizzes:[{id:'old',collectionId:'c1',format:'mcq',title:'Stale lecture',alreadyShared:false}]})");await run('firstLoad');
assert.equal(run('shareCollectionId'),'c2');
assert.doesNotMatch(document.querySelector('#share-set').innerHTML,/Stale lecture/);
// Failed sharing preserves selections for retry; a duplicate click schedules no second write.
run(`$('#share-set').value='psych';$('#share-set').onchange();api=async()=>{throw Error('Sharing unavailable')};`);
await run("$('#share-form').onsubmit({preventDefault(){}})");
assert.equal(document.querySelector('#share-dialog').open,true);assert.equal(document.querySelector('#share-set').value,'psych');
assert.equal(document.querySelector('#share-error').textContent,'Sharing unavailable');assert.equal(document.querySelector('#confirm-share').disabled,false);
run(`let finishShare,writes=0;api=()=>{writes++;return new Promise(resolve=>finishShare=resolve)};let sharing=$('#share-form').onsubmit({preventDefault(){}})`);
await run("$('#share-form').onsubmit({preventDefault(){}})");assert.equal(run('writes'),1);
run("finishShare({groupId:'study-circle',shareId:'another'})");await run('sharing');
// Outside a group, selecting a destination remains explicit.
run("api=fixtureSocialApi;currentView='study';currentGroupId='study-circle'");await run('openShareDialog()');
assert.equal(document.querySelector('#share-group-field').hidden,false);assert.equal(document.querySelector('#share-group').value,'');
console.log('Group and sharing checks passed: detail-only leave, hidden overview, collection-first selection, all saved formats, empty collections, stale requests, failed-sharing retry, duplicate-submit prevention, and explicit destination outside groups.');

// Already-shared sets remain visible but disabled for the selected group.
run("api=fixtureSocialApi;currentView='groups';currentGroupId='study-circle';groupFixture.addedQuizIds=['saved-quiz'];");
await run('openShareDialog()');run("$('#share-collection').value='c1'");await run("$('#share-collection').onchange()");
assert.match(document.querySelector('#share-set').innerHTML,/value="saved-quiz"[^>]* disabled>[^<]*Already added/);
assert.doesNotMatch(document.querySelector('#share-set').innerHTML,/value="cards"[^>]* disabled/);
run("$('#share-set').value='saved-quiz';$('#share-set').onchange()");assert.equal(document.querySelector('#confirm-share').disabled,true);
run("$('#share-set').value='cards';$('#share-set').onchange()");assert.equal(document.querySelector('#confirm-share').disabled,false);
// A concurrent share by another request is rejected and refreshed as disabled.
run(`api=async(url,options)=>{if(options?.method==='POST'){groupFixture.addedQuizIds=['saved-quiz','cards'];throw Error('This set is already in the group.')};return fixtureSocialApi(url,options)};`);
await run("$('#share-form').onsubmit({preventDefault(){}})");
assert.equal(document.querySelector('#share-dialog').open,true);
assert.match(document.querySelector('#share-set').innerHTML,/value="cards"[^>]* disabled>[^<]*Already added/);
assert.equal(document.querySelector('#confirm-share').disabled,true);
assert.equal(document.querySelector('#share-error').textContent,'');
// Sharing to another destination recomputes eligibility instead of reusing the old group.
run("shareTargetGroupId=null;shareGroups.push({id:'other-circle'});$('#share-group').value='other-circle';api=fixtureSocialApi");
await run("$('#share-group').onchange()");
assert.doesNotMatch(document.querySelector('#share-set').innerHTML,/Already added/);
run("$('#share-set').value='saved-quiz';$('#share-set').onchange()");assert.equal(document.querySelector('#confirm-share').disabled,false);
console.log('Duplicate sharing checks passed: disabled existing options, blocked programmatic choice, silent concurrent-conflict refresh, and group-specific eligibility.');

// Shared practice returns to its own group even without an in-memory group selection.
run(`
openGroup=realOpenGroup;currentGroupId=null;let returnCalls=[];
api=async(url,options)=>{returnCalls.push({url,method:options?.method||'GET'});if(url.endsWith('/progress'))return {saved:true};return fixtureSocialApi(url,options)};
startQuiz({id:'shared-return',shareId:'return',groupId:'study-circle',title:'Shared practice',mode:'shared',format:'flashcard',questions:structuredClone(samples.flashcard)});
`);
assert.match(document.querySelector('#back-library').innerHTML,/Return to group/);
run('showSummary()');assert.match(document.querySelector('#summary').innerHTML,/Return to group/);
await run("$('#back-library').onclick()");
assert.equal(run('returnCalls[0].url'),'/api/shared-sets/return/progress');
assert.equal(run('returnCalls[0].method'),'PUT');assert.equal(run('currentGroupId'),'study-circle');
assert.equal(run('currentView'),'groups');assert.equal(document.querySelector('#group-detail').hidden,false);
assert.equal(document.querySelector('#back-library').disabled,false);
run("startQuiz({id:'private',title:'Private quiz',mode:'generated',format:'mcq',questions:structuredClone(samples.mcq)})");
assert.match(document.querySelector('#back-library').innerHTML,/>Home</);
await run("$('#back-library').onclick()");assert.equal(run('currentView'),'library');
// A departed/removed group returns to the group list rather than a hidden error panel.
run(`api=async(url,options)=>{if(url==='/api/groups/no-longer-available')throw Error('Study group not found.');if(url.endsWith('/progress'))return {saved:true};return fixtureSocialApi(url,options)};
startQuiz({id:'shared-gone',shareId:'gone',groupId:'no-longer-available',title:'Old shared set',mode:'shared',format:'flashcard',questions:structuredClone(samples.flashcard)});`);
await run("$('#back-library').onclick()");assert.equal(run('currentView'),'groups');
assert.equal(document.querySelector('#group-detail').hidden,true);assert.equal(document.querySelector('#back-library').disabled,false);
console.log('Shared practice return passed: top/summary labels, saved progress before return, group identity after reload, private Home reset, and missing-group recovery.');
