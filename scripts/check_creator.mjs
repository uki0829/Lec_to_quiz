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
assert.equal(document.querySelector('#count-label').textContent,'Sections');
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
