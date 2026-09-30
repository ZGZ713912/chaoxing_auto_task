// ==UserScript==
// @name         超星学习通 · 防暂停保活开关
// @namespace    local.noir.chaoxing.keepawake
// @version      1.0.0
// @description  屏蔽失焦/切屏导致的视频暂停，自动继续播放；右下角小圆钮一键开关服务（ON 生效 / OFF 完全还原）
// @author       noir
// @match        *://*.chaoxing.com/*
// @match        *://*.edu.cn/*
// @match        *://*.nbdlib.cn/*
// @match        *://*.hnsyu.net/*
// @match        *://*.gdhkmooc.com/*
// @run-at       document-start
// @grant        none
// ==/UserScript==

(function () {
  'use strict';

  var STORE_KEY = 'cx_keep_awake_enabled';
  var DEFAULT_ON = true;

  function readEnabled() {
    try {
      var v = window.localStorage.getItem(STORE_KEY);
      if (v === null) return DEFAULT_ON;
      return v === '1';
    } catch (e) {
      return DEFAULT_ON;
    }
  }

  var enabled = readEnabled();

  // ---- 备份真实实现 ----
  var realHidden = Object.getOwnPropertyDescriptor(Document.prototype, 'hidden');
  var realVisState = Object.getOwnPropertyDescriptor(Document.prototype, 'visibilityState');
  var realHasFocus = Document.prototype.hasFocus;
  var realAdd = EventTarget.prototype.addEventListener;

  var BLOCKED = {
    visibilitychange: 1,
    webkitvisibilitychange: 1,
    mozvisibilitychange: 1,
    blur: 1,
    focusout: 1,
    pagehide: 1,
    freeze: 1,
    mouseleave: 1
  };

  function realHiddenValue(self) {
    return realHidden && realHidden.get ? realHidden.get.call(self) : false;
  }
  function realVisStateValue(self) {
    return realVisState && realVisState.get ? realVisState.get.call(self) : 'visible';
  }

  // ---- 1. 伪可见性：始终 visible ----
  function defineSpoof(proto, name, getter) {
    try {
      Object.defineProperty(proto, name, { configurable: true, get: getter });
    } catch (e) {}
  }
  defineSpoof(Document.prototype, 'hidden', function () {
    return enabled ? false : realHiddenValue(this);
  });
  defineSpoof(Document.prototype, 'visibilityState', function () {
    return enabled ? 'visible' : realVisStateValue(this);
  });
  defineSpoof(Document.prototype, 'webkitHidden', function () {
    return enabled ? false : realHiddenValue(this);
  });
  defineSpoof(Document.prototype, 'webkitVisibilityState', function () {
    return enabled ? 'visible' : realVisStateValue(this);
  });
  defineSpoof(Document.prototype, 'mozHidden', function () {
    return enabled ? false : realHiddenValue(this);
  });
  defineSpoof(Document.prototype, 'mozVisibilityState', function () {
    return enabled ? 'visible' : realVisStateValue(this);
  });

  // ---- 2. 伪焦点：hasFocus 始终 true ----
  try {
    Document.prototype.hasFocus = function () {
      return enabled ? true : realHasFocus.call(this);
    };
  } catch (e) {}

  // ---- 3. 拦截监听注册：丢弃会导致暂停的事件 ----
  EventTarget.prototype.addEventListener = function (type, listener, options) {
    try {
      if (
        enabled &&
        BLOCKED[String(type).toLowerCase()] &&
        (this === document ||
          this === window ||
          this === document.documentElement ||
          this === document.body)
      ) {
        return;
      }
    } catch (e) {}
    return realAdd.call(this, type, listener, options);
  };

  // ---- 4. 封掉 on* 赋值（开启时吞掉，关闭时还原）----
  function lockProp(target, prop) {
    var real = null;
    var holder = target;
    try {
      while (holder && !real) {
        real = Object.getOwnPropertyDescriptor(holder, prop);
        if (!real) holder = Object.getPrototypeOf(holder);
      }
    } catch (e) {}
    var val = real && 'value' in real ? real.value : null;
    try {
      Object.defineProperty(target, prop, {
        configurable: true,
        enumerable: false,
        get: function () {
          if (enabled) return null;
          if (real && real.get) return real.get.call(target);
          return val;
        },
        set: function (v) {
          if (enabled) return;
          if (real && real.set) {
            real.set.call(target, v);
          } else {
            val = v;
          }
        }
      });
    } catch (e) {}
  }
  ['onblur', 'onfocusout', 'onvisibilitychange', 'onwebkitvisibilitychange', 'onmouseleave'].forEach(
    function (p) {
      lockProp(window, p);
    }
  );
  ['onvisibilitychange', 'onwebkitvisibilitychange', 'onmouseleave'].forEach(function (p) {
    lockProp(document, p);
  });

  // ---- 5. 状态同步（同源 iframe 共享 localStorage；storage 事件 + 轮询兜底）----
  window.addEventListener('storage', function (e) {
    if (e && e.key === STORE_KEY) enabled = readEnabled();
  });

  // ---- 6. 自动恢复播放 ----
  var RESUME_RE = /^(继续播放|继续学习|点击继续|继续观看|继续|播放)$/;

  function visible(el) {
    try {
      if (!el || !el.getBoundingClientRect) return false;
      var r = el.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) return false;
      var s = (el.ownerDocument.defaultView || window).getComputedStyle(el);
      return s.display !== 'none' && s.visibility !== 'hidden' && parseFloat(s.opacity) > 0.01;
    } catch (e) {
      return false;
    }
  }

  function findResumeMask() {
    try {
      var nodes = document.querySelectorAll('a,button,div,span,p,i');
      for (var i = 0; i < nodes.length; i++) {
        var el = nodes[i];
        var t = (el.textContent || '').trim();
        if (t.length > 12 || !RESUME_RE.test(t)) continue;
        if (el.children.length > 1) continue;
        if (!visible(el)) continue;
        return el;
      }
    } catch (e) {}
    return null;
  }

  function resumeVideo(video) {
    try {
      var p = video.play();
      if (p && p.catch) p.catch(function () {});
    } catch (e) {}
    try {
      var doc = video.ownerDocument;
      var view = doc.defaultView || window;
      var r = video.getBoundingClientRect();
      var x = r.left + r.width / 2;
      var y = r.top + r.height / 2;
      var opts = {
        bubbles: true,
        cancelable: true,
        view: view,
        clientX: x,
        clientY: y,
        screenX: (view.screenX || 0) + x,
        screenY: (view.screenY || 0) + y
      };
      ['mousemove', 'mousedown', 'mouseup', 'click', 'pointerdown', 'pointerup'].forEach(function (type) {
        try {
          var Ctor = type.indexOf('pointer') === 0 && view.PointerEvent ? view.PointerEvent : view.MouseEvent;
          video.dispatchEvent(new Ctor(type, opts));
        } catch (e) {}
      });
    } catch (e) {}
  }

  function tick() {
    var s = readEnabled();
    if (s !== enabled) enabled = s;
    if (!enabled) return;

    var paused = [];
    try {
      var videos = document.querySelectorAll('video');
      for (var i = 0; i < videos.length; i++) {
        if (videos[i].paused && !videos[i].ended && videos[i].readyState > 0) paused.push(videos[i]);
      }
    } catch (e) {}

    if (!paused.length) return;

    var mask = findResumeMask();
    if (mask) {
      try {
        mask.click();
      } catch (e) {}
      try {
        mask.dispatchEvent(
          new MouseEvent('click', { bubbles: true, cancelable: true, view: window })
        );
      } catch (e) {}
    }

    // 仅在“窗口确实失焦”或“出现继续播放遮罩”时恢复，避免和手动暂停/随机暂停打架
    var lostFocus = !realHasFocus.call(document);
    if (!lostFocus && !mask) return;

    for (var j = 0; j < paused.length; j++) resumeVideo(paused[j]);
  }

  if (window.top) setInterval(tick, 1500);

  // ---- 7. 右下角开关按钮（仅顶层页面）----
  var isTop = false;
  try {
    isTop = window.top === window;
  } catch (e) {
    isTop = false;
  }

  function mountToggle() {
    if (!isTop || !document.body) return false;
    if (document.getElementById('cx-kaw-toggle')) return true;

    var POS_KEY = 'cx_keep_awake_pos';
    var pos = null;
    try {
      pos = JSON.parse(window.localStorage.getItem(POS_KEY) || 'null');
    } catch (e) {}

    var btn = document.createElement('div');
    btn.id = 'cx-kaw-toggle';
    btn.title = '超星防暂停保活：点击开关';
    btn.style.cssText = [
      'position:fixed',
      'z-index:2147483647',
      'width:56px',
      'height:56px',
      'border-radius:50%',
      'display:flex',
      'align-items:center',
      'justify-content:center',
      'flex-direction:column',
      'font:12px/1.15 -apple-system,"Microsoft YaHei",sans-serif',
      'color:#fff',
      'cursor:pointer',
      'user-select:none',
      'box-shadow:0 3px 10px rgba(0,0,0,.35)',
      'border:2px solid rgba(255,255,255,.65)',
      'opacity:.9',
      'text-align:center'
    ].join(';');
    btn.style.right = '16px';
    btn.style.bottom = '96px';
    if (pos && typeof pos.left === 'number') {
      btn.style.left = pos.left + 'px';
      btn.style.top = pos.top + 'px';
      btn.style.right = 'auto';
      btn.style.bottom = 'auto';
    }

    function paint() {
      btn.style.background = enabled ? '#22a06b' : '#6b7280';
      btn.innerHTML = enabled ? '保活<br>ON' : '保活<br>OFF';
    }
    paint();

    var dragging = false;
    var moved = false;
    var sx = 0;
    var sy = 0;
    var ox = 0;
    var oy = 0;

    btn.addEventListener('mousedown', function (e) {
      dragging = true;
      moved = false;
      sx = e.clientX;
      sy = e.clientY;
      var r = btn.getBoundingClientRect();
      ox = r.left;
      oy = r.top;
      btn.style.right = 'auto';
      btn.style.bottom = 'auto';
      e.preventDefault();
    });

    window.addEventListener('mousemove', function (e) {
      if (!dragging) return;
      var dx = e.clientX - sx;
      var dy = e.clientY - sy;
      if (Math.abs(dx) + Math.abs(dy) > 4) moved = true;
      if (!moved) return;
      var left = Math.max(0, Math.min(window.innerWidth - 56, ox + dx));
      var top = Math.max(0, Math.min(window.innerHeight - 56, oy + dy));
      btn.style.left = left + 'px';
      btn.style.top = top + 'px';
    });

    window.addEventListener('mouseup', function () {
      if (!dragging) return;
      dragging = false;
      if (moved) {
        try {
          window.localStorage.setItem(
            POS_KEY,
            JSON.stringify({ left: parseInt(btn.style.left, 10), top: parseInt(btn.style.top, 10) })
          );
        } catch (e) {}
      } else {
        enabled = !enabled;
        try {
          window.localStorage.setItem(STORE_KEY, enabled ? '1' : '0');
        } catch (e) {}
        paint();
      }
    });

    document.body.appendChild(btn);
    return true;
  }

  function waitBody() {
    if (mountToggle()) return;
    var mo = new MutationObserver(function () {
      if (mountToggle()) mo.disconnect();
    });
    try {
      mo.observe(document.documentElement || document, { childList: true, subtree: true });
    } catch (e) {}
    var n = 0;
    var t = setInterval(function () {
      if (mountToggle() || ++n > 60) clearInterval(t);
    }, 500);
  }

  waitBody();
})();
