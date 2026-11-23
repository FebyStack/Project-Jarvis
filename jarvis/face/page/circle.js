// The circle of silk lines, from the 2026-11-17 mockup, drawn at 160 points. It only draws; the app decides.
(function () {
  var RED_ACTIVE = '#FF3B30', RED_RING = '#C2241B', RED_DEEP = '#6B1512', GREY = '#8F8784', DOT = '#FF6A5F';
  var c = document.getElementById('orb'), word = document.getElementById('word'), dpr = window.devicePixelRatio || 2;
  c.width = c.height = 160 * dpr;
  var x = c.getContext('2d'), R = 250, N = 150, p = [], t = 0;
  var e = 0.12, te = 0.12, amp = 0, gain = 0, level = 0, rot = 0, wob = 0, spin = 0;
  var mode = 'idle', ringOn = false, off = false, paused = false, last = 0, gen = 0;
  var E = { idle: 0.12, listen: 0.45, work: 1, talk: 0.85, muted: 0, off: 0 };
  var FPS = { idle: 10, listen: 30, work: 30, talk: 30, muted: 0, off: 0 };    // 0: one still frame, no loop
  var still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)');
  for (var i = 0; i < N; i++) p.push({ a: Math.random() * 6.283, r: Math.sqrt(Math.random()) * R, s: (Math.random() - .5) * .5, w: Math.random() * 6.283 });
  function rgb(hex) { return parseInt(hex.slice(1, 3), 16) + ',' + parseInt(hex.slice(3, 5), 16) + ',' + parseInt(hex.slice(5, 7), 16); }
  function rgba(hex, a) { return 'rgba(' + rgb(hex) + ',' + a + ')'; }
  function ease(rate, k) { return 1 - Math.pow(1 - rate, k); }
  function ring(base, rate, k1, k2, al, col) {
    x.beginPath();
    for (var k = 0; k <= 240; k++) {
      var th = k / 240 * 6.283, n = Math.sin(k * k1 + spin * rate) * Math.sin(k * k2 - t * 1.7) + 0.5 * Math.sin(k * 0.9 + spin * rate * 2.3);
      var rr = R * base + n * (3 + e * 14 + amp * 46);
      if (k) x.lineTo(Math.cos(th) * rr, Math.sin(th) * rr); else x.moveTo(Math.cos(th) * rr, Math.sin(th) * rr);
    }
    x.strokeStyle = rgba(col, al); x.stroke();
  }
  function draw(k) {                       // k: frames of 1/60 s since the last draw
    var line = off ? GREY : RED_ACTIVE;
    e += (te - e) * ease(0.022, k);
    rot += 0.016 * k * (0.25 + e * 1.6); wob += 0.016 * k * (0.8 + e * 6); spin += 0.016 * k * (1 + e * 3);
    var ta = off || mode === 'muted' ? 0 : level;
    gain += ((ta ? 1 : 0) - gain) * ease(0.03, k);
    amp += (ta * gain - amp) * ease(0.25, k);
    x.setTransform(1, 0, 0, 1, 0, 0); x.clearRect(0, 0, c.width, c.height);
    var s = c.width / 640; x.setTransform(s, 0, 0, s, c.width / 2, c.height / 2);
    var sc = 1 + amp * 0.07, q = [];
    for (var i = 0; i < N; i++) {
      var n = p[i], a = n.a + rot * n.s;
      var r = (n.r + Math.sin(wob + n.w) * (5 + e * 30) + Math.sin(t * 13 + n.w * 3) * e * 9) * sc;
      if (r > R + 18) r = R + 18;
      q.push([Math.cos(a) * r, Math.sin(a) * r]);
    }
    var th = 62 + e * 30, bend = 0.9 - e * 0.25, top = 0.25 + e * 0.45, B = 12, paths = []; x.lineWidth = 2;
    for (var b = 0; b < B; b++) paths.push(new Path2D());          // one stroke per opacity step, one fill for every dot
    for (var i = 0; i < N; i++) for (var j = i + 1; j < N; j++) {
      var dx = q[i][0] - q[j][0], dy = q[i][1] - q[j][1], d2 = dx * dx + dy * dy;
      if (d2 < th * th) {
        var g = paths[Math.min(B - 1, Math.floor((1 - Math.sqrt(d2) / th) * B))];
        g.moveTo(q[i][0], q[i][1]); g.quadraticCurveTo((q[i][0] + q[j][0]) / 2 * bend, (q[i][1] + q[j][1]) / 2 * bend, q[j][0], q[j][1]);
      }
    }
    for (var b = 0; b < B; b++) { x.strokeStyle = rgba(line, (top * (b + 0.5) / B).toFixed(3)); x.stroke(paths[b]); }
    var dots = new Path2D(), rd = 3 + e * 2;
    for (var m = 0; m < N; m++) { dots.moveTo(q[m][0] + rd, q[m][1]); dots.arc(q[m][0], q[m][1], rd, 0, 6.283); }
    x.fillStyle = off ? GREY : DOT; x.fill(dots);
    x.lineWidth = 2.4;
    ring(1.06, 3, 0.35, 0.11, (0.35 + e * 0.4).toFixed(2), line);
    ring(0.82, -2.2, 0.21, 0.07, (0.15 + e * 0.3).toFixed(2), line);
    ring(0.55, 3.8, 0.47, 0.13, (0.12 + e * 0.3).toFixed(2), line);
    ring(1.16, -1.6, 0.6, 0.05, (0.1 + e * 0.25).toFixed(2), line);
    if (ringOn) {                          // the outer ring: Jarvis wants something; it pulses inside the panel
      var pulse = 0.5 + 0.5 * Math.sin(t * 4);
      x.lineWidth = 9; x.strokeStyle = rgba(RED_DEEP, 0.5 + 0.4 * pulse);
      x.beginPath(); x.arc(0, 0, R * (1.22 + 0.015 * pulse), 0, 6.283); x.stroke();
      x.lineWidth = 3; x.strokeStyle = rgba(RED_RING, 0.6 + 0.4 * pulse); x.stroke();
    }
  }
  function frame(k) { t += 0.016 * k; draw(k); }
  function stillFrame() { e = te; amp = off || mode === 'muted' ? 0 : level; frame(1); }
  function start() {                       // restart drawing for the current mode; a new generation ends any old loop
    gen++; last = 0;
    if (paused) return;
    if (!FPS[mode] || (still && still.matches)) { stillFrame(); return; }
    loop(0, gen);
  }
  function loop(now, g) {
    if (g !== gen) return;
    requestAnimationFrame(function (n) { loop(n, g); });
    if (!last) last = now;
    var dt = now - last;
    if (dt < 1000 / FPS[mode] - 2) return;
    last = now; frame(Math.min(Math.max(dt, 1) / 16.667, 6));
  }
  window.face = {
    show: function (o) {
      var m = o.mode in E ? o.mode : mode, changed = m !== mode;
      mode = m; te = E[m]; off = m === 'off'; ringOn = !!o.ring; level = Math.min(1, Math.max(0, +o.level || 0));
      word.textContent = off && o.word ? String(o.word) : '';
      if (changed || (still && still.matches)) start();
    },
    pause: function (on) { paused = !!on; if (paused) gen++; else start(); }
  };
  start();
})();
