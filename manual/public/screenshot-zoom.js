// Keep interface screenshots readable without an external image service.
const screenshots = document.querySelectorAll('.sl-markdown-content .theme-screenshot, .sl-markdown-content img:not(.theme-screenshot img)');
if (screenshots.length) {
  const dialog = document.createElement('dialog');
  dialog.className = 'screenshot-dialog';
  dialog.setAttribute('aria-label', 'Screenshot preview');
  const heading = document.createElement('div');
  heading.className = 'screenshot-dialog-heading';
  const original = document.createElement('a');
  original.textContent = 'Open full-size image';
  original.target = '_blank';
  original.rel = 'noreferrer';
  const close = document.createElement('button');
  close.type = 'button';
  close.textContent = 'Close';
  close.addEventListener('click', () => dialog.close());
  heading.append(original, close);
  const preview = document.createElement('img');
  const description = document.createElement('p');
  description.className = 'screenshot-description';
  dialog.append(heading, preview, description);
  document.body.append(dialog);
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  let activeScreenshot;
  const selectedImage = screenshot => screenshot.matches('img') ? screenshot : screenshot.querySelector(
    document.documentElement.dataset.theme === 'dark' ? '.screenshot-dark' : '.screenshot-light'
  );
  const updatePreview = () => {
    if (!activeScreenshot) return;
    const image = selectedImage(activeScreenshot);
    preview.src = image.currentSrc || image.src;
    preview.alt = image.alt;
    original.href = preview.src;
    description.textContent = image.alt;
  };
  new MutationObserver(() => { if (dialog.open) updatePreview(); }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  for (const screenshot of screenshots) {
    const image = selectedImage(screenshot);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'screenshot-enlarge';
    button.title = 'Enlarge screenshot';
    button.setAttribute('aria-label', `Enlarge screenshot: ${image.alt}`);
    screenshot.before(button);
    button.append(screenshot);
    button.addEventListener('click', () => {
      activeScreenshot = screenshot;
      updatePreview();
      dialog.showModal();
      close.focus();
    });
  }
}
