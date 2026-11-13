/* Stable shared chrome: navigation disclosure and unobscured focus/anchors. No CSS injection. */
(() => {
  const header = document.querySelector('.site-header, #header');
  if (!header) return;
  const button = header.querySelector('[data-header-menu]');
  const panel = button && document.getElementById(button.getAttribute('aria-controls'));
  const narrow = window.matchMedia('(max-width: 1000px)');
  function close(restoreFocus = false) {
    header.classList.remove('is-menu-open');
    button?.setAttribute('aria-expanded', 'false');
    if (restoreFocus) button?.focus();
  }
  if (button && panel) {
    header.classList.add('is-enhanced');
    panel.classList.add('header-navigation');
    button.hidden = false;
    button.addEventListener('click', () => {
      const open = header.classList.toggle('is-menu-open');
      button.setAttribute('aria-expanded', String(open));
    });
    document.addEventListener('click', event => { if (!header.contains(event.target)) close(); });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && header.classList.contains('is-menu-open')) {
        event.preventDefault();
        close(true);
      }
    });
    narrow.addEventListener('change', () => {
      const hiddenFocus = narrow.matches && panel.contains(document.activeElement);
      close(hiddenFocus);
    });
  }
  function reveal(element) {
    if (!element || header.contains(element) || element.closest('dialog') || window.matchMedia('print').matches) return;
    const top = element.getBoundingClientRect().top;
    const clearance = header.getBoundingClientRect().bottom + 12;
    if (top < clearance) window.scrollBy(0, top - clearance);
  }
  document.addEventListener('focusin', event => {
    if (!header.contains(event.target)) close();
    requestAnimationFrame(() => reveal(event.target));
  });
  function revealHash() {
    let id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    requestAnimationFrame(() => reveal(id && document.getElementById(id)));
  }
  window.addEventListener('hashchange', revealHash);
  revealHash();
})();
