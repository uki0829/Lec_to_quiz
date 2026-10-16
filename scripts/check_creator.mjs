import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const elements=new Map();
function element(){return {value:'',dataset:{},open:false,hidden:false,disabled:false,textContent:'',innerHTML:'',style:{},classList:{add(){},remove(){},toggle(){}},addEventListener(){},querySelectorAll(){return []},setAttribute(){},focus(){},click(){this.onclick?.()},showModal(){this.open=true},close(){this.open=false}};}
const document={querySelector(s){if(!elements.has(s))elements.set(s,element());return elements.get(s)},querySelectorAll(){return []}};
class FormData {constructor(){this.values=[]}append(...entry){this.values.push(entry)}}
const context=vm.createContext({document,window:{addEventListener(){}},localStorage:{setItem(){}},FormData,structuredClone,console,setTimeout,clearTimeout,setInterval(){},confirm(){return false}});
vm.runInContext(readFileSync('source/app.js','utf8'),context);
const local=readFileSync('source/local.js','utf8').replace(/\nboot\(\);\s*$/,'');
vm.runInContext(local,context);
const run=code=>vm.runInContext(code,context);
run("$('#count').value='6';currentCollection={name:'Machine Learning',materials:[{id:'old',searchReady:true}]};collectionId='c1';updateComposerState();");
assert.equal(document.querySelector('#composer-options-step').hidden,true);
assert.equal(document.querySelector('#upload-continue').disabled,true);
assert.equal(document.querySelector('#generate').disabled,true);
// Existing sources cannot silently skip upload: using them is an explicit action.
run("$('#use-saved-materials').onclick();");
assert.equal(document.querySelector('#composer-options-step').hidden,false);
assert.equal(document.querySelector('#generate').disabled,true);
run("$('#request').value='Learning rate';updateComposerState();");
assert.equal(document.querySelector('#generate').disabled,false);
run("$('#composer-back').onclick();$('#composer-notes').value='New lecture';updateComposerState();");
assert.equal(document.querySelector('#composer-options-step').hidden,true);
assert.equal(document.querySelector('#upload-continue').disabled,false);
// Exercise the upload handler against durable material responses and job outcomes.
run(`
let outcome='failed',ready=false,calls=[];
api=async(url,options)=>{calls.push({url,options});if(url==='/api/materials')return {materialId:'new',jobId:'job'};if(url==='/api/materials/new')return {id:'new',collectionId:'c1',title:'Second lecture',searchReady:ready};throw Error(url)};
refreshLibrary=async()=>{currentCollection={name:'Machine Learning',materials:[{id:'old',searchReady:true},{id:'new',searchReady:ready}]};updateComposerState()};
watchJob=async()=>{if(outcome!=='completed'){lastFailedJob='job';throw Error('Processing was '+outcome)}return {kind:'material',material_id:'new'}};
`);
await assert.rejects(run('ensureMaterial(true)'),/failed/);
run('setBusy(false)');
assert.equal(document.querySelector('#composer-options-step').hidden,true);
assert.equal(document.querySelector('#upload-continue').disabled,true);
assert.equal(document.querySelector('#composer-retry').hidden,false);
assert.equal(run('composerMaterialId'),'new');
// Completion alone is insufficient: the source must be indexed and searchable.
await assert.rejects(run("finishComposerMaterial('new')"),/not ready/);
assert.equal(document.querySelector('#composer-options-step').hidden,true);
run("ready=true;format='flashcard'");
await run("finishComposerMaterial('new')");
run("setBusy(false)");
assert.equal(document.querySelector('#composer-options-step').hidden,false);
assert.equal(document.querySelector('#composer-collection').disabled,true);
assert.equal(run('format'),'flashcard');
assert.equal(run('composerJobId'),null);
// A removed or unavailable bound lecture blocks generation despite other ready lectures.
run("currentCollection.materials=currentCollection.materials.filter(m=>m.id!=='new');updateComposerState()");
assert.equal(document.querySelector('#generate').disabled,true);
// The hidden generation action also guards the stage, independently of button state.
run("composerStep='upload';busy=false;calls=[]");
await run("$('#generate').onclick()");
assert.equal(run('calls.length'),0);
// First-time uploads omit collectionId; the server creates and returns their collection.
run("collectionId=null;composerMaterialId=null;composerReady=false;$('#composer-notes').value='First lecture';outcome='completed';ready=true;calls=[]");
await run('ensureMaterial(true)');
assert.equal(run("calls[0].options.body.values.some(([name])=>name==='collectionId')"),false);
assert.equal(run('collectionId'),'c1');
assert.equal(run('composerStep'),'options');
console.log('Creator checks passed: upload-first gating, explicit saved lectures, failed-job recovery, indexed readiness, collection ownership, format retention, and first-upload collection creation.');
// Cancellation also leaves the upload step locked, with durable retry information.
run("composerStep='upload';composerReady=false;composerMaterialId=null;composerJobId=null;$('#composer-notes').value='Cancelled lecture';outcome='cancelled';calls=[]");
await assert.rejects(run('ensureMaterial(true)'),/cancelled/);
run('setBusy(false)');
assert.equal(document.querySelector('#composer-options-step').hidden,true);
assert.equal(document.querySelector('#generate').disabled,true);
assert.equal(document.querySelector('#composer-retry').hidden,false);
// Boot restores a format while buttons are disabled; clicking a disabled button would fail.
context.localStorage.getItem=()=>JSON.stringify({collectionId:'c1',format:'flashcard',count:'4',request:'Gradient descent',creator:{open:true,step:'options',materialId:'new',title:'Second lecture',heading:'Create flashcards'}});
run(`
activeJob=null;lastFailedJob=null;composerJobId=null;format='mcq';
checkConnection=async()=>{};
api=async(url)=>{if(url==='/api/collections')return {collections:[{id:'c1'}]};if(url==='/api/materials/new')return {id:'new',collectionId:'c1',title:'Second lecture',searchReady:true};throw Error(url)};
`);
await run('boot()');
assert.equal(run('format'),'flashcard');
assert.equal(run('composerStep'),'options');
assert.equal(document.querySelector('#composer-title').textContent,'Create flashcards');
console.log('Cancellation and refresh restoration checks passed.');

