/* Add/update proposals need guidance before their action buttons are available. */
document.addEventListener('DOMContentLoaded', () => {
  const decision = document.querySelector('[name=decision]');
  const guidance = document.querySelector('[name=proposed_guidance]');
  if (!decision || !guidance) return;
  const update = () => {
    guidance.required = ['add', 'update'].includes(decision.value);
    guidance.dispatchEvent(new Event('input', { bubbles: true }));
  };
  decision.addEventListener('change', update);
  update();
});
