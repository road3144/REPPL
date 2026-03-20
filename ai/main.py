"""
영상 이미지 합성 파이프라인 v3
================================
Grounding DINO + SAM 강제 파이프라인. 폴백 없음.

필수 라이브러리:
  pip install opencv-python numpy torch torchvision
  pip install groundingdino-py
  pip install segment-anything   (또는 pip install sam-2)
"""

import cv2
import numpy as np
import os
import re
import sys
import logging

try:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

# ── 필수 임포트 ──
import torch

# Grounding DINO
from groundingdino.util.inference import (
    load_model as gdino_load,
    predict as gdino_predict,
    load_image as gdino_load_image,
)

# SAM — SAM2와 SAM1 독립 임포트 (둘 다 가능하게)
_SAM2 = False
_SAM1 = False
try:
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    _SAM2 = True
except ImportError:
    pass

try:
    from segment_anything import sam_model_registry, SamPredictor
    _SAM1 = True
except ImportError:
    pass

if not _SAM2 and not _SAM1:
    raise ImportError(
        "SAM이 설치되지 않았습니다.\n"
        "  pip install segment-anything\n"
        "  또는 pip install sam-2"
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── 경로 자동 탐색 ──
BASE = os.path.dirname(os.path.abspath(__file__))
for _d in ["inputs", os.path.join("ai", "inputs")]:
    if os.path.isdir(os.path.join(BASE, _d)):
        INPUTS = os.path.join(BASE, _d)
        break
else:
    INPUTS = os.path.join(BASE, "inputs")
OUTPUTS = INPUTS.replace("inputs", "outputs")
os.makedirs(OUTPUTS, exist_ok=True)

for _d in [os.path.join(os.path.dirname(BASE), "models"),
           os.path.join(BASE, "models")]:
    if os.path.isdir(_d):
        MODELS = _d
        break
else:
    MODELS = os.path.join(BASE, "models")

# ── Grounding DINO 가중치 (필수) ──
def _find(d, names):
    for n in names:
        p = os.path.join(d, n)
        if os.path.isfile(p):
            return p
    return None


def _find_dino_config():
    """
    Grounding DINO config 파일을 탐색한다.
    1) models/ 디렉토리에서 직접 찾기
    2) pip 설치된 groundingdino 패키지 내부에서 찾기
    """
    # 1) models/ 디렉토리
    for name in ["GroundingDINO_SwinT_OGC.py", "GroundingDINO_SwinB_cfg.py"]:
        p = os.path.join(MODELS, name)
        if os.path.isfile(p):
            return p

    # 2) pip 패키지 내부 (groundingdino/config/)
    try:
        import groundingdino
        pkg_dir = os.path.dirname(groundingdino.__file__)
        config_dir = os.path.join(pkg_dir, "config")
        for name in ["GroundingDINO_SwinT_OGC.py", "GroundingDINO_SwinB_cfg.py"]:
            p = os.path.join(config_dir, name)
            if os.path.isfile(p):
                return p
    except Exception:
        pass

    return None


DINO_CFG = _find_dino_config()
DINO_CK = _find(MODELS, [
    "groundingdino_swint_ogc.pth",
    "groundingdino_swinb_cogcoor.pth",
])
if not DINO_CK:
    raise FileNotFoundError(
        f"Grounding DINO 체크포인트(.pth)를 찾을 수 없습니다.\n"
        f"  다운로드:\n"
        f"    wget https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0-alpha/groundingdino_swint_ogc.pth\n"
        f"  위치: {MODELS}"
    )
if not DINO_CFG:
    raise FileNotFoundError(
        f"Grounding DINO config(.py)를 찾을 수 없습니다.\n"
        f"  groundingdino 패키지가 올바르게 설치되었는지 확인하세요:\n"
        f"    pip install groundingdino-py\n"
        f"  또는 수동으로 GroundingDINO_SwinT_OGC.py를 {MODELS}에 복사하세요."
    )

# ── SAM 가중치 (필수) ──
SAM_TYPE, SAM_CKPT, SAM_VER = None, None, None
_SAM_CANDIDATES = [
    ("sam2_hiera_l", "sam2.1_hiera_large.pt", "sam2"),
    ("sam2_hiera_b+", "sam2.1_hiera_base_plus.pt", "sam2"),
    ("sam2_hiera_s", "sam2.1_hiera_small.pt", "sam2"),
    ("vit_h", "sam_vit_h_4b8939.pth", "sam1"),
    ("vit_l", "sam_vit_l_0b3195.pth", "sam1"),
    ("vit_b", "sam_vit_b_01ec64.pth", "sam1"),
]
for _t, _f, _v in _SAM_CANDIDATES:
    _p = os.path.join(MODELS, _f)
    if os.path.isfile(_p):
        if _v == "sam2" and not _SAM2:
            continue
        if _v == "sam1" and not _SAM1:
            continue
        SAM_TYPE, SAM_CKPT, SAM_VER = _t, _p, _v
        break

if not SAM_CKPT:
    raise FileNotFoundError(
        f"SAM 가중치를 찾을 수 없습니다.\n"
        f"  다운로드: wget https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth\n"
        f"  위치: {MODELS}"
    )

log.info(f"DINO: ✅ {os.path.basename(DINO_CK)}")
log.info(f"SAM:  ✅ {SAM_VER}/{SAM_TYPE} ({os.path.basename(SAM_CKPT)})")
log.info(f"GPU:  {'✅ ' + torch.cuda.get_device_name(0) if torch.cuda.is_available() else '❌ CPU'}")
log.info(f"경로: {INPUTS}")


# ══════════════════════════════════════════════════════════════
# 유틸리티
# ══════════════════════════════════════════════════════════════
def _find_image(stem, d=None):
    d = d or INPUTS
    for ext in (".png", ".jpg", ".jpeg"):
        p = os.path.join(d, stem + ext)
        if os.path.isfile(p):
            return p
    raise FileNotFoundError(f"'{stem}' 이미지 없음 ({d})")


def _largest_cc(mask):
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if n <= 1:
        return mask
    best = np.argmax(stats[1:, cv2.CC_STAT_AREA]) + 1
    out = np.zeros_like(mask)
    out[labels == best] = 255
    return out


# ══════════════════════════════════════════════════════════════
# STEP 1 — 프롬프트
# ══════════════════════════════════════════════════════════════
def step1_prompt():
    print("=" * 55)
    print("  영상 합성 AI  (Grounding DINO + SAM)")
    print("=" * 55)
    print("  inputs/ 폴더에 영상·이미지를 넣고 프롬프트를 입력하세요.")
    print("  예) test_video.mp4 coca cola can")
    print()
    try:
        p = input("프롬프트: ").strip()
    except UnicodeDecodeError:
        raw = sys.stdin.buffer.readline()
        for enc in ("utf-8", "euc-kr", "cp949"):
            try:
                p = raw.decode(enc).strip()
                break
            except Exception:
                continue
        else:
            p = raw.decode("utf-8", errors="replace").strip()
    if not p:
        sys.exit(0)
    return p


# ══════════════════════════════════════════════════════════════
# STEP 2 — 파싱
# ══════════════════════════════════════════════════════════════
_KO_EN = {
    "코카콜라": "coca cola can", "콜라": "cola can",
    "시계": "wall clock", "물병": "water bottle",
    "커피": "coffee cup", "맥주": "beer can",
    "합성해줘": "", "합성": "", "빈 공간에": "", "책상 위": "",
    "의": "", "를": "", "을": "", "에": "",
}


def step2_parse(prompt):
    m = re.search(r'([\w\-./\\]+\.(?:mp4|avi|mov|mkv))', prompt, re.I)
    if not m:
        raise ValueError("영상 파일명을 찾을 수 없습니다")

    vname = m.group(1)
    vpath = os.path.join(INPUTS, vname) if not os.path.isabs(vname) else vname
    if not os.path.isfile(vpath):
        raise FileNotFoundError(f"영상 없음: {vpath}")

    rest = (prompt[:m.start()] + prompt[m.end():]).strip()
    for ko, en in _KO_EN.items():
        rest = rest.replace(ko, en)
    kw = rest.strip() or "object"

    log.info(f"영상: {os.path.basename(vpath)}  키워드: '{kw}'")
    return vpath, kw


# ══════════════════════════════════════════════════════════════
# STEP 3 — Gemini 목업
# ══════════════════════════════════════════════════════════════
def step3_gemini(video_path, prompt):
    cap = cv2.VideoCapture(video_path)
    ret, f1 = cap.read()
    cap.release()
    if not ret:
        raise IOError("첫 프레임 읽기 실패")

    gpath = _find_image("changed_first_frame")
    f2 = cv2.imread(gpath)
    if f2 is None:
        raise IOError(f"합성 프레임 로드 실패: {gpath}")

    log.info(f"원본 {f1.shape[1]}×{f1.shape[0]}  생성 {f2.shape[1]}×{f2.shape[0]}")
    return f1, f2


# ══════════════════════════════════════════════════════════════
# STEP 4 — Grounding DINO + SAM (폴백 없음)
# ══════════════════════════════════════════════════════════════
def _dino_detect(frame, keyword):
    """
    Grounding DINO로 객체 BBox를 검출한다.
    검출된 모든 객체의 bbox 리스트를 반환한다.

    핵심 수정:
    - DINO는 프롬프트 끝에 마침표(.)가 필요함 → 자동 추가
    - 낮은 임계값으로 시작, 검출될 때까지 단계적 하향
    - 검출 실패 시 Exception (폴백 없음)
    """
    log.info(f"DINO 검출: '{keyword}'")

    # ★ DINO 프롬프트 전처리: 끝에 마침표 필수
    caption = keyword.strip().lower()
    if not caption.endswith("."):
        caption += "."

    model = gdino_load(DINO_CFG, DINO_CK)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)

    tmp = os.path.join(OUTPUTS, "_dino_tmp.jpg")
    cv2.imwrite(tmp, frame)
    src, tensor = gdino_load_image(tmp)

    # '간판+흙'처럼 복합 객체 탐지 시, 간판만 높은 임계값에서 
    # 먼저 찾아져버리고 루프가 종료(break)되는 문제를 막기 위해
    # 처음부터 중간~낮은 임계값(0.15) 한 번으로 전체를 탐지합니다.
    # 낮은 신뢰도의 오탐은 아래 CONF_RATIO 필터링에서 제거됩니다.
    boxes, logits, phrases = gdino_predict(
        model, tensor, caption, box_threshold=0.15, text_threshold=0.15
    )

    try:
        os.remove(tmp)
    except OSError:
        pass

    if len(boxes) == 0:
        raise RuntimeError(
            f"Grounding DINO가 '{keyword}'를 검출하지 못했습니다.\n"
            f"  시도한 프롬프트: '{caption}'\n"
            f"  해결: 더 구체적인 영어 키워드 사용 (예: 'red coca cola can')"
        )

    # 신뢰도 필터링: 최고 신뢰도의 89% 미만 제거 로직은 
    # '간판+흙'처럼 여러 객체를 찾아야 할 때 흙이 짤리는 원인이 됩니다.
    # 비율을 0.89에서 0.50으로 대폭 낮춰, 주변 부위(흙, 기둥)도 합격하도록 변경합니다.
    CONF_RATIO = 0.50
    best_conf = logits.max().item()
    min_conf = best_conf * CONF_RATIO

    h, w = frame.shape[:2]
    all_bboxes = []
    for i in range(len(boxes)):
        conf = logits[i].item()
        cx, cy, bw, bh = boxes[i].cpu().numpy()
        x1 = max(0, int((cx - bw / 2) * w))
        y1 = max(0, int((cy - bh / 2) * h))
        bw_px = min(int(bw * w), w - x1)
        bh_px = min(int(bh * h), h - y1)

        if conf >= min_conf:
            all_bboxes.append((x1, y1, bw_px, bh_px))
            log.info(f"DINO ✅ [{len(all_bboxes)}]: ({x1},{y1},{bw_px},{bh_px}) "
                     f"conf={conf:.3f} '{phrases[i]}'")
        else:
            log.info(f"DINO ❌ 필터링: ({x1},{y1},{bw_px},{bh_px}) "
                     f"conf={conf:.3f} < {min_conf:.3f} (최소 기준)")

    log.info(f"DINO 총 {len(all_bboxes)}개 객체 채택 (전체 {len(boxes)}개 중, "
             f"최소 신뢰도 {min_conf:.3f})")
    return all_bboxes


