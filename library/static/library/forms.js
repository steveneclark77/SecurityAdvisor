/* Keep action buttons unavailable until their form's required input is ready. */
(() => {
  function ready(form) {
    return Array.from(form.elements).every(field => {
      if (!field.willValidate) return true;
      if (!field.validity.valid) return false;
      if (field.required && ['text', 'search', 'email', 'url', 'tel', 'password', 'textarea'].includes(field.type)) {
        return field.value.trim().length > 0;
      }
      return true;
    });
  }
  function update(form) {
    const valid = ready(form);
    form.querySelectorAll('button:not([type]), button[type="submit"], input[type="submit"]').forEach(button => {
      if (!button.formNoValidate) button.disabled = !valid;
    });
  }
  function refresh() { document.querySelectorAll('form').forEach(update); }
  document.addEventListener('input', event => { if (event.target.form) update(event.target.form); });
  document.addEventListener('change', event => { if (event.target.form) update(event.target.form); });
  document.addEventListener('focusin', event => { if (event.target.form) update(event.target.form); });
  window.addEventListener('pageshow', refresh);
  document.querySelectorAll('[data-open-dialog]').forEach(button => {
    button.addEventListener('click', () => document.getElementById(button.dataset.openDialog).showModal());
  });
  document.querySelectorAll('[data-close-dialog]').forEach(button => {
    button.addEventListener('click', () => button.closest('dialog').close());
  });
  refresh();
})();
