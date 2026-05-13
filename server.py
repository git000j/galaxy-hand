from flask import Flask, render_template_string
import socket

app = Flask(__name__)

HTML = '''
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>Galaxy Hand</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #000; overflow: hidden; }
  canvas { display: block; }
  #video { display: none; }
  #hud {
    position: fixed; top: 10px; left: 10px;
    color: #a070ff; font-family: monospace; font-size: 13px;
    pointer-events: none; z-index: 10;
    text-shadow: 0 0 8px #a070ff;
  }
  #gesture {
    position: fixed; bottom: 20px; left: 50%;
    transform: translateX(-50%);
    color: #40ffcc; font-family: monospace; font-size: 15px;
    pointer-events: none; z-index: 10;
    text-shadow: 0 0 10px #40ffcc;
    background: rgba(0,0,0,0.4);
    padding: 6px 16px; border-radius: 20px;
  }
  #startBtn {
    position: fixed; top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    background: linear-gradient(135deg, #6020c0, #40ffcc);
    color: white; border: none; padding: 20px 40px;
    font-size: 20px; font-family: monospace;
    border-radius: 30px; cursor: pointer;
    box-shadow: 0 0 30px #6020c080;
    z-index: 100;
  }
</style>
</head>
<body>
<canvas id="galaxy"></canvas>
<video id="video" playsinline></video>
<div id="hud">✦ GALAXY HAND CONTROLLER ✦</div>
<div id="gesture">Show your hand to the camera</div>
<button id="startBtn" onclick="startApp()">✦ TAP TO START ✦</button>

<script src="https://cdn.jsdelivr.net/npm/@mediapipe/hands/hands.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils/camera_utils.js"></script>

<script>
const canvas = document.getElementById('galaxy');
const ctx = canvas.getContext('2d');
const video = document.getElementById('video');
const gestureEl = document.getElementById('gesture');

canvas.width = window.innerWidth;
canvas.height = window.innerHeight;
window.addEventListener('resize', () => {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
});

// ── PARTICLES ──
const NUM_PARTICLES = 600;
const particles = [];

class Particle {
  constructor() { this.reset(); }
  reset() {
    const angle = Math.random() * Math.PI * 2;
    const r = 60 + Math.random() * 280;
    this.cx = canvas.width / 2;
    this.cy = canvas.height / 2;
    this.angle = angle;
    this.orbitR = r;
    this.orbitSpeed = (0.002 + Math.random() * 0.006) * (Math.random() < 0.5 ? 1 : -1);
    this.x = this.cx + Math.cos(angle) * r;
    this.y = this.cy + Math.sin(angle) * r;
    this.vx = 0; this.vy = 0;
    this.size = 0.8 + Math.random() * 2.5;
    this.hue = 200 + Math.random() * 160;
    this.alpha = 0.4 + Math.random() * 0.6;
  }
  update(pullX, pullY, explode, spinBoost) {
    this.cx = canvas.width / 2;
    this.cy = canvas.height / 2;
    this.angle += this.orbitSpeed + spinBoost * 0.008;
    const tx = this.cx + Math.cos(this.angle) * this.orbitR;
    const ty = this.cy + Math.sin(this.angle) * this.orbitR;
    this.x += (tx - this.x) * 0.04;
    this.y += (ty - this.y) * 0.04;

    if (pullX !== null) {
      const dx = pullX - this.x;
      const dy = pullY - this.y;
      const dist = Math.hypot(dx, dy) + 1;
      const force = Math.min(4000 / (dist * dist), 2.5);
      this.vx += (dx / dist) * force;
      this.vy += (dy / dist) * force;
    }
    if (explode) {
      this.vx += (Math.random() - 0.5) * 12;
      this.vy += (Math.random() - 0.5) * 12;
    }
    this.x += this.vx; this.y += this.vy;
    this.vx *= 0.88; this.vy *= 0.88;

    if (this.x < 0) this.x = canvas.width;
    if (this.x > canvas.width) this.x = 0;
    if (this.y < 0) this.y = canvas.height;
    if (this.y > canvas.height) this.y = 0;
  }
  draw() {
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
    ctx.fillStyle = `hsla(${this.hue}, 90%, 70%, ${this.alpha})`;
    ctx.fill();
  }
}

for (let i = 0; i < NUM_PARTICLES; i++) particles.push(new Particle());

// ── SHAPES ──
const SHAPE_TYPES = ['triangle','square','hexagon','star','ring'];
const shapes = Array.from({length: 6}, () => ({
  cx: 100 + Math.random() * (window.innerWidth - 200),
  cy: 100 + Math.random() * (window.innerHeight - 200),
  type: SHAPE_TYPES[Math.floor(Math.random() * SHAPE_TYPES.length)],
  r: 30 + Math.random() * 50,
  angle: 0,
  rotSpeed: (Math.random() - 0.5) * 0.03,
  hue: Math.random() * 360,
}));

function polyPoints(n, cx, cy, r, offset) {
  const pts = [];
  for (let i = 0; i < n; i++) {
    const a = offset + (2 * Math.PI * i / n);
    pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]);
  }
  return pts;
}

function drawShape(sh, spinBoost) {
  sh.angle += sh.rotSpeed + spinBoost * 0.004;
  ctx.strokeStyle = `hsla(${sh.hue}, 90%, 70%, 0.7)`;
  ctx.lineWidth = 1.5;
  ctx.shadowColor = `hsla(${sh.hue}, 90%, 70%, 0.8)`;
  ctx.shadowBlur = 10;
  ctx.beginPath();
  const {cx, cy, r, angle, type} = sh;

  if (type === 'triangle') {
    const p = polyPoints(3, cx, cy, r, angle);
    ctx.moveTo(p[0][0], p[0][1]);
    p.slice(1).forEach(pt => ctx.lineTo(pt[0], pt[1]));
    ctx.closePath();
  } else if (type === 'square') {
    const p = polyPoints(4, cx, cy, r, angle + Math.PI/4);
    ctx.moveTo(p[0][0], p[0][1]);
    p.slice(1).forEach(pt => ctx.lineTo(pt[0], pt[1]));
    ctx.closePath();
  } else if (type === 'hexagon') {
    const p = polyPoints(6, cx, cy, r, angle);
    ctx.moveTo(p[0][0], p[0][1]);
    p.slice(1).forEach(pt => ctx.lineTo(pt[0], pt[1]));
    ctx.closePath();
  } else if (type === 'star') {
    const outer = polyPoints(5, cx, cy, r, angle);
    const inner = polyPoints(5, cx, cy, r * 0.4, angle + Math.PI/5);
    ctx.moveTo(outer[0][0], outer[0][1]);
    for (let i = 0; i < 5; i++) {
      ctx.lineTo(inner[i][0], inner[i][1]);
      ctx.lineTo(outer[(i+1)%5][0], outer[(i+1)%5][1]);
    }
    ctx.closePath();
  } else if (type === 'ring') {
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(cx, cy, r * 0.5, 0, Math.PI * 2);
  }
  ctx.stroke();
  ctx.shadowBlur = 0;
}

// ── HAND STATE ──
let handState = {
  landmarks: [],
  pinch: false,
  spread: false,
  fist: false,
  fingersUp: 0,
  palm: null,
};
let explodeTimer = 0;
let spinBoost = 0;
const trail = [];

// ── MEDIAPIPE HANDS ──
function startApp() {
  document.getElementById('startBtn').style.display = 'none';

  const hands = new Hands({locateFile: f =>
    `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${f}`
  });
  hands.setOptions({
    modelComplexity: 0,
    minDetectionConfidence: 0.6,
    minTrackingConfidence: 0.5,
    maxNumHands: 1,
  });

  hands.onResults(onResults);

  navigator.mediaDevices.getUserMedia({
    video: { facingMode: 'user', width: 320, height: 240 }
  }).then(stream => {
    video.srcObject = stream;
    video.play();
    const camera = new Camera(video, {
      onFrame: async () => { await hands.send({image: video}); },
      width: 320, height: 240,
    });
    camera.start();
  }).catch(err => {
    gestureEl.textContent = 'Camera error: ' + err.message;
  });
}

function dist(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function onResults(results) {
  if (!results.multiHandLandmarks || results.multiHandLandmarks.length === 0) {
    handState.landmarks = [];
    handState.palm = null;
    handState.pinch = false;
    handState.spread = false;
    handState.fist = false;
    handState.fingersUp = 0;
    return;
  }

  const lm = results.multiHandLandmarks[0];
  const W = canvas.width, H = canvas.height;

  handState.landmarks = lm.map(p => ({
    x: p.x * W, y: p.y * H
  }));

  const baseIds = [0,1,5,9,13,17];
  const px = baseIds.reduce((s,i) => s + lm[i].x, 0) / 6 * W;
  const py = baseIds.reduce((s,i) => s + lm[i].y, 0) / 6 * H;
  handState.palm = {x: px, y: py};

  handState.pinch = dist(lm[4], lm[8]) < 0.07;

  const palmWidth = dist(lm[5], lm[17]);
  handState.spread = palmWidth > 0.35;

  const tips =    [8, 12, 16, 20];
  const knuckles= [6, 10, 14, 18];
  handState.fingersUp = tips.filter((t,i) => lm[t].y < lm[knuckles[i]].y).length;
  handState.fist = handState.fingersUp === 0;
}

// ── CONNECTIONS ──
const CONNECTIONS = [
  [0,1],[1,2],[2,3],[3,4],
  [0,5],[5,6],[6,7],[7,8],
  [5,9],[9,10],[10,11],[11,12],
  [9,13],[13,14],[14,15],[15,16],
  [13,17],[17,18],[18,19],[19,20],
  [0,17]
];

// ── BACKGROUND STARS ──
const bgStars = Array.from({length: 150}, () => ({
  x: Math.random() * window.innerWidth,
  y: Math.random() * window.innerHeight,
  r: Math.random() < 0.8 ? 1 : 2,
  b: 0.2 + Math.random() * 0.8,
}));

// ── MAIN LOOP ──
function loop() {
  requestAnimationFrame(loop);

  const W = canvas.width, H = canvas.height;
  const {landmarks, pinch, spread, fist, fingersUp, palm} = handState;

  if (fist && explodeTimer === 0) explodeTimer = 10;
  if (spread) spinBoost = Math.min(spinBoost + 0.3, 8);
  else spinBoost = Math.max(spinBoost - 0.15, 0);

  const explodeNow = explodeTimer > 0;
  if (explodeTimer > 0) explodeTimer--;

  const pullX = palm ? palm.x : null;
  const pullY = palm ? palm.y : null;

  if (palm) {
    trail.push({x: palm.x, y: palm.y});
    if (trail.length > 25) trail.shift();
  }

  // Background
  ctx.fillStyle = 'rgba(3, 3, 18, 0.18)';
  ctx.fillRect(0, 0, W, H);

  // BG stars
  bgStars.forEach(s => {
    ctx.beginPath();
    ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(180,180,220,${s.b * 0.5})`;
    ctx.fill();
  });

  // Nebula glow
  if (palm) {
    const g = ctx.createRadialGradient(palm.x, palm.y, 0, palm.x, palm.y, 200);
    g.addColorStop(0, 'rgba(80,30,160,0.12)');
    g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
  }

  // Particles
  particles.forEach(p => {
    p.update(pullX, pullY, explodeNow, spinBoost);
    p.draw();
  });

  // Shapes
  shapes.forEach(sh => {
    if (pinch && palm) {
      const dx = palm.x - sh.cx;
      const dy = palm.y - sh.cy;
      const d = Math.hypot(dx, dy) + 1;
      sh.cx += dx / d * 2.5;
      sh.cy += dy / d * 2.5;
    }
    drawShape(sh, spinBoost);
  });

  // Trail
  for (let i = 1; i < trail.length; i++) {
    const a = i / trail.length;
    ctx.beginPath();
    ctx.moveTo(trail[i-1].x, trail[i-1].y);
    ctx.lineTo(trail[i].x, trail[i].y);
    ctx.strokeStyle = `rgba(${Math.floor(a*255)}, 100, 220, ${a * 0.7})`;
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  // Hand skeleton
  if (landmarks.length > 0) {
    CONNECTIONS.forEach(([a, b]) => {
      ctx.beginPath();
      ctx.moveTo(landmarks[a].x, landmarks[a].y);
      ctx.lineTo(landmarks[b].x, landmarks[b].y);
      ctx.strokeStyle = 'rgba(0, 200, 180, 0.7)';
      ctx.lineWidth = 2;
      ctx.stroke();
    });
    landmarks.forEach((lm, i) => {
      const isTip = [4,8,12,16,20].includes(i);
      ctx.beginPath();
      ctx.arc(lm.x, lm.y, isTip ? 7 : 4, 0, Math.PI * 2);
      ctx.fillStyle = isTip ? '#ff5050' : '#50ffc8';
      ctx.fill();
      ctx.strokeStyle = 'white';
      ctx.lineWidth = 1;
      ctx.stroke();
    });
  }

  // Gesture HUD
  let gesture = '· show your hand ·';
  if (pinch)          gesture = '🤌 PINCH — pulling shapes';
  else if (fist)      gesture = '✊ FIST — galaxy explodes!';
  else if (spread)    gesture = '✋ SPREAD — spinning galaxy';
  else if (fingersUp === 1) gesture = '☝️ POINT — attracting particles';
  else if (fingersUp >= 4)  gesture = '🖐 OPEN — free orbit';
  gestureEl.textContent = gesture;
}

loop();
</script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML)

if __name__ == '__main__':
    # Get local IP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    print("=" * 50)
    print(f"  Open on your phone: http://{ip}:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)
