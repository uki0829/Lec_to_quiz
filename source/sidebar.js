// A local appearance preference; no study data or credentials are stored here.
(() => {
  const root=document.querySelector('#authenticated-app'),sidebar=document.querySelector('#study-sidebar'),toggle=document.querySelector('#sidebar-toggle');
  let collapsed=false;
  try{collapsed=localStorage.getItem('lecture-lab-sidebar-collapsed')==='true';}catch{}
  function apply(){
    root.classList.toggle('sidebar-collapsed',collapsed);
    sidebar.inert=collapsed;sidebar.setAttribute('aria-hidden',String(collapsed));
    toggle.setAttribute('aria-expanded',String(!collapsed));
    const label=collapsed?'Show sidebar':'Hide sidebar';toggle.setAttribute('aria-label',label);toggle.title=label;
  }
  toggle.addEventListener('click',()=>{collapsed=!collapsed;apply();try{localStorage.setItem('lecture-lab-sidebar-collapsed',String(collapsed));}catch{}});
  apply();
})();