def _sam_segment(frame, bbox):
    """
    SAM으로 정밀 마스크를 추출한다.
    SAM2 또는 SAM1을 사용. 폴백 없음.
    """
    x, y, w, h = bbox
    fh, fw = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    box_arr = np.array([x, y, x + w, y + h])

    if SAM_VER == "sam2":
        log.info(f"SAM2: {SAM_TYPE} on {device}")
        predictor = SAM2ImagePredictor.from_pretrained(
            f"facebook/{SAM_TYPE.replace('_', '-')}"
        )
        predictor.set_image(rgb)
        masks, scores, _ = predictor.predict(
            box=box_arr, multimask_output=True
        )
    else:
        log.info(f"SAM1: {SAM_TYPE} on {device}")
        sam = sam_model_registry[SAM_TYPE](checkpoint=SAM_CKPT)
        sam.to(device)
        predictor = SamPredictor(sam)
        predictor.set_image(rgb)

        # bbox + 내부 중앙 1개 fg 포인트만 사용. 3x3 그리드는 외곽을 파먹거나 배경을 찍어 누끼를 망칠 확률이 높음.
        coords, labels = [], []
        cx, cy = x + w // 2, y + h // 2
        coords.append([np.clip(cx, 0, fw - 1), np.clip(cy, 0, fh - 1)])
        labels.append(1)  # foreground

        # 외곽 bg 포인트 (여유값 20으로 늘림)
        m = 20
        for bxp, byp in [
            (cx, max(0, y - m)),
            (cx, min(fh - 1, y + h + m)),
            (max(0, x - m), cy),
            (min(fw - 1, x + w + m), cy),
        ]:
            coords.append([bxp, byp])
            labels.append(0)  # background

        masks, scores, _ = predictor.predict(
            point_coords=np.array(coords),
            point_labels=np.array(labels),
            box=box_arr[None, :],
            multimask_output=True,
        )

    best = (masks[np.argmax(scores)] * 255).astype(np.uint8)
    log.info(f"SAM ✅: score={scores.max():.4f}")

    # GPU 메모리 해제
    if SAM_VER != "sam2":
        del sam
    del predictor
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return _largest_cc(best)


