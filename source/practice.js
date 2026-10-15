// Dedicated study pages use existing authenticated set/progress APIs.
const initialPracticePath=location.pathname;
let practiceBooting=true,practiceRouteBusy=false;
function practicePath(q){
  if(q?.mode==='generated'&&q.id)return '/study/quiz/'+encodeURIComponent(q.id);
  if(q?.mode==='shared'&&q.shareId)return '/study/shared/'+encodeURIComponent(q.shareId);
  return '/study/local';
}
function syncPracticePage(view,replace=false){
  const active=view==='study'&&quiz&&quiz.format!=='cheatsheet';
  $('#authenticated-app').classList.toggle('practice-page',Boolean(active));
  if(practiceBooting||practiceRouteBusy)return;
  const path=active?practicePath(quiz):'/';
  if(location.pathname!==path)history[replace?'replaceState':'pushState'](null,'',path);
}
async function loadPracticeRoute(path){
  practiceRouteBusy=true;cancelQuizAdvance();closeQuizExplanation();
  try{
    const match=path.match(/^\/study\/(quiz|shared)\/([^/]+)$/);
    if(match){
      const id=decodeURIComponent(match[2]),shared=match[1]==='shared';
      const same=shared?quiz?.shareId===id:quiz?.id===id&&quiz?.mode==='generated';
      if(!same){
        const q=validateImported(await api((shared?'/api/shared-sets/':'/api/quizzes/')+encodeURIComponent(id)));
        startQuiz(q);if(q.progress?.review)showSummary();
      }else showView('study');
    }else if(path==='/study/local'&&quiz&&quiz.format!=='cheatsheet')showView('study');
    else showView('library');
    saveSnapshot();
  }catch(err){showView('library');message(err.message,true);}
  finally{practiceRouteBusy=false;syncPracticePage(currentView,true);}
}
async function finishPracticeBoot(preferGenerated=false){
  if(!practiceBooting)return;
  practiceBooting=false;
  if(!preferGenerated&&initialPracticePath.startsWith('/study/'))await loadPracticeRoute(initialPracticePath);
  else syncPracticePage(currentView,true);
}
window.addEventListener('popstate',()=>{scheduleSave(!$('#summary').hidden);loadPracticeRoute(location.pathname);});
