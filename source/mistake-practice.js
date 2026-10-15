// Follow-up generation uses server-regraded saved attempts and the existing RAG job pipeline.
let mistakeQuizId=null,mistakeItems=[],mistakeRequestKey=null,mistakeSignature='',mistakeJobId=null,mistakeSubmitting=false;
function mistakeSummaryAction(){
  const eligible=quiz?.id&&quiz.mode==='generated'&&['mcq','calculation'].includes(quiz.format);
  const count=eligible?quiz.questions.filter(q=>answers[q.id]?.submitted&&!answers[q.id]?.correct).length:0;
  return count?'<button id="practice-mistakes" class="completion-restart mistake-start"><span class="restart-icon">'+flashIcon('sparkles')+'</span><span><strong>Practice my mistakes</strong><small>'+count+' incorrect or skipped</small></span>'+flashIcon('chevron-right')+'</button>':'';
}
function bindMistakeSummary(){const button=$('#practice-mistakes');if(button)button.onclick=openMistakePractice;}
function renderMistakeChoices(){
  $('#mistake-choices').innerHTML=mistakeItems.map(q=>'<label class="mistake-choice"><input type="checkbox" value="'+esc(q.questionId)+'" checked><span><span class="mistake-status">'+(q.status==='skipped'?'Skipped':'Incorrect')+'</span><strong class="mistake-prompt" data-no-translate>'+mathHtml(q.prompt)+'</strong>'+(q.source?'<small data-no-translate>'+esc(q.source.name)+' · '+esc(q.source.locator)+'</small>':'')+'</span></label>').join('');
  $('#mistake-choices').querySelectorAll('input').forEach(input=>input.onchange=()=>{
    mistakeRequestKey=null;mistakeSignature='';mistakeJobId=null;$('#mistake-message').textContent='';syncMistakeControls();
  });
  syncMistakeControls();
}
function selectedMistakes(){return [...$('#mistake-choices').querySelectorAll('input:checked')].map(input=>input.value);}
function syncMistakeControls(){
  const locked=mistakeSubmitting||Boolean(busy&&mistakeJobId);
  $('#mistake-generate').disabled=locked||!selectedMistakes().length;
  $('#mistake-generate').textContent=locked?'Creating…':mistakeJobId?'Try again':'Generate four questions';
  $('#mistake-cancel-job').hidden=!(activeJob&&activeJob===mistakeJobId);
  $('#close-mistakes').disabled=locked;
  $('#mistake-choices').querySelectorAll('input').forEach(input=>input.disabled=locked);
}
async function openMistakePractice(){
  if(busy||mistakeSubmitting||!quiz?.id)return;
  const origin=quiz;
  mistakeQuizId=origin.id;mistakeItems=[];mistakeRequestKey=null;mistakeSignature='';mistakeJobId=null;
  $('#mistake-choices').innerHTML='';$('#mistake-message').textContent='Loading missed questions…';$('#mistake-dialog').showModal();syncMistakeControls();
  try{
    await flushPracticeProgress();
    const result=await api('/api/quizzes/'+origin.id+'/mistakes');
    if(quiz?.id!==origin.id||!$('#mistake-dialog').open)return;
    mistakeItems=result.questions;renderMistakeChoices();
    $('#mistake-message').textContent=mistakeItems.length?'':'No mistakes to practice.';
  }catch(error){$('#mistake-message').textContent=error.message;}
}
function syncMistakeJob(job){
  const context=job.mistakePractice||job.params?.mistakePractice;if(!context)return;
  const origin=context.parentQuizId||job.params?.parentQuizId;
  mistakeJobId=job.id;
  if(mistakeQuizId!==origin||!mistakeItems.length){
    mistakeQuizId=origin;mistakeItems=context.questions;renderMistakeChoices();
  }
  if(job.status==='completed'){
    if($('#mistake-dialog').open)$('#mistake-dialog').close();return;
  }
  if(!$('#mistake-dialog').open)$('#mistake-dialog').showModal();
  $('#mistake-message').textContent=['failed','interrupted','cancelled'].includes(job.status)?friendlyJobError(job):job.stage;
  syncMistakeControls();
}
async function generateMistakePractice(){
  if(busy||mistakeSubmitting)return;
  const ids=selectedMistakes();if(!ids.length||!mistakeQuizId)return;
  const signature=JSON.stringify([mistakeQuizId,ids]);
  if(signature!==mistakeSignature){mistakeSignature=signature;mistakeRequestKey=window.crypto?.randomUUID?.()||Date.now().toString(36)+Math.random().toString(36).slice(2);mistakeJobId=null;}
  mistakeSubmitting=true;setBusy(true);$('#mistake-message').textContent='Creating new practice from your lectures…';syncMistakeControls();
  try{
    let response;
    if(mistakeJobId){
      const previous=await api('/api/jobs/'+mistakeJobId);
      response=['failed','interrupted','cancelled'].includes(previous.status)
        ?await api('/api/jobs/'+mistakeJobId+'/retry',{method:'POST'}):{jobId:previous.id};
    }else response=await api('/api/quizzes/'+mistakeQuizId+'/mistakes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({questionIds:ids,count:4,requestId:mistakeRequestKey})});
    mistakeJobId=response.jobId;syncMistakeControls();
    const job=await watchJob(response.jobId);
    if(job.result?.status!=='ready'){
      mistakeJobId=null;mistakeRequestKey=null;mistakeSignature='';
      throw Error(job.result?.message||'Add clearer lecture material and try again.');
    }
    const result=validateImported(await api('/api/quizzes/'+job.result.quizId));
    $('#mistake-dialog').close();parentQuizId=null;updateFollowup();startQuiz(result);saveSnapshot();
  }catch(error){
    if(!$('#mistake-dialog').open)$('#mistake-dialog').showModal();
    $('#mistake-message').textContent=error.message;
  }finally{mistakeSubmitting=false;if(!activeJob)setBusy(false);syncMistakeControls();saveSnapshot();}
}
$('#mistake-generate').onclick=generateMistakePractice;
$('#close-mistakes').onclick=()=>{if(!mistakeSubmitting&&!busy)$('#mistake-dialog').close();};
$('#mistake-dialog').addEventListener('cancel',event=>{if(mistakeSubmitting||busy)event.preventDefault();});
$('#mistake-cancel-job').onclick=async()=>{
  if(!mistakeJobId)return;
  try{await api('/api/jobs/'+mistakeJobId+'/cancel',{method:'POST'});$('#mistake-message').textContent='Cancelling…';}
  catch(error){$('#mistake-message').textContent=error.message;}
};
