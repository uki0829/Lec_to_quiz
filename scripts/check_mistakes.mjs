import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const elements=new Map(),calls=[],opened=[];
function element(){let html='';return {hidden:false,disabled:false,textContent:'',open:false,inputs:[],
 get innerHTML(){return html},set innerHTML(value){html=value;this.inputs=[...value.matchAll(/<input type="checkbox" value="([^"]+)" checked>/g)].map(m=>({value:m[1],checked:true,disabled:false}));},
 querySelectorAll(selector){return selector==='input:checked'?this.inputs.filter(x=>x.checked):this.inputs},
 showModal(){this.open=true},close(){this.open=false},addEventListener(){},focus(){}};}
const $=selector=>{if(!elements.has(selector))elements.set(selector,element());return elements.get(selector)};
let failNetwork=true,failJob=false,postBodies=[],counter=0;
const parent={id:'parent',mode:'generated',format:'mcq',questions:[{id:'wrong'},{id:'skip'},{id:'right'}]};
const items=[{questionId:'wrong',prompt:'Learning rate?',status:'incorrect',source:{name:'Lecture.pdf',locator:'Page 2'}},
 {questionId:'skip',prompt:'Update rule?',status:'skipped',source:{name:'Lecture.pdf',locator:'Page 3'}}];
const context=vm.createContext({$,window:{crypto:{randomUUID:()=>`mistake-request-${++counter}`}},Date,Math,
 quiz:parent,answers:{wrong:{submitted:true,correct:false},skip:{submitted:true,skipped:true},right:{submitted:true,correct:true}},
 busy:false,activeJob:null,parentQuizId:null,esc:String,mathHtml:String,flashIcon:x=>`<i>${x}</i>`,
 setBusy(value){context.busy=value},saveSnapshot(){},updateFollowup(){},friendlyJobError:job=>job.error||job.status,
 async flushPracticeProgress(){calls.push('flush')},validateImported:q=>q,
 startQuiz(q){opened.push(q.id);context.quiz=q},
 async api(path,options){calls.push(path);
  if(path==='/api/quizzes/parent/mistakes'&&!options)return {questions:items};
  if(path==='/api/quizzes/parent/mistakes'&&options?.method==='POST'){
   postBodies.push(JSON.parse(options.body));if(failNetwork)throw Error('Network unavailable');return {jobId:'job-1'};
  }
  if(path==='/api/jobs/job-1')return {id:'job-1',status:'failed'};
  if(path==='/api/jobs/job-1/retry')return {jobId:'job-2'};
  if(path==='/api/quizzes/followup')return {id:'followup',mode:'generated',format:'mcq',questions:[]};
  throw Error(path);
 },
 async watchJob(id){calls.push('watch:'+id);if(failJob)throw Error('Generation unavailable');return {result:{status:'ready',quizId:'followup'}}}
});
vm.runInContext(fs.readFileSync('source/mistake-practice.js','utf8'),context);
assert.match(context.mistakeSummaryAction(),/Practice my mistakes/);
assert.match(context.mistakeSummaryAction(),/2 incorrect or skipped/);
context.quiz={...parent,mode:'shared'};assert.equal(context.mistakeSummaryAction(),'');
context.quiz={...parent,format:'flashcard'};assert.equal(context.mistakeSummaryAction(),'');context.quiz=parent;
await context.openMistakePractice();assert.equal(calls[0],'flush');
assert.deepEqual([...context.selectedMistakes()],['wrong','skip']);
assert.equal($('#mistake-dialog').open,true);
await context.generateMistakePractice();assert.equal(context.quiz.id,'parent');assert.match($('#mistake-message').textContent,/Network/);
failNetwork=false;failJob=true;await context.generateMistakePractice();
assert.equal(postBodies[0].requestId,postBodies[1].requestId);
assert.deepEqual(postBodies[0].questionIds,['wrong','skip']);assert.equal(postBodies[0].count,4);
assert.equal(context.quiz.id,'parent');assert.match($('#mistake-message').textContent,/unavailable/);
failJob=false;await context.generateMistakePractice();
assert.ok(calls.includes('/api/jobs/job-1/retry'));assert.deepEqual(opened,['followup']);
assert.equal($('#mistake-dialog').open,false);assert.equal(context.answers.wrong.correct,false);
// Restored in-flight work reconstructs its selected focus and supports cancellation.
context.activeJob='restored-job';context.busy=true;
context.syncMistakeJob({id:'restored-job',status:'running',stage:'Searching lectures',params:{parentQuizId:'other-parent',mistakePractice:{questions:[items[0]]}}});
assert.equal($('#mistake-dialog').open,true);assert.equal($('#mistake-cancel-job').hidden,false);
assert.equal($('#mistake-generate').disabled,true);assert.deepEqual([...context.selectedMistakes()],['wrong']);
context.syncMistakeJob({id:'restored-job',status:'completed',params:{parentQuizId:'other-parent',mistakePractice:{questions:[items[0]]}}});
assert.equal($('#mistake-dialog').open,false);
console.log('Mistake practice checks passed: graded-set eligibility, saved attempts, selected focus, network idempotency, failure/retry, original progress preservation, and resumed job controls.');
