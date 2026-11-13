/* Progressive enhancement: contextual choices and one accessible help dialog per field. */
(() => {
  if (window.securityAdvisorFieldHelp) return;
  window.securityAdvisorFieldHelp = true;
  let nextId = 0;
  const enhanced = new WeakSet();
  function enhance(root = document) {
    const candidates = root.querySelectorAll('form [data-field-info], form input:not([type=hidden]):not([type=submit]):not([type=button]), form select, form textarea');
    candidates.forEach(widget => {
      if (enhanced.has(widget) || widget.closest('dialog') || widget.dataset.noFieldInfo || widget.closest('.empty-form')) return;
      if (widget.classList.contains('action-select') || (widget.closest('.selector') && !widget.dataset.fieldInfo)) return;
      if (widget.parentElement.closest('[data-field-info]')) return; // Checkbox/radio group shares one help control.
      const form = widget.closest('form');
      if (form.method.toLowerCase() !== 'post' || widget.closest('[data-view-controls], .actions')) return;
      const label = (widget.id && form.querySelector(`label[for="${CSS.escape(widget.id)}"]`)) || (widget.dataset.fieldId && form.querySelector(`label[for="${CSS.escape(widget.dataset.fieldId)}"]`)) || widget.closest('label');
      const labelCopy = label?.cloneNode(true);
      labelCopy?.querySelectorAll('input,select,textarea,button').forEach(child => child.remove());
      const heading = widget.dataset.fieldLabel || labelCopy?.textContent.trim().replace(/:$/, '') || widget.name?.replaceAll('_', ' ') || 'Field';
      // Preserve explicit labels such as All states and Unassigned on hand-written filters.
      if (widget.tagName === 'SELECT' && !widget.multiple) {
        for (const option of widget.options) {
          if (option.value === '' && /^[-–—]+$/.test(option.textContent.trim())) option.textContent = `Select ${heading.toLowerCase()}`;
        }
      }
      const group = widget.dataset.fieldId && form.querySelector(`#${CSS.escape(widget.dataset.fieldId)}`);
      const anchor = group && group !== widget && group.contains(widget) ? group : widget;
      if (enhanced.has(anchor)) return;
      enhanced.add(anchor);
      enhanced.add(widget);
      let fieldLabel = label;
      if (anchor !== widget) {
        fieldLabel = null;
        const candidate = anchor.previousElementSibling?.querySelector('label');
        if (candidate?.textContent.trim().replace(/:$/, '') === heading) fieldLabel = candidate;
      }
      const id = `field-help-${++nextId}`;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'info-button';
      button.dataset.openDialog = id;
      button.setAttribute('aria-label', `Help for ${heading}`);
      button.setAttribute('aria-haspopup', 'dialog');
      button.setAttribute('aria-controls', id);
      const icon = document.createElement('span');
      icon.setAttribute('aria-hidden', 'true');
      icon.textContent = 'i';
      button.append(icon);
      if (fieldLabel) fieldLabel.after(button); else anchor.before(button);
      const dialog = document.createElement('dialog');
      dialog.id = id;
      dialog.className = 'field-help-dialog';
      dialog.setAttribute('aria-labelledby', `${id}-title`);
      const title = document.createElement('h2');
      title.id = `${id}-title`;
      title.textContent = `${heading} help`;
      dialog.append(title);
      const help = (anchor.id && form.querySelector(`#${CSS.escape(anchor.id + '_helptext')}`)) || (widget.dataset.fieldId && form.querySelector(`#${CSS.escape(widget.dataset.fieldId + '_helptext')}`));
      if (help) {
        dialog.append(help); // Move trusted, server-rendered help; never parse input as HTML.
        for (const control of [anchor, ...anchor.querySelectorAll('input,select,textarea')]) {
          const references = (control.getAttribute('aria-describedby') || '').split(/\s+/).filter(value => value && value !== help.id);
          if (references.length) control.setAttribute('aria-describedby', references.join(' '));
          else control.removeAttribute('aria-describedby');
        }
      } else {
        const text = document.createElement('p');
        text.textContent = widget.dataset.fieldInfo || `${heading}: choose or enter a value for this field.`;
        dialog.append(text);
      }
      const close = document.createElement('button');
      close.type = 'button';
      close.className = 'button-secondary';
      close.dataset.closeDialog = '';
      close.textContent = 'Close';
      dialog.append(close);
      document.body.append(dialog);
    });
  }
  document.addEventListener('click', event => {
    const opener = event.target.closest('[data-open-dialog]');
    if (opener) {
      const dialog = document.getElementById(opener.dataset.openDialog);
      if (dialog && !dialog.open) dialog.showModal();
    }
    const closer = event.target.closest('[data-close-dialog]');
    if (closer) closer.closest('dialog')?.close();
  });
  enhance();
  // Django admin adds inline forms dynamically. Scope enhancement to those additions.
  new MutationObserver(records => {
    for (const record of records) for (const node of record.addedNodes) {
      if (node.nodeType === Node.ELEMENT_NODE && !node.closest('dialog') && node.querySelector('input,select,textarea')) enhance(node);
    }
  }).observe(document.body, {childList: true, subtree: true});
})();
