/* Add/link a contact in another tab, then refresh choices without losing form input. */
(() => {
  const selectors = Array.from(document.querySelectorAll('select[data-owner-options]'));
  function addOption(select) {
    const option = new Option('＋ Add a new contact…', '__add_contact__');
    select.add(option);
  }
  selectors.forEach(select => {
    let previous = select.value;
    addOption(select);
    select.addEventListener('change', () => {
      if (select.value === '__add_contact__') {
        select.value = previous;
        window.open(select.dataset.ownerCreate, '_blank', 'noopener');
      } else previous = select.value;
    });
    const refresh = document.createElement('button');
    refresh.type = 'button';
    refresh.className = 'button-secondary owner-refresh';
    refresh.textContent = 'Refresh contacts';
    const status = document.createElement('span');
    status.className = 'owner-status';
    status.setAttribute('role', 'status');
    select.after(refresh, status);
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
        addOption(select);
        status.textContent = 'Contacts refreshed. Select the owner after linking the new contact.';
      } catch {
        status.textContent = 'Unable to refresh contacts. Try again; your form entries are preserved.';
      } finally { refresh.disabled = false; }
    }
    refresh.addEventListener('click', update);
  });
})();
