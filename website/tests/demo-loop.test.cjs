const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

const source = readFileSync(join(__dirname, '../dist/app.js'), 'utf8');

// Exercise the real page script with controlled browser events and time.
function page({ reduced = false, observer = true, lang = 'zh-CN' } = {}) {
  let now = 0;
  let nextTimer = 0;
  const timers = new Map();
  class Element extends EventTarget {
    constructor() {
      super();
      this.disabled = false;
      this.writes = [];
      this.dataset = {};
      const classes = new Set();
      this.classList = {
        add: value => classes.add(value),
        remove: value => classes.delete(value),
        toggle: (value, enabled) => enabled ? classes.add(value) : classes.delete(value),
        contains: value => classes.has(value),
      };
    }
    set textContent(value) { this.text = value; this.writes.push(value); }
    get textContent() { return this.text; }
    setAttribute() {}
    click() { if (!this.disabled) this.dispatchEvent(new Event('click')); }
  }
  const selectors = ['#demo-text', '#demo-preedit', '#demo-status', '#demo-candidates', '#play-demo', '.demo-shell', '#motion-toggle'];
  const elements = Object.fromEntries(selectors.map(selector => [selector, new Element()]));
  const demo = elements['.demo-shell'];
  const text = elements['#demo-text'];
  text.textContent = '用 LiltKey，把想法写下来。';
  const document = Object.assign(new EventTarget(), {
    body: new Element(), documentElement: Object.assign(new Element(), { lang }), hidden: false,
    querySelector: selector => elements[selector],
    querySelectorAll: selector => selector === '.hero, .demo-shell, .guide-section' ? [demo] : [],
    getElementById: id => elements[`#${id}`],
  });
  const media = Object.assign(new EventTarget(), { matches: reduced });
  const observers = [];
  class Observer {
    constructor(callback) { this.callback = callback; this.targets = new Set(); observers.push(this); }
    observe(target) { this.targets.add(target); }
    unobserve(target) { this.targets.delete(target); }
  }
  const window = Object.assign(new EventTarget(), {
    matchMedia: () => media, IntersectionObserver: Observer, location: { hash: '' },
  });
  if (!observer) delete window.IntersectionObserver;
  vm.runInNewContext(source, {
    document, window, IntersectionObserver: Observer,
    localStorage: { getItem: () => null, setItem() {} },
    setTimeout(callback, delay) {
      const id = ++nextTimer;
      timers.set(id, { callback, at: now + delay });
      return id;
    },
    clearTimeout: id => timers.delete(id),
  });
  return {
    text, preedit: elements['#demo-preedit'], candidates: elements['#demo-candidates'],
    status: elements['#demo-status'], button: elements['#play-demo'], motion: elements['#motion-toggle'],
    motionLabel: () => elements['#motion-toggle'].title,
    cycles: () => text.writes.filter(value => value === '今天一起').length,
    advance(milliseconds) {
      const end = now + milliseconds;
      let guard = 0;
      while (timers.size) {
        const [id, timer] = [...timers].sort((a, b) => a[1].at - b[1].at)[0];
        if (timer.at > end) break;
        assert.ok(++guard < 2000, 'Timer loop must yield between frames');
        now = timer.at;
        timers.delete(id);
        timer.callback();
      }
      now = end;
    },
    visible(value) {
      for (const observer of observers) {
        if (observer.targets.has(demo)) observer.callback([
          { target: demo, isIntersecting: value, intersectionRatio: value ? 1 : 0 },
        ]);
      }
    },
    hidden(value) { document.hidden = value; document.dispatchEvent(new Event('visibilitychange')); },
    reduce(value) { media.matches = value; media.dispatchEvent(new Event('change')); },
  };
}

test('visible demo repeats after showing the completed sentence', () => {
  const p = page();
  p.visible(true);
  p.advance(15000);
  assert.ok(p.cycles() >= 2, 'The input demo should start multiple cycles');
  assert.ok(p.text.writes.filter(value => value === '用 LiltKey，把想法写下来。').length >= 3);
});

test('pinyin candidates commit before voice preedit uses the same native panel', () => {
  const p = page();
  p.visible(true);
  p.advance(1400);
  assert.equal(p.candidates.hidden, false);
  assert.equal(p.status.hidden, true);
  assert.match(p.preedit.textContent, /^[a-z ]+$/);
  p.advance(2000);
  assert.ok(p.text.writes.includes('今天一起写下想法。'));
  assert.equal(p.candidates.hidden, true);
  assert.equal(p.status.hidden, false);
  assert.ok(p.preedit.textContent.length > 0);
  p.advance(2500);
  assert.equal(p.preedit.textContent, '');
  assert.equal(p.text.textContent, '用 LiltKey，把想法写下来。');
  assert.equal(p.status.hidden, true, 'The native panel closes after committing');
});

test('pausing during pinyin cancels all remaining native input stages', () => {
  const p = page();
  p.visible(true);
  p.advance(1400);
  p.button.click();
  const writes = p.preedit.writes.length;
  p.advance(15000);
  assert.equal(p.preedit.writes.length, writes);
  assert.equal(p.preedit.textContent, '');
  assert.equal(p.candidates.hidden, true);
  assert.equal(p.status.hidden, true);
});