// New reference format has sections and no irrelevant difficulty control.
run("format='cheatsheet';updateComposerState()");
assert.equal(document.querySelector('#count-field').hidden,true);
assert.equal(document.querySelector('#difficulty-field').hidden,true);
assert.equal(document.querySelector('#generate').textContent,'Create cheat sheet');
run("savedSets=[{id:'sheet',title:'Gradient reference',format:'cheatsheet',sectionCount:4,questionCount:0},{id:'quiz',title:'Gradient quiz',format:'mcq',questionCount:6}];$('#search-sets').value='';$('#set-format-filter').value='cheatsheet';renderQuizGrid()");
assert.match(document.querySelector('#quiz-grid').innerHTML,/4 sections/);
assert.match(document.querySelector('#quiz-grid').innerHTML,/Open sheet/);
assert.doesNotMatch(document.querySelector('#quiz-grid').innerHTML,/Gradient quiz/);
const cards=[{dataset:{materialTitle:'gradient.pdf'},hidden:false},{dataset:{materialTitle:'history.pdf'},hidden:false}];
document.querySelector('#collection-materials').querySelectorAll=()=>cards;
run("$('#search-sets').value='gradient';setLibraryTab('materials')");
assert.equal(document.querySelector('#search-sets').disabled,false);
assert.equal(document.querySelector('#set-format-filter').hidden,true);
assert.equal(cards[0].hidden,false);assert.equal(cards[1].hidden,true);
console.log('Library checks passed: sheet counts, type filter, material search, and cheat sheet settings.');
// Folder deletion clears only dependent work and resets a removed bound lecture.
run(`
collectionRows=[{id:'gone',name:'Old course'},{id:'kept',name:'Another course'}];collectionId='gone';
quiz={id:'removed-quiz',mode:'generated'};answers={q0:{value:1}};parentQuizId='removed-quiz';parentQuizTitle='Old set';
materialId='removed-material';composerMaterialId='removed-material';composerReady=true;composerStep='options';lastFailedJob='removed-job';
folderDeletion={id:'gone',revision:'r1'};$('#delete-folder-dialog').showModal();
api=async(url,options)=>{calls.push({url,options});return {deletedMaterialIds:['removed-material'],deletedQuizIds:['removed-quiz'],deletedJobIds:['removed-job']}};
refreshLibrary=async()=>{collectionRows=collectionRows.filter(c=>c.id!=='gone')};
`);
await run("$('#confirm-delete-folder').onclick()");
assert.equal(run('collectionId'),'kept');assert.equal(run('quiz'),null);
assert.equal(run('parentQuizId'),null);assert.equal(run('materialId'),null);
assert.equal(run('composerStep'),'upload');assert.equal(run('composerReady'),false);
assert.equal(run('lastFailedJob'),null);assert.equal(document.querySelector('#delete-folder-dialog').open,false);
// Deleting another folder preserves active practice. Failure preserves all state.
run("collectionId='kept';quiz={id:'keep-quiz',mode:'generated'};answers={q0:{value:2}};folderDeletion={id:'gone',revision:'r2'};$('#delete-folder-dialog').showModal();");
await run("$('#confirm-delete-folder').onclick()");
assert.equal(run('quiz.id'),'keep-quiz');assert.equal(run('answers.q0.value'),2);
run("folderDeletion={id:'kept',revision:'stale'};$('#delete-folder-dialog').showModal();api=async()=>{throw Error('Folder contents changed. Close and reopen the deletion preview.');}");
await run("$('#confirm-delete-folder').onclick()");
assert.equal(run('collectionId'),'kept');assert.equal(run('quiz.id'),'keep-quiz');
assert.equal(document.querySelector('#delete-folder-dialog').open,true);
assert.match(document.querySelector('#delete-folder-error').textContent,/changed/);
run("closeFolderDeletion()");assert.equal(document.querySelector('#delete-folder-dialog').open,false);
console.log('Folder UI checks passed: dependent-state cleanup, preserved unrelated practice, stale-preview errors, and cancellation.');
// A bank may contain the same question ID from different saved sets.
run(`
busy=false;collectionId='course';currentCollection={id:'course',materials:[]};$('#search-sets').value='';
bankRows=[{...structuredClone(samples.flashcard[0]),originQuizId:'set-a',originQuestionId:'q0',quizTitle:'Lecture A',starred:true},{...structuredClone(samples.flashcard[1]),originQuizId:'set-b',originQuestionId:'q0',quizTitle:'Lecture B',starred:true}];
practiceQuestionBank();
`);
assert.equal(run('quiz.mode'),'bank');assert.equal(run('quiz.questions.length'),2);
assert.notEqual(run('quiz.questions[0].id'),run('quiz.questions[1].id'));
assert.equal(run('cardOrigin(quiz.questions[0]).questionId'),'q0');
run(`api=async(url,options)=>({starred:JSON.parse(options.body).starred});`);
await run('toggleQuestionStar(quiz.questions[0])');
assert.equal(run('bankRows.length'),1);assert.equal(run('isQuestionStarred(quiz.questions[0])'),false);
await run('toggleQuestionStar(quiz.questions[0])');
assert.equal(run('bankRows.length'),2);assert.equal(run('isQuestionStarred(quiz.questions[0])'),true);
run(`let hintCalls=0;api=async()=>{hintCalls++;return {hint:'Think about the direction of the gradient.'}};`);
await run('requestFlashcardHint(quiz.questions[0])');
assert.equal(run('answers[quiz.questions[0].id].hintVisible'),true);
await run('requestFlashcardHint(quiz.questions[0])');
assert.equal(run('answers[quiz.questions[0].id].hintVisible'),false);assert.equal(run('hintCalls'),1);
run(`const bankCard=structuredClone(quiz.questions[0]);const bigBank={title:'Question bank',mode:'bank',format:'flashcard',questions:Array.from({length:64},(_,i)=>({...bankCard,id:'bank-'+i}))};validateImported(bigBank);`);
assert.throws(()=>run(`validateImported({...bigBank,mode:'imported'})`));
console.log('Question bank checks passed: origin identities, unique practice IDs, star/unstar, cached hint toggling, and 64-card bank restoration.');

