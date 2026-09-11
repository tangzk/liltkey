const demoText = document.querySelector('#demo-text');
const demoStatus = document.querySelector('#demo-status');
const demoButton = document.querySelector('#play-demo');
const demoShell = document.querySelector('.demo-shell');
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const motionToggle = document.querySelector('#motion-toggle');
const runningReveals = new Map();
let manuallyPaused = false;
try { manuallyPaused = localStorage.getItem('liltkey-motion') === 'paused'; } catch {}
let demoTimer;
let autoDemoTimer;
let demoVisible = false;
let demoHasStarted = false;
let demoRunning = false;

const motionAllowed = () => !reducedMotion.matches && !manuallyPaused;

function clearAutoDemo() {
  clearTimeout(autoDemoTimer);
  autoDemoTimer = undefined;
}

function finishDemo() {
  clearTimeout(demoTimer);
  clearAutoDemo();
  demoRunning = false;
  demoText.textContent = '用 LiltKey，把想法写下来。';
  demoStatus.textContent = '停顿后，补充标点并提交。';
  demoButton.innerHTML = '再看一次 <span aria-hidden="true">↻</span>';
  demoButton.disabled = false;
  demoShell.classList.remove('playing');
}

function startDemo(manual = false) {
  clearAutoDemo();
  clearTimeout(demoTimer);
  demoHasStarted = true;
  demoStatus.setAttribute('aria-live', manual ? 'polite' : 'off');
  if (!motionAllowed()) {
    finishDemo();
    return;
  }
  demoRunning = true;
  demoButton.disabled = true;
  demoButton.textContent = '演示中…';
  demoStatus.textContent = '正在显示临时文字…';
  demoShell.classList.add('playing');
  demoText.textContent = '';
  const characters = Array.from('用 LiltKey 把想法写下来');
  let frame = 0;
  function tick() {
    demoText.textContent = characters.slice(0, ++frame).join('');
    demoTimer = setTimeout(frame < characters.length ? tick : finishDemo, frame < characters.length ? 95 : 850);
  }
  tick();
}

function scheduleAutoDemo() {
  if (!demoVisible || demoHasStarted || autoDemoTimer !== undefined || !motionAllowed() || document.hidden) return;
  autoDemoTimer = setTimeout(() => startDemo(), 1000);
}

function cancelReveals() {
  for (const animation of runningReveals.values()) animation.cancel();
  runningReveals.clear();
}

function applyMotionPreference() {
  const paused = !motionAllowed();
  document.documentElement.classList.toggle('motion-paused', paused);
  document.body.classList.toggle('motion-paused', paused);
  motionToggle.disabled = reducedMotion.matches;
  const label = reducedMotion.matches ? '系统已开启减少动态效果' : paused ? '开启动效' : '暂停页面动效';
  motionToggle.setAttribute('aria-label', label);
  motionToggle.title = label;
  if (paused) {
    cancelReveals();
    clearAutoDemo();
    if (demoRunning) finishDemo();
  } else {
    scheduleAutoDemo();
  }
}

demoButton.disabled = false;
demoButton.addEventListener('click', () => startDemo(true));
motionToggle.hidden = false;
motionToggle.addEventListener('click', () => {
  manuallyPaused = !manuallyPaused;
  try { localStorage.setItem('liltkey-motion', manuallyPaused ? 'paused' : 'full'); } catch {}
  applyMotionPreference();
});
reducedMotion.addEventListener('change', applyMotionPreference);
applyMotionPreference();
document.body.classList.add('motion-ready');

function updatePageVisibility() {
  document.body.classList.toggle('page-hidden', document.hidden);
  if (document.hidden) {
    clearAutoDemo();
    cancelReveals();
    if (demoRunning) finishDemo();
  } else {
    scheduleAutoDemo();
  }
}
document.addEventListener('visibilitychange', updatePageVisibility);
updatePageVisibility();

function currentAnchor() {
  try { return document.getElementById(decodeURIComponent(window.location.hash.slice(1))); } catch { return null; }
}

if ('IntersectionObserver' in window) {
  const scenes = new IntersectionObserver(entries => {
    for (const entry of entries) {
      const inView = entry.isIntersecting && entry.intersectionRatio >= .15;
      entry.target.classList.toggle('is-in-view', inView);
      if (entry.target === demoShell) {
        demoVisible = inView;
        if (demoVisible) scheduleAutoDemo();
        else {
          clearAutoDemo();
          if (demoRunning) finishDemo();
        }
      }
    }
  }, { threshold: .15 });
  document.querySelectorAll('.hero, .demo-shell, .guide-section').forEach(node => scenes.observe(node));

  const reveals = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (!entry.isIntersecting || entry.intersectionRatio < .08) continue;
      const node = entry.target;
      reveals.unobserve(node);
      const anchor = currentAnchor();
      if (!motionAllowed() || document.hidden || !node.animate || node.contains(document.activeElement) ||
          (anchor && (anchor.contains(node) || node.contains(anchor)))) continue;
      // Only the animation hides content; cancelling or unsupported APIs leave it visible.
      const animation = node.animate([
        { opacity: 0, transform: 'translateY(18px)' },
        { opacity: 1, transform: 'translateY(0)' }
      ], { duration: 600, delay: Number(node.dataset.revealDelay), easing: 'cubic-bezier(.2,.7,.3,1)', fill: 'backwards' });
      runningReveals.set(node, animation);
      animation.finished.then(() => runningReveals.delete(node), () => runningReveals.delete(node));
    }
  }, { threshold: .08 });
  const groups = ['.site-header', '.hero-copy > *', '.demo-shell', '.principles > span',
    '.section-heading', '.feature', '.guide-layout > div:first-child', '.steps li',
    '.installation', '.faq-section > div:first-child', '.faq-list details', '.footer'];
  for (const selector of groups) {
    document.querySelectorAll(selector).forEach((node, index) => {
      node.dataset.revealDelay = String(Math.min(index, 3) * 80);
      reveals.observe(node);
    });
  }
}

window.addEventListener('hashchange', cancelReveals);
document.addEventListener('focusin', event => {
  for (const [node, animation] of runningReveals) {
    if (node.contains(event.target)) {
      animation.cancel();
      runningReveals.delete(node);
    }
  }
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
