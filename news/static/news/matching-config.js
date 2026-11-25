document.addEventListener('DOMContentLoaded', () => {
  const autonomy = document.querySelector('[name=autonomous_enabled]');
  const calibration = document.querySelector('[name=active_calibration]');
  if (!autonomy || !calibration) return;
  const update = () => {
    calibration.required = autonomy.checked;
    calibration.dispatchEvent(new Event('input', {bubbles:true}));
  };
  autonomy.addEventListener('change', update);
  update();
});
