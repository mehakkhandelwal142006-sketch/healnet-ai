"""
camera_bp.py  —  HealNet AI
────────────────────────────────────────────────────────────────
Camera-based Blood Pressure trend estimation using PPG technology.
Matches the architecture of camera_vitals.py exactly.

Usage (in app.py):
    from camera_bp import render_camera_bp_page
    render_camera_bp_page()

Requirements:  No extra pip installs needed.
               Uses browser WebRTC + vanilla JS for PPG processing.

Algorithm:
    1. Access rear camera + flashlight via getUserMedia
    2. Sample red/blue channels from 60×60 px centre crop at ~30 fps
    3. Band-pass filter 0.5–3.0 Hz to isolate pulse waveform
    4. Detect peaks → Heart Rate
    5. Measure systolic rise-time per pulse cycle → PTT proxy
    6. Map PTT to BP estimate via Bramwell-Hill approximation
    7. Display result + log history in-session

Disclaimer:
    Camera BP estimation reflects cardiovascular trends only.
    It is NOT a substitute for a validated blood pressure cuff.
    Do not use for diagnosis or medication decisions.
"""

import streamlit as st
import streamlit.components.v1 as components


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS  (same pattern as camera_vitals.py)
# ─────────────────────────────────────────────────────────────────────────────

def _sub_label(text: str):
    st.html(f'<div class="sub-label">{text}</div>')


def _info_card(title: str, body: str, color: str = "#3399ff"):
    st.html(f"""
    <div style="background:rgba(255,255,255,0.55);border:1px solid {color}33;
                border-left:4px solid {color};border-radius:12px;
                padding:14px 18px;margin-bottom:10px;
                backdrop-filter:blur(10px);">
      <div style="font-size:.80rem;font-weight:700;color:{color};
                  text-transform:uppercase;letter-spacing:.10em;margin-bottom:6px;">{title}</div>
      <div style="font-size:.84rem;color:#1e2d3d;line-height:1.65;">{body}</div>
    </div>""")


# ─────────────────────────────────────────────────────────────────────────────
#  CAMERA BP WIDGET  (pure HTML + JS, rendered inside Streamlit)
# ─────────────────────────────────────────────────────────────────────────────

