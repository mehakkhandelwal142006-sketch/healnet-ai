"""
pupil_analysis.py — HealNet Pupil Detection Engine  (Enhanced v2)
==================================================================
Improvements over v1:
  - Full preprocessing pipeline: gamma correction, bilateral filter,
    CLAHE contrast normalisation, unsharp masking
  - Multi-run consensus (3 preprocessing variants, median aggregation)
  - Otsu adaptive thresholding (deterministic, replaces unstable percentile)
  - Ellipse fitting (accurate circularity)
  - Multi-scale Hough voting (robust iris detection)
  - Physiological PIR clamp (rejects impossible values)
  - Deterministic confidence scorer (same image = same score always)
  - Contour quality gating

Dependencies:
    pip install opencv-python mediapipe numpy pillow
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Tuple, List
import io

try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False

# ── Constants ──────────────────────────────────────────────────────────────────
PIR_NORMAL_MIN        = 0.20
PIR_NORMAL_MAX        = 0.45
PIR_DILATED           = 0.50
PIR_CONSTRICTED       = 0.18
PIR_PHYSIO_MIN        = 0.10   # below → biologically implausible
PIR_PHYSIO_MAX        = 0.80   # above → biologically implausible
ANISOCORIA_THRESHOLD  = 0.10
CIRCULARITY_THRESHOLD = 0.70
_N_RUNS               = 3      # preprocessing variants for consensus

SEVERITY = {
    "NORMAL":   ("#00aa66", "OK"),
    "MILD":     ("#e0a000", "MILD"),
    "MODERATE": ("#f57c00", "MODERATE"),
    "SEVERE":   ("#dd2844", "SEVERE"),
    "ERROR":    ("#888888", "ERROR"),
}


# ── Data class ─────────────────────────────────────────────────────────────────
@dataclass
class PupilResult:
    pupil_radius_px:   float = 0.0
    iris_radius_px:    float = 0.0
    pupil_iris_ratio:  float = 0.0
    is_dilated:        bool  = False
    is_constricted:    bool  = False
    is_irregular:      bool  = False
    circularity:       float = 1.0
    annotated_image:   Optional[np.ndarray] = None
    condition:         str        = "NORMAL"
    severity:          str        = "NORMAL"
    clinical_notes:    List[str]  = field(default_factory=list)
    possible_causes:   List[str]  = field(default_factory=list)
    confidence:        int   = 0
    error:             str   = ""
    center:            Tuple[int, int] = (0, 0)
    method:            str   = "opencv"
    pir_std:           float = 0.0
    quality_grade:     str   = "B"


# ═══════════════════════════════════════════════════════════
# STAGE 1 — PREPROCESSING
# ═══════════════════════════════════════════════════════════

def _correct_gamma(img, gamma):
    inv = 1.0 / gamma
    lut = np.array([((i / 255.0) ** inv) * 255 for i in range(256)], dtype=np.uint8)
    return cv2.LUT(img, lut)

def _auto_gamma(gray):
    mean = float(np.clip(gray.mean(), 5.0, 250.0))
    return float(np.clip(np.log(128.0 / 255.0) / np.log(mean / 255.0), 0.5, 2.5))

def _apply_clahe(bgr, clip_limit=2.5, tile=(8, 8)):
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile)
    l2 = clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l2, a, b]), cv2.COLOR_LAB2BGR)

def _unsharp_mask(gray, sigma=1.5, strength=0.6):
    blurred = cv2.GaussianBlur(gray, (0, 0), sigma)
    return cv2.addWeighted(gray, 1 + strength, blurred, -strength, 0)

def _preprocess(img_bgr, clahe_clip=2.5, bilateral_sigma=60.0):
    gray_raw = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gamma    = _auto_gamma(gray_raw)
    img1     = _correct_gamma(img_bgr, gamma)
    img2     = cv2.bilateralFilter(img1, d=9, sigmaColor=bilateral_sigma, sigmaSpace=bilateral_sigma)
    img3     = _apply_clahe(img2, clip_limit=clahe_clip)
    gray_out = _unsharp_mask(cv2.cvtColor(img3, cv2.COLOR_BGR2GRAY), sigma=1.5, strength=0.6)
    return img3, gray_out

def _make_variants(img_bgr):
    params = [(2.0, 50.0), (2.5, 60.0), (3.0, 75.0)]
    return [_preprocess(img_bgr, clahe_clip=cl, bilateral_sigma=bs)
            for cl, bs in params[:_N_RUNS]]


# ═══════════════════════════════════════════════════════════
# STAGE 2 — QUALITY ASSESSMENT
# ═══════════════════════════════════════════════════════════

def _assess_quality(gray):
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    mean_b  = float(gray.mean())
    std_b   = float(gray.std())
    contrast = std_b / max(mean_b, 1.0)
    sh = 3 if lap_var >= 400 else 2 if lap_var >= 150 else 1 if lap_var >= 50 else 0
    br = 2 if 55 <= mean_b <= 185 else 1 if 35 <= mean_b <= 215 else 0
    co = 2 if contrast >= 0.30 else 1 if contrast >= 0.15 else 0
    total = sh + br + co
    grade = "A" if total >= 5 else "B" if total >= 3 else "C"
    return grade


# ═══════════════════════════════════════════════════════════
# STAGE 3 — PUPIL EXTRACTION (from ROI)
# ═══════════════════════════════════════════════════════════

def _extract_pupil(gray_roi, iris_radius):
    blur = cv2.GaussianBlur(gray_roi, (5, 5), 0)
    _, dark = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    k_open  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, k_close)
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN,  k_open)

    contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return iris_radius * 0.28, 1.0, False

    min_a = np.pi * (iris_radius * 0.08) ** 2
    max_a = np.pi * (iris_radius * 0.75) ** 2
    valid = [c for c in contours if min_a < cv2.contourArea(c) < max_a]
    if not valid:
        valid = [max(contours, key=cv2.contourArea)]

    best_c, best_circ = None, -1.0
    for c in valid:
        area  = cv2.contourArea(c)
        perim = cv2.arcLength(c, True)
        circ  = (4 * np.pi * area / perim ** 2) if perim > 0 else 0.0
        if circ > best_circ:
            best_circ, best_c = circ, c

    if best_c is not None and len(best_c) >= 5:
        try:
            ellipse      = cv2.fitEllipse(best_c)
            axes         = ellipse[1]
            pupil_radius = float(min(axes) / 2.0)
            circularity  = float(min(axes) / max(axes)) if max(axes) > 0 else 1.0
            return pupil_radius, float(np.clip(circularity, 0.0, 1.0)), True
        except cv2.error:
            pass

    _, pr = cv2.minEnclosingCircle(best_c)[:2] if best_c is not None else (None, iris_radius * 0.28)
    area  = cv2.contourArea(best_c) if best_c is not None else 0
    perim = cv2.arcLength(best_c, True) if best_c is not None else 1
    circ  = (4 * np.pi * area / perim ** 2) if perim > 0 else 1.0
    return float(pr), float(np.clip(circ, 0.0, 1.0)), True


# ═══════════════════════════════════════════════════════════
# STAGE 4 — SINGLE PASS DETECTORS
# ═══════════════════════════════════════════════════════════

def _pass_opencv(bgr, gray):
    h, w = bgr.shape[:2]
    candidates = []
    for dp in [1.0, 1.2, 1.5]:
        circles = cv2.HoughCircles(
            gray, cv2.HOUGH_GRADIENT, dp=dp,
            minDist=w // 3, param1=70, param2=28,
            minRadius=int(min(h, w) * 0.12),
            maxRadius=int(min(h, w) * 0.52),
        )
        if circles is not None:
            for c in circles[0]:
                candidates.append(c)
    if not candidates:
        return None

    cands = np.array(candidates, dtype=np.float32)
    used  = [False] * len(cands)
    clusters = []
    for i, c in enumerate(cands):
        if used[i]: continue
        group = [c]; used[i] = True
        for j, d in enumerate(cands):
            if not used[j] and np.linalg.norm(c[:2] - d[:2]) < 15:
                group.append(d); used[j] = True
        clusters.append(np.mean(group, axis=0))

    best = max(clusters, key=lambda c: c[2])
    cx, cy, iris_radius = int(best[0]), int(best[1]), float(best[2])

    r  = int(iris_radius * 0.92)
    x1 = max(0, cx - r); y1 = max(0, cy - r)
    x2 = min(w, cx + r); y2 = min(h, cy + r)
    roi = gray[y1:y2, x1:x2]
    if roi.size == 0: return None

    pupil_r, circ, _ = _extract_pupil(roi, iris_radius)
    pir = pupil_r / iris_radius
    return pir, circ, iris_radius, cx, cy


def _pass_mediapipe(bgr, gray):
    if not MEDIAPIPE_AVAILABLE:
        return None
    h, w = bgr.shape[:2]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    mp_fm = mp.solutions.face_mesh
    with mp_fm.FaceMesh(static_image_mode=True, refine_landmarks=True,
                        max_num_faces=1, min_detection_confidence=0.35) as fm:
        results = fm.process(rgb)
    if not results.multi_face_landmarks:
        return None
    lm = results.multi_face_landmarks[0].landmark
    best = None
    for idx_range in [range(468, 473), range(473, 478)]:
        pts = np.array([[lm[i].x * w, lm[i].y * h] for i in idx_range], dtype=np.float32)
        center = pts.mean(axis=0)
        radius = float(np.linalg.norm(pts - center, axis=1).mean())
        if radius < 4: continue
        if best is None or radius > best[1]:
            best = (center, radius)
    if best is None: return None
    iris_center, iris_radius = best
    cx, cy = int(iris_center[0]), int(iris_center[1])
    r  = int(iris_radius * 1.10)
    x1 = max(0, cx - r); y1 = max(0, cy - r)
    x2 = min(w, cx + r); y2 = min(h, cy + r)
    roi = gray[y1:y2, x1:x2]
    if roi.size == 0: return None
    pupil_r, circ, _ = _extract_pupil(roi, iris_radius)
    pir = pupil_r / iris_radius
    return pir, circ, iris_radius, cx, cy


# ═══════════════════════════════════════════════════════════
# STAGE 5 — CONSENSUS AGGREGATION
# ═══════════════════════════════════════════════════════════

def _consensus(variants, use_mediapipe, original_bgr):
    pirs, circs, iris_rs, cxs, cys = [], [], [], [], []
    method_used   = "opencv"
    iris_detected = False

    for bgr_var, gray_var in variants:
        res = None
        if use_mediapipe:
            res = _pass_mediapipe(bgr_var, gray_var)
            if res:
                method_used   = "mediapipe"
                iris_detected = True
        if res is None:
            res = _pass_opencv(bgr_var, gray_var)
            if res:
                iris_detected = True
        if res:
            pir, circ, ir, cx, cy = res
            if PIR_PHYSIO_MIN <= pir <= PIR_PHYSIO_MAX:
                pirs.append(pir); circs.append(circ)
                iris_rs.append(ir); cxs.append(cx); cys.append(cy)

    if not pirs:
        h2, w2 = original_bgr.shape[:2]
        return 0.30, 1.0, min(h2, w2) * 0.30, 0.0, w2//2, h2//2, "opencv", False

    pir         = float(np.median(pirs))
    circularity = float(np.median(circs))
    iris_radius = float(np.median(iris_rs))
    pir_std     = float(np.std(pirs))
    cx          = int(np.median(cxs))
    cy          = int(np.median(cys))
    return pir, circularity, iris_radius, pir_std, cx, cy, method_used, iris_detected


# ═══════════════════════════════════════════════════════════
# STAGE 6 — DETERMINISTIC CONFIDENCE SCORER
# ═══════════════════════════════════════════════════════════

def _score_confidence(method, iris_detected, quality_grade,
                      pir_std, pir, circularity, iris_radius, img_shape):
    score = 0
    score += 38 if method == "mediapipe" else 28   # method base
    if iris_detected: score += 12
    score += {"A": 15, "B": 8, "C": 0}.get(quality_grade, 0)
    if   pir_std < 0.01: score += 15
    elif pir_std < 0.03: score += 10
    elif pir_std < 0.06: score += 6
    if   PIR_NORMAL_MIN <= pir <= PIR_NORMAL_MAX: score += 8
    elif PIR_PHYSIO_MIN  <= pir <= PIR_PHYSIO_MAX: score += 4
    if   circularity >= 0.85: score += 7
    elif circularity >= 0.70: score += 4
    elif circularity >= 0.55: score += 2
    min_dim = min(img_shape[:2])
    if 0.10 < (iris_radius / min_dim) < 0.60: score += 5
    return int(np.clip(score, 0, 100))


# ═══════════════════════════════════════════════════════════
# STAGE 7 — CLASSIFY & ANNOTATE
# ═══════════════════════════════════════════════════════════

def _classify_and_annotate(original_bgr, cx, cy, pupil_radius, iris_radius,
                            pir, circularity, confidence, method, pir_std, quality_grade):
    condition = "NORMAL"; severity = "NORMAL"
    clinical_notes = []; possible_causes = []

    if pir > PIR_DILATED:
        condition = "DILATED"
        excess = pir - PIR_NORMAL_MAX
        severity = "SEVERE" if excess > 0.20 else "MODERATE" if excess > 0.10 else "MILD"
        clinical_notes += [f"PIR {pir:.3f} exceeds normal ceiling ({PIR_NORMAL_MAX})",
                           "Mydriasis detected — pupil abnormally large"]
        possible_causes += [
            "Stimulant / recreational drug use (cocaine, amphetamines)",
            "Anticholinergic medication (atropine, antihistamines)",
            "Traumatic brain injury or raised intracranial pressure",
            "Oculomotor (CN III) nerve palsy",
            "Extreme anxiety or sympathetic activation",
            "Severe haemorrhage / shock",
        ]
    elif pir < PIR_CONSTRICTED:
        condition = "CONSTRICTED"
        deficit = PIR_NORMAL_MIN - pir
        severity = "SEVERE" if deficit > 0.10 else "MODERATE" if deficit > 0.05 else "MILD"
        clinical_notes += [f"PIR {pir:.3f} below normal floor ({PIR_NORMAL_MIN})",
                           "Miosis detected — pupil abnormally small"]
        possible_causes += [
            "Opioid / narcotic use (morphine, heroin, fentanyl)",
            "Cholinergic medication / organophosphate poisoning",
            "Horner's syndrome (sympathetic chain disruption)",
            "Pontine haemorrhage",
            "Bright ambient light (rule out first)",
        ]
    else:
        clinical_notes.append(f"PIR {pir:.3f} — within normal range ({PIR_NORMAL_MIN}–{PIR_NORMAL_MAX})")

    is_dilated     = condition == "DILATED"
    is_constricted = condition == "CONSTRICTED"
    is_irregular   = circularity < CIRCULARITY_THRESHOLD

    if is_irregular:
        if condition == "NORMAL": condition = "IRREGULAR"; severity = "MILD"
        clinical_notes.append(f"Pupil circularity {circularity:.3f} < threshold {CIRCULARITY_THRESHOLD}")
        possible_causes += ["Iritis or uveitis", "Previous ocular surgery",
                            "Iris trauma", "Congenital coloboma"]

    if not possible_causes:
        possible_causes.append("No abnormality — routine follow-up as advised")

    if pir_std > 0.05:
        clinical_notes.append(
            f"Measurement variability high (std={pir_std:.3f}) — consider a clearer image")
    elif pir_std < 0.02:
        clinical_notes.append(f"Consensus stable across preprocessing runs (std={pir_std:.3f})")

    # Annotation
    annotated = original_bgr.copy()
    col_map = {"NORMAL":(0,200,100),"DILATED":(0,80,220),"CONSTRICTED":(220,140,0),"IRREGULAR":(0,165,255)}
    col = col_map.get(condition, (180,180,180))
    cv2.circle(annotated, (cx, cy), int(iris_radius),  (160,160,160), 2)
    cv2.circle(annotated, (cx, cy), int(pupil_radius), col, 2)
    cv2.drawMarker(annotated, (cx, cy), col, cv2.MARKER_CROSS, 14, 2)
    cv2.putText(annotated, f"{condition}  PIR:{pir:.3f}",
                (10,28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, col, 2, cv2.LINE_AA)
    cv2.putText(annotated, f"Circ:{circularity:.2f}  Conf:{confidence}%  Q:{quality_grade}  [{method.upper()}]",
                (10,52), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (200,200,200), 1, cv2.LINE_AA)
    cv2.putText(annotated, f"PIR std:{pir_std:.3f}",
                (10,72), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160,160,160), 1, cv2.LINE_AA)

    return PupilResult(
        pupil_radius_px  = round(pupil_radius, 2),
        iris_radius_px   = round(iris_radius, 2),
        pupil_iris_ratio = round(pir, 4),
        is_dilated       = is_dilated,
        is_constricted   = is_constricted,
        is_irregular     = is_irregular,
        circularity      = round(circularity, 4),
        annotated_image  = annotated,
        condition        = condition,
        severity         = severity,
        clinical_notes   = clinical_notes,
        possible_causes  = possible_causes,
        confidence       = confidence,
        center           = (cx, cy),
        method           = method,
        pir_std          = round(pir_std, 4),
        quality_grade    = quality_grade,
    )


def _error_result(msg):
    return PupilResult(severity="ERROR", condition="ERROR", error=msg,
                       clinical_notes=[f"Detection error: {msg}"])


# ═══════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════

def analyze_pupil_image(image_bytes: bytes) -> PupilResult:
    if not image_bytes:
        return _error_result("No image data provided")
    try:
        arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        img = None
    if img is None:
        return _error_result("Could not decode image")

    # Canonical resize
    h, w = img.shape[:2]
    if w != 640:
        scale = 640 / w
        interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
        img = cv2.resize(img, (640, int(h * scale)), interpolation=interp)

    # Quality assessment on raw image
    gray_raw     = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    quality_grade = _assess_quality(gray_raw)

    # Generate preprocessing variants
    variants = _make_variants(img)

    # Consensus detection
    pir, circularity, iris_radius, pir_std, cx, cy, method, iris_detected = \
        _consensus(variants, use_mediapipe=MEDIAPIPE_AVAILABLE, original_bgr=img)

    pupil_radius = pir * iris_radius

    # Deterministic confidence
    confidence = _score_confidence(
        method=method, iris_detected=iris_detected,
        quality_grade=quality_grade, pir_std=pir_std,
        pir=pir, circularity=circularity,
        iris_radius=iris_radius, img_shape=img.shape,
    )

    return _classify_and_annotate(
        original_bgr=img, cx=cx, cy=cy,
        pupil_radius=pupil_radius, iris_radius=iris_radius,
        pir=pir, circularity=circularity,
        confidence=confidence, method=method,
        pir_std=pir_std, quality_grade=quality_grade,
    )


def analyze_both_eyes(left_bytes: Optional[bytes], right_bytes: Optional[bytes]) -> dict:
    left_result  = analyze_pupil_image(left_bytes)  if left_bytes  else None
    right_result = analyze_pupil_image(right_bytes) if right_bytes else None
    anisocoria = False; anisocoria_sev = "NORMAL"; anisocoria_notes = []

    if (left_result and right_result
            and left_result.condition  != "ERROR"
            and right_result.condition != "ERROR"):
        diff = abs(left_result.pupil_iris_ratio - right_result.pupil_iris_ratio)
        if diff > ANISOCORIA_THRESHOLD:
            anisocoria = True
            anisocoria_sev = "SEVERE" if diff > 0.20 else "MODERATE" if diff > 0.15 else "MILD"
            anisocoria_notes = [
                f"PIR difference: {diff:.3f} (threshold >= {ANISOCORIA_THRESHOLD})",
                "Anisocoria detected — pupils are unequal in size",
                "Possible causes: Horner's syndrome, CN III palsy, Adie's tonic pupil, trauma.",
            ]

    return {"left": left_result, "right": right_result,
            "anisocoria": anisocoria,
            "anisocoria_severity": anisocoria_sev,
            "anisocoria_notes": anisocoria_notes}


def image_to_bytes(img_bgr: np.ndarray, fmt: str = ".jpg") -> bytes:
    ok, buf = cv2.imencode(fmt, img_bgr)
    return buf.tobytes() if ok else b""


def pil_to_bytes(pil_img) -> bytes:
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG")
    return buf.getvalue()