'use strict';
(function () {
  const menus = () => Array.from(document.querySelectorAll('details.more-menu'));
  const closeAll = except => menus().forEach(m => { if (m !== except && m.open) m.open = false; });

  document.addEventListener('click', event => {
    const menu = event.target.closest('details.more-menu');
    if (!menu) { closeAll(); return; }
    closeAll(menu);
    if (event.target.closest('.menu-item')) setTimeout(() => { menu.open = false; }, 0);
  });

  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const open = menus().find(m => m.open);
    if (!open) return;
    open.open = false;
    const summary = open.querySelector('summary');
    if (summary) summary.focus();
  });

  menus().forEach(menu => {
    const summary = menu.querySelector('summary');
    if (!summary) return;
    summary.setAttribute('aria-haspopup', 'true');
    summary.setAttribute('aria-expanded', String(menu.open));
    menu.addEventListener('toggle', () => summary.setAttribute('aria-expanded', String(menu.open)));
  });

  document.querySelectorAll('[role="tablist"]').forEach(list => {
    list.addEventListener('keydown', event => {
      const tabs = Array.from(list.querySelectorAll('[role="tab"]'));
      const i = tabs.indexOf(document.activeElement);
      if (i < 0) return;
      let next = null;
      if (event.key === 'ArrowRight') next = (i + 1) % tabs.length;
      else if (event.key === 'ArrowLeft') next = (i - 1 + tabs.length) % tabs.length;
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = tabs.length - 1;
      if (next === null) return;
      event.preventDefault();
      tabs[next].focus();
      tabs[next].click();
    });
  });
})();
