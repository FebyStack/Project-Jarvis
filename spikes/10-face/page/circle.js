// Probe copy of the 2026-11-17 mockup's circle, drawn at 160 points, with a frame-rate cap.
(function () {
  var c = document.getElementById('orb'), dpr = window.devicePixelRatio || 2;
  c.width = c.height = 160 * dpr;
  var x = c.getContext('2d'), R = 250, N = 150, p = [], t = 0;
  var e = 0.12, te = 0.12, st = 'idle', amp = 0, gain = 0, rot = 0, wob = 0, spin = 0;
  var E = { idle: 0.12, listen: 0.45, work: 1, talk: 0.85 }, fps = 30, last = 0, paused = false, batch = false;
  for (var i = 0; i < N; i++) p.push({ a: Math.random() * 6.283, r: Math.sqrt(Math.random()) * R, s: (Math.random() - .5) * .5, w: Math.random() * 6.283 });
  function ease(rate, k) { return 1 - Math.pow(1 - rate, k); }
  function ring(base, rate, k1, k2, al) {
    x.beginPath();
    for (var k = 0; k <= 240; k++) {
      var th = k / 240 * 6.283, n = Math.sin(k * k1 + spin * rate) * Math.sin(k * k2 - t * 1.7) + 0.5 * Math.sin(k * 0.9 + spin * rate * 2.3);
      var rr = R * base + n * (3 + e * 14 + amp * 46);
      if (k) x.lineTo(Math.cos(th) * rr, Math.sin(th) * rr); else x.moveTo(Math.cos(th) * rr, Math.sin(th) * rr);
    }
    x.strokeStyle = 'rgba(255,59,48,' + al + ')'; x.stroke();
  }
  function draw(k) {                       // k: frames of 1/60 s since the last draw
    e += (te - e) * ease(0.022, k);
    rot += 0.016 * k * (0.25 + e * 1.6); wob += 0.016 * k * (0.8 + e * 6); spin += 0.016 * k * (1 + e * 3);
    var ta = st === 'talk' ? Math.abs(Math.sin(t * 9)) * Math.abs(Math.sin(t * 2.3) + 0.4 * Math.sin(t * 5.1))
           : st === 'listen' ? 0.35 * Math.abs(Math.sin(t * 4.2)) : 0;
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
    var th = 62 + e * 30, bend = 0.9 - e * 0.25, top = 0.25 + e * 0.45; x.lineWidth = 2;
    if (batch) {                           // one stroke per opacity step instead of one per line
      var B = 12, paths = [];
      for (var b = 0; b < B; b++) paths.push(new Path2D());
      for (var i = 0; i < N; i++) for (var j = i + 1; j < N; j++) {
        var dx = q[i][0] - q[j][0], dy = q[i][1] - q[j][1], d2 = dx * dx + dy * dy;
        if (d2 < th * th) {
          var g = paths[Math.min(B - 1, Math.floor((1 - Math.sqrt(d2) / th) * B))];
          g.moveTo(q[i][0], q[i][1]); g.quadraticCurveTo((q[i][0] + q[j][0]) / 2 * bend, (q[i][1] + q[j][1]) / 2 * bend, q[j][0], q[j][1]);
        }
      }
      for (var b = 0; b < B; b++) { x.strokeStyle = 'rgba(255,59,48,' + (top * (b + 0.5) / B).toFixed(3) + ')'; x.stroke(paths[b]); }
      var dots = new Path2D(), rd = 3 + e * 2;
      for (var m = 0; m < N; m++) { dots.moveTo(q[m][0] + rd, q[m][1]); dots.arc(q[m][0], q[m][1], rd, 0, 6.283); }
      x.fillStyle = '#ff6a5f'; x.fill(dots);
    } else {
    for (var i = 0; i < N; i++) for (var j = i + 1; j < N; j++) {
      var dx = q[i][0] - q[j][0], dy = q[i][1] - q[j][1], d = Math.sqrt(dx * dx + dy * dy);
      if (d < th) {
        x.strokeStyle = 'rgba(255,59,48,' + (top * (1 - d / th)).toFixed(3) + ')';
        x.beginPath(); x.moveTo(q[i][0], q[i][1]);
        x.quadraticCurveTo((q[i][0] + q[j][0]) / 2 * bend, (q[i][1] + q[j][1]) / 2 * bend, q[j][0], q[j][1]); x.stroke();
      }
    }
    x.fillStyle = '#ff6a5f';
    for (var m = 0; m < N; m++) { x.beginPath(); x.arc(q[m][0], q[m][1], 3 + e * 2, 0, 6.283); x.fill(); }
    }
    x.lineWidth = 2.4;
    ring(1.06, 3, 0.35, 0.11, (0.35 + e * 0.4).toFixed(2));
    ring(0.82, -2.2, 0.21, 0.07, (0.15 + e * 0.3).toFixed(2));
    ring(0.55, 3.8, 0.47, 0.13, (0.12 + e * 0.3).toFixed(2));
    ring(1.16, -1.6, 0.6, 0.05, (0.1 + e * 0.25).toFixed(2));
  }
  var timer = false, gen = 0;
  function loop(now, g) {
    if (g !== gen) return;
    if (timer) { now = performance.now(); if (!paused) setTimeout(function () { loop(0, g); }, 1000 / fps); }
    else if (!paused) requestAnimationFrame(function (n) { loop(n, g); });
    if (!last) last = now;
    var dt = now - last;
    if (!timer && dt < 1000 / fps - 2) return;
    last = now; var k = Math.min(Math.max(dt, 1) / 16.667, 6); t += 0.016 * k; draw(k);
  }
  function post(m) { window.webkit.messageHandlers.face.postMessage(m); }
  window.face = {
    show: function (o) { if (o.mode in E) { st = o.mode; te = E[o.mode]; } if (o.fps) fps = o.fps; if ('batch' in o) batch = o.batch; if ('timer' in o && o.timer !== timer) { timer = o.timer; gen++; last = 0; loop(performance.now(), gen); } },
    pause: function (on) { paused = on; if (!on) { gen++; last = 0; loop(performance.now(), gen); } },
    echo: function (s) { post({ type: 'echo', s: s, len: s.length }); }
  };
  loop(performance.now(), gen);
})();