BP_WIDGET_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Segoe UI', sans-serif;
    background: transparent;
    color: #0a2540;
    padding: 0;
  }

  .container {
    max-width: 680px;
    margin: 0 auto;
    padding: 12px;
  }

  /* ── Step badge ── */
  .steps {
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
    flex-wrap: wrap;
  }
  .step {
    padding: 5px 12px;
    border-radius: 20px;
    font-size: .72rem;
    font-weight: 700;
    letter-spacing: .06em;
    text-transform: uppercase;
    border: 1px solid #d0dde8;
    color: #8aa8c0;
    background: rgba(255,255,255,0.6);
    transition: all .3s;
  }
  .step.active {
    background: #cc4444;
    color: #fff;
    border-color: #cc4444;
  }
  .step.done {
    background: #00c878;
    color: #fff;
    border-color: #00c878;
  }

  /* ── Video / canvas area ── */
  .video-area {
    position: relative;
    width: 100%;
    max-width: 360px;
    margin: 0 auto 16px;
    border-radius: 18px;
    overflow: hidden;
    background: #111;
    aspect-ratio: 1 / 1;
    box-shadow: 0 8px 32px rgba(0,0,0,0.25);
  }
  video, #overlay-canvas {
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    object-fit: cover;
    border-radius: 18px;
  }
  #overlay-canvas { z-index: 2; }

  .guide-ring {
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    width: 120px; height: 120px;
    border-radius: 50%;
    border: 3px dashed rgba(255,255,255,0.50);
    z-index: 3;
    pointer-events: none;
    transition: border-color .4s;
  }
  .guide-ring.measuring { border-color: rgba(220,60,60,0.85); animation: pulse-ring 1s ease-in-out infinite; }
  .guide-ring.done      { border-color: rgba(0,200,120,0.90); }

  @keyframes pulse-ring {
    0%,100% { transform: translate(-50%,-50%) scale(1);    opacity:.9; }
    50%      { transform: translate(-50%,-50%) scale(1.08); opacity:.5; }
  }

  .status-pill {
    position: absolute;
    bottom: 14px; left: 50%;
    transform: translateX(-50%);
    background: rgba(0,0,0,0.62);
    color: #fff;
    font-size: .72rem;
    font-weight: 700;
    letter-spacing: .06em;
    padding: 4px 14px;
    border-radius: 20px;
    z-index: 4;
    white-space: nowrap;
    backdrop-filter: blur(8px);
  }

  /* ── Waveform canvas ── */
  #waveform {
    width: 100%;
    height: 80px;
    background: rgba(0,20,40,0.06);
    border-radius: 10px;
    margin-bottom: 16px;
    border: 1px solid rgba(200,80,80,0.20);
  }

  /* ── Result cards ── */
  .results {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 12px;
    margin-bottom: 16px;
  }
  .result-card {
    background: rgba(255,255,255,0.68);
    border: 1px solid rgba(200,100,100,0.25);
    border-radius: 14px;
    padding: 14px 16px;
    text-align: center;
    backdrop-filter: blur(10px);
    box-shadow: 0 4px 16px rgba(200,80,80,0.08);
  }
  .result-label {
    font-size: .65rem;
    font-weight: 700;
    color: #8a5858;
    text-transform: uppercase;
    letter-spacing: .14em;
    margin-bottom: 6px;
  }
  .result-value {
    font-size: 2.0rem;
    font-weight: 800;
    color: #0a2540;
    line-height: 1;
  }
  .result-unit {
    font-size: .72rem;
    color: #9a7878;
    margin-top: 3px;
  }
  .result-status {
    margin-top: 6px;
    font-size: .70rem;
    font-weight: 700;
    padding: 2px 10px;
    border-radius: 8px;
    display: inline-block;
  }
  .status-normal   { background: rgba(0,200,120,.14);   color: #006640; border: 1px solid rgba(0,200,120,.30); }
  .status-elevated { background: rgba(59,158,219,.14);  color: #003a80; border: 1px solid rgba(59,158,219,.28); }
  .status-warning  { background: rgba(220,130,0,.14);   color: #7a4000; border: 1px solid rgba(220,130,0,.30); }
  .status-danger   { background: rgba(220,40,60,.14);   color: #8a0020; border: 1px solid rgba(220,40,60,.30); }
  .status-unknown  { background: rgba(100,160,220,.14); color: #003a80; border: 1px solid rgba(100,160,220,.28); }

  /* ── Progress bar ── */
  .progress-wrap {
    background: rgba(200,80,80,0.10);
    border-radius: 8px;
    height: 8px;
    margin-bottom: 8px;
    overflow: hidden;
  }
  .progress-bar {
    height: 100%;
    background: linear-gradient(90deg, #cc4444, #ff8866);
    border-radius: 8px;
    transition: width .3s;
  }
  .progress-label {
    font-size: .72rem;
    color: #6a9abf;
    text-align: center;
    margin-bottom: 14px;
  }

  /* ── Context selector ── */
  .context-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 14px;
    align-items: center;
  }
  .context-row label {
    font-size: .72rem;
    font-weight: 700;
    color: #5a88b0;
    text-transform: uppercase;
    letter-spacing: .08em;
    white-space: nowrap;
  }
  .context-row select {
    flex: 1;
    min-width: 180px;
    padding: 6px 10px;
    border-radius: 8px;
    border: 1px solid rgba(100,160,220,0.35);
    background: rgba(255,255,255,0.75);
    font-size: .80rem;
    color: #0a2540;
    cursor: pointer;
  }

  /* ── Buttons ── */
  .btn-row { display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
  button.primary-btn, button.secondary-btn {
    flex: 1;
    min-width: 120px;
    padding: 10px 18px;
    border: none;
    border-radius: 11px;
    font-size: .80rem;
    font-weight: 700;
    cursor: pointer;
    transition: all .22s;
    letter-spacing: .04em;
  }
  button.primary-btn {
    background: linear-gradient(135deg, #cc4444, #992222);
    color: #fff;
    box-shadow: 0 3px 12px rgba(180,50,50,0.28);
  }
  button.primary-btn:hover  { background: linear-gradient(135deg, #dd5555, #bb3333); transform: translateY(-1px); }
  button.primary-btn:disabled { opacity: .45; cursor: not-allowed; transform: none; }
  button.secondary-btn {
    background: rgba(255,255,255,0.70);
    color: #1a3a5c;
    border: 1px solid rgba(100,160,220,0.35);
  }
  button.secondary-btn:hover { background: rgba(255,255,255,0.90); }

  /* ── Disclaimer banner ── */
  .disclaimer {
    background: rgba(255,248,210,0.80);
    border: 1px solid rgba(220,160,0,0.35);
    border-left: 4px solid #e0a000;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: .74rem;
    color: #7a5000;
    line-height: 1.6;
    margin-bottom: 14px;
  }

  /* ── Tip cards ── */
  .tip-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 14px; }
  .tip-card {
    background: rgba(255,255,255,0.55);
    border: 1px solid rgba(200,100,100,0.18);
    border-radius: 10px;
    padding: 10px 12px;
    font-size: .73rem;
    color: #6a3030;
    line-height: 1.55;
  }
  .tip-card strong { color: #0a2540; display: block; margin-bottom: 3px; }

  /* ── History table ── */
  .hist-table {
    width: 100%;
    border-collapse: collapse;
    font-size: .76rem;
    margin-top: 6px;
  }
  .hist-table th {
    background: rgba(200,80,80,0.10);
    color: #7a2a2a;
    font-weight: 700;
    text-transform: uppercase;
    font-size: .65rem;
    letter-spacing: .10em;
    padding: 7px 10px;
    text-align: left;
  }
  .hist-table td {
    padding: 7px 10px;
    border-bottom: 1px solid rgba(200,100,100,0.10);
    color: #1a3a5c;
  }
  .hist-table tr:last-child td { border-bottom: none; }
  .hist-table tr:hover td { background: rgba(255,100,100,0.04); }

  @media (max-width: 480px) {
    .results { grid-template-columns: 1fr; }
    .tip-grid { grid-template-columns: 1fr; }
    .result-value { font-size: 1.7rem; }
  }
</style>
</head>
<body>
<div class="container">

  <!-- Step indicator -->
  <div class="steps">
    <div class="step" id="step1">1 · Camera Access</div>
    <div class="step" id="step2">2 · Place Finger</div>
    <div class="step" id="step3">3 · Measuring</div>
    <div class="step" id="step4">4 · BP Result</div>
  </div>

  <!-- Disclaimer -->
  <div class="disclaimer">
    ⚠️ <strong>Wellness trend indicator only — not a medical device.</strong>
    Camera-based BP estimation uses PPG waveform analysis and cannot replace
    a validated blood pressure cuff. Do not use these readings for diagnosis
    or medication decisions. Consult a healthcare professional for clinical readings.
  </div>

  <!-- Context selector -->
  <div class="context-row">
    <label>Context</label>
    <select id="context-select">
      <option>Sitting (resting)</option>
      <option>Lying down</option>
      <option>Standing</option>
      <option>Before meal</option>
      <option>After meal</option>
      <option>After exercise</option>
      <option>Morning (just woke up)</option>
    </select>
  </div>

  <!-- Camera preview -->
  <div class="video-area">
    <video id="cam" autoplay playsinline muted></video>
    <canvas id="overlay-canvas"></canvas>
    <div class="guide-ring" id="guide-ring"></div>
    <div class="status-pill" id="status-pill">Press Start</div>
  </div>

  <!-- Torch status indicator -->
  <div id="torch-indicator" style="text-align:center;font-size:.75rem;font-weight:700;
       margin-bottom:10px;color:#aaa;letter-spacing:.06em;">
    🔦 Torch status will show after camera starts
  </div>

  <!-- Waveform -->
  <canvas id="waveform"></canvas>

  <!-- Progress -->
  <div class="progress-wrap"><div class="progress-bar" id="progress-bar" style="width:0%"></div></div>
  <div class="progress-label" id="progress-label">Ready — press Start to begin</div>

  <!-- Buttons -->
  <div class="btn-row">
    <button class="primary-btn"   id="start-btn"  onclick="startMeasurement()">&#9654; Start Measurement</button>
    <button class="secondary-btn" id="stop-btn"   onclick="stopMeasurement()" disabled>&#9632; Stop</button>
    <button class="secondary-btn" id="reset-btn"  onclick="resetMeasurement()">&#8635; Reset</button>
  </div>

  <!-- Results -->
  <div class="results" id="results" style="display:none;">
    <div class="result-card">
      <div class="result-label">Systolic</div>
      <div class="result-value" id="sys-value">&#8212;</div>
      <div class="result-unit">mmHg</div>
      <div class="result-status status-unknown" id="sys-status">Pending</div>
    </div>
    <div class="result-card">
      <div class="result-label">Diastolic</div>
      <div class="result-value" id="dia-value">&#8212;</div>
      <div class="result-unit">mmHg</div>
      <div class="result-status status-unknown" id="dia-status">Pending</div>
    </div>
    <div class="result-card">
      <div class="result-label">Heart Rate</div>
      <div class="result-value" id="hr-value">&#8212;</div>
      <div class="result-unit">bpm</div>
      <div class="result-status status-unknown" id="hr-status">Pending</div>
    </div>
  </div>

  <!-- Tips -->
  <div class="tip-grid">
    <div class="tip-card"><strong>On Mobile</strong>Use Chrome on Android for best torch support. Cover the rear lens fully with your fingertip — firmly but gently.</div>
    <div class="tip-card"><strong>No Torch?</strong>If torch does not activate, go to a bright room and press your fingertip tightly against the lens to block external light.</div>
    <div class="tip-card"><strong>Duration</strong>Measurement takes 30 seconds. Keep your finger on the camera the entire time — even small gaps reduce accuracy.</div>
    <div class="tip-card"><strong>Warmth Helps</strong>If your finger is cold, warm it up first — poor circulation weakens the PPG signal significantly.</div>
  </div>

  <!-- History -->
  <div id="history-section" style="display:none;">
    <div style="font-size:.72rem;font-weight:700;color:#8a5858;text-transform:uppercase;
                letter-spacing:.14em;margin-bottom:8px;">Session History</div>
    <div style="background:rgba(255,255,255,0.55);border:1px solid rgba(200,100,100,0.20);
                border-radius:12px;overflow:hidden;">
      <table class="hist-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Systolic (mmHg)</th>
            <th>Diastolic (mmHg)</th>
            <th>HR (bpm)</th>
            <th>Context</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody id="hist-body"></tbody>
      </table>
    </div>
  </div>

</div>

<script>
/* ======================================================
   BP-PPG signal processing engine
   Algorithm:
     1. Access rear camera + flashlight via getUserMedia
     2. Sample 60x60 px centre crop every ~33ms (30 fps)
     3. Average RED channel across crop -> raw PPG signal
     4. Band-pass filter 0.5-3.0 Hz (30-180 BPM range)
     5. Detect peaks -> Heart Rate (bpm)
     6. Measure systolic rise-time per cycle -> PTT proxy (ms)
     7. PTT -> BP via Bramwell-Hill: BP = A/PTT + B
   ====================================================== */

const SAMPLE_DURATION_S = 30;
const FPS               = 30;
const CROP_SIZE         = 100;  // larger crop improves signal when torch is weak

// PTT -> BP population-mean calibration coefficients
const SYS_A = 2800, SYS_B = 60;
const DIA_A = 1400, DIA_B = 40;

// State
let stream         = null;
let animFrame      = null;
let rawSignal      = [];
let filteredSignal = [];
let rSamples       = [];
let bSamples       = [];
let startTime      = null;
let measuring      = false;
let history        = [];
let torchOn        = false;
let fingerFrames   = 0;   // count frames where finger detected

// DOM refs
const video       = document.getElementById('cam');
const overlayC    = document.getElementById('overlay-canvas');
const waveC       = document.getElementById('waveform');
const guideRing   = document.getElementById('guide-ring');
const statusPill  = document.getElementById('status-pill');
const progressBar = document.getElementById('progress-bar');
const progressLbl = document.getElementById('progress-label');
const startBtn    = document.getElementById('start-btn');
const stopBtn     = document.getElementById('stop-btn');

const overlayCtx  = overlayC.getContext('2d');
const waveCtx     = waveC.getContext('2d');

// Camera helpers — 3-tier fallback for maximum mobile compatibility
async function getCamera() {
  // Tier 1: ideal mobile rear-cam + torch in constraints
  const tier1 = {
    video: {
      facingMode: { exact: 'environment' },
      width:  { ideal: 320 },
      height: { ideal: 320 },
      frameRate: { ideal: 30, min: 15 },
      advanced: [{ torch: true }],
    }
  };
  // Tier 2: rear cam, no torch in constraints (apply after)
  const tier2 = {
    video: {
      facingMode: { ideal: 'environment' },
      width:  { ideal: 320 },
      height: { ideal: 320 },
      frameRate: { ideal: 30 },
    }
  };
  // Tier 3: any camera (desktop fallback)
  const tier3 = { video: true };

  for (const constraints of [tier1, tier2, tier3]) {
    try {
      stream = await navigator.mediaDevices.getUserMedia(constraints);
      break;
    } catch(e) {
      stream = null;
    }
  }

  if (!stream) throw new Error('No camera available');

  // Try to enable torch via 3 methods
  const track = stream.getVideoTracks()[0];
  torchOn = false;
  // Method A: applyConstraints advanced
  try {
    await track.applyConstraints({ advanced: [{ torch: true }] });
    torchOn = true;
  } catch(_) {}
  // Method B: ImageCapture API (Android Chrome)
  if (!torchOn && typeof ImageCapture !== 'undefined') {
    try {
      const ic = new ImageCapture(track);
      const caps = await ic.getPhotoCapabilities();
      if (caps.fillLightMode && caps.fillLightMode.includes('flash')) {
        await ic.setOptions({ fillLightMode: 'flash' });
        torchOn = true;
      }
    } catch(_) {}
  }

  // Update torch indicator
  const tind = document.getElementById('torch-indicator');
  if (tind) tind.textContent = torchOn ? '🔦 Torch ON' : '💡 No torch — use bright light';
  if (tind) tind.style.color = torchOn ? '#00c878' : '#e0a000';

  video.srcObject = stream;
  await new Promise(r => { video.onloadedmetadata = r; });
  await video.play();
  overlayC.width  = video.videoWidth  || 320;
  overlayC.height = video.videoHeight || 320;
}

// Red-channel sampler
function sampleRed() {
  const w  = video.videoWidth  || 640;
  const h  = video.videoHeight || 640;
  const cx = Math.floor(w / 2);
  const cy = Math.floor(h / 2);
  const half = Math.floor(CROP_SIZE / 2);
  const tmp = document.createElement('canvas');
  tmp.width = CROP_SIZE; tmp.height = CROP_SIZE;
  const ctx = tmp.getContext('2d');
  ctx.drawImage(video, cx - half, cy - half, CROP_SIZE, CROP_SIZE, 0, 0, CROP_SIZE, CROP_SIZE);
  const px = ctx.getImageData(0, 0, CROP_SIZE, CROP_SIZE).data;
  let rSum = 0, bSum = 0;
  const total = CROP_SIZE * CROP_SIZE;
  for (let i = 0; i < px.length; i += 4) {
    rSum += px[i];
    bSum += px[i + 2];
  }
  return { r: rSum / total, b: bSum / total };
}

// Band-pass filter (moving-average difference, same as camera_vitals.py)
function bandPassFilter(signal) {
  if (signal.length < 6) return signal.slice();
  const slow = movingAvg(signal, Math.floor(FPS * 0.8));
  const fast = movingAvg(signal, Math.floor(FPS * 0.1));
  return fast.map((v, i) => v - slow[i]);
}

function movingAvg(arr, win) {
  win = Math.max(1, Math.min(win, arr.length));
  const out = new Array(arr.length).fill(0);
  let sum = 0;
  for (let i = 0; i < arr.length; i++) {
    sum += arr[i];
    if (i >= win) sum -= arr[i - win];
    out[i] = sum / Math.min(i + 1, win);
  }
  return out;
}

// Peak detector (same as camera_vitals.py)
function detectPeaks(signal) {
  if (signal.length < 5) return [];
  const m  = signal.reduce((a, b) => a + b, 0) / signal.length;
  const sd = Math.sqrt(signal.map(v => (v - m) ** 2).reduce((a, b) => a + b, 0) / signal.length);
  const thresh = m + 0.5 * sd;
  const minGap = Math.floor(FPS * 0.35);
  const peaks  = [];
  let lastPeak = -minGap;
  for (let i = 1; i < signal.length - 1; i++) {
    if (signal[i] > thresh &&
        signal[i] > signal[i - 1] &&
        signal[i] > signal[i + 1] &&
        (i - lastPeak) >= minGap) {
      peaks.push(i);
      lastPeak = i;
    }
  }
  return peaks;
}

// PTT estimation from PPG waveform
// PTT = systolic rise-time per cardiac cycle (ms)
// Stiffer arteries (higher BP) = shorter rise-time = shorter PTT
function estimatePTT(signal, peaks) {
  if (peaks.length < 3) return null;
  const riseTimes = [];
  for (let i = 1; i < peaks.length; i++) {
    const seg = signal.slice(peaks[i - 1], peaks[i]);
    if (seg.length < 3) continue;
    let minIdx = 0;
    for (let j = 1; j < seg.length; j++) {
      if (seg[j] < seg[minIdx]) minIdx = j;
    }
    let maxIdx = minIdx;
    for (let j = minIdx + 1; j < seg.length; j++) {
      if (seg[j] > seg[maxIdx]) maxIdx = j;
    }
    const riseMs = ((maxIdx - minIdx) / FPS) * 1000;
    if (riseMs > 50 && riseMs < 500) riseTimes.push(riseMs);
  }
  if (riseTimes.length === 0) return null;
  riseTimes.sort((a, b) => a - b);
  return riseTimes[Math.floor(riseTimes.length / 2)];
}

// PTT -> BP (Bramwell-Hill approximation)
function pttToBP(pttMs) {
  if (!pttMs || pttMs <= 0) return { sys: null, dia: null };
  let sys = Math.round(SYS_A / pttMs + SYS_B);
  let dia = Math.round(DIA_A / pttMs + DIA_B);
  sys = Math.max(70, Math.min(220, sys));
  dia = Math.max(40, Math.min(130, dia));
  return { sys, dia };
}

// Finger detection — adaptive threshold: with torch red >> blue; without torch, looser check
function fingerOnCamera(r, b) {
  if (torchOn) return r > 100 && r > b * 1.8;
  // Without torch: finger still blocks most light, red channel will be relatively elevated
  return r > 60 && r > b * 1.3;
}

// Waveform renderer
function drawWaveform() {
  const W = waveC.offsetWidth || 560;
  const H = waveC.offsetHeight || 80;
  waveC.width = W; waveC.height = H;
  waveCtx.clearRect(0, 0, W, H);
  const sig = filteredSignal.length >= 5 ? filteredSignal : rawSignal.slice();
  if (sig.length < 2) {
    waveCtx.fillStyle = 'rgba(200,80,80,0.25)';
    waveCtx.font = '12px sans-serif';
    waveCtx.fillText('Waveform will appear once signal is detected...', 14, H / 2 + 4);
    return;
  }
  const minV  = Math.min(...sig);
  const maxV  = Math.max(...sig);
  const range = maxV - minV || 1;
  const pad   = 10;
  const innerH = H - 2 * pad;
  const step   = W / (sig.length - 1);
  waveCtx.beginPath();
  waveCtx.strokeStyle = '#cc3333';
  waveCtx.lineWidth   = 2;
  waveCtx.shadowColor = 'rgba(200,50,50,0.40)';
  waveCtx.shadowBlur  = 6;
  sig.forEach((v, i) => {
    const x = i * step;
    const y = pad + innerH - ((v - minV) / range) * innerH;
    i === 0 ? waveCtx.moveTo(x, y) : waveCtx.lineTo(x, y);
  });
  waveCtx.stroke();
}

// Main capture loop
function captureLoop() {
  if (!measuring) return;
  const elapsed = (Date.now() - startTime) / 1000;
  const { r, b } = sampleRed();
  rawSignal.push(r);
  rSamples.push(r);
  bSamples.push(b);
  filteredSignal = bandPassFilter(rawSignal);
  drawWaveform();
  if (fingerOnCamera(r, b)) {
    fingerFrames++;
    guideRing.className    = 'guide-ring measuring';
    statusPill.textContent = 'Reading pulse...';
  } else {
    guideRing.className    = 'guide-ring';
    statusPill.textContent = torchOn ? 'Place finger on camera' : 'Cover lens firmly — no torch';
  }
  const pct = Math.min(100, (elapsed / SAMPLE_DURATION_S) * 100);
  progressBar.style.width = pct + '%';
  progressLbl.textContent = elapsed < SAMPLE_DURATION_S
    ? 'Measuring... ' + Math.ceil(SAMPLE_DURATION_S - elapsed) + 's remaining'
    : 'Processing...';
  setStep(3);
  if (elapsed >= SAMPLE_DURATION_S) { finishMeasurement(); return; }
  animFrame = requestAnimationFrame(captureLoop);
}

// Finish & compute
function finishMeasurement() {
  measuring = false;
  cancelAnimationFrame(animFrame);

  // Signal quality gate: finger should have been detected for >40% of frames
  const totalFrames  = rawSignal.length;
  const fingerRatio  = fingerFrames / (totalFrames || 1);
  const qualityOk    = fingerRatio > 0.40;

  const peaks     = detectPeaks(filteredSignal);
  const durationS = rawSignal.length / FPS;
  const bpm       = Math.round((peaks.length / durationS) * 60);
  const validBPM  = (bpm >= 40 && bpm <= 200) ? bpm : null;
  const pttMs     = estimatePTT(filteredSignal, peaks);
  const { sys, dia } = pttToBP(pttMs);

  if (!qualityOk) {
    statusPill.textContent  = 'Poor signal — retry';
    progressLbl.textContent = 'Finger not detected for enough time (' + Math.round(fingerRatio*100) + '%). Please retry and keep fingertip firmly over the lens.';
    guideRing.className     = 'guide-ring';
    startBtn.disabled = false;
    stopBtn.disabled  = true;
    setStep(1);
    return;
  }

  displayResult(sys, dia, validBPM);
  recordHistory(sys, dia, validBPM);
  statusPill.textContent  = 'Done';
  guideRing.className     = 'guide-ring done';
  progressLbl.textContent = 'Measurement complete (finger detected ' + Math.round(fingerRatio*100) + '% of time)';
  progressBar.style.width = '100%';
  startBtn.disabled = false;
  stopBtn.disabled  = true;
  setStep(4);
}

// Classification helpers
function bpClass(sys, dia) {
  if (!sys || !dia)            return 'status-unknown';
  if (sys >= 180 || dia >= 120) return 'status-danger';
  if (sys >= 130 || dia >= 80)  return 'status-warning';
  if (sys >= 120)               return 'status-elevated';
  if (sys < 90  || dia < 60)   return 'status-warning';
  return 'status-normal';
}

function bpLabel(sys, dia) {
  if (!sys || !dia)             return 'Insufficient signal';
  if (sys >= 180 || dia >= 120) return 'Hypertensive crisis';
  if (sys >= 140 || dia >= 90)  return 'Stage 2 hypertension';
  if (sys >= 130 || dia >= 80)  return 'Stage 1 hypertension';
  if (sys >= 120)               return 'Elevated';
  if (sys < 90  || dia < 60)   return 'Low (hypotension)';
  return 'Normal';
}

function hrClass(bpm) {
  if (!bpm)       return ['--', 'status-unknown', 'Insufficient signal'];
  if (bpm < 60)   return [bpm,  'status-warning', 'Low (bradycardia)'];
  if (bpm <= 100) return [bpm,  'status-normal',  'Normal'];
  if (bpm <= 120) return [bpm,  'status-warning', 'Elevated'];
  return                 [bpm,  'status-danger',  'High (tachycardia)'];
}

// Display result
function displayResult(sys, dia, bpm) {
  document.getElementById('results').style.display = 'grid';
  const cls = bpClass(sys, dia);
  const lbl = bpLabel(sys, dia);
  document.getElementById('sys-value').textContent  = sys  || '--';
  document.getElementById('sys-status').textContent = lbl;
  document.getElementById('sys-status').className   = 'result-status ' + cls;
  document.getElementById('dia-value').textContent  = dia  || '--';
  document.getElementById('dia-status').textContent = lbl;
  document.getElementById('dia-status').className   = 'result-status ' + cls;
  const [hv, hc, hl] = hrClass(bpm);
  document.getElementById('hr-value').textContent  = hv;
  document.getElementById('hr-status').textContent = hl;
  document.getElementById('hr-status').className   = 'result-status ' + hc;
}

// History
function recordHistory(sys, dia, bpm) {
  const now     = new Date().toLocaleTimeString();
  const context = document.getElementById('context-select').value;
  history.unshift({
    time: now, sys: sys || '?', dia: dia || '?',
    hr: bpm || '?', context: context, status: bpLabel(sys, dia)
  });
  if (history.length > 10) history.pop();
  renderHistory();
}

function renderHistory() {
  document.getElementById('history-section').style.display = 'block';
  document.getElementById('hist-body').innerHTML = history.map(h =>
    '<tr><td>' + h.time + '</td><td>' + h.sys + '</td><td>' + h.dia +
    '</td><td>' + h.hr + '</td><td>' + h.context + '</td><td>' + h.status + '</td></tr>'
  ).join('');
}

// Step indicator
function setStep(n) {
  for (let i = 1; i <= 4; i++) {
    const el = document.getElementById('step' + i);
    el.className = i < n ? 'step done' : (i === n ? 'step active' : 'step');
  }
}

// Public controls
async function startMeasurement() {
  try {
    if (!stream) await getCamera();
    rawSignal = []; filteredSignal = []; rSamples = []; bSamples = [];
    fingerFrames = 0;
    measuring = true; startTime = Date.now();
    startBtn.disabled = true; stopBtn.disabled = false;
    progressBar.style.width = '0%';
    document.getElementById('results').style.display = 'none';
    guideRing.className    = 'guide-ring';
    statusPill.textContent = 'Place finger on camera';
    setStep(2);
    captureLoop();
  } catch(e) {
    statusPill.textContent  = 'Camera error';
    progressLbl.textContent = 'Camera access denied. Please allow camera permission.';
    console.error(e);
  }
}

function stopMeasurement() {
  measuring = false;
  cancelAnimationFrame(animFrame);
  statusPill.textContent  = 'Stopped';
  progressLbl.textContent = 'Measurement stopped.';
  startBtn.disabled = false; stopBtn.disabled = true;
  guideRing.className = 'guide-ring';
  setStep(1);
}

function resetMeasurement() {
  stopMeasurement();
  rawSignal = []; filteredSignal = []; rSamples = []; bSamples = [];
  fingerFrames = 0;
  document.getElementById('results').style.display = 'none';
  progressBar.style.width   = '0%';
  progressLbl.textContent   = 'Ready -- press Start to begin';
  statusPill.textContent    = 'Press Start';
  drawWaveform();
  setStep(1);
}

drawWaveform();
</script>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN PAGE RENDERER
# ─────────────────────────────────────────────────────────────────────────────

def render_camera_bp_page():
    """
    Call this function from app.py inside the `elif page == "BP Camera":` block.
    """

    st.html('<div class="page-header"><h1>🩺 BP Camera — Blood Pressure Monitor</h1></div>')

    # ── How it works section ──────────────────────────────────────────────────
    with st.expander("ℹ️ How does this work?", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            _info_card(
                "PPG + PTT Technology",
                """<b>Photoplethysmography (PPG)</b> captures your pulse waveform via
                the camera — the same principle as Camera Vitals.<br><br>
                Blood pressure is estimated from the <b>Pulse Transit Time (PTT)</b>:
                the systolic rise-time within each heartbeat. Stiffer vessels
                (higher BP) produce shorter rise-times. We map PTT to systolic /
                diastolic estimates using the Bramwell-Hill approximation.""",
                "#cc4444"
            )
        with col2:
            _info_card(
                "Accuracy & Limitations",
                """✅ <b>Heart Rate</b> — Reliable, same as Camera Vitals.<br>
                ⚠️ <b>Blood Pressure</b> — Trend indicator only; roughly ±10–20 mmHg vs cuff.<br>
                ❌ <b>Clinical use</b> — Not a certified medical device. Always use
                a validated cuff for clinical readings.<br><br>
                <i>For best results: sit still for 2 min before measuring,
                cover the rear lens fully, and enable the torch.</i>""",
                "#e0a000"
            )

    st.markdown("---")

    # ── Instructions ─────────────────────────────────────────────────────────
    _sub_label("📋 Quick Instructions")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info("**Step 1**\n\nClick **▶ Start Measurement** and allow camera access when prompted.")
    with c2:
        st.info("**Step 2**\n\nCover the **rear camera lens** completely with your fingertip.\nThe flashlight will turn on automatically.")
    with c3:
        st.info("**Step 3**\n\nKeep your finger **still** for 30 seconds.\nYour BP trend will appear automatically.")

    st.markdown("---")

    # ── Mobile iframe camera permission patch ────────────────────────────────
    # Streamlit renders components.html inside an iframe. Mobile browsers require
    # the iframe to explicitly carry allow="camera" — inject it via a MutationObserver.
    st.html("""
    <script>
      (function patchIframes() {
        function allow() {
          document.querySelectorAll('iframe').forEach(function(f) {
            var cur = f.getAttribute('allow') || '';
            if (!cur.includes('camera')) {
              f.setAttribute('allow', cur + ' camera *; microphone *');
            }
          });
        }
        allow();
        var obs = new MutationObserver(allow);
        obs.observe(document.body, { childList: true, subtree: true });
      })();
    </script>
    """)

    # ── BP Widget ────────────────────────────────────────────────────────────
    _sub_label("🎥 Live Measurement")
    components.html(BP_WIDGET_HTML, height=940, scrolling=False)

    st.markdown("---")

    # ── Clinical notes ────────────────────────────────────────────────────────
    _sub_label("📌 BP Reference Ranges")
    n1, n2 = st.columns(2)
    with n1:
        st.markdown("""
**Blood Pressure Categories (AHA):**
- 🟢 Normal: < 120 / < 80 mmHg
- 🔵 Elevated: 120–129 / < 80 mmHg
- 🟡 Stage 1 Hypertension: 130–139 / 80–89 mmHg
- 🟠 Stage 2 Hypertension: ≥ 140 / ≥ 90 mmHg
- 🔴 Hypertensive Crisis: ≥ 180 / ≥ 120 mmHg
- 🟡 Low BP (Hypotension): < 90 / < 60 mmHg
        """)
    with n2:
        st.markdown("""
**Tips for accurate readings:**
- Sit quietly for at least 2 minutes before measuring
- Rest your arm at heart level
- Avoid caffeine or exercise 30 min before
- Take 2–3 readings and note the average
- Measure at the same time each day for trend tracking

*Camera values are estimates — always confirm with a cuff.*
        """)