def _refine_mask(mask, frame, bbox):
    """단순 가우시안 스무딩 + 모폴로지.
    캔(Can) 처럼 반사되거나 여러 색이 있는 다중 색상 객체의 내부를 갉아먹는 색상 기반 필터(HSV) 삭제."""
    
    # 너무 강하게 외곽을 깎는 로직(erosion x 2 등)도 완화합니다.
    x, y, w, h = bbox
    # 블러 커널 사이즈 (과도한 깎임 방지)
    bk = max(3, int(min(w, h) * 0.03)) | 1
    # 짝수면 홀수로 맞춰줍니다 (bk |= 1)
    sm = cv2.GaussianBlur(mask.astype(np.float32) / 255, (bk, bk), 0)
    _, ref = cv2.threshold((sm * 255).astype(np.uint8), 128, 255, cv2.THRESH_BINARY)

    # 모폴로지 (닫기-열기, 수축 횟수 1회로 줄임)
    ke = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    ref = cv2.morphologyEx(ref, cv2.MORPH_CLOSE, ke, iterations=1)
    
    # 캔 뚜껑/모서리가 날아가지 않도록 살짝만(1px 단위) 파먹기
    ref = cv2.erode(ref, np.ones((3, 3), np.uint8), iterations=1)

    return _largest_cc(ref)


