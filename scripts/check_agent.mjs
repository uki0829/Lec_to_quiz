import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const elements=new Map(),calls=[],opened=[];
function element(){return {value:'',textContent:'',innerHTML:'',disabled:false,hidden:false,dataset:{},
  setAttribute(){},setSelectionRange(){},querySelectorAll(){return []},focus(){},click(){this.onclick?.()},scrollHeight:500,scrollTop:0};}
const $=selector=>{if(!elements.has(selector))elements.set(selector,element());return elements.get(selector)};
const escape=value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
let nonce=0,failNetwork=false;
let messages=[];
const set={id:'set-1',title:'Lecture practice',format:'mcq',count:6,sources:[{id:'source-1',name:'Lecture.pdf',locator:'Page 2'}]};
const context=vm.createContext({$,document:{querySelectorAll(){return []}},console,Math,Date,
  window:{addEventListener(){},crypto:{randomUUID:()=>`request-key-${++nonce}`}},setTimeout(){return 1},clearTimeout(){},
  collectionId:'course-1',collectionRows:[{id:'course-1',name:'Physics'},{id:'course-2',name:'Psychology'}],
  currentCollection:{id:'course-1',materials:[{searchReady:true}]},currentView:'agent',busy:false,activeJob:null,
  esc:escape,mathHtml:escape,folderName:x=>x,flashIcon:x=>`<i>${x}</i>`,formatIcon:x=>x,formatName:x=>x,
  showView(view){context.currentView=view},saveSnapshot(){},syncMenus(){},
  validateImported:q=>q,async flushPracticeProgress(){},startQuiz(q){opened.push(q.id)},openSource(id){calls.push(['source',id])},
  async api(path,options){
    calls.push({path,options});
    if(options?.method==='POST'&&path.endsWith('/messages')){
      if(failNetwork)throw Error('Network unavailable');
      const request=JSON.parse(options.body);
      if(!request.message.startsWith('/')){
        messages=[{id:'u-chat',role:'user',state:'ready',text:request.message},
          {id:'a-chat',role:'assistant',state:'ready',chat:true,text:'Study agenda\n• Review the lecture.',sources:[{id:'source-1',name:'Lecture.pdf',locator:'Page 2'}]}];
        return {messageId:'a-chat',messages};
      }
      messages=[{id:'u1',role:'user',state:'ready',text:request.message},
        {id:'a1',role:'assistant',state:'pending',text:'Creating practice.',jobId:'job-1'}];
      return {messageId:'a1',messages};
    }
    if(path.endsWith('/agent'))return {messages};
    if(path==='/api/quizzes/set-1')return {...set,mode:'generated',questions:[]};
    throw Error(path);
  },
  async watchJob(id){calls.push(['watch',id]);messages=[messages[0],{id:'a1',role:'assistant',state:'ready',text:'Your study set is ready.',quizId:'set-1',set}];},
});
vm.runInContext('function setBusy(value){busy=value;syncAgentState()}',context);
vm.runInContext(readFileSync('source/agent.js','utf8'),context);
const run=code=>vm.runInContext(code,context);
await run('openStudyAgent()');
assert.equal($('#agent-send').disabled,true);
$('#agent-input').value='/quiz Create six questions on forces';run('syncAgentState()');
assert.equal($('#agent-send').disabled,false);
await run('sendAgentMessage()');
const sent=calls.find(c=>c.path?.endsWith('/messages'));
assert.equal(sent.path,'/api/collections/course-1/agent/messages');
assert.equal(JSON.parse(sent.options.body).message,'/quiz Create six questions on forces');
assert.deepEqual(opened,[]); // A finished set stays in the conversation until deliberately opened.
assert.match($('#agent-messages').innerHTML,/Start practice/);
assert.match($('#agent-messages').innerHTML,/Lecture.pdf/);
assert.equal($('#agent-input').value,'');
assert.equal(context.busy,false);
await run("openAgentSet('set-1')");assert.deepEqual(opened,['set-1']);
assert.ok(calls.some(c=>Array.isArray(c)&&c[0]==='watch'&&c[1]==='job-1'));

// A failed network request preserves the draft and idempotency key for retry.
failNetwork=true;$('#agent-input').value='/quiz More practice on forces';
await run('sendAgentMessage()');
assert.equal($('#agent-input').value,'/quiz More practice on forces');
assert.match($('#agent-error').textContent,/Network/);
const lastRequest=JSON.parse(calls.filter(c=>c.path?.endsWith('/messages')).at(-1).options.body);
failNetwork=false;await run('sendAgentMessage()');
const retriedRequest=JSON.parse(calls.filter(c=>c.path?.endsWith('/messages')).at(-1).options.body);
assert.equal(lastRequest.requestId,retriedRequest.requestId);

