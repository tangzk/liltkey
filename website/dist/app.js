const demoText = document.querySelector('#demo-text');
const demoPreedit = document.querySelector('#demo-preedit');
const demoCandidates = document.querySelector('#demo-candidates');
const demoStatus = document.querySelector('#demo-status');
const demoButton = document.querySelector('#play-demo');
const demoShell = document.querySelector('.demo-shell');
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const motionToggle = document.querySelector('#motion-toggle');
const canObserveVisibility = 'IntersectionObserver' in window;
const runningReveals = new Map();
const strings = {
  zh: {
    motionPaused: '动效已暂停', playDemo: '播放演示 ▶', pauseDemo: '暂停演示 Ⅱ',
    committed: '用 LiltKey，把想法写下来。', voicePreedit: '用 LiltKey 把想法写下来',
    reducedMotion: '系统已开启减少动态效果', resumeMotion: '开启动效', pauseMotion: '暂停页面动效',
    copied: '已复制', copiedStatus: '命令已复制到剪贴板。',
    copyManually: '请手动复制', copyManuallyStatus: '自动复制不可用，已选中命令，请按 Ctrl+C 或使用系统复制操作。',
    copy: '复制',
  },
  en: {
    motionPaused: 'Animations paused', playDemo: 'Play demo ▶', pauseDemo: 'Pause demo Ⅱ',
    committed: 'Write it down with LiltKey.', voicePreedit: 'Write it down with LiltKey',
    reducedMotion: 'Reduced motion is on in your system settings', resumeMotion: 'Resume animations', pauseMotion: 'Pause animations',
    copied: 'Copied', copiedStatus: 'Command copied to clipboard.',
    copyManually: 'Copy manually', copyManuallyStatus: 'Automatic copy is unavailable. The command is selected; press Ctrl+C to copy it.',
    copy: 'Copy',
  },
};
const t = String(document.documentElement.lang).startsWith('en') ? strings.en : strings.zh;
let manuallyPaused = false;
try { manuallyPaused = localStorage.getItem('liltkey-motion') === 'paused'; } catch {}
let demoTimer;
let autoDemoTimer;
let demoVisible = false;
let demoPaused = !canObserveVisibility;
let demoRunning = false;

const motionAllowed = () => !reducedMotion.matches && !manuallyPaused;

function showInputPhase(phase) {
  demoShell.dataset.phase = phase;
  demoCandidates.hidden = phase !== 'pinyin';
  demoStatus.hidden = phase !== 'voice';
}

function clearAutoDemo() {
  clearTimeout(autoDemoTimer);
  autoDemoTimer = undefined;
}

function updateDemoControl() {
  const paused = demoPaused || !motionAllowed();
  demoShell.classList.toggle('demo-paused', paused);
  demoButton.disabled = !motionAllowed();
  demoButton.textContent = !motionAllowed() ? t.motionPaused : demoPaused ? t.playDemo : t.pauseDemo;
}

function finishDemo(repeat = true) {
  clearTimeout(demoTimer);
  clearAutoDemo();
  demoRunning = false;
  if (!canObserveVisibility) demoPaused = true;
  demoText.textContent = t.committed;
  demoPreedit.textContent = '';
  showInputPhase('committed');
  demoShell.classList.remove('playing');
  updateDemoControl();
  if (repeat) scheduleAutoDemo(1800);
}

function stopDemo() {
  clearAutoDemo();
  if (demoRunning) finishDemo(false);
  updateDemoControl();
}

function startDemo() {
  clearAutoDemo();
  clearTimeout(demoTimer);
  demoStatus.setAttribute('aria-live', 'off');
  if (!motionAllowed() || demoPaused || document.hidden) return;
  demoRunning = true;
  updateDemoControl();
  demoShell.classList.add('playing');
  demoText.textContent = '今天一起';
  demoPreedit.textContent = 'xie xia xiang fa';
  showInputPhase('pinyin');
  demoTimer = setTimeout(() => {
    demoText.textContent = '今天一起写下想法。';
    demoPreedit.textContent = '';
    showInputPhase('committed');
    demoTimer = setTimeout(startVoiceDemo, 500);
  }, 1600);
}

function startVoiceDemo() {
  demoText.textContent = '';
  // The native plugin status is Chinese-only; the English page shows it as-is.
  demoStatus.textContent = '语音输入：录音中，松开 Ctrl+Alt 结束';
  showInputPhase('voice');
  const characters = Array.from(t.voicePreedit);
  let frame = 0;
  function tick() {
    demoPreedit.textContent = characters.slice(0, ++frame).join('');
    demoTimer = setTimeout(frame < characters.length ? tick : finishDemo, frame < characters.length ? 95 : 850);
  }
  tick();
}

function scheduleAutoDemo(delay = 1000) {
  if (!demoVisible || demoPaused || demoRunning || autoDemoTimer !== undefined || !motionAllowed() || document.hidden) return;
  autoDemoTimer = setTimeout(() => {
    autoDemoTimer = undefined;
    if (demoVisible) startDemo();
  }, delay);
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
  const label = reducedMotion.matches ? t.reducedMotion : paused ? t.resumeMotion : t.pauseMotion;
  motionToggle.setAttribute('aria-label', label);
  motionToggle.title = label;
  if (paused) {
    cancelReveals();
    stopDemo();
  } else {
    scheduleAutoDemo();
  }
  updateDemoControl();
}

demoButton.addEventListener('click', () => {
  demoPaused = !demoPaused;
  if (demoPaused) stopDemo();
  else startDemo();
});
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
    cancelReveals();
    stopDemo();
  } else {
    scheduleAutoDemo();
  }
}
document.addEventListener('visibilitychange', updatePageVisibility);
updatePageVisibility();

function currentAnchor() {
  try { return document.getElementById(decodeURIComponent(window.location.hash.slice(1))); } catch { return null; }
}

if (canObserveVisibility) {
  const scenes = new IntersectionObserver(entries => {
    for (const entry of entries) {
      const inView = entry.isIntersecting && entry.intersectionRatio >= .15;
      entry.target.classList.toggle('is-in-view', inView);
      if (entry.target === demoShell) {
        demoVisible = inView;
        if (demoVisible) scheduleAutoDemo();
        else stopDemo();
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
      button.textContent = t.copied;
      status.textContent = t.copiedStatus;
    } catch {
      const range = document.createRange();
      range.selectNodeContents(target);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      button.textContent = t.copyManually;
      status.textContent = t.copyManuallyStatus;
    }
    clearTimeout(feedbackTimer);
    feedbackTimer = setTimeout(() => { button.textContent = t.copy; }, 2500);
  });
});
