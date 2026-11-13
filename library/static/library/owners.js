/* Add/link a contact in another tab, then refresh choices without losing form input. */
(() => {
  const selectors = Array.from(document.querySelectorAll('select[data-owner-options]'));
  selectors.forEach(select => {
    const add = document.createElement('a');
    add.className = 'button button-secondary owner-add';
    add.textContent = 'Add contact';
    add.href = select.dataset.ownerCreate;
    add.target = '_blank';
    add.rel = 'noopener';
    add.setAttribute('aria-label', 'Add contact (opens in a new tab)');
    const refresh = document.createElement('button');
    refresh.type = 'button';
    refresh.className = 'button-secondary owner-refresh';
    refresh.classList.add('icon-button');
    refresh.setAttribute('aria-label', 'Refresh contacts');
    refresh.title = 'Refresh contacts';
    const icon = document.createElement('span');
    icon.setAttribute('aria-hidden', 'true');
    icon.textContent = '↻';
    refresh.append(icon);
    const status = document.createElement('span');
    status.className = 'owner-status';
    status.setAttribute('role', 'status');
    select.after(add, refresh, status);
    async function update() {
      refresh.disabled = true;
      try {
        const response = await fetch(select.dataset.ownerOptions, {credentials: 'same-origin', headers: {'Accept': 'application/json'}});
        if (!response.ok) throw new Error('Contact list unavailable');
        const {contacts} = await response.json();
        const current = select.value;
        const retained = select.selectedOptions[0]?.textContent;
        select.replaceChildren(new Option('Unassigned', ''));
        for (const contact of contacts) select.add(new Option(contact.name, String(contact.id)));
        // The server form validates retention; refresh never grants assignment permission.
        if (current && !contacts.some(contact => String(contact.id) === current)) select.add(new Option(retained, current));
        select.value = current;
        status.textContent = 'Contacts updated.';
      } catch {
        status.textContent = 'Unable to refresh. Try again; your entries are preserved.';
      } finally { refresh.disabled = false; }
    }
    refresh.addEventListener('click', update);
  });
})();
