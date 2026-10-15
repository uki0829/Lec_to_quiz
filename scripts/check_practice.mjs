import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const classes=new Set(),events={},calls=[],elements=new Map();
const element=()=>({hidden:true,classList:{toggle(name,on){on?classes.add(name):classes.delete(name)}}});
const location={pathname:'/study/quiz/deep-link'};
const history={pushState(_,__,path){location.pathname=path;calls.push(['push',path])},replaceState(_,__,path){location.pathname=path;calls.push(['replace',path])}};
const context=vm.createContext({location,history,encodeURIComponent,decodeURIComponent,console,
 window:{addEventListener(name,fn){events[name]=fn}},
 $:selector=>{if(!elements.has(selector))elements.set(selector,element());return elements.get(selector)},
 quiz:{id:'stale-snapshot',mode:'generated',format:'mcq'},currentView:'library',
 validateImported:q=>q,showSummary(){calls.push(['summary'])},saveSnapshot(){},scheduleSave(){},cancelQuizAdvance(){},closeQuizExplanation(){},
 message(message){calls.push(['error',message])},
 async api(path){calls.push(['api',path]);if(path.endsWith('missing'))throw Error('Set unavailable');return {id:path.split('/').pop(),shareId:path.includes('shared-sets')?path.split('/').pop():undefined,mode:path.includes('shared-sets')?'shared':'generated',format:'flashcard'};}
});
vm.runInContext(`function showView(view){currentView=view;syncPracticePage(view)} function startQuiz(q){quiz=q;showView('study')}`,context);
vm.runInContext(readFileSync('source/practice.js','utf8'),context);
await vm.runInContext('finishPracticeBoot()',context);
assert.equal(vm.runInContext('quiz.id',context),'deep-link');
assert.ok(classes.has('practice-page'));
assert.equal(location.pathname,'/study/quiz/deep-link');
vm.runInContext("showView('library')",context);
assert.equal(location.pathname,'/');assert.equal(classes.has('practice-page'),false);
vm.runInContext("showView('study')",context);assert.equal(location.pathname,'/study/quiz/deep-link');
location.pathname='/';await events.popstate();assert.equal(vm.runInContext('currentView',context),'library');
await vm.runInContext("loadPracticeRoute('/study/shared/shared-1')",context);
assert.equal(vm.runInContext('quiz.shareId',context),'shared-1');assert.equal(location.pathname,'/study/shared/shared-1');
vm.runInContext("quiz={mode:'sample',format:'mcq'};showView('study')",context);
assert.equal(location.pathname,'/study/local');
vm.runInContext("quiz={mode:'generated',format:'cheatsheet'};showView('study')",context);
assert.equal(location.pathname,'/');assert.equal(classes.has('practice-page'),false);
await vm.runInContext("loadPracticeRoute('/study/quiz/missing')",context);
assert.equal(location.pathname,'/');assert.equal(vm.runInContext('currentView',context),'library');
assert.ok(calls.some(c=>c[0]==='error'));
console.log('Study route checks passed: deep-link overrides stale snapshots, private/shared API resolution, Home/Back, local samples, sheet separation, and missing-set recovery.');
// A completed background generation takes precedence over its parent's initial deep link.
location.pathname='/study/quiz/deep-link';
vm.runInContext("practiceBooting=true;quiz={id:'completed-followup',mode:'generated',format:'mcq'};currentView='study'",context);
await vm.runInContext('finishPracticeBoot(true)',context);
assert.equal(vm.runInContext('quiz.id',context),'completed-followup');
assert.equal(location.pathname,'/study/quiz/completed-followup');
console.log('Refreshed background generation opens its completed follow-up instead of reopening the parent route.');