// Restart persists an empty session under the same ID and updates the home card.
run(`
savedSets=[{id:'restart-set',title:'Saved set',format:'flashcard',questionCount:6,answeredCount:6}];
quiz={id:'restart-set',title:'Saved set',mode:'generated',format:'flashcard',questions:structuredClone(samples.flashcard)};
index=5;answers=Object.fromEntries(quiz.questions.map(q=>[q.id,{submitted:true,correct:true,reviewed:true}]));
let capturedState=null,capturedProgress=null;
localStorage.setItem=(key,value)=>capturedState=JSON.parse(value);
api=async(url,options)=>{capturedProgress=JSON.parse(options.body);return {saved:true}};
showSummary();$('#review-restart').onclick();
`);
await new Promise(resolve=>setTimeout(resolve,300));
assert.deepEqual(JSON.parse(JSON.stringify(run('capturedProgress'))),{index:0,answers:{},review:false});
assert.equal(run('capturedState.quiz.id'),'restart-set');
assert.equal(run('capturedState.quiz.progress.review'),false);
assert.equal(run('savedSets[0].answeredCount'),0);
run("$('#back-library').onclick();");
assert.equal(run('currentView'),'library');assert.equal(run('activeLibraryTab'),'sets');
assert.doesNotMatch(document.querySelector('#quiz-grid').innerHTML,/Continue · 6/);
run("showSummary();$('#back-library').onclick();");
assert.equal(run('capturedState.quiz.progress.review'),true);
console.log('Restart persistence checks passed: unchanged identity, cleared answers/review, current home counts, and Home opens Sets.');

