const demoText = document.querySelector('#demo-text');
const demoStatus = document.querySelector('#demo-status');
const demoButton = document.querySelector('#play-demo');
const demoShell = document.querySelector('.demo-shell');
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
let demoTimer;

function finishDemo() {
  clearTimeout(demoTimer);
  demoText.textContent = '用 LiltKey，把想法写下来。';
  demoStatus.textContent = '停顿后，补充标点并提交。';
  demoButton.innerHTML = '再看一次 <span aria-hidden="true">↻</span>';
  demoButton.disabled = false;
  demoShell.classList.remove('playing');
}

demoButton.addEventListener('click', () => {
  clearTimeout(demoTimer);
  if (reducedMotion.matches) {
    finishDemo();
    return;
  }
  demoButton.disabled = true;
  demoButton.textContent = '演示中…';
  demoStatus.textContent = '正在显示临时文字…';
  demoShell.classList.add('playing');
  demoText.textContent = '';
  const frames = ['用', '用 LiltKey', '用 LiltKey 把', '用 LiltKey 把想法', '用 LiltKey 把想法写下来'];
  let frame = 0;
  function tick() {
    demoText.textContent = frames[frame++];
    demoTimer = setTimeout(frame < frames.length ? tick : finishDemo, frame < frames.length ? 650 : 1100);
  }
  tick();
});

reducedMotion.addEventListener('change', () => {
  if (reducedMotion.matches && demoButton.disabled) finishDemo();
});

document.querySelectorAll('[data-copy]').forEach(button => {
  let feedbackTimer;
  button.addEventListener('click', async () => {
    const target = document.getElementById(button.dataset.copy);
    const status = document.querySelector('#copy-status');
    try {
      await navigator.clipboard.writeText(target.textContent.trim());
      button.textContent = '已复制';
      status.textContent = '命令已复制到剪贴板。';
    } catch {
      const range = document.createRange();
      range.selectNodeContents(target);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      button.textContent = '请手动复制';
      status.textContent = '自动复制不可用，已选中命令，请按 Ctrl+C 或使用系统复制操作。';
    }
    clearTimeout(feedbackTimer);
    feedbackTimer = setTimeout(() => { button.textContent = '复制'; }, 2500);
  });
});
