document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('[data-match-review]');
  if (!form) return;
  const outcome = form.querySelector('[name=outcome]');
  const update = () => {
    for (const name of ['name','description','severity','kind','remediation','identifiers']) {
      const row = form.querySelector(`[name=${name}]`)?.closest('p');
      if (row) row.hidden = outcome.value !== 'new';
    }
    const targetRow = form.querySelector('[name=target]')?.closest('p');
    if (targetRow) targetRow.hidden = outcome.value !== 'match';
    for (const [name, value] of [['target', 'match'], ['name', 'new']]) {
      const field = form.querySelector(`[name=${name}]`);
      if (field) {
        field.required = outcome.value === value;
        field.dispatchEvent(new Event('input', {bubbles:true}));
      }
    }
  };
  outcome.addEventListener('change', update);
  update();
});
