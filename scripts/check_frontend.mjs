import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const text=readFileSync(new URL('../source/app.js',import.meta.url),'utf8');
const elements=new Map();
const element=()=>({value:'',dataset:{},addEventListener(){},querySelectorAll(){return []},setAttribute(){},click(){},focus(){},style:{},hidden:false});
const document={querySelector(s){if(!elements.has(s))elements.set(s,element());return elements.get(s);},querySelectorAll(){return []}};
const context=vm.createContext({document,window:{},structuredClone,console,scheduleSave(){}});
vm.runInContext(text,context);
const {gradeNumeric,validateImported,samples,inferRequestedFormat}=context.window.__lectureLab;
assert.equal(gradeNumeric('2.4e0',2.4,.001),true);
assert.equal(gradeNumeric('-0.5',-.5,.001),true);
assert.equal(gradeNumeric('2.401',2.4,.001),true);
assert.equal(gradeNumeric('3.6',2.4,.001),false);
for(const value of ['2.4abc','Infinity','NaN','','0x10'])assert.equal(gradeNumeric(value,2.4,.001),null);
for(const [format,questions] of Object.entries(samples)){
  assert.equal(questions.length,6);
  assert.doesNotThrow(()=>validateImported({title:'Sample',questions}));
  if(format==='calculation')for(const q of questions)assert.equal(gradeNumeric(String(q.numericAnswer),q.numericAnswer,q.tolerance),true);
}
assert.throws(()=>validateImported({title:'Invalid',questions:[{id:'x',type:'mcq'}]}));
assert.throws(()=>validateImported({title:'Invalid',questions:[]}));
assert.equal(inferRequestedFormat('Create four flashcards'), 'flashcard');
assert.equal(inferRequestedFormat('Multiple-choice questions with a numerical example'), 'mcq');
assert.equal(inferRequestedFormat('Calculation questions about gradients'), 'calculation');
assert.equal(inferRequestedFormat('Compare flashcards and multiple choice'), null);
assert.equal(inferRequestedFormat('Explain calculus'), null);
vm.runInContext("format='flashcard';document.querySelector('#count').value='4';startQuiz({title:'Older quiz',questions:structuredClone(samples.mcq),mode:'sample',format:'mcq'});",context);
assert.equal(vm.runInContext('format',context),'flashcard');
assert.equal(document.querySelector('#count').value,'4');
console.log('Frontend checks passed: sample schemas, six-question count, scientific notation, invalid input, numeric tolerance.');
const sheet=context.window.__lectureLab.sampleSheet();
assert.equal(sheet.sections.length,6);
assert.equal(validateImported(sheet).format,'cheatsheet');
assert.equal(inferRequestedFormat('Create a cheat sheet'),'cheatsheet');
assert.throws(()=>validateImported({...sheet,sections:[{...sheet.sections[0],points:[]}]}));
assert.throws(()=>validateImported({...sheet,sections:[sheet.sections[0],sheet.sections[0]]}));
vm.runInContext('saveSnapshot=()=>{};startQuiz(window.__lectureLab.sampleSheet());',context);
assert.equal(document.querySelector('#study').hidden,true);
assert.equal(document.querySelector('#cheatsheet').hidden,false);
assert.match(document.querySelector('#sheet-sections').innerHTML,/Open source material/);
assert.match(document.querySelector('#sheet-sections').innerHTML,/sheet-section-5/);
console.log('Cheat sheet frontend checks passed: schema, sample, rendering, evidence controls, and import rejection.');
if(process.argv[2]){
  const exported=JSON.parse(readFileSync(process.argv[2],'utf8'));
  const imported=validateImported(exported);
  assert.equal(imported.format,'cheatsheet');assert.ok(imported.sections.length);
  assert.ok(imported.sections.every(s=>s.source.id&&s.source.quote));
  console.log('Exported live cheat sheet passed import validation.');
}
// Completion separates skipped questions from completed work and preserves identity.
vm.runInContext("startQuiz({id:'generated-check',title:'Quiz',mode:'generated',format:'mcq',questions:structuredClone(samples.mcq)});",context);
assert.equal(document.querySelector('#mode-badge').hidden,true);
assert.match(document.querySelector('#next').innerHTML,/^Next</);
vm.runInContext("index=quiz.questions.length-1;$('#next').onclick();",context);
const summary=document.querySelector('#summary').innerHTML;
assert.equal((summary.match(/<button /g)||[]).length,3);
assert.match(summary,/Back to last question/);assert.match(summary,/>Home</);
assert.match(summary,/Restart quiz/);assert.match(summary,/Session summary/);
assert.match(summary,/<dt>Completed<\/dt><dd>0<\/dd>/);
assert.match(summary,/<dt>Remaining<\/dt><dd>6<\/dd>/);
assert.doesNotMatch(summary,/Practice unfinished|Return to questions|Export quiz/);
vm.runInContext("$('#review-previous').onclick();",context);
assert.equal(vm.runInContext('index',context),5);
assert.equal(vm.runInContext('quiz.id',context),'generated-check');
assert.equal(document.querySelector('#summary').hidden,true);
vm.runInContext("let returnedToLibrary=false;$('#back-library').click=()=>returnedToLibrary=true;showSummary();$('#review-next').onclick();",context);
assert.equal(vm.runInContext('returnedToLibrary',context),true);
vm.runInContext("startQuiz({title:'Sample',mode:'sample',format:'mcq',questions:structuredClone(samples.mcq)});",context);
assert.equal(document.querySelector('#mode-badge').hidden,false);
const page=readFileSync('source/page.html','utf8');
assert.doesNotMatch(page,/<button id="export"/);
assert.match(page, /id="back-library"[^]*?aria-hidden="true">Home<\/button>/);
console.log('Practice navigation checks passed: completion counts, restart/back/home, preserved quiz identity, and distinct sample mode.');

