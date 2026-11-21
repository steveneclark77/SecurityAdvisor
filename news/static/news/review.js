/* Review decisions require their conditional fields before submission. */
document.addEventListener('DOMContentLoaded', () => {
  const decision = document.querySelector('[name=decision]');
  if (!decision) return;
  const requirements = [
    [document.querySelector('[name=proposed_guidance]'), ['add', 'update']],
    [document.querySelector('[name=name]'), ['accept']],
  ];
  const update = () => {
    for (const [field, decisions] of requirements) {
      if (!field) continue;
      field.required = decisions.includes(decision.value);
      field.dispatchEvent(new Event('input', { bubbles: true }));
    }
  };
  decision.addEventListener('change', update);
  update();
});
