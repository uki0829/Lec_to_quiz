// A local appearance preference; no study data or credentials are stored here.
(() => {
  const root=document.querySelector('#authenticated-app'),sidebar=document.querySelector('#study-sidebar'),toggle=document.querySelector('#sidebar-toggle');
  let collapsed=false;
  try{collapsed=localStorage.getItem('lecture-lab-sidebar-collapsed')==='true';}catch{}
  function apply(){
    root.classList.toggle('sidebar-collapsed',collapsed);
    // The collapsed rail remains keyboard-accessible.
    sidebar.inert=false;sidebar.removeAttribute('aria-hidden');
    sidebar.querySelector('.sidebar-folder-intro')?.setAttribute('aria-hidden',String(collapsed));
    toggle.setAttribute('aria-expanded',String(!collapsed));
    const label=collapsed?'Expand sidebar':'Collapse sidebar';toggle.setAttribute('aria-label',label);toggle.title=label;
  }
  toggle.addEventListener('click',()=>{collapsed=!collapsed;apply();try{localStorage.setItem('lecture-lab-sidebar-collapsed',String(collapsed));}catch{}});
  apply();
})();