for (const time of [1400, 4000]) {
  test(`demo pause stops both typing and delayed replay at ${time} ms`, () => {
    const p = page();
    p.visible(true);
    p.advance(time);
    assert.equal(p.button.disabled, false, 'The pause button must remain usable while typing');
    p.button.click();
    const writes = p.text.writes.length;
    p.advance(15000);
    assert.equal(p.text.writes.length, writes, 'Paused text must remain still');
    const cycles = p.cycles();
    p.button.click();
    p.advance(15000);
    assert.ok(p.cycles() >= cycles + 2, 'Resuming should restore the loop');
  });
}

for (const event of ['hidden', 'offscreen']) {
  test(`${event} stops the loop and returning resumes it`, () => {
    const p = page();
    p.visible(true);
    p.advance(1400);
    if (event === 'hidden') p.hidden(true); else p.visible(false);
    const writes = p.text.writes.length;
    p.advance(15000);
    assert.equal(p.text.writes.length, writes);
    const cycles = p.cycles();
    if (event === 'hidden') p.hidden(false); else p.visible(true);
    p.advance(15000);
    assert.ok(p.cycles() >= cycles + 2);
  });
}

test('system reduced motion disables autoplay and can change during playback', () => {
  const p = page({ reduced: true });
  p.visible(true);
  p.advance(15000);
  assert.equal(p.cycles(), 0);
  p.reduce(false);
  p.advance(15000);
  assert.ok(p.cycles() >= 2);
  p.reduce(true);
  const writes = p.text.writes.length;
  p.advance(15000);
  assert.equal(p.text.writes.length, writes);
});

test('global motion toggle stops and resumes automatic cycles', () => {
  const p = page();
  p.visible(true);
  p.advance(1400);
  p.motion.click();
  const writes = p.text.writes.length;
  p.advance(15000);
  assert.equal(p.text.writes.length, writes);
  const cycles = p.cycles();
  p.motion.click();
  p.advance(15000);
  assert.ok(p.cycles() >= cycles + 2);
});

test('repeated visibility notifications do not schedule overlapping demos', () => {
  const p = page();
  for (let i = 0; i < 8; i++) { p.visible(true); p.hidden(false); }
  p.advance(1400);
  assert.equal(p.cycles(), 1);
});

test('local pause survives visibility and global motion changes', () => {
  const p = page();
  p.visible(true);
  p.advance(1400);
  p.button.click();
  const writes = p.text.writes.length;
  p.hidden(true);
  p.visible(false);
  p.motion.click();
  p.reduce(true);
  p.reduce(false);
  p.motion.click();
  p.hidden(false);
  p.visible(true);
  p.advance(15000);
  assert.equal(p.text.writes.length, writes, 'Only an explicit resume should undo a local pause');
  p.button.click();
  p.advance(15000);
  assert.ok(p.cycles() >= 3);
});

test('without visibility observation the button provides manual playback', () => {
  const p = page({ observer: false });
  p.advance(15000);
  assert.equal(p.cycles(), 0);
  assert.match(p.button.textContent, /播放/);
  p.button.click();
  p.advance(15000);
  assert.equal(p.cycles(), 1, 'One click should play one complete demo without offscreen autoplay');
  assert.match(p.button.textContent, /播放/);
  p.button.click();
  p.advance(15000);
  assert.equal(p.cycles(), 2);
});

test('English page keeps the pinyin stage and dictates an English sentence', () => {
  const p = page({ lang: 'en' });
  p.visible(true);
  p.advance(1400);
  assert.equal(p.preedit.textContent, 'xie xia xiang fa');
  p.advance(2000);
  assert.ok(p.text.writes.includes('今天一起写下想法。'));
  assert.equal(p.status.hidden, false);
  assert.equal(p.status.textContent, '语音输入：录音中，松开 Ctrl+Alt 结束', 'The native status is Chinese-only, so the demo must not translate it');
  assert.match(p.preedit.textContent, /^[\x20-\x7e]+$/, 'Voice preedit should be English');
  p.advance(4000);
  assert.equal(p.text.textContent, 'Write it down with LiltKey.');
  assert.ok(p.cycles() >= 1);
});

test('English page labels demo and motion controls in English', () => {
  const p = page({ lang: 'en' });
  p.visible(true);
  p.advance(1400);
  assert.match(p.button.textContent, /Pause demo/);
  assert.match(p.motionLabel(), /Pause animations/);
  p.button.click();
  assert.match(p.button.textContent, /Play demo/);
  p.motion.click();
  assert.match(p.button.textContent, /Animations paused/);
  assert.match(p.motionLabel(), /Resume animations/);
});

test('English page loops as reliably as the Chinese page', () => {
  const p = page({ lang: 'en' });
  p.visible(true);
  p.advance(15000);
  assert.ok(p.cycles() >= 2);
});