// Flip both ways without leaking answers or discarding recall progress.
vm.runInContext("startQuiz({id:'flip-check',title:'Flashcards',mode:'generated',format:'flashcard',questions:structuredClone(samples.flashcard)});",context);
assert.match(document.querySelector('#question').innerHTML,/aria-label="Show answer"/);
vm.runInContext("$('#flash-flip').onclick();",context);
assert.match(document.querySelector('#question').innerHTML,/aria-label="Show question"/);
vm.runInContext("$('#known').onclick();$('#flash-flip').onclick();",context);
assert.equal(vm.runInContext('answers[quiz.questions[0].id].submitted',context),true);
assert.equal(vm.runInContext('answers[quiz.questions[0].id].correct',context),true);
assert.equal(vm.runInContext('answers[quiz.questions[0].id].revealed',context),false);
assert.doesNotMatch(document.querySelector('#question').innerHTML,/class="flash-explanation"/);
assert.match(document.querySelector('#previous').innerHTML,/Back/);
assert.match(document.querySelector('#next').innerHTML,/Continue/);
assert.equal(document.querySelector('#flash-position').textContent,'1 / 6');
console.log('Flashcard checks passed: reversible flip, hidden answer/explanation on front, preserved recall, and Back/Continue.');

// Review counts survive a flip back; restarting clears only session progress.
assert.equal(vm.runInContext('answers[quiz.questions[0].id].reviewed',context),true);
vm.runInContext("quiz.questions[0].starred=true;quiz.questions[0].hint='A saved cue';showSummary();",context);
assert.match(document.querySelector('#summary').innerHTML,/<dt>Completed<\/dt><dd>1<\/dd>/);
assert.match(document.querySelector('#summary').innerHTML,/<dt>Remaining<\/dt><dd>5<\/dd>/);
assert.match(document.querySelector('#summary').innerHTML,/Recalled/);
vm.runInContext("quiz.questions.forEach(q=>answers[q.id]={reviewed:true,revealed:false});showSummary();",context);
assert.match(document.querySelector('#summary').innerHTML,/You reviewed every card!/);
assert.match(document.querySelector('#summary').innerHTML,/<dt>Completed<\/dt><dd>6<\/dd>/);
assert.match(document.querySelector('#summary').innerHTML,/<dt>Remaining<\/dt><dd>0<\/dd>/);
assert.doesNotMatch(document.querySelector('#summary').innerHTML,/recalled ·/);
vm.runInContext("$('#review-restart').onclick();",context);
assert.equal(vm.runInContext('index',context),0);
assert.equal(vm.runInContext('Object.keys(answers).length',context),0);
assert.equal(vm.runInContext('quiz.progress.review',context),false);
assert.equal(vm.runInContext('quiz.id',context),'flip-check');
assert.equal(vm.runInContext('quiz.questions[0].starred',context),true);
assert.equal(vm.runInContext('quiz.questions[0].hint',context),'A saved cue');
assert.equal(document.querySelector('#summary').hidden,true);
assert.equal(document.querySelector('#flash-position').textContent,'1 / 6');
assert.match(document.querySelector('#question').innerHTML,/aria-label="Show answer"/);
vm.runInContext("startQuiz({title:'MCQ',mode:'sample',format:'mcq',questions:structuredClone(samples.mcq)});quiz.questions.forEach((q,i)=>answers[q.id]={submitted:true,correct:i<4});showSummary();",context);
assert.match(document.querySelector('#summary').innerHTML,/Practice complete!/);
assert.match(document.querySelector('#summary').innerHTML,/4 correct · 2 incorrect/);
console.log('Completion checks passed: reviewed versus recalled, skipped questions, complete sessions, and restart retaining stars/hints.');

