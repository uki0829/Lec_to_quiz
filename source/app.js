const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const lecture=`Sample lecture: Gradient descent\n\nPage 1 — Objective and update\nWe minimize a differentiable loss L(w). The gradient points toward the steepest local increase, so gradient descent takes a step in the negative gradient direction. The update is w_new = w - eta * gradient(L(w)). Eta is the learning rate. A stationary point has zero gradient but is not necessarily a global minimum.\n\nPage 2 — Learning rate and a quadratic\nA very small learning rate can make progress slow. A large learning rate may overshoot or diverge. Consider L(w) = w^2, whose gradient is 2w. If w = 3 and eta = 0.1, one update gives 3 - 0.1 * 6 = 2.4. For this quadratic, w_new = (1 - 2*eta)*w. Starting with w = 1 and eta = 1.1 gives w_new = -1.2 and a larger loss.\n\nPage 3 — Batch, stochastic, and vector updates\nFull-batch gradient descent uses all training examples to calculate each gradient. SGD uses one sampled example; mini-batch methods use a subset. For a vector w, subtract eta times the gradient component by component. If w = [2, -1], gradient = [4, -2], and eta = 0.25, the updated vector is [1, -0.5]. If a scalar gradient is zero, the ordinary gradient-descent update leaves the scalar unchanged.`;
const source=(page,quote)=>({name:'Sample gradient-descent lecture',locator:'Page '+page,quote});
const base=(id,type,prompt,answer,explanation,page,quote,extras={})=>({id,type,prompt,answer,explanation,steps:[],source:source(page,quote),...extras});
const samples={
mcq:[
base('m1','mcq','Which update moves opposite to the gradient?','w_new = w − η ∇L(w)','The gradient points toward local increase. Subtracting a positive learning rate times the gradient moves in the opposite direction.',1,'The update is w_new = w - eta * gradient(L(w)).',{options:['w_new = w + η ∇L(w)','w_new = w − η ∇L(w)','w_new = η + ∇L(w)','w_new = ∇L(w) / η'],correctIndex:1}),
base('m2','mcq','For L(w) = w², w = 3, and η = 0.1, what is w after one update?','2.4','The gradient is 2w = 6, so the update is 3 − 0.1 × 6 = 2.4.',2,'If w = 3 and eta = 0.1, one update gives 3 - 0.1 * 6 = 2.4.',{options:['3.6','0.6','2.4','2.9'],correctIndex:2}),
base('m3','mcq','What can happen when the learning rate is too large?','Updates can overshoot or diverge.','A large step can move past a useful region and increase the loss. A larger learning rate is not always faster or better.',2,'A large learning rate may overshoot or diverge.',{options:['Updates always converge faster.','Updates can overshoot or diverge.','The gradient always becomes zero.','The training data becomes larger.'],correctIndex:1}),
base('m4','mcq','How does full-batch gradient descent differ from SGD?','Full-batch uses all examples; SGD uses one sampled example.','The distinction here is how many examples are used to calculate an update, not whether the model has one or many parameters.',3,'Full-batch gradient descent uses all training examples to calculate each gradient. SGD uses one sampled example.',{options:['Full-batch uses one example; SGD uses all examples.','They are identical.','SGD requires zero gradients.','Full-batch uses all examples; SGD uses one sampled example.'],correctIndex:3}),
base('m5','mcq','Does a zero gradient prove that a point is a global minimum?','No. It identifies a stationary point.','A stationary point may be a minimum, maximum, or saddle point. The source does not equate zero gradient with global optimality.',1,'A stationary point has zero gradient but is not necessarily a global minimum.',{options:['Yes, for every differentiable loss.','Only if the learning rate is large.','No. It identifies a stationary point.','It proves the loss equals zero.'],correctIndex:2}),
base('m6','mcq','Given w = [2, −1], gradient = [4, −2], and η = 0.25, what is the updated vector?','[1, −0.5]','Apply the update component by component: 2 − 0.25 × 4 = 1; −1 − 0.25 × (−2) = −0.5.',3,'If w = [2, -1], gradient = [4, -2], and eta = 0.25, the updated vector is [1, -0.5].',{options:['[3, −1.5]','[1, −0.5]','[1, −1.5]','[−2, 1]'],correctIndex:1})],
flashcard:[
base('f1','flashcard','What is the gradient-descent update rule?','w_new = w − η ∇L(w)','η is the learning rate, and ∇L(w) is the gradient evaluated at the current parameter value.',1,'The update is w_new = w - eta * gradient(L(w)).'),
base('f2','flashcard','Why do we subtract the gradient?','The gradient points toward local increase, so we step in the opposite direction.','This is a local direction argument; a finite step is not guaranteed to reduce the loss for every learning rate.',1,'The gradient points toward the steepest local increase'),
base('f3','flashcard','What is the tradeoff when choosing a learning rate?','Small steps may be slow; large steps may overshoot or diverge.','The step size affects both how quickly parameters move and whether updates remain stable.',2,'A very small learning rate can make progress slow. A large learning rate may overshoot or diverge.'),
base('f4','flashcard','What separates full-batch, SGD, and mini-batch updates?','They use all examples, one sampled example, and a subset of examples respectively.','These choices change how the gradient estimate is calculated.',3,'Full-batch gradient descent uses all training examples'),
base('f5','flashcard','What does a zero gradient tell you?','The point is stationary; it does not necessarily establish a global minimum.','The loss landscape needs additional analysis.',1,'A stationary point has zero gradient but is not necessarily a global minimum.'),
base('f6','flashcard','How do you update a parameter vector?','Subtract the learning rate times each corresponding gradient component.','The vector and gradient must have matching dimensions.',3,'For a vector w, subtract eta times the gradient component by component.')],
calculation:[
base('c1','calculation','For L(w) = w², w = 3, and η = 0.1, calculate w after one update.','2.4','Use the gradient at the current value before updating.',2,'L(w) = w^2, whose gradient is 2w.',{numericAnswer:2.4,tolerance:0.001,steps:['Compute the gradient: 2 × 3 = 6.','Compute the step: 0.1 × 6 = 0.6.','Update: 3 − 0.6 = 2.4.']}),
base('c2','calculation','Continue from w = 2.4 with L(w) = w² and η = 0.1. What is w after the next update?','1.92','Recalculate the gradient at 2.4 instead of reusing the previous gradient.',2,'For this quadratic, w_new = (1 - 2*eta)*w.',{numericAnswer:1.92,tolerance:0.001,steps:['Compute the gradient: 2 × 2.4 = 4.8.','Compute the step: 0.1 × 4.8 = 0.48.','Update: 2.4 − 0.48 = 1.92.']}),
base('c3','calculation','For L(w) = w², w = −2, and η = 0.25, calculate the updated w.','−1','Subtracting a negative gradient moves the parameter toward zero.',2,'L(w) = w^2, whose gradient is 2w.',{numericAnswer:-1,tolerance:0.001,steps:['Gradient: 2 × (−2) = −4.','Step: 0.25 × (−4) = −1.','Update: −2 − (−1) = −1.']}),
base('c4','calculation','For L(w) = w², w = 1, and η = 1.1, calculate the next w.','−1.2','This step crosses zero and increases the loss from 1 to 1.44.',2,'Starting with w = 1 and eta = 1.1 gives w_new = -1.2 and a larger loss.',{numericAnswer:-1.2,tolerance:0.001,steps:['Gradient: 2 × 1 = 2.','Step: 1.1 × 2 = 2.2.','Update: 1 − 2.2 = −1.2.']}),
base('c5','calculation','Given w = [2, −1], gradient = [4, −2], and η = 0.25, calculate only the second component after updating.','−0.5','Apply the update to the second component using its matching gradient.',3,'If w = [2, -1], gradient = [4, -2], and eta = 0.25, the updated vector is [1, -0.5].',{numericAnswer:-0.5,tolerance:0.001,steps:['Second parameter: −1.','Second gradient: −2.','Update: −1 − 0.25 × (−2) = −0.5.']}),
base('c6','calculation','If w = 5, the gradient is 0, and η = 0.2, what is the updated w?','5','The ordinary gradient-descent update does not move when the gradient is zero.',3,'If a scalar gradient is zero, the ordinary gradient-descent update leaves the scalar unchanged.',{numericAnswer:5,tolerance:0.001,steps:['Step: 0.2 × 0 = 0.','Update: 5 − 0 = 5.']})]};
let attachments=[],format='mcq',quiz=null,index=0,answers={},busy=false;
const mimeByExt={pdf:'application/pdf',png:'image/png',jpg:'image/jpeg',jpeg:'image/jpeg',webp:'image/webp',mp3:'audio/mpeg',wav:'audio/wav',ogg:'audio/ogg',flac:'audio/flac',m4a:'audio/mp4',mp4:'video/mp4',webm:'video/webm',txt:'text/plain'};
function message(text,error=false){$('#setup-message').className='toast'+(error?' error':'');$('#setup-message').textContent=text;if(typeof applyToast==='function')applyToast(text,error);}
function listFiles(){for(const selector of ['#file-list','#composer-file-list']){const target=$(selector);if(!target)continue;target.innerHTML=attachments.map((f,i)=>'<div class="file-row"><img class="icon" src="/static/icons/file-text.svg" alt=""><span class="file-name" title="'+esc(f.name)+'">'+esc(f.name)+'</span><span>'+Math.max(.01,f.size/1048576).toFixed(2)+' MB</span><button type="button" data-remove="'+i+'" aria-label="Remove '+esc(f.name)+'"><img class="icon" src="/static/icons/x.svg" alt=""></button></div>').join('');target.querySelectorAll('[data-remove]').forEach(b=>b.onclick=()=>{attachments.splice(Number(b.dataset.remove),1);materialDirty=true;listFiles();});}if(typeof updateComposerState==='function')updateComposerState();}
function inferRequestedFormat(text){const found=[];if(/flash\s*cards?/i.test(text))found.push('flashcard');if(/cheat[ -]?sheets?/i.test(text))found.push('cheatsheet');if(/multiple[ -]?choice|\bmcq\b/i.test(text))found.push('mcq');if(/calculation\s+(?:questions|practice)|numeric(?:al)?\s+(?:questions|practice)/i.test(text))found.push('calculation');return found.length===1?found[0]:null;}
function addFiles(files){if(busy)return;const next=[...attachments,...Array.from(files)];if(next.length>4)return message('Choose at most four files.',true);if(next.reduce((sum,f)=>sum+f.size,0)>1024**3)return message('Use at most 1 GB of files per material set.',true);for(const f of next){const ext=f.name.split('.').pop().toLowerCase();const limit=ext==='pdf'?25*1024**2:['png','jpg','jpeg','webp'].includes(ext)?10*1024**2:ext==='txt'?500*1024:500*1024**2;if(!mimeByExt[ext]||!f.size)return message('Choose a nonempty supported PDF, image, audio, video, or text file.',true);if(f.size>limit)return message(f.name+' exceeds its file-size limit.',true);}attachments=next;materialDirty=true;message('');listFiles();}
$('#files').onchange=e=>{addFiles(e.target.files);e.target.value='';};
['dragenter','dragover'].forEach(t=>$('#drop').addEventListener(t,e=>{e.preventDefault();$('#drop').classList.add('drag');}));['dragleave','drop'].forEach(t=>$('#drop').addEventListener(t,e=>{e.preventDefault();$('#drop').classList.remove('drag');if(t==='drop')addFiles(e.dataTransfer.files);}));
$('#reset-material').onclick=()=>{if(busy)return;attachments=[];$('#notes').value='';materialId=null;materialDirty=true;$('#saved-materials').value='';$('#material-summary').innerHTML='';listFiles();message('');saveSnapshot();};
document.querySelectorAll('[data-format]').forEach(b=>b.onclick=()=>{format=b.dataset.format;document.querySelectorAll('[data-format]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));if(typeof updateComposerState==='function')updateComposerState();});
function startQuiz(q){cancelQuizAdvance();closeQuizExplanation();quiz=q;index=q.progress?.index||0;answers=q.progress?.answers||{};$('#saved-quizzes').value=q.id||'';$('#empty').hidden=true;$('#summary').hidden=true;$('#study').hidden=q.format==='cheatsheet';$('#cheatsheet').hidden=q.format!=='cheatsheet';$('#sample-context').hidden=q.mode!=='sample';$('#mode-badge').textContent=q.mode==='sample'?(q.format==='cheatsheet'?'Sample sheet':q.format==='flashcard'?'Sample flashcards':'Sample quiz'):q.mode==='imported'?(q.format==='cheatsheet'?'Imported sheet':'Imported quiz'):q.mode==='shared'?(q.demo?'Demo shared set':'Shared set'):'';$('#mode-badge').hidden=!['sample','imported','shared'].includes(q.mode);$('#mode-badge').className='badge'+(q.mode==='sample'?' sample-badge':'');$('#quiz-title').innerHTML=mathHtml(q.title);if(typeof updateQuizContext==='function')updateQuizContext(q);hideFlashcardAnswer();if(typeof updateSocialQuiz==='function')updateSocialQuiz(q);render();}
function sourceHtml(q){const label=q.practiceExample?'Concept source: ':'Source: ';if(quiz?.mode==='shared'||(!q.source.id&&quiz?.mode!=='sample'))return '<details class="source-ref"><summary>'+label+esc(q.source.name)+' · '+esc(q.source.locator)+'</summary><blockquote>'+mathHtml(q.source.quote)+'</blockquote></details>';return '<details class="source-ref"><summary>'+label+esc(q.source.name)+' · '+esc(q.source.locator)+'</summary><blockquote>'+mathHtml(q.source.quote)+'</blockquote><button class="quiet source-open" data-source="'+esc(q.source.id||'sample')+'">Open source material</button></details>';}
function mathHtml(value,options){return window.LectureMath?window.LectureMath.toHtml(value,options):esc(value);}
function flashIcon(name){return '<img class="icon" src="/static/icons/'+name+'.svg" alt="" aria-hidden="true">';}
function feedbackHtml(q,a){const heading=q.type==='flashcard'?'Explanation':a.skipped?'Answer':a.correct?'That’s correct.':'Let’s work through it.';return '<div class="feedback '+(q.type==='flashcard'?'':a.correct?'good':'bad')+'"><h5>'+heading+'</h5><p>'+mathHtml(q.explanation)+'</p>'+(q.type==='calculation'?'<p style="margin-top:9px"><strong>Answer: '+mathHtml(q.answer)+'</strong></p>':'')+(q.steps?.length?'<ol>'+q.steps.map(x=>'<li>'+mathHtml(x)+'</li>').join('')+'</ol>':'')+'</div>';}
let answerAudioContext=null,answerSoundEnabled=true,answerSoundEpoch=0;
try{answerSoundEnabled=localStorage.getItem('lecture-lab-sound')!=='off';}catch{}
function setAnswerSound(enabled){
  answerSoundEnabled=enabled;answerSoundEpoch++;
  try{localStorage.setItem('lecture-lab-sound',enabled?'on':'off');}catch{}
}
async function playAnswerSound(correct){
  if(!answerSoundEnabled)return false;
  const epoch=answerSoundEpoch;
  try{
    const Audio=window.AudioContext||window.webkitAudioContext;
    if(!Audio)return false;
    if(!answerAudioContext||answerAudioContext.state==='closed')answerAudioContext=new Audio();
    if(answerAudioContext.state==='suspended')await answerAudioContext.resume();
    if(!answerSoundEnabled||epoch!==answerSoundEpoch)return false;
    const start=answerAudioContext.currentTime+.005;
    const notes=correct?[[523.25,0,.12],[659.25,.09,.12],[783.99,.18,.17]]:[[196,0,.13],[146.83,.12,.18]];
    for(const [frequency,offset,duration] of notes){
      const oscillator=answerAudioContext.createOscillator(),gain=answerAudioContext.createGain();
      oscillator.type='sine';oscillator.frequency.setValueAtTime(frequency,start+offset);
      gain.gain.setValueAtTime(0,start+offset);
      gain.gain.linearRampToValueAtTime(.07,start+offset+.012);
      gain.gain.exponentialRampToValueAtTime(.001,start+offset+duration);
      oscillator.connect(gain);gain.connect(answerAudioContext.destination);
      oscillator.start(start+offset);oscillator.stop(start+offset+duration+.015);
      oscillator.onended=()=>{oscillator.disconnect();gain.disconnect();};
    }
    return true;
  }catch{return false;}
}
let quizAdvanceTimer=null,quizAdvanceEpoch=0;
function cancelQuizAdvance(){clearTimeout(quizAdvanceTimer);quizAdvanceTimer=null;quizAdvanceEpoch++;}
function closeQuizExplanation(){const dialog=$('#quiz-explanation-dialog');if(dialog?.open)dialog.close();}
function dismissQuizExplanation(){closeQuizExplanation();$('#quiz-explanation')?.focus({preventScroll:true});}
function advanceQuiz(){if(!quiz)return;if(index<quiz.questions.length-1)goToQuestion(index+1);else showSummary();}
function fitQuizStage(){
  const card=$('#question');
  if($('#authenticated-app').classList?.contains?.('practice-page')||quiz?.questions?.[index]?.type!=='mcq'||$('#study').hidden||!card?.getBoundingClientRect)return;
  // Keep navigation in view; long questions scroll inside the card.
  const available=window.innerHeight-(card.getBoundingClientRect().top+window.scrollY)-$('.study-footer').offsetHeight-58;
  card.style.setProperty('--quiz-stage-height',Math.max(300,Math.min(660,available))+'px');
}
window.addEventListener?.('resize',fitQuizStage);
document.fonts?.ready.then(fitQuizStage);
function openQuizExplanation(){
  const currentQuiz=quiz,currentIndex=index,q=quiz?.questions?.[index],a=q&&answers[q.id];
  if(!q||!(q.type==='mcq'&&a?.submitted||q.type==='flashcard'&&a?.revealed))return;
  cancelQuizAdvance();
  const dialog=$('#quiz-explanation-dialog');
  $('#quiz-explanation-content').innerHTML=feedbackHtml(q,a)+sourceHtml(q);
  $('#quiz-explanation-content').scrollTop=0;
  $('#quiz-explanation-content').querySelectorAll('.source-open').forEach(b=>b.onclick=()=>openSource(b.dataset.source));
  $('#quiz-explanation-next').textContent=index===quiz.questions.length-1?'View summary':'Continue';
  $('#quiz-explanation-next').onclick=()=>{closeQuizExplanation();if(quiz===currentQuiz&&index===currentIndex)advanceQuiz();};
  $('#quiz-explanation-close').onclick=dismissQuizExplanation;
  dialog.oncancel=event=>{event.preventDefault();dismissQuizExplanation();};
  if(!dialog.open)dialog.showModal();
}
function submitChoice(choice,skipped=false){
  const q=quiz?.questions?.[index];
  if(q?.type!=='mcq'||answers[q.id]?.submitted)return;
  if(!skipped&&(!Number.isInteger(choice)||choice<0||choice>=q.options.length))return;
  const correct=!skipped&&choice===q.correctIndex;
  answers[q.id]={selected:skipped?null:choice,submitted:true,correct,...(skipped?{skipped:true}:{})};
  if(!skipped)playAnswerSound(correct);
  render();
  if(!correct)return openQuizExplanation();
  cancelQuizAdvance();
  const currentQuiz=quiz,currentIndex=index,epoch=quizAdvanceEpoch;
  quizAdvanceTimer=setTimeout(()=>{
    quizAdvanceTimer=null;
    if(epoch===quizAdvanceEpoch&&quiz===currentQuiz&&index===currentIndex&&!$('#study').hidden&&
       (typeof currentView==='undefined'||currentView==='study'))advanceQuiz();
  },550);
}
function submitCalculation(){
  const q=quiz?.questions?.[index];
  if(q?.type!=='calculation'||(answers[q.id]?.submitted&&answers[q.id]?.correct))return;
  const value=$('#number-answer').value.trim();
  const correct=gradeNumeric(value,q.numericAnswer,q.tolerance);
  if(correct===null){$('#answer-message').textContent='Enter a number, e.g. 2.4 or -0.5.';return;}
  answers[q.id]={value,submitted:true,correct};
  playAnswerSound(correct);
  render();
  if(!correct){$('#number-answer').focus({preventScroll:true});$('#number-answer').select?.();}
  if(!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches){
    $('#numeric-answer-field')?.animate?.(correct?
      [{transform:'scale(1)'},{transform:'scale(1.015)'},{transform:'scale(1)'}]:
      [{transform:'translateX(0)'},{transform:'translateX(-5px)'},{transform:'translateX(5px)'},{transform:'translateX(0)'}],
      {duration:correct?280:220,easing:'ease-out'});
  }
}
function renderQuizProgress(){
  const target=$('#quiz-progress');target.hidden=quiz.questions[index].type!=='mcq';
  if(target.hidden)return;
  const completed=quiz.questions.filter(q=>answers[q.id]?.submitted).length;
  target.innerHTML='<span class="quiz-progress-count" aria-label="'+completed+' completed">'+completed+'</span><div class="quiz-segments">'+
    quiz.questions.map((q,i)=>'<button class="quiz-segment '+(answers[q.id]?.submitted?(answers[q.id].correct?'is-correct':'is-wrong'):'')+' '+(i===index?'is-current':'')+'" data-quiz-index="'+i+'" aria-label="Question '+(i+1)+(answers[q.id]?.submitted?(answers[q.id].correct?', correct':', needs practice'):', unanswered')+'" '+(i===index?'aria-current="step"':'')+'><span></span></button>').join('')+
    '</div><span class="quiz-progress-total" aria-label="'+quiz.questions.length+' questions">'+quiz.questions.length+'</span>';
  target.querySelectorAll('[data-quiz-index]').forEach(button=>button.onclick=()=>goToQuestion(Number(button.dataset.quizIndex)));
}
function render(){if(!quiz)return;if(quiz.format==='cheatsheet')return renderCheatSheet();const q=quiz.questions[index],a=answers[q.id]||{};renderQuizProgress();$('#question-nav').innerHTML=quiz.questions.map((x,i)=>'<button class="q-dot '+(i===index?'current ':'')+(answers[x.id]?.submitted?(answers[x.id].correct?'done':'missed'):'')+'" data-index="'+i+'" '+(i===index?'aria-current="step"':'')+' aria-label="Question '+(i+1)+'">'+(i+1)+'</button>').join('');$('#question-nav').querySelectorAll('button').forEach(b=>b.onclick=()=>{goToQuestion(Number(b.dataset.index));});const done=Object.values(answers).filter(x=>x.submitted).length;$('#progress-bar').style.width=done/quiz.questions.length*100+'%';let html='<div class="question-meta"><span>Question '+(index+1)+' of '+quiz.questions.length+'</span><span>'+({mcq:'Multiple choice',flashcard:'Flashcard',calculation:'Calculation'})[q.type]+'</span></div><h4 tabindex="-1" id="question-prompt">'+mathHtml(q.prompt)+'</h4>';
if(q.type==='mcq'){
  html='<div class="quiz-card-toolbar"><span>Question '+(index+1)+' of '+quiz.questions.length+'</span><button id="quiz-sound" class="quiz-sound" aria-label="'+(answerSoundEnabled?'Mute sounds':'Enable sounds')+'" aria-pressed="'+answerSoundEnabled+'" title="'+(answerSoundEnabled?'Sounds on':'Sounds off')+'">'+flashIcon(answerSoundEnabled?'volume-2':'volume-x')+'</button></div><div class="quiz-content"><div class="quiz-content-inner"><h4 tabindex="-1" id="question-prompt">'+mathHtml(q.prompt)+'</h4>'+
    '<p class="quiz-answer-label" role="status">'+(a.submitted?a.skipped?'Answer revealed':a.correct?'Correct!':'':'Choose an answer')+'</p><div class="options" role="group" aria-label="Answer options">'+
    q.options.map((x,i)=>'<button class="option '+(a.selected===i?'selected ':'')+(a.submitted?(i===q.correctIndex?'correct':a.selected===i?'wrong':''):'')+'" data-answer="'+i+'" aria-pressed="'+String(a.selected===i)+'" '+(a.submitted?'disabled':'')+'><span class="letter">'+(i+1)+'</span><span class="option-text">'+mathHtml(x)+'</span>'+(a.submitted&&i===q.correctIndex?'<span class="answer-state">'+flashIcon('check')+'<span class="sr-only">Correct answer</span></span>':a.submitted&&a.selected===i?'<span class="answer-state">'+flashIcon('x')+'<span class="sr-only">Your answer, incorrect</span></span>':'')+'</button>').join('')+'</div>'+
    '</div></div><div class="quiz-bottom-actions">'+(a.submitted?'<button class="practice-button explanation-button" id="quiz-explanation">Explanation</button>':'<button class="quiz-skip" id="quiz-skip">Don’t know?</button>')+'</div>';
}

if(q.type==='calculation'){html=html.replace('<span>Calculation</span>', '<span class="calculation-meta-actions">Calculation<button id="quiz-sound" class="quiz-sound" aria-label="'+(answerSoundEnabled?'Mute sounds':'Enable sounds')+'" aria-pressed="'+answerSoundEnabled+'" title="'+(answerSoundEnabled?'Sounds on':'Sounds off')+'">'+flashIcon(answerSoundEnabled?'volume-2':'volume-x')+'</button></span>');html+='<label class="sr-only" for="number-answer">Your numeric answer</label><div class="numeric-row"><div id="numeric-answer-field" class="numeric-answer-field '+(a.submitted?(a.correct?'is-correct':'is-wrong'):'')+'"><input class="field" id="number-answer" inputmode="decimal" enterkeyhint="done" placeholder="Type answer and press Enter" aria-invalid="'+Boolean(a.submitted&&!a.correct)+'" value="'+esc(a.value||'')+'" '+(a.submitted&&a.correct?'disabled':'')+'>'+(a.submitted?'<span class="numeric-answer-state" role="status">'+flashIcon(a.correct?'check':'x')+'<span class="sr-only">'+(a.correct?'Correct answer':'Incorrect answer')+'</span></span>':'')+'</div><div class="numeric-actions">'+(a.submitted?'<details id="calculation-solution" class="calculation-solution"><summary class="practice-button explanation-button">Explanation</summary><div id="calculation-solution-panel" class="calculation-solution-panel" role="region" aria-label="Worked solution" tabindex="0">'+feedbackHtml(q,a)+sourceHtml(q)+'</div></details>':'')+'</div></div><div id="answer-message" role="alert" class="tiny"></div><details class="hint"><summary>Need a starting point?</summary><p>Substitute given values into the relevant formula.</p></details>';}
if(q.type==='flashcard'){
  const origin=q.originQuizId||quiz.id,eligible=Boolean(origin&&(quiz.mode==='generated'||quiz.mode==='bank'));
  const starred=typeof isQuestionStarred==='function'?isQuestionStarred(q):Boolean(q.starred);
  const hintShown=Boolean(a.hintVisible&&q.hint);
  html='<div class="flashcard-shell"><div class="flashcard-toolbar"><button id="flash-hint" class="flash-hint" '+(!eligible||q.hintLoading?'disabled':'')+' aria-expanded="'+hintShown+'">'+flashIcon('lightbulb')+(q.hintLoading?'Getting hint…':hintShown?'Hide hint':'Get a hint')+'</button><button id="flash-star" class="flash-star '+(starred?'is-starred':'')+'" aria-label="'+(starred?'Unstar card':'Star card')+'" aria-pressed="'+starred+'" title="'+(eligible?'Save to question bank':'Save a generated card')+'" '+(!eligible||q.starLoading?'disabled':'')+'>'+flashIcon(starred?'star-filled':'star')+'</button></div>'+(hintShown?'<div class="flash-hint-text" role="status">'+mathHtml(q.hint)+'</div>':'')+'<button id="flash-flip" class="flash-flip '+(a.revealed?'answer-face':'')+'" aria-label="'+(a.revealed?'Show question':'Show answer')+'" aria-describedby="question-prompt"><span id="question-prompt" class="flash-card-text">'+mathHtml(a.revealed?q.answer:q.prompt)+'</span></button></div>';
  // Reserve this row on both faces so flipping never moves navigation.
  html=html.slice(0,-6)+'<div class="flash-recall"><button class="practice-button explanation-button" id="quiz-explanation" '+(!a.revealed?'hidden':'')+'>Explanation</button></div></div>';
}
$('#question').setAttribute('data-type',q.type);$('#study').setAttribute('data-format',q.type);
$('#question').innerHTML=html;$('#previous').disabled=index===0;
if(q.type==='calculation'&&a.submitted){
  const solution=$('#calculation-solution'),panel=$('#calculation-solution-panel');
  const collapse=()=>{solution.open=false;solution.querySelector('summary')?.focus();};
  panel.onclick=event=>{if(!event.target.closest('button,a,summary,input,select,label')&&!window.getSelection?.()?.toString())collapse();};
  panel.onkeydown=event=>{if(event.key==='Escape'||event.target===panel&&['Enter',' '].includes(event.key)){event.preventDefault();collapse();}};
}

$('#previous').innerHTML=flashIcon('arrow-left')+(q.type==='flashcard'?'Back':'Previous');
$('#next').innerHTML=(q.type==='flashcard'?'Continue':'Next')+flashIcon('arrow-right');$('#next').title=index===quiz.questions.length-1?'View results':'Next question';
$('#flash-position').hidden=q.type!=='flashcard';$('#flash-position').textContent=(index+1)+' / '+quiz.questions.length;

$('#question').querySelectorAll('[data-answer]').forEach(b=>b.onclick=()=>submitChoice(Number(b.dataset.answer)));if($('#quiz-explanation'))$('#quiz-explanation').onclick=openQuizExplanation;if($('#quiz-skip'))$('#quiz-skip').onclick=()=>submitChoice(null,true);if($('#quiz-sound'))$('#quiz-sound').onclick=()=>{setAnswerSound(!answerSoundEnabled);render();$('#quiz-sound').focus();};document.querySelectorAll('.source-open').forEach(b=>b.onclick=()=>openSource(b.dataset.source));scheduleSave();if($('#number-answer'))$('#number-answer').oninput=e=>{answers[q.id]={...answers[q.id],value:e.target.value};scheduleSave();};if($('#number-answer'))$('#number-answer').onkeydown=e=>{if(e.key==='Enter'&&!e.isComposing&&!e.repeat){e.preventDefault();submitCalculation();}};if($('#flash-flip'))$('#flash-flip').onclick=()=>{answers[q.id]={...answers[q.id],reviewed:true,revealed:!answers[q.id]?.revealed};render();$('#flash-flip').focus();};if($('#flash-hint'))$('#flash-hint').onclick=()=>requestFlashcardHint(q);if($('#flash-star'))$('#flash-star').onclick=()=>toggleQuestionStar(q);fitQuizStage();}
function sampleSheet(){
  return {title:'Gradient descent',format:'cheatsheet',mode:'sample',questions:[],sections:samples.flashcard.map((q,i)=>({id:'s'+i,heading:q.prompt,points:[q.answer],formulas:[],source:q.source}))};
}
function renderCheatSheet(){
  $('#study').hidden=true;$('#summary').hidden=true;$('#cheatsheet').hidden=false;$('#sheet-title').innerHTML=mathHtml(quiz.title);
  $('#sheet-nav').innerHTML=quiz.sections.map((s,i)=>'<button class="quiet" data-sheet-section="'+i+'">'+mathHtml(s.heading)+'</button>').join('');
  $('#sheet-sections').innerHTML=quiz.sections.map((s,i)=>'<article class="sheet-section" id="sheet-section-'+i+'"><h3 tabindex="-1">'+mathHtml(s.heading)+'</h3><ul>'+s.points.map(t=>'<li>'+mathHtml(t)+'</li>').join('')+'</ul>'+s.formulas.map(t=>'<div class="sheet-formula">'+mathHtml(t,{formula:true})+'</div>').join('')+sourceHtml(s)+'</article>').join('');
  $('#sheet-nav').querySelectorAll('[data-sheet-section]').forEach(b=>b.onclick=()=>{const section=$('#sheet-section-'+b.dataset.sheetSection);section.scrollIntoView({behavior:'smooth',block:'start'});section.querySelector('h3').focus({preventScroll:true});});
  $('#sheet-sections').querySelectorAll('.source-open').forEach(b=>b.onclick=()=>openSource(b.dataset.source));
  saveSnapshot();
}
async function downloadCheatSheet(type){
  if(quiz?.format!=='cheatsheet')return;
  const button=$(type==='pdf'?'#sheet-print':'#sheet-export');
  if(button.disabled)return;
  const sheet={title:quiz.title,description:quiz.description,sections:quiz.sections};
  button.disabled=true;
  try{
    const response=await fetch('/api/cheatsheets/export?format='+type,{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify(sheet)});
    if(!response.ok){const error=await response.json();throw Error(error.detail||error.error||'Export failed. Try again.');}
    const url=URL.createObjectURL(await response.blob()),link=document.createElement('a');
    link.href=url;link.download='lecture-lab-study-guide.'+type;link.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(error){message(error.message,true);}finally{button.disabled=false;}
}
$('#sheet-export').onclick=()=>downloadCheatSheet('html');$('#sheet-print').onclick=()=>downloadCheatSheet('pdf');
function gradeNumeric(value,expected,tolerance){if(!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(value))return null;const n=Number(value);return Number.isFinite(n)?Math.abs(n-expected)<=tolerance+Number.EPSILON*Math.max(1,Math.abs(expected)):null;}
function hideFlashcardAnswer(){
  const q=quiz?.questions?.[index],a=q&&answers[q.id];
  if(q?.type==='flashcard'&&a)answers[q.id]={...a,reviewed:!!(a.reviewed||a.revealed||a.submitted),revealed:false};
}
function goToQuestion(position){cancelQuizAdvance();closeQuizExplanation();index=position;hideFlashcardAnswer();render();$('#question-prompt')?.focus({preventScroll:true});}
$('#previous').onclick=()=>{if(index>0)goToQuestion(index-1);};
$('#next').onclick=advanceQuiz;
function showSummary(){
  cancelQuizAdvance();closeQuizExplanation();
  scheduleSave(true);
  const cards=quiz.format==='flashcard',total=quiz.questions.length;
  const completed=quiz.questions.filter(q=>cards
    ? answers[q.id]?.reviewed||answers[q.id]?.revealed||answers[q.id]?.submitted
    : answers[q.id]?.submitted).length;
  const graded=quiz.questions.filter(q=>answers[q.id]?.submitted);
  const correct=graded.filter(q=>answers[q.id].correct).length;
  const remaining=total-completed,percent=Math.round(completed/total*100);
  const status=q=>{const a=answers[q.id];if(cards)return a?.reviewed||a?.revealed||a?.submitted?'Reviewed':'Not reviewed';return a?.skipped?'Skipped':a?.submitted
    ? a.correct?(cards?'Recalled':'Correct'):(cards?'Practice again':'Incorrect')
    : cards&&(a?.reviewed||a?.revealed)?'Reviewed':cards?'Not reviewed':'Not answered';};
  $('#study').hidden=true;$('#summary').hidden=false;
  $('#summary').innerHTML='<div class="completion-heading"><h2 id="completion-title" tabindex="-1">'+
    (remaining?'Session summary':cards?'You reviewed every card!':'Practice complete!')+
    '</h2><span class="completion-mark" aria-hidden="true">'+flashIcon(remaining?'book-open':'check')+'</span></div>'+
    '<div class="completion-grid"><section class="completion-overview" aria-label="Session progress"><h3>Your progress</h3>'+
    '<div class="completion-progress"><div class="completion-ring" style="--completion:'+percent+'%" aria-hidden="true"><span>'+percent+'%</span></div>'+
    '<dl class="completion-counts"><div><dt>Completed</dt><dd>'+completed+'</dd></div><div><dt>Remaining</dt><dd>'+remaining+'</dd></div></dl></div>'+
    (!cards&&graded.length?'<p class="completion-score">'+correct+' correct · '+(graded.length-correct)+' incorrect</p>':'')+
    '</section><section class="completion-next" aria-label="Next steps"><h3>Next steps</h3>'+
    '<button id="review-restart" class="completion-restart"><span class="restart-icon">'+flashIcon('rotate-ccw')+'</span><span><strong>Restart '+(cards?'flashcards':'quiz')+'</strong><small>'+total+' '+(cards?'cards':'questions')+'</small></span>'+flashIcon('chevron-right')+'</button></section></div>'+
    '<details class="completion-details"><summary>Question summary</summary><ol class="completion-questions">'+
    quiz.questions.map(q=>'<li><span>'+mathHtml(q.prompt)+'</span><strong>'+status(q)+'</strong></li>').join('')+'</ol></details>'+
    '<div class="completion-footer"><button class="completion-back" id="review-previous">'+flashIcon('arrow-left')+'Back to last question</button><button class="completion-home" id="review-next">Home'+flashIcon('arrow-right')+'</button></div>';
  $('#review-restart').onclick=()=>{
    index=0;answers={};quiz.progress={index:0,answers:{},review:false};
    $('#summary').hidden=true;$('#study').hidden=false;render();
    $('#quiz-title').setAttribute('tabindex','-1');$('#quiz-title').focus();
  };
  $('#review-previous').onclick=()=>{$('#study').hidden=false;$('#summary').hidden=true;goToQuestion(total-1);$('#quiz-title').setAttribute('tabindex','-1');$('#quiz-title').focus();};
  $('#review-next').onclick=()=>$('#back-library').click();
  $('#completion-title').focus();
}

function exportQuiz(){if(!quiz)return;const payload={title:quiz.title,description:quiz.description,format:quiz.format,mode:quiz.mode,questions:quiz.questions,...(quiz.format==='cheatsheet'?{sections:quiz.sections}:{})};const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=quiz.format==='cheatsheet'?'lecture-lab-cheatsheet.json':'lecture-lab-quiz.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function validateImported(q){if(q?.format==='cheatsheet')return validateImportedSheet(q);if(!q||typeof q.title!=='string'||q.title.length>180||!Array.isArray(q.questions)||q.questions.length<1||q.questions.length>(q.mode==='bank'?500:12))throw Error('Choose a Lecture Lab quiz with 1–12 questions.');const ids=new Set();for(const x of q.questions){if(!x||!['mcq','flashcard','calculation'].includes(x.type)||typeof x.id!=='string'||ids.has(x.id)||typeof x.prompt!=='string'||typeof x.answer!=='string'||typeof x.explanation!=='string'||!x.source||!['name','locator','quote'].every(k=>typeof x.source[k]==='string')||!Array.isArray(x.steps)||!x.steps.every(y=>typeof y==='string'))throw Error('The quiz has missing or invalid question fields.');ids.add(x.id);if(x.type==='mcq'&&(!Array.isArray(x.options)||x.options.length<2||x.options.length>6||!x.options.every(y=>typeof y==='string')||!Number.isInteger(x.correctIndex)||x.correctIndex<0||x.correctIndex>=x.options.length))throw Error('A multiple-choice question has invalid options.');if(x.type==='calculation'&&(!Number.isFinite(x.numericAnswer)||!Number.isFinite(x.tolerance)||x.tolerance<0||x.tolerance>1))throw Error('A calculation question has an invalid numeric answer or tolerance.');}return q;}
function validateImportedSheet(q){
  if(typeof q.title!=='string'||!q.title.trim()||q.title.length>180||!Array.isArray(q.sections)||q.sections.length<1||q.sections.length>2048)throw Error('Choose a valid Lecture Lab cheat sheet.');
  const ids=new Set();for(const s of q.sections){
    if(!s||typeof s.id!=='string'||ids.has(s.id)||typeof s.heading!=='string'||!s.heading.trim()||s.heading.length>120||!Array.isArray(s.points)||!Array.isArray(s.formulas)||s.points.length+s.formulas.length<1||s.points.length+s.formulas.length>120||![...s.points,...s.formulas].every(t=>typeof t==='string'&&t.trim()&&t.length<=6000)||!s.source||!['name','locator','quote'].every(k=>typeof s.source[k]==='string'))throw Error('The cheat sheet has invalid sections or sources.');
    ids.add(s.id);
  }return {...q,questions:[]};
}
$('#import-file').onchange=async e=>{try{const f=e.target.files[0];if(!f)return;if(f.size>1024*1024)throw Error('Import a quiz smaller than 1 MB.');const raw=JSON.parse(await f.text());const q=validateImported({...raw,mode:raw?.mode==='sample'?'sample':'imported'});startQuiz({...q,format:q.format||q.questions[0].type});message('Set imported.');}catch(err){message(err.message,true);}e.target.value='';};
window.__lectureLab={samples,gradeNumeric,validateImported,inferRequestedFormat,sampleSheet,validateImportedSheet};
