"""
camera_vitals.py  —  HealNet AI
────────────────────────────────────────────────────────────────
Camera-based Heart Rate & SpO₂ estimation using PPG technology.
Works on both desktop and mobile browsers.

Usage (in app.py):
    from camera_vitals import render_camera_vitals_page
    render_camera_vitals_page()

Requirements:  No extra pip installs needed.
               Uses browser WebRTC + vanilla JS for PPG processing.
"""

import streamlit as st
import streamlit.components.v1 as components


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
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
#  CAMERA PPG WIDGET  (pure HTML + JS, rendered inside Streamlit)
# ─────────────────────────────────────────────────────────────────────────────

PPG_WIDGET_HTML = """
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

  /* ── Layout ── */
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
    background: #3399ff;
    color: #fff;
    border-color: #3399ff;
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

  /* Finger placement guide ring */
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
  .guide-ring.finger-on  { border-color: rgba(0,245,150,0.80); }
  .guide-ring.measuring  { border-color: rgba(255,80,80,0.80); animation: pulse-ring 1s ease-in-out infinite; }

  @keyframes pulse-ring {
    0%,100% { transform: translate(-50%,-50%) scale(1);   opacity:.9; }
    50%      { transform: translate(-50%,-50%) scale(1.08); opacity:.5; }
  }

  /* Status pill overlay */
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
    border: 1px solid rgba(100,160,220,0.22);
  }

  /* ── Result cards ── */
  .results {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 16px;
  }
  .result-card {
    background: rgba(255,255,255,0.68);
    border: 1px solid rgba(100,160,220,0.30);
    border-radius: 14px;
    padding: 14px 16px;
    text-align: center;
    backdrop-filter: blur(10px);
    box-shadow: 0 4px 16px rgba(100,160,220,0.10);
  }
  .result-label {
    font-size: .65rem;
    font-weight: 700;
    color: #5a88b0;
    text-transform: uppercase;
    letter-spacing: .14em;
    margin-bottom: 6px;
  }
  .result-value {
    font-size: 2.4rem;
    font-weight: 800;
    color: #0a2540;
    line-height: 1;
  }
  .result-unit  {
    font-size: .72rem;
    color: #8ab0cc;
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
  .status-normal   { background: rgba(0,200,120,.14); color: #006640; border: 1px solid rgba(0,200,120,.30); }
  .status-warning  { background: rgba(220,130,0,.14);  color: #7a4000; border: 1px solid rgba(220,130,0,.30); }
  .status-danger   { background: rgba(220,40,60,.14);  color: #8a0020; border: 1px solid rgba(220,40,60,.30); }
  .status-unknown  { background: rgba(100,160,220,.14); color: #003a80; border: 1px solid rgba(100,160,220,.28); }

  /* ── Progress bar ── */
  .progress-wrap {
    background: rgba(100,160,220,0.12);
    border-radius: 8px;
    height: 8px;
    margin-bottom: 8px;
    overflow: hidden;
  }
  .progress-bar {
    height: 100%;
    background: linear-gradient(90deg, #3399ff, #00c878);
    border-radius: 8px;
    transition: width .3s;
  }
  .progress-label {
    font-size: .72rem;
    color: #6a9abf;
    text-align: center;
    margin-bottom: 14px;
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
    background: linear-gradient(135deg, #3399ff, #1166dd);
    color: #fff;
    box-shadow: 0 3px 12px rgba(30,100,220,0.25);
  }
  button.primary-btn:hover  { background: linear-gradient(135deg, #55aaff, #2277ee); transform: translateY(-1px); }
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
    border: 1px solid rgba(100,160,220,0.22);
    border-radius: 10px;
    padding: 10px 12px;
    font-size: .73rem;
    color: #2d5a8e;
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
    background: rgba(100,160,220,0.12);
    color: #2d5a8e;
    font-weight: 700;
    text-transform: uppercase;
    font-size: .65rem;
    letter-spacing: .10em;
    padding: 7px 10px;
    text-align: left;
  }
  .hist-table td {
    padding: 7px 10px;
    border-bottom: 1px solid rgba(100,160,220,0.12);
    color: #1a3a5c;
  }
  .hist-table tr:last-child td { border-bottom: none; }
  .hist-table tr:hover td { background: rgba(100,170,255,0.06); }

  /* Responsive */
  @media (max-width: 420px) {
    .results { grid-template-columns: 1fr; }
    .tip-grid { grid-template-columns: 1fr; }
    .result-value { font-size: 1.9rem; }
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
    <div class="step" id="step4">4 · Result</div>
  </div>

  <!-- Disclaimer -->
  <div class="disclaimer">
    ⚠️ <strong>For informational purposes only.</strong>
    This is a PPG-based estimation — not a certified medical device.
    Consult a doctor for clinical readings. BP shown is an experimental estimate.
  </div>

  <!-- Camera preview -->
  <div class="video-area">
    <video id="cam" autoplay playsinline muted></video>
    <canvas id="overlay-canvas"></canvas>
    <div class="guide-ring" id="guide-ring"></div>
    <div class="status-pill" id="status-pill">Press Start</div>
  </div>

  <!-- Waveform -->
  <canvas id="waveform"></canvas>

  <!-- Progress -->
  <div class="progress-wrap"><div class="progress-bar" id="progress-bar" style="width:0%"></div></div>
  <div class="progress-label" id="progress-label">Ready — press Start to begin</div>

  <!-- Buttons -->
  <div class="btn-row">
    <button class="primary-btn"   id="start-btn"  onclick="startMeasurement()">▶ Start Measurement</button>
    <button class="secondary-btn" id="stop-btn"   onclick="stopMeasurement()" disabled>⏹ Stop</button>
    <button class="secondary-btn" id="reset-btn"  onclick="resetMeasurement()">↺ Reset</button>
  </div>

  <!-- Results -->
  <div class="results" id="results" style="display:none;">
    <div class="result-card">
      <div class="result-label">❤️ Heart Rate</div>
      <div class="result-value" id="hr-value">—</div>
      <div class="result-unit">beats per minute</div>
      <div class="result-status status-unknown" id="hr-status">Pending</div>
    </div>
    <div class="result-card">
      <div class="result-label">🫁 SpO₂ (Estimated)</div>
      <div class="result-value" id="spo2-value">—</div>
      <div class="result-unit">% saturation</div>
      <div class="result-status status-unknown" id="spo2-status">Estimated</div>
    </div>
  </div>

  <!-- Tips -->
  <div class="tip-grid">
    <div class="tip-card"><strong>📱 On Mobile</strong>Use the rear camera. Cover it fully with your fingertip — gently, don't press too hard.</div>
    <div class="tip-card"><strong>💡 Keep Still</strong>Rest your hand on a table. Movement causes noise in the signal and reduces accuracy.</div>
    <div class="tip-card"><strong>⏱ Duration</strong>Measurement takes ~20 seconds. Keep your finger on the camera until the result appears.</div>
    <div class="tip-card"><strong>🌡️ Warmth Helps</strong>If your finger is cold, warm it up first — poor circulation affects signal quality.</div>
  </div>

  <!-- History -->
  <div id="history-section" style="display:none;">
    <div style="font-size:.72rem;font-weight:700;color:#5a88b0;text-transform:uppercase;
                letter-spacing:.14em;margin-bottom:8px;">📋 Measurement History</div>
    <div style="background:rgba(255,255,255,0.55);border:1px solid rgba(100,160,220,0.22);
                border-radius:12px;overflow:hidden;">
      <table class="hist-table">
        <thead>
          <tr><th>Time</th><th>Heart Rate (bpm)</th><th>SpO₂ (%)</th><th>Status</th></tr>
        </thead>
        <tbody id="hist-body"></tbody>
      </table>
    </div>
  </div>

</div>

<script>
/* ══════════════════════════════════════════════════════════════
   PPG (Photoplethysmography) signal processing engine
   Algorithm:
     1. Access rear camera + flashlight via getUserMedia
     2. Sample a 60×60 px centre crop every ~33ms (≈30 fps)
     3. Average the RED channel across the crop → raw PPG signal
     4. Band-pass filter 0.5–3.0 Hz (≈ 30–180 BPM)
     5. Detect peaks; BPM = (peak_count / duration) × 60
     6. SpO₂ estimated from R/IR ratio proxy (single-camera heuristic)
   ══════════════════════════════════════════════════════════════ */

const SAMPLE_DURATION_S = 20;   // seconds of signal to collect
const FPS               = 30;   // target frames per second
const CROP_SIZE         = 60;   // pixel crop of finger area

// ── State ──────────────────────────────────────────────────────
let stream         = null;
let animFrame      = null;
let rawSignal      = [];   // raw red-channel averages
let filteredSignal = [];   // band-pass filtered
let startTime      = null;
let measuring      = false;
let history        = [];   // {time, hr, spo2, status}

// ── DOM refs ───────────────────────────────────────────────────
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

// ── Camera helpers ─────────────────────────────────────────────
async function getCamera() {
  const constraints = {
    video: {
      facingMode: { ideal: 'environment' },  // rear cam
      width:  { ideal: 640 },
      height: { ideal: 640 },
      frameRate: { ideal: FPS },
      torch: true,          // flashlight on (mobile)
    }
  };
  try {
    stream = await navigator.mediaDevices.getUserMedia(constraints);
  } catch(e) {
    // Fallback: any camera, no torch
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
  }

  // Try to enable torch
  const track = stream.getVideoTracks()[0];
  try {
    await track.applyConstraints({ advanced: [{ torch: true }] });
  } catch(_) {}

  video.srcObject = stream;
  await new Promise(r => { video.onloadedmetadata = r; });
  await video.play();
  overlayC.width  = video.videoWidth  || 640;
  overlayC.height = video.videoHeight || 640;
}

// ── Red-channel sampler ────────────────────────────────────────
function sampleRed() {
  const w = video.videoWidth  || 640;
  const h = video.videoHeight || 640;
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
    rSum += px[i];     // R
    bSum += px[i + 2]; // B (proxy for IR in single-camera setup)
  }
  return { r: rSum / total, b: bSum / total };
}

// ── Band-pass filter (simple moving-average difference) ─────────
//   Approximates a 0.5–3 Hz pass-band at 30 fps
function bandPassFilter(signal) {
  if (signal.length < 6) return signal.slice();
  const slow = movingAvg(signal, Math.floor(FPS * 0.8));   // ~0.5 Hz
  const fast = movingAvg(signal, Math.floor(FPS * 0.1));   // ~3.0 Hz
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

// ── Peak detector (local maxima above mean + 0.5σ) ───────────
function detectPeaks(signal) {
  if (signal.length < 5) return [];
  const mean = signal.reduce((a, b) => a + b, 0) / signal.length;
  const sd   = Math.sqrt(signal.map(v => (v - mean) ** 2).reduce((a, b) => a + b, 0) / signal.length);
  const thresh = mean + 0.5 * sd;
  const minGap = Math.floor(FPS * 0.35); // min 0.35 s between peaks (~170 bpm max)
  const peaks  = [];
  let lastPeak = -minGap;
  for (let i = 1; i < signal.length - 1; i++) {
    if (signal[i] > thresh && signal[i] > signal[i-1] && signal[i] > signal[i+1] && (i - lastPeak) >= minGap) {
      peaks.push(i);
      lastPeak = i;
    }
  }
  return peaks;
}

// ── SpO₂ estimate (heuristic, single camera) ────────────────
//   Real SpO₂ needs 660nm + 940nm; this is a rough proxy only
function estimateSpo2(rSamples, bSamples) {
  if (rSamples.length < 10) return null;
  const rAC  = std(rSamples);
  const rDC  = mean(rSamples);
  const bAC  = std(bSamples);
  const bDC  = mean(bSamples);
  if (rDC === 0 || bDC === 0) return null;
  const R    = (rAC / rDC) / (bAC / bDC);
  // Empirical calibration: SpO₂ ≈ 110 − 25 × R  (from literature approximations)
  const spo2 = Math.round(110 - 25 * R);
  return Math.max(80, Math.min(100, spo2));
}

function mean(arr) { return arr.reduce((a, b) => a + b, 0) / arr.length; }
function std(arr) {
  const m = mean(arr);
  return Math.sqrt(arr.map(v => (v - m) ** 2).reduce((a, b) => a + b, 0) / arr.length);
}

// ── Finger detection (checks if frame is mostly red + dark) ──
function fingerOnCamera(r, b) {
  // When finger covers cam with torch: red channel high, blue low
  return r > 100 && r > b * 1.8;
}

// ── Waveform renderer ─────────────────────────────────────────
function drawWaveform() {
  const W = waveC.offsetWidth || 560;
  const H = waveC.offsetHeight || 80;
  waveC.width = W; waveC.height = H;
  waveCtx.clearRect(0, 0, W, H);

  const sig = filteredSignal.length >= 5 ? filteredSignal : rawSignal.slice();
  if (sig.length < 2) {
    waveCtx.fillStyle = 'rgba(100,160,220,0.18)';
    waveCtx.font = '12px sans-serif';
    waveCtx.fillText('Waveform will appear once signal is detected…', 14, H / 2 + 4);
    return;
  }

  const minV = Math.min(...sig);
  const maxV = Math.max(...sig);
  const range = maxV - minV || 1;
  const pad = 10;
  const innerH = H - 2 * pad;
  const step  = W / (sig.length - 1);

  waveCtx.beginPath();
  waveCtx.strokeStyle = '#e03030';
  waveCtx.lineWidth   = 2;
  waveCtx.shadowColor = 'rgba(220,50,50,0.35)';
  waveCtx.shadowBlur  = 6;

  sig.forEach((v, i) => {
    const x = i * step;
    const y = pad + innerH - ((v - minV) / range) * innerH;
    i === 0 ? waveCtx.moveTo(x, y) : waveCtx.lineTo(x, y);
  });
  waveCtx.stroke();
}

// ── Main capture loop ─────────────────────────────────────────
let rSamples = [], bSamples = [];

function captureLoop() {
  if (!measuring) return;
  const elapsed = (Date.now() - startTime) / 1000;

  // Sample
  const { r, b } = sampleRed();
  rawSignal.push(r);
  rSamples.push(r);
  bSamples.push(b);

  // Filter & draw waveform
  filteredSignal = bandPassFilter(rawSignal);
  drawWaveform();

  // Finger detection feedback
  if (fingerOnCamera(r, b)) {
    guideRing.className = 'guide-ring measuring';
    statusPill.textContent = '🔴 Reading pulse…';
  } else {
    guideRing.className = 'guide-ring';
    statusPill.textContent = '👆 Place finger on camera';
  }

  // Progress
  const pct = Math.min(100, (elapsed / SAMPLE_DURATION_S) * 100);
  progressBar.style.width = pct + '%';
  progressLbl.textContent  = elapsed < SAMPLE_DURATION_S
    ? `Measuring… ${Math.ceil(SAMPLE_DURATION_S - elapsed)}s remaining`
    : 'Processing…';

  setStep(3);

  // Done?
  if (elapsed >= SAMPLE_DURATION_S) {
    finishMeasurement();
    return;
  }

  animFrame = requestAnimationFrame(captureLoop);
}

// ── Finish & compute result ────────────────────────────────────
function finishMeasurement() {
  measuring = false;
  cancelAnimationFrame(animFrame);

  const peaks = detectPeaks(filteredSignal);
  const durationS = rawSignal.length / FPS;
  const bpm = Math.round((peaks.length / durationS) * 60);

  // Sanity clamp
  const validBPM = (bpm >= 40 && bpm <= 200) ? bpm : null;
  const spo2Raw  = estimateSpo2(rSamples, bSamples);

  displayResult(validBPM, spo2Raw);
  recordHistory(validBPM, spo2Raw);

  statusPill.textContent = '✅ Done';
  guideRing.className    = 'guide-ring done';
  progressLbl.textContent = 'Measurement complete';
  progressBar.style.width = '100%';

  startBtn.disabled = false;
  stopBtn.disabled  = true;
  setStep(4);
}

// ── Display result ────────────────────────────────────────────
function hrClass(bpm) {
  if (!bpm) return ['—', 'status-unknown', 'Insufficient signal'];
  if (bpm < 60)        return [bpm, 'status-warning', 'Low (Bradycardia)'];
  if (bpm <= 100)      return [bpm, 'status-normal',  'Normal'];
  if (bpm <= 120)      return [bpm, 'status-warning', 'Elevated'];
  return                      [bpm, 'status-danger',  'High (Tachycardia)'];
}
function spo2Class(v) {
  if (!v) return ['—', 'status-unknown', 'Estimated'];
  if (v >= 95)  return [v, 'status-normal',  'Normal'];
  if (v >= 90)  return [v, 'status-warning', 'Low — watch closely'];
  return               [v, 'status-danger',  'Critical — seek help'];
}

function displayResult(bpm, spo2) {
  document.getElementById('results').style.display = 'grid';

  const [hv, hc, hl] = hrClass(bpm);
  document.getElementById('hr-value').textContent   = hv;
  document.getElementById('hr-status').textContent  = hl;
  document.getElementById('hr-status').className    = `result-status ${hc}`;

  const [sv, sc, sl] = spo2Class(spo2);
  document.getElementById('spo2-value').textContent  = sv;
  document.getElementById('spo2-status').textContent = sl;
  document.getElementById('spo2-status').className   = `result-status ${sc}`;
}

// ── History ───────────────────────────────────────────────────
function recordHistory(bpm, spo2) {
  const now = new Date().toLocaleTimeString();
  const [,, hl] = hrClass(bpm);
  history.unshift({ time: now, hr: bpm || '?', spo2: spo2 || '?', status: hl });
  if (history.length > 10) history.pop();
  renderHistory();
}

function renderHistory() {
  const sec  = document.getElementById('history-section');
  const tbody = document.getElementById('hist-body');
  sec.style.display = 'block';
  tbody.innerHTML = history.map(h => `
    <tr>
      <td>${h.time}</td>
      <td>${h.hr}</td>
      <td>${h.spo2}</td>
      <td>${h.status}</td>
    </tr>`).join('');
}

// ── Step indicator ────────────────────────────────────────────
function setStep(n) {
  for (let i = 1; i <= 4; i++) {
    const el = document.getElementById(`step${i}`);
    el.className = i < n ? 'step done' : (i === n ? 'step active' : 'step');
  }
}

// ── Public controls ───────────────────────────────────────────
async function startMeasurement() {
  try {
    if (!stream) await getCamera();
    rawSignal      = [];
    filteredSignal = [];
    rSamples       = [];
    bSamples       = [];
    measuring      = true;
    startTime      = Date.now();
    startBtn.disabled = true;
    stopBtn.disabled  = false;
    progressBar.style.width = '0%';
    document.getElementById('results').style.display = 'none';
    guideRing.className  = 'guide-ring';
    statusPill.textContent = '👆 Place finger on camera';
    setStep(2);
    captureLoop();
  } catch(e) {
    statusPill.textContent = '❌ Camera error';
    progressLbl.textContent = 'Camera access denied. Please allow camera permission.';
    console.error(e);
  }
}

function stopMeasurement() {
  measuring = false;
  cancelAnimationFrame(animFrame);
  statusPill.textContent    = 'Stopped';
  progressLbl.textContent   = 'Measurement stopped.';
  startBtn.disabled         = false;
  stopBtn.disabled          = true;
  guideRing.className       = 'guide-ring';
  setStep(1);
}

function resetMeasurement() {
  stopMeasurement();
  rawSignal      = [];
  filteredSignal = [];
  rSamples       = [];
  bSamples       = [];
  document.getElementById('results').style.display  = 'none';
  progressBar.style.width   = '0%';
  progressLbl.textContent   = 'Ready — press Start to begin';
  statusPill.textContent    = 'Press Start';
  drawWaveform();
  setStep(1);
}

// Init waveform placeholder
drawWaveform();
</script>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN PAGE RENDERER
# ─────────────────────────────────────────────────────────────────────────────

def render_camera_vitals_page():
    """
    Call this function from app.py inside the `elif page == "Camera Vitals":` block.
    """

    st.html('<div class="page-header"><h1>📷 Camera Vitals — PPG Heart Rate</h1></div>')

    # ── How it works section ──────────────────────────────────────────────────
    with st.expander("ℹ️ How does this work?", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            _info_card(
                "PPG Technology",
                """<b>Photoplethysmography (PPG)</b> is the same technology used
                in smartwatches and pulse oximeters.<br><br>
                When you place your finger over the camera (with the flashlight on),
                the light passes through your skin. Your blood vessels expand and
                contract with every heartbeat, slightly changing how much light
                reaches the camera sensor. We measure this change to calculate
                your heart rate.""",
                "#3399ff"
            )
        with col2:
            _info_card(
                "Accuracy & Limitations",
                """✅ <b>Heart Rate</b> — Reliable, comparable to a pulse oximeter.<br>
                ⚠️ <b>SpO₂</b> — Rough estimate only; real SpO₂ needs two wavelengths of light (660nm + 940nm).<br>
                ❌ <b>Blood Pressure</b> — Cannot be measured from a single camera without hardware sensors.<br><br>
                <i>This is for informational use only — not a medical device.</i>""",
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
        st.info("**Step 3**\n\nKeep your finger **still** for 20 seconds.\nYour heart rate will appear automatically.")

    st.markdown("---")

    # ── PPG Widget ───────────────────────────────────────────────────────────
    _sub_label("🎥 Live Measurement")
    components.html(PPG_WIDGET_HTML, height=860, scrolling=False)

    st.markdown("---")

    # ── Clinical notes ────────────────────────────────────────────────────────
    _sub_label("📌 Clinical Notes")
    n1, n2 = st.columns(2)
    with n1:
        st.markdown("""
**Normal Heart Rate Ranges:**
- 🟢 Normal (Adult): 60–100 bpm
- 🟡 Bradycardia: < 60 bpm
- 🟡 Elevated: 100–120 bpm
- 🔴 Tachycardia: > 120 bpm
        """)
    with n2:
        st.markdown("""
**Normal SpO₂ Ranges:**
- 🟢 Normal: 95–100%
- 🟡 Mild Hypoxemia: 90–94%
- 🔴 Severe Hypoxemia: < 90%

*SpO₂ value is estimated and not clinically certified.*
        """)