// Returning to cards never exposes a previously revealed answer or explanation.
vm.runInContext("startQuiz({id:'return-check',title:'Cards',mode:'generated',format:'flashcard',questions:structuredClone(samples.flashcard),progress:{index:0,answers:{f1:{revealed:true,submitted:true,correct:true}}}});",context);
assert.match(document.querySelector('#question').innerHTML,/aria-label="Show answer"/);
assert.doesNotMatch(document.querySelector('#question').innerHTML,/class="flash-explanation"/);
assert.equal(vm.runInContext('answers.f1.reviewed',context),true);
vm.runInContext("$('#flash-flip').onclick();$('#next').onclick();$('#flash-flip').onclick();$('#previous').onclick();",context);
assert.equal(vm.runInContext('index',context),0);
assert.equal(vm.runInContext('answers.f1.submitted&&answers.f1.correct',context),true);
assert.match(document.querySelector('#question').innerHTML,/aria-label="Show answer"/);
vm.runInContext("$('#next').onclick();",context);
assert.equal(vm.runInContext('index',context),1);
assert.match(document.querySelector('#question').innerHTML,/aria-label="Show answer"/);
vm.runInContext("goToQuestion(5);$('#flash-flip').onclick();showSummary();$('#review-previous').onclick();",context);
assert.match(document.querySelector('#question').innerHTML,/aria-label="Show answer"/);
assert.doesNotMatch(document.querySelector('#question').innerHTML,/class="flash-explanation"/);
vm.runInContext("$('#flash-flip').onclick();",context);
assert.match(document.querySelector('#question').innerHTML,/aria-label="Show question"/);
assert.match(document.querySelector('#question').innerHTML,/class="flash-explanation"/);
vm.runInContext("startQuiz({title:'MCQ',mode:'sample',format:'mcq',questions:structuredClone(samples.mcq),progress:{index:0,answers:{m1:{selected:1,submitted:true,correct:true}}}});$('#next').onclick();$('#previous').onclick();",context);
assert.equal(vm.runInContext('answers.m1.submitted',context),true);
assert.match(document.querySelector('#question').innerHTML,/That’s correct/);
const styles=readFileSync('source/studio.css','utf8');
assert.match(styles,/\.flash-flip\{[^}]*color:#293348;/);
assert.doesNotMatch(styles,/\.flash-flip\.answer-face\{[^}]*color:/);
console.log('Card return checks passed: question-first on reopen/back/forward/summary, retained review and grading, and matching text color.');

// Grading is immediate, immutable after submission, and never replays on render.
const tones=[],savedSound={};let audioInstances=0;
class TestAudio {
  constructor(){audioInstances++;this.state='running';this.currentTime=1;this.destination={};}
  createOscillator(){const tone={};tones.push(tone);return {frequency:{setValueAtTime(value){tone.frequency=value}},connect(){},start(value){tone.start=value},stop(value){tone.stop=value},disconnect(){}};}
  createGain(){return {gain:{setValueAtTime(){},linearRampToValueAtTime(value){assert.equal(value,.07)},exponentialRampToValueAtTime(){}},connect(){},disconnect(){}};}
}
context.window.AudioContext=TestAudio;
context.localStorage={getItem:key=>savedSound[key],setItem:(key,value)=>savedSound[key]=value};
vm.runInContext("startQuiz({title:'Quiz',mode:'sample',format:'mcq',questions:structuredClone(samples.mcq)});submitChoice(1);",context);
assert.equal(vm.runInContext('answers.m1.correct',context),true);
assert.equal(vm.runInContext('answers.m1.submitted',context),true);
assert.deepEqual(tones.map(t=>t.frequency),[523.25,659.25,783.99]);
assert.equal(audioInstances,1);
assert.match(document.querySelector('#question').innerHTML,/Correct!/);
assert.doesNotMatch(document.querySelector('#question').innerHTML,/Check answer/);
assert.match(document.querySelector('#question').innerHTML,/Correct answer/);
vm.runInContext('render();submitChoice(0);',context);
assert.equal(tones.length,3);assert.equal(vm.runInContext('answers.m1.selected',context),1);
vm.runInContext("$('#next').onclick();submitChoice(0);",context);
assert.equal(vm.runInContext('answers.m2.correct',context),false);
assert.deepEqual(tones.slice(3).map(t=>t.frequency),[196,146.83]);
assert.match(document.querySelector('#question').innerHTML,/Your answer, incorrect/);
assert.match(document.querySelector('#quiz-progress').innerHTML,/2 completed/);
vm.runInContext("setAnswerSound(false);$('#next').onclick();submitChoice(1);",context);
assert.equal(tones.length,5);assert.equal(savedSound['lecture-lab-sound'],'off');
vm.runInContext("$('#next').onclick();submitChoice(null,true);",context);
assert.equal(vm.runInContext('answers.m4.skipped',context),true);
assert.equal(tones.length,5);
assert.match(document.querySelector('#question').innerHTML,/Answer revealed/);
vm.runInContext('setAnswerSound(true);',context);
assert.equal(savedSound['lecture-lab-sound'],'on');
class FailedAudio extends TestAudio {constructor(){super();this.state='suspended'}async resume(){throw Error('Audio unavailable')}}
context.window.AudioContext=FailedAudio;
vm.runInContext('answerAudioContext=null;',context);
assert.equal(await vm.runInContext('playAnswerSound(true)',context),false);
assert.equal(vm.runInContext('answers.m2.correct',context),false);
assert.match(page,/id="quiz-progress"/);
console.log('Quiz interaction and sound checks passed: instant grading, one sound per new answer, distinct tones, mute persistence, skip, progress, and audio failure fallback.');