// Empty folders can generate from general knowledge without uploading lectures.
context.currentCollection={id:'course-1',materials:[]};$('#agent-input').value='/quiz Quiz me';
run('syncAgentState()');assert.equal($('#agent-send').disabled,false);
const before=calls.filter(c=>c.path?.endsWith('/messages')).length;await run('sendAgentMessage()');
assert.equal(calls.filter(c=>c.path?.endsWith('/messages')).length,before+1);
assert.equal($('#agent-error').textContent,'');
assert.match($('#agent-ready').textContent,/General knowledge/);

// With no folders, the first send creates a private destination, then generates.
const regularApi=context.api;
context.collectionId=null;context.collectionRows=[];context.currentCollection=null;
context.refreshLibrary=async()=>{context.currentCollection={id:'new-folder',materials:[]};context.collectionRows=[{id:'new-folder',name:'Agent practice'}]};
context.api=async(path,options)=>path==='/api/collections'?({id:'new-folder'}):regularApi(path,options);
$('#agent-input').value='/quiz Create a quiz about memory';run('syncAgentState()');
assert.equal($('#agent-send').disabled,false);
await run('sendAgentMessage()');
assert.equal(context.collectionId,'new-folder');
assert.ok(calls.some(c=>c.path==='/api/collections/new-folder/agent/messages'));
context.api=regularApi;context.collectionId='course-1';
run("agentMessages=[{id:'general-result',role:'assistant',state:'ready',text:'Ready',set:{id:'general',title:'Memory',format:'mcq',count:4,grounding:'general',sources:[]}}];renderAgentConversation()");
assert.match($('#agent-messages').innerHTML,/General knowledge/);
assert.doesNotMatch($('#agent-messages').innerHTML,/lecture source/);

// Ordinary messages show an inline reply and sources, without a generation job.
const watches=calls.filter(c=>Array.isArray(c)&&c[0]==='watch').length;
$('#agent-input').value='Create a study agenda';await run('sendAgentMessage()');
assert.match($('#agent-messages').innerHTML,/Study agenda/);
assert.match($('#agent-messages').innerHTML,/data-agent-source="source-1"/);
assert.doesNotMatch($('#agent-messages').innerHTML,/Start practice|Open guide|agent-result/);
assert.equal(calls.filter(c=>Array.isArray(c)&&c[0]==='watch').length,watches);
assert.equal(context.busy,false);

// A late response from another folder cannot replace the visible conversation.
context.currentCollection={id:'course-1',materials:[{searchReady:true}]};
let resolveOld;
const oldApi=context.api;
context.api=path=>path.includes('course-1/agent')?new Promise(resolve=>resolveOld=resolve):Promise.resolve({messages:[]});
const stale=run('loadAgentConversation()');
context.collectionId='course-2';context.currentCollection={id:'course-2',materials:[{searchReady:true}]};
await run('loadAgentConversation()');
resolveOld({messages:[{id:'secret-old',role:'user',state:'ready',text:'Old folder request'}]});await stale;
assert.doesNotMatch($('#agent-messages').innerHTML,/Old folder request/);
context.api=oldApi;

run('resetAgentSession()');
assert.equal($('#agent-messages').innerHTML,'');assert.equal($('#agent-input').value,'');
const page=readFileSync('source/page.html','utf8');
assert.match(page,/id="nav-agent"/);assert.match(page,/id="agent-view"/);assert.match(page,/agent.js/);
// Slash selection inserts a command; it never submits the message.
const requestsBefore=calls.filter(c=>c.path?.endsWith('/messages')).length;
$('#agent-input').value='/';$('#agent-input').oninput();
assert.equal($('#agent-command-menu').hidden,false);
assert.match($('#agent-command-menu').innerHTML,/Flashcards/);
assert.equal(run('agentCommandMatches.length'),4);
$('#agent-input').value='/fl';$('#agent-input').oninput();
assert.equal(run('agentCommandMatches.length'),1);
$('#agent-input').onkeydown({key:'Enter',preventDefault(){}});
assert.equal($('#agent-input').value,'/flashcards ');
assert.equal($('#agent-command-menu').hidden,true);
assert.equal(calls.filter(c=>c.path?.endsWith('/messages')).length,requestsBefore);
$('#agent-input').value='/';$('#agent-input').oninput();
$('#agent-input').onkeydown({key:'Escape',preventDefault(){}});
run('syncAgentState()');assert.equal($('#agent-command-menu').hidden,true);
$('#agent-input').value='Explain /quiz';$('#agent-input').oninput();assert.equal($('#agent-command-menu').hidden,true);
console.log('Study agent checks passed: folder-scoped requests, explicit practice opening, source links, network retry idempotency, optional uploads and no-folder creation, stale-response isolation, and session cleanup.');