// Material processing shows an accessible bar without internal unit counts.
run("showJob({kind:'material',status:'running',stage:'Reading PDF pages',completed:3,total:20})");
assert.match(document.querySelector('#job-status').innerHTML, /<progress/);
assert.doesNotMatch(document.querySelector('#job-status').innerHTML, /units|Reading PDF pages|3 of 20/);
run("showJob({kind:'material',status:'running',completed:0,total:0})");
assert.match(document.querySelector('#job-status').innerHTML, /<progress/);
assert.doesNotMatch(document.querySelector('#job-status').innerHTML, /value=/);
// Opening the uploader after cancellation clears both modal and global errors.
run("activeJob=null;busy=false;currentCollection={name:'Physics',materials:[]};collectionId='c1';message('Processing cancelled',true);$('#job-panel').hidden=false;openUpload()");
assert.equal(document.querySelector('#upload-message').textContent, '');
assert.equal(document.querySelector('#composer-message').textContent, '');
assert.equal(document.querySelector('#job-panel').hidden, true);
assert.equal(document.querySelector('#job-status').innerHTML, '');
console.log('Upload polish passed: progress-only material processing and cleared cancellation errors on reopening.');

// Star feedback is immediate, persisted on success, and rolled back on failure.
run("quiz={id:'optimistic-star',collectionId:'c1',mode:'generated',format:'flashcard',title:'Cards',questions:structuredClone(samples.flashcard)};collectionId='c1';currentCollection={id:'c1',materials:[]};bankRows=[];index=0;answers={};");
let finishStar;
context.api=(url,options)=>new Promise(resolve=>{finishStar=()=>resolve({starred:JSON.parse(options.body).starred})});
let pendingStar=run('toggleQuestionStar(quiz.questions[0])');
assert.equal(run('isQuestionStarred(quiz.questions[0])'),true);
assert.match(document.querySelector('#question').innerHTML,/flash-star is-starred/);
finishStar();await pendingStar;
assert.equal(run('quiz.questions[0].starred'),true);
assert.equal(run('bankRows.length'),1);
let failStar;
context.api=()=>new Promise((resolve,reject)=>{failStar=()=>reject(Error('Save failed'))});
pendingStar=run('toggleQuestionStar(quiz.questions[0])');
assert.equal(run('isQuestionStarred(quiz.questions[0])'),false);
failStar();await pendingStar;
assert.equal(run('isQuestionStarred(quiz.questions[0])'),true);
assert.equal(run('bankRows.length'),1);
assert.match(document.querySelector('#composer-message').textContent,/Save failed/);
console.log('Star feedback passed: immediate selection, saved question bank, and rollback after failed save.');