def extract_shadow_map(f1, f2, mask):
    if f1.shape[:2] != f2.shape[:2]:
        f1 = cv2.resize(f1, (f2.shape[1], f2.shape[0]))
    hsv1 = cv2.cvtColor(f1, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv2 = cv2.cvtColor(f2, cv2.COLOR_BGR2HSV).astype(np.float32)
    v1 = hsv1[:, :, 2]
    v2 = hsv2[:, :, 2]
    
    v1_safe = np.clip(v1, 1e-5, 255.0)
    raw_ratio = v2 / v1_safe
    
    kernel = np.ones((51, 51), np.uint8)
    dilated_mask = cv2.dilate(mask, kernel, iterations=2)
    bg_ratio = raw_ratio[dilated_mask == 0]
    base_ratio = np.median(bg_ratio) if len(bg_ratio) > 0 else 1.0
    
    normalized_ratio = raw_ratio / base_ratio
    shadow_map = np.clip(normalized_ratio, 0.0, 1.0)
    
    # ── 그림자 탐지 영역 완화 (부드럽고 넓은 그림자) ──
    # 1) 객체 주변 80px(더 넓게) 그림자 탐지 영역으로 설정
    shadow_zone = cv2.dilate(mask, np.ones((80, 80), np.uint8), iterations=1)
    shadow_map[shadow_zone == 0] = 1.0
    
    # 2) 객체 내부는 그림자 아님
    shadow_map[mask > 0] = 1.0
    
    # 3) 마스크 경계 주변 임계값 완화
    near_mask = cv2.dilate(mask, np.ones((20, 20), np.uint8), iterations=1)
    near_border = (near_mask > 0) & (mask == 0)
    shadow_map[near_border & (shadow_map > 0.88)] = 1.0
    
    # 4) 전체적으로 임계값 완화: 부드러운 그림자(Soft Shadow) 살림
    shadow_map[shadow_map > 0.94] = 1.0
    
    shadow_map = cv2.GaussianBlur(shadow_map, (25, 25), 0)
    log.info(f"AI 그림자 추출 완료 (base_ratio: {base_ratio:.3f})")
    return shadow_map

def step4_extract(first_frame, generated_frame, keyword):
    """DINO → SAM → 정제. 다중 객체 지원. 폴백 없음."""
    all_bboxes = _dino_detect(generated_frame, keyword)

    # 각 bbox에 대해 SAM 세그멘테이션 실행 후 마스크 결합
    fh, fw = generated_frame.shape[:2]
    combined_mask = np.zeros((fh, fw), dtype=np.uint8)

    for i, bbox in enumerate(all_bboxes):
        log.info(f"SAM 세그멘테이션 [{i+1}/{len(all_bboxes)}]: bbox={bbox}")
        mask_i = _sam_segment(generated_frame, bbox)
        mask_i = _refine_mask(mask_i, generated_frame, bbox)
        combined_mask = cv2.bitwise_or(combined_mask, mask_i)

    log.info(f"마스크 결합 완료: {len(all_bboxes)}개 객체")

    # 그림자 추출 (결합된 마스크 기준)
    shadow_map = extract_shadow_map(first_frame, generated_frame, combined_mask)

    # bbox를 결합된 영역(마스크 + 그림자) 기준으로 재계산
    shadow_binary = (shadow_map < 0.98).astype(np.uint8) * 255
    merged = cv2.bitwise_or(combined_mask, shadow_binary)

    coords = cv2.findNonZero(merged)
    if coords is not None:
        mx, my, mw, mh = cv2.boundingRect(coords)
        gh, gw = combined_mask.shape[:2]
        p = 20
        bbox = (max(0, mx - p), max(0, my - p),
                min(mw + 2 * p, gw - max(0, mx - p)),
                min(mh + 2 * p, gh - max(0, my - p)))

    log.info(f"최종 bbox(그림자 포함): {bbox}")
    cv2.imwrite(os.path.join(OUTPUTS, "object_mask.png"), combined_mask)
    cv2.imwrite(os.path.join(OUTPUTS, "shadow_map.png"), ((1.0 - shadow_map)*255).astype(np.uint8))
    return combined_mask, shadow_map, bbox


# ══════════════════════════════════════════════════════════════
# STEP 5 — 스케일링
# ══════════════════════════════════════════════════════════════
def step5_scale(f2, mask, shadow_map, bbox, vw, vh):
    gen_h, gen_w = f2.shape[:2]
    sx, sy = vw / gen_w, vh / gen_h
    gx, gy, gw, gh = bbox

    crop = f2[gy:gy + gh, gx:gx + gw].copy()
    mcrop = mask[gy:gy + gh, gx:gx + gw].copy()
    scrop = shadow_map[gy:gy + gh, gx:gx + gw].copy()
    
    crop = cv2.bitwise_and(crop, crop, mask=mcrop)

    vx, vy = int(gx * sx), int(gy * sy)
    vw_b, vh_b = max(1, int(gw * sx)), max(1, int(gh * sy))

    obj = cv2.resize(crop, (vw_b, vh_b), interpolation=cv2.INTER_LANCZOS4)
    ms = cv2.resize(mcrop, (vw_b, vh_b), interpolation=cv2.INTER_LINEAR)
    _, mr = cv2.threshold(ms, 128, 255, cv2.THRESH_BINARY)
    
    sr = cv2.resize(scrop, (vw_b, vh_b), interpolation=cv2.INTER_LINEAR)

    log.info(f"스케일: 생성({gx},{gy},{gw},{gh}) → 영상({vx},{vy},{vw_b},{vh_b})")
    cv2.imwrite(os.path.join(OUTPUTS, "object_crop.png"), obj)
    cv2.imwrite(os.path.join(OUTPUTS, "mask_roi.png"), mr)
    return obj, mr, sr, (vx, vy, vw_b, vh_b)


# ══════════════════════════════════════════════════════════════
# STEP 5.5 — Contact Shadow (마스크 하단 기반)
# ══════════════════════════════════════════════════════════════
def step6_composite(vpath, obj, mr, sr, vbbox, opath):
    cap = cv2.VideoCapture(vpath)
    vw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out = cv2.VideoWriter(opath, cv2.VideoWriter_fourcc(*'mp4v'), fps, (vw, vh))

    bx, by, bw, bh = vbbox
    y1, y2 = max(0, by), min(vh, by + bh)
    x1, x2 = max(0, bx), min(vw, bx + bw)
    oy1 = y1 - by
    oy2 = bh - (by + bh - y2)
    ox1 = x1 - bx
    ox2 = bw - (bx + bw - x2)

    fg = obj[oy1:oy2, ox1:ox2].astype(np.float32)
    cm = mr[oy1:oy2, ox1:ox2]

    # 소프트 알파 (외곽선을 부드럽게 풀기 위해 페더링 강화)
    alpha = cv2.GaussianBlur(cm.astype(np.float32) / 255, (0, 0), sigmaX=3.5)
    inner = cv2.erode(cm, np.ones((3, 3), np.uint8), iterations=1)
    alpha[inner > 0] = 1.0
    alpha = np.clip(alpha, 0, 1)
    a3 = np.stack([alpha] * 3, axis=-1)

    # AI 생성 원본 그림자 추출 비율
    clip_shadow = sr[oy1:oy2, ox1:ox2]
    s3 = np.stack([clip_shadow] * 3, axis=-1)

    log.info(f"합성: {vw}×{vh} {fps:.0f}fps {total}f")

    # --- 추가: 깊이 추정(Z-Depth) 모델 적용 ---
    log.info("Z-Depth 가림(Occlusion) 처리를 위해 Depth Estimation 모델 로딩 (Intel/dpt-large)...")
    from transformers import pipeline
    from PIL import Image
    device_id = 0 if torch.cuda.is_available() else -1
    depth_estimator = pipeline(task="depth-estimation", model="Intel/dpt-large", device=device_id)

    # --- 첫 프레임 기준 객체의 가상 깊이(Z-Depth) 산출 ---
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    ret, bg_frame = cap.read()
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # 위치 초기화
    
    bg_pil = Image.fromarray(cv2.cvtColor(bg_frame, cv2.COLOR_BGR2RGB))
    bg_depth_out = depth_estimator(bg_pil)
    # 크기 조절된 np array (0~255 값. 값이 클수록 카메라에 가까움)
    bg_depth = np.array(bg_depth_out["depth"].resize((vw, vh), Image.Resampling.BILINEAR))
    
    # 합성 물체가 바닥에 닿는 하단 부분(y2 근처)의 깊이를 객체의 베이스(가상) 깊이로 설정
    # 안정적인 측정을 위해 ROI 내 하단 20px 영역의 중앙값 사용
    bottom_y_start = max(y1, y2 - 20)
    base_depth = np.median(bg_depth[bottom_y_start:y2, x1:x2])
    log.info(f"합성 객체의 추정 Z-Depth 베이스 값: {base_depth:.1f} (0~255)")


    n = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        roi = frame[y1:y2, x1:x2].astype(np.float32)

        # ------------------------------------------------------------
        # Z-Depth 기반 동적 마스킹 (손, 사람 등 모든 프론트 객체) 판별
        # ------------------------------------------------------------
        # 현재 프레임의 깊이 맵 추출
        frame_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        curr_depth_out = depth_estimator(frame_pil)
        curr_depth = np.array(curr_depth_out["depth"].resize((vw, vh), Image.Resampling.BILINEAR))
        
        # 합성이 일어날 ROI 구역의 깊이 타일
        roi_depth = curr_depth[y1:y2, x1:x2]

        # 객체보다 카메라에 더 가까운(깊이 값이 더 큰) 픽셀은 가림막(Occlusion) 처리
        # 오차(Tolerance)를 두어 자연스러운 윤곽선 보장 (+ 5)
        # 0~255 스케일에서 5 정도의 차이는 꽤 분명한 전경/배경 차이 단서임
        Depth_Tolerance = 5
        occlusion_mask = (roi_depth > (base_depth + Depth_Tolerance)).astype(np.float32)

        # 가림막 마스크 경계선을 부드럽게 (알파 블렌딩용 가우시안)
        occ_float = cv2.GaussianBlur(occlusion_mask.astype(np.float32), (15, 15), 0)
        occ_3 = np.stack([occ_float]*3, axis=-1)

        # ------------------------------------------------------------
        # 합성 계산
        # ------------------------------------------------------------
        # 원본 알파값(a3)에서 앞을 가리는 부분(occ_3)은 알파값을 깎아냄 (투명화)
        occluded_a3 = a3 * (1.0 - occ_3)

        # 그림자(s3) 역시 물체 앞을 지나는 것 위에는 생기면 안됨.
        # s3는 값이 0일수록 어두움(그림자), 1.0에 가까울수록 원본(밝음).
        # occ_3 가 1.0(가림)인 곳은 그림자 효과를 없애서 1.0으로 만듦
        occluded_s3 = 1.0 - ((1.0 - s3) * (1.0 - occ_3))

        # (1) AI 그림자를 배경에 적용
        roi = roi * occluded_s3

        # (2) 객체 알파 블렌딩을 그 위에 적용
        roi = fg * occluded_a3 + roi * (1.0 - occluded_a3)

        frame[y1:y2, x1:x2] = np.clip(roi, 0, 255).astype(np.uint8)
        out.write(frame)
        n += 1

    cap.release()
    out.release()
    log.info(f"완료: {n}f → {opath}")


# ══════════════════════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════════════════════
def main():
    prompt = step1_prompt()

    log.info("─" * 45)
    log.info("STEP 2 — 파싱")
    try:
        vpath, kw = step2_parse(prompt)
    except (ValueError, FileNotFoundError) as e:
        print(f"❌ {e}")
        return

    log.info("─" * 45)
    log.info("STEP 3 — Gemini")
    f1, f2 = step3_gemini(vpath, prompt)

    cap = cv2.VideoCapture(vpath)
    vw, vh = int(cap.get(3)), int(cap.get(4))
    cap.release()

    log.info("─" * 45)
    log.info("STEP 4 — DINO + SAM 객체 추출")
    mask, shadow_map, bbox = step4_extract(f1, f2, kw)

    log.info("─" * 45)
    log.info("STEP 5 — 스케일링")
    obj, mr, sr, vbbox = step5_scale(f2, mask, shadow_map, bbox, vw, vh)

    log.info("─" * 45)
    log.info("STEP 6 — 합성")
    opath = os.path.join(OUTPUTS, "output_composited.mp4")
    step6_composite(vpath, obj, mr, sr, vbbox, opath)

    print()
    print("=" * 55)
    print("  ✅ 합성 완료!")
    print(f"  출력: {opath}")
    print("=" * 55)


if __name__ == "__main__":
    main()
