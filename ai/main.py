"""
영상 이미지 합성 파이프라인 v3 + Gemini API 연동
=================================================
Grounding DINO + SAM 강제 파이프라인 + Gemini 3.1 Flash Image Preview (Nano Banana 2) API.

사용법:
  1) inputs/ 폴더에 영상(.mp4)과 합성할 이미지(.png/.jpg)를 넣는다.
  2) python main.py 실행
  3) 프롬프트 입력 (예: "책상 위 빈 공간에 콜라를 합성해줘")
  4) 자동으로 Gemini API 호출 → changed_first_frame 생성 → 합성 완료

필수 라이브러리:
  pip install opencv-python numpy torch torchvision
  pip install groundingdino-py
  pip install segment-anything   (또는 pip install sam-2)
  pip install python-dotenv google-genai
"""

import cv2
import numpy as np
import os
import re
import sys
import logging
import glob
from io import BytesIO
from PIL import Image as PILImage

from google import genai
from google.genai import types

try:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── 시나리오 특화 설정: 뒤쪽 고정 객체(냉장고) + 전경 인물/반려동물 오클루전 ──
FRIDGE_OCCLUSION_CFG = {
    "ring_inner_erode": 4,
    "ring_outer_dilate": 10,
    "dynamic_clip_grow": 5,
    "boundary_band_outer": 7,
    "boundary_band_inner": 3,
    "occ_on_frames": 2,
    "occ_off_frames": 6,
    "occ_float_bin_thr": 0.065,
    "occ_final_bin_thr": 0.22,
    "motion_min_area": 32,
    "motion_keep_near_obj_kernel": 9,
    "temporal_decay_hold": 0.52,
    "temporal_decay_release": 0.18,
}

# ── .env 로드 ──
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass  # dotenv 없으면 환경변수에서 직접 읽기

GEMINI_MODEL = "gemini-3.1-flash-image-preview"

# ── Gemini 클라이언트 초기화 ──
# 우선순위: Vertex AI (일일 할당량 없음) > API Key (무료 일일 한도 있음)
_GCP_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
_GCP_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

gemini_client = None
_USE_VERTEX = False

if _GCP_PROJECT:
    # Vertex AI 모드: 일일 할당량 없음, 크레딧 차감 방식
    # 사전 필요: gcloud auth application-default login
    gemini_client = genai.Client(
        vertexai=True,
        project=_GCP_PROJECT,
        location=_GCP_LOCATION,
    )
    _USE_VERTEX = True
    log.info(f"Gemini: Vertex AI 모드 (project={_GCP_PROJECT}, location={_GCP_LOCATION})")
elif _GEMINI_API_KEY:
    # Developer API 모드: 무료 일일 한도 있음
    gemini_client = genai.Client(api_key=_GEMINI_API_KEY)
    log.info("Gemini: Developer API 모드 (⚠️ 무료 일일 할당량 제한 있음)")
else:
    log.warning("Gemini: API 설정 없음 — .env에 GOOGLE_CLOUD_PROJECT 또는 GEMINI_API_KEY를 설정하세요.")

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

_SAM2_HF_MODEL_MAP = {
    "sam2_hiera_l": "facebook/sam2.1-hiera-large",
    "sam2_hiera_b+": "facebook/sam2.1-hiera-base-plus",
    "sam2_hiera_s": "facebook/sam2.1-hiera-small",
}

log.info(f"DINO: ✅ {os.path.basename(DINO_CK)}")
log.info(f"SAM:  ✅ {SAM_VER}/{SAM_TYPE} ({os.path.basename(SAM_CKPT)})")
log.info(f"GPU:  {'✅ ' + torch.cuda.get_device_name(0) if torch.cuda.is_available() else '❌ CPU'}")
log.info(f"경로: {INPUTS}")


# ── Model cache (per-frame 추론 시 반복 로드 방지) ──
_cached_dino_model = None
_cached_sam_predictor = None
_cached_sam_obj = None


def _get_cached_dino_model():
    """DINO 모델을 캐싱하여 반복 로드를 방지한다."""
    global _cached_dino_model
    if _cached_dino_model is None:
        _cached_dino_model = gdino_load(DINO_CFG, DINO_CK)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _cached_dino_model = _cached_dino_model.to(device)
        log.info("DINO 모델 캐시 초기화")
    return _cached_dino_model


def _get_cached_sam_predictor():
    """SAM predictor를 캐싱하여 반복 초기화를 방지한다."""
    global _cached_sam_predictor, _cached_sam_obj
    if _cached_sam_predictor is not None:
        return _cached_sam_predictor
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if SAM_VER == "sam2":
        _cached_sam_predictor = SAM2ImagePredictor.from_pretrained(
            _SAM2_HF_MODEL_MAP[SAM_TYPE]
        )
    else:
        _cached_sam_obj = sam_model_registry[SAM_TYPE](checkpoint=SAM_CKPT)
        _cached_sam_obj.to(device)
        _cached_sam_predictor = SamPredictor(_cached_sam_obj)
    log.info(f"SAM predictor 캐시 초기화: {SAM_VER}/{SAM_TYPE}")
    return _cached_sam_predictor


def _release_cached_models():
    """캐시된 모델을 해제하여 GPU 메모리를 확보한다."""
    global _cached_dino_model, _cached_sam_predictor, _cached_sam_obj
    _cached_dino_model = None
    _cached_sam_predictor = None
    if _cached_sam_obj is not None:
        del _cached_sam_obj
        _cached_sam_obj = None
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    log.info("캐시 모델 해제")


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
# STEP 1 — 프롬프트 (간소화)
# ══════════════════════════════════════════════════════════════
def step1_prompt():
    """
    사용자에게 한국어 프롬프트만 입력받는다.
    예: "책상 위 빈 공간에 콜라를 합성해줘"
    """
    print("=" * 55)
    print("  영상 합성 AI  (Gemini + DINO + SAM)")
    print("=" * 55)
    print("  inputs/ 폴더에 영상(.mp4)과 합성할 이미지를 넣고")
    print("  원하는 내용을 입력하세요.")
    print()
    print("  예) 책상 위 빈 공간에 콜라를 합성해줘")
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
# STEP 2 — 자동 파일 탐색 + 키워드 추출
# ══════════════════════════════════════════════════════════════
def step2_auto_detect(user_prompt):
    """
    inputs/ 폴더에서 영상과 합성할 이미지를 자동 탐색하고,
    사용자 프롬프트에서 DINO 키워드를 추출한다.

    반환: (video_path, object_image_path, dino_keyword)
    """
    # 영상 파일 탐색
    video_exts = ("*.mp4", "*.avi", "*.mov", "*.mkv")
    videos = []
    for ext in video_exts:
        videos.extend(glob.glob(os.path.join(INPUTS, ext)))
    if not videos:
        raise FileNotFoundError(f"inputs/ 폴더에 영상 파일이 없습니다: {INPUTS}")
    vpath = videos[0]  # 첫 번째 영상 사용
    log.info(f"영상 발견: {os.path.basename(vpath)}")

    # 합성할 이미지 탐색 (영상의 첫 프레임이 아닌 별도 이미지)
    img_exts = ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.webp")
    images = []
    for ext in img_exts:
        images.extend(glob.glob(os.path.join(INPUTS, ext)))

    # first_frame, changed_first_frame 등 파이프라인 생성 파일은 제외
    skip_stems = {"first_frame", "changed_first_frame", "ref_depth_map", "create_gemini"}
    obj_images = [
        p for p in images
        if os.path.splitext(os.path.basename(p))[0].lower() not in skip_stems
    ]

    if not obj_images:
        raise FileNotFoundError(
            f"inputs/ 폴더에 합성할 이미지가 없습니다.\n"
            f"  영상과 함께 합성할 객체 이미지(.png/.jpg)를 넣어주세요."
        )
    obj_img_path = obj_images[0]
    log.info(f"합성 이미지 발견: {os.path.basename(obj_img_path)}")

    # DINO 키워드 추출 (이미지 파일명에서 추출 시도 → 실패 시 "object")
    stem = os.path.splitext(os.path.basename(obj_img_path))[0]
    kw_from_file = re.sub(r'[_\-\d]+', ' ', stem).strip()

    # 한국어 → 영어 매핑 (DINO 검색용)
    _KO_EN = {
        "코카콜라": "coca cola can", "콜라": "cola can", "콜라캔": "cola can",
        "사과": "apple", "사과주스": "apple juice can", "에이드": "ade can",
        "음료": "beverage can", "캔": "can", "병": "bottle",
        "시계": "wall clock", "물병": "water bottle",
        "커피": "coffee cup", "맥주": "beer can",
        "컵": "cup", "접시": "plate", "꽃병": "vase",
        "막걸리": "makgeolli bottle", "소주": "soju bottle",
        "와인": "wine bottle", "주스": "juice bottle",
    }

    kw = ""
    for ko, en in _KO_EN.items():
        if ko in user_prompt:
            kw = en
            break

    if not kw:
        kw = kw_from_file if kw_from_file else "object"

    log.info(f"DINO 키워드: '{kw}'")
    return vpath, obj_img_path, kw


# ======================================================================
# STEP 3 — Gemini API 호출 (changed_first_frame.png 생성)
# ======================================================================
def _cv2_to_pil(img, max_side=1024):
    """OpenCV BGR 이미지를 리사이즈하여 PIL Image로 변환."""
    h, w = img.shape[:2]
    if max(h, w) > max_side:
        scale = max_side / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)),
                         interpolation=cv2.INTER_AREA)
    return PILImage.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


def _load_obj_as_pil(path, max_side=512):
    """파일에서 객체 이미지를 읽어 PIL Image로 변환 (알파채널 흰배경 합성)."""
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise IOError(f"이미지 로드 실패: {path}")
    if img.ndim == 3 and img.shape[2] == 4:
        alpha = img[:, :, 3:4].astype(np.float32) / 255.0
        rgb = img[:, :, :3].astype(np.float32)
        white = np.full_like(rgb, 255.0)
        img = (rgb * alpha + white * (1.0 - alpha)).astype(np.uint8)
    elif img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return _cv2_to_pil(img, max_side)


def _pil_to_cv2(pil_img):
    """PIL Image를 OpenCV BGR ndarray로 변환."""
    # RGBA → RGB 변환 (알파 채널 제거)
    if pil_img.mode == "RGBA":
        pil_img = pil_img.convert("RGB")
    elif pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")
    arr = np.array(pil_img, dtype=np.uint8)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def _extract_image_from_response(response):
    """Gemini 응답에서 이미지를 추출하여 PIL Image로 반환한다."""
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            img = PILImage.open(BytesIO(part.inline_data.data))
            return img
    return None


def _analyze_frame_for_prompt(frame):
    """원본 프레임의 시각적 특성을 분석하여 Gemini 프롬프트용 설명을 반환."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if lap_var > 500: sharpness = "sharp and high-definition"
    elif lap_var > 200: sharpness = "moderately sharp (typical broadcast/streaming quality)"
    elif lap_var > 50: sharpness = "slightly soft and blurry (compressed video quality)"
    else: sharpness = "very soft and blurry (low-quality or heavily compressed)"
    mean_brightness = gray.mean()
    if mean_brightness > 180: brightness = "brightly lit / slightly overexposed"
    elif mean_brightness > 120: brightness = "well-lit with normal exposure"
    elif mean_brightness > 70: brightness = "moderately dim / indoor lighting"
    else: brightness = "dark / low-light scene"
    b, g, r = cv2.mean(frame)[:3]
    if r > b + 15: color_temp = "warm-toned (yellowish/orange indoor lighting)"
    elif b > r + 15: color_temp = "cool-toned (bluish/daylight)"
    else: color_temp = "neutral color temperature"
    contrast = gray.std()
    if contrast > 60: contrast_desc = "high contrast"
    elif contrast > 35: contrast_desc = "moderate contrast"
    else: contrast_desc = "low contrast / flat lighting"
    patch = gray[h // 4: 3 * h // 4, w // 4: 3 * w // 4]
    noise_level = np.median(np.abs(cv2.Laplacian(patch, cv2.CV_64F))) / 0.6745
    if noise_level > 8: noise_desc = "noticeable grain/noise"
    elif noise_level > 3: noise_desc = "slight compression noise"
    else: noise_desc = "clean with minimal noise"
    return (
        f"Image quality: {sharpness}, {brightness}, {color_temp}, "
        f"{contrast_desc}, {noise_desc}. "
        f"(Sharpness={lap_var:.0f}, Brightness={mean_brightness:.0f}, Noise={noise_level:.1f})"
    )


def _build_gemini_prompt(kw, w1, h1, user_prompt, frame_quality_desc=""):
    """Gemini에 전달할 이미지 합성 프롬프트를 생성한다. 사용자 원문을 직접 전달."""

    quality_section = ""
    if frame_quality_desc:
        quality_section = (
            f"\n"
            f"===== VISUAL QUALITY MATCHING (CRITICAL) =====\n"
            f"The background image (Image 1) has these characteristics:\n"
            f"{frame_quality_desc}\n"
            f"\n"
            f"You MUST make the composited {kw} visually blend with Image 1:\n"
            f"- Match the SAME level of sharpness/softness — if the background is blurry "
            f"or soft from video compression, the added object must also appear equally soft. "
            f"Do NOT render the object in crisp high-definition if the background is low-quality.\n"
            f"- Match the SAME color temperature and white balance — if the scene has warm "
            f"yellowish indoor lighting, the object must reflect that same warm tone.\n"
            f"- Match the SAME brightness, contrast, and exposure level.\n"
            f"- Match the SAME noise/grain texture if visible.\n"
            f"- The object should look like it was FILMED by the same camera in the same scene, "
            f"not like a clean product photo pasted on top.\n"
        )

    return (
        f"I am giving you two images.\n"
        f"Image 1: a {w1}x{h1} LANDSCAPE background photo.\n"
        f"Image 2: the object to overlay (a {kw}).\n"
        f"\n"
        f"===== USER REQUEST (in Korean) =====\n"
        f"\"{user_prompt}\"\n"
        f"\n"
        f"===== ABSOLUTE RULE: PRESERVE THE ORIGINAL IMAGE =====\n"
        f"Image 1 is the SACRED BACKGROUND. Every single pixel of Image 1 that is NOT "
        f"covered by the new object MUST remain EXACTLY the same — no color shifts, "
        f"no texture changes, no added/removed furniture, no modified floors, walls, "
        f"tiles, people, lighting, or any other element. "
        f"If you compare the output with Image 1, the ONLY difference should be "
        f"the newly added {kw}.\n"
        f"\n"
        f"===== CRITICAL: DO NOT REMOVE OR REPLACE EXISTING OBJECTS =====\n"
        f"All existing objects, signs, billboards, posters, furniture, vehicles, and items "
        f"that are already visible in Image 1 MUST remain in the output EXACTLY as they are. "
        f"You are ADDING the {kw} to an EMPTY space — NOT replacing anything. "
        f"If there is a sign, billboard, or any object already at or near the placement location, "
        f"place the {kw} NEXT TO it, not ON TOP of it. "
        f"NEVER delete, hide, cover, or modify any pre-existing object in Image 1.\n"
        f"{quality_section}"
        f"\n"
        f"===== TASK =====\n"
        f"Read the user's Korean request above. It specifies WHERE to ADD the {kw}. "
        f"ADD the {kw} from Image 2 onto Image 1 at the EXACT location "
        f"described in the user request. This is purely ADDITIVE — "
        f"you are placing a NEW object into the scene without changing anything else.\n"
        f"\n"
        f"===== PLACEMENT =====\n"
        f"- Interpret the user's Korean placement description precisely.\n"
        f"- Match the perspective, lighting, and scale of Image 1.\n"
        f"- Add a small natural shadow beneath the {kw} only.\n"
        f"\n"
        f"===== STRICT PROHIBITIONS =====\n"
        f"- Do NOT remove, delete, hide, or replace ANY existing object in Image 1.\n"
        f"- Do NOT alter, repaint, recolor, or regenerate ANY part of Image 1.\n"
        f"- Do NOT add new furniture, tiles, patterns, or surfaces.\n"
        f"- Do NOT change the floor, walls, background, or any existing objects.\n"
        f"- Do NOT change people's appearance, clothing, or positions.\n"
        f"- Do NOT move, resize, or modify existing signs, billboards, or posters.\n"
        f"- Do NOT crop, rotate, or change to portrait orientation.\n"
        f"- The output MUST be {w1}x{h1} LANDSCAPE, identical to Image 1 except for the added {kw}."
    )


def _parse_rate_limit_error(error_msg):
    """
    429 에러를 분석하여 (is_daily_exhausted, retry_seconds) 를 반환한다.
    - is_daily_exhausted: True면 일일 한도 소진 (Developer API 전용, 재시도 무의미)
    - retry_seconds: API가 권장하는 대기시간
    Vertex AI 모드에서는 일일 한도가 없으므로 항상 분당 제한만 해당.
    """
    err = str(error_msg)

    # Vertex AI는 일일 한도 없음 → 항상 분당 RPM 제한
    if _USE_VERTEX:
        is_daily = False
    else:
        # Developer API: 일일 한도 소진 감지
        is_daily = "PerDay" in err and "limit: 0" in err

    # 권장 대기시간 파싱
    m = re.search(r'retry in ([\d.]+)s', err, re.IGNORECASE)
    retry_sec = float(m.group(1)) + 2 if m else 10  # 여유 2초

    return is_daily, retry_sec


def step3_gemini(video_path, obj_img_path, kw, user_prompt=""):
    """
    Gemini API 호출 → changed_first_frame.png 저장 → (f1, f2) 반환.
    항상 새로 생성 (캐시 사용 안 함).
    """
    cap = cv2.VideoCapture(video_path)
    ret, f1 = cap.read()
    cap.release()
    if not ret:
        raise IOError("첫 프레임 읽기 실패")

    h1, w1 = f1.shape[:2]
    first_frame_path = os.path.join(INPUTS, "first_frame.png")
    cv2.imwrite(first_frame_path, f1)

    changed_path = os.path.join(INPUTS, "changed_first_frame.png")

    if gemini_client is None:
        raise RuntimeError(
            ".env에 GOOGLE_CLOUD_PROJECT (Vertex AI) 또는 GEMINI_API_KEY를 설정하세요."
        )

    # ── 원본 화질 분석 + Gemini 프롬프트 ──
    quality_desc = _analyze_frame_for_prompt(f1)
    log.info(f"원본 화질: {quality_desc}")
    gemini_prompt = _build_gemini_prompt(kw, w1, h1, user_prompt, quality_desc)

    first_pil = _cv2_to_pil(f1, max_side=1280)
    obj_pil = _load_obj_as_pil(obj_img_path, max_side=512)
    log.info(f"API 페이로드: 배경 {first_pil.size}, 객체 {obj_pil.size}")

    f2 = None
    for attempt in range(5):
        log.info(f"Gemini API (시도 {attempt+1}/5)...")
        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[gemini_prompt, first_pil, obj_pil],
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                ),
            )
            result_pil = _extract_image_from_response(response)
            if result_pil is not None:
                f2 = _pil_to_cv2(result_pil)
                log.info("API 성공!")
                break
            raise RuntimeError("Gemini 응답에 이미지 없음")
        except Exception as e:
            err_str = str(e)
            log.warning(f"시도 {attempt+1} 실패: {err_str[:200]}")
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                is_daily, wait = _parse_rate_limit_error(err_str)
                if is_daily:
                    raise RuntimeError(
                        "❌ Gemini API 일일 무료 할당량이 소진되었습니다.\n"
                        "  해결 방법:\n"
                        "  1) 내일 다시 시도\n"
                        "  2) 다른 API Key 사용\n"
                        "  3) Google AI Studio에서 유료 플랜 활성화"
                    )
                log.info(f"분당 Rate limit — {wait:.0f}초 대기 후 재시도...")
                import time; time.sleep(wait)
            elif attempt < 4:
                import time; time.sleep(5)
    if f2 is None:
        raise RuntimeError("Gemini API 5회 실패")

    cv2.imwrite(changed_path, f2)
    log.info(f"changed_first_frame 저장: {f2.shape[1]}x{f2.shape[0]}")

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


def _sam_segment(frame, bbox, fg_points=None):
    """
    SAM으로 정밀 마스크를 추출한다.
    fg_points: 선택적 foreground 좌표 힌트 [(x,y), ...] — Diff에서 전달
    """
    x, y, w, h = bbox
    fh, fw = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    box_arr = np.array([x, y, x + w, y + h])

    if SAM_VER == "sam2":
        log.info(f"SAM2: {SAM_TYPE} on {device}")
        predictor = SAM2ImagePredictor.from_pretrained(
            _SAM2_HF_MODEL_MAP[SAM_TYPE]
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

        coords, labels = [], []

        if fg_points and len(fg_points) > 0:
            for px, py in fg_points:
                coords.append([np.clip(px, 0, fw - 1), np.clip(py, 0, fh - 1)])
                labels.append(1)
            log.info(f"SAM fg 포인트: Diff 기반 {len(fg_points)}개")
        else:
            cx, cy = x + w // 2, y + h // 2
            coords.append([np.clip(cx, 0, fw - 1), np.clip(cy, 0, fh - 1)])
            labels.append(1)

        cx_bg, cy_bg = x + w // 2, y + h // 2
        m = 20
        for bxp, byp in [
            (cx_bg, max(0, y - m)),
            (cx_bg, min(fh - 1, y + h + m)),
            (max(0, x - m), cy_bg),
            (min(fw - 1, x + w + m), cy_bg),
        ]:
            coords.append([bxp, byp])
            labels.append(0)

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
    객체 외곽이 과하게 줄어들면 동적 오클루전이 몸통을 복원할 여유가 줄어들기 때문에,
    기존보다 덜 공격적으로 마스크를 정리한다."""
    x, y, w, h = bbox

    # 과도한 수축 방지: blur 커널을 조금 줄이고 threshold를 완화한다.
    bk = max(3, int(min(w, h) * 0.022)) | 1
    sm = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (bk, bk), 0)
    _, ref = cv2.threshold((sm * 255).astype(np.uint8), 120, 255, cv2.THRESH_BINARY)

    ke = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    ref = cv2.morphologyEx(ref, cv2.MORPH_CLOSE, ke, iterations=1)
    ref = cv2.morphologyEx(ref, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)

    # 기존 1회 erosion은 큰 물체에서도 외곽을 깎아 몸통 복원 여유를 줄였으므로 제거한다.
    return _largest_cc(ref)


def extract_shadow_map(f1, f2, mask):
    """
    그림자 추출 (main_shadow.py 방식 적용).

    3단계 교차 검증:
    1) 밝기 비율 + Bottom-Anchored 타원형 공간 가중치
    2) 빛 방향 추론 → 방향성 가중치
    3) 연결성 + 형태(aspect ratio) 검증
    """
    if f1.shape[:2] != f2.shape[:2]:
        f1 = cv2.resize(f1, (f2.shape[1], f2.shape[0]))

    # ── 밝기 비율 계산 ──
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
    shadow_map_raw = np.clip(normalized_ratio, 0.0, 1.0)

    # ═══════════════════════════════════════
    # 1단계: Bottom-Anchored 타원형 공간 가중치
    # (방향 무관 — 야외 12시 방향 그림자도 처리 가능)
    # ═══════════════════════════════════════
    y_coords, x_coords = np.where(mask > 0)
    if len(y_coords) > 0:
        min_y, max_y = int(np.min(y_coords)), int(np.max(y_coords))
        min_x, max_x = int(np.min(x_coords)), int(np.max(x_coords))
        cx = (min_x + max_x) // 2
        cy = (min_y + max_y) // 2
        obj_h = max_y - min_y
        obj_w = max_x - min_x

        # 앵커: 객체 하단 20% 지점 (접촉 그림자의 중심)
        anchor_y = max_y - (obj_h * 0.2)
        anchor_x = cx

        H, W = mask.shape
        Y, X = np.ogrid[:H, :W]
        dist_x = (X - anchor_x) / (obj_w * 1.5 + 1e-5)
        dist_y = (Y - anchor_y) / (obj_h * 0.8 + 1e-5)
        ellipse_dist = np.sqrt(dist_x**2 + dist_y**2)
        spatial_weight = np.clip(1.7 - ellipse_dist * 1.4, 0.0, 1.0)

        # 상단 감쇠 (객체 위쪽으로 갈수록 그림자 약화)
        up_penalty = np.clip((Y - min_y) / (cy - min_y + 1e-5), 0.0, 1.0)
        up_penalty[Y >= cy] = 1.0

        final_weight = spatial_weight * up_penalty
        shadow_depth = 1.0 - shadow_map_raw
        shadow_depth *= final_weight
        shadow_map_raw = 1.0 - shadow_depth

    shadow_map_raw[mask > 0] = 1.0
    shadow_map_raw[shadow_map_raw > 0.95] = 1.0

    # ═══════════════════════════════════════
    # 2단계: 빛 방향 추론 → 방향성 가중치
    # ═══════════════════════════════════════
    shadow_binary = (shadow_map_raw < 0.95).astype(np.uint8) * 255

    # 객체 근처의 그림자 overlap으로 빛 방향 추론
    base_shadow_overlap = cv2.bitwise_and(
        shadow_binary,
        cv2.dilate(mask, np.ones((15, 15), np.uint8))
    )
    M_obj = cv2.moments(mask)
    M_shd = cv2.moments(base_shadow_overlap)

    if M_obj['m00'] > 0 and M_shd['m00'] > 0:
        obj_cx = M_obj['m10'] / M_obj['m00']
        obj_cy = M_obj['m01'] / M_obj['m00']
        sx = M_shd['m10'] / M_shd['m00']
        sy = M_shd['m01'] / M_shd['m00']

        vx, vy = sx - obj_cx, sy - obj_cy
        norm = np.hypot(vx, vy)

        if norm > 5.0:
            vx, vy = vx / norm, vy / norm
            H, W = mask.shape
            Y, X = np.ogrid[:H, :W]
            dist = np.maximum(1e-5, np.hypot(X - obj_cx, Y - obj_cy))
            dot_product = ((X - obj_cx) * vx + (Y - obj_cy) * vy) / dist
            dir_weight = np.clip((dot_product + 0.3) / 0.7, 0.0, 1.0)

            shadow_depth = 1.0 - shadow_map_raw
            shadow_depth *= dir_weight
            shadow_map_raw = 1.0 - shadow_depth
            shadow_binary = (shadow_map_raw < 0.95).astype(np.uint8) * 255

    # ═══════════════════════════════════════
    # 3단계: 연결성 + 형태 검증
    # (객체와 연결되고 종횡비가 합리적인 blob만 유지)
    # ═══════════════════════════════════════
    kernel_40 = np.ones((40, 40), np.uint8)
    dilated_for_check = cv2.dilate(mask, kernel_40, iterations=1)

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        shadow_binary, connectivity=8
    )
    valid_shadow = np.zeros_like(shadow_binary)
    for label in range(1, num_labels):
        blob = (labels == label).astype(np.uint8)
        overlap = cv2.bitwise_and(blob, dilated_for_check)
        area = stats[label, cv2.CC_STAT_AREA]
        bw = stats[label, cv2.CC_STAT_WIDTH]
        bh = stats[label, cv2.CC_STAT_HEIGHT]
        aspect = max(bw / max(1, bh), bh / max(1, bw))

        # 객체와 연결 + 최소 면적 + 합리적 종횡비
        if cv2.countNonZero(overlap) > 0 and area > 150 and aspect < 6.0:
            valid_shadow[blob == 1] = 255

    # 검증된 그림자만 적용
    shadow_map = np.where(valid_shadow == 255, shadow_map_raw, 1.0)
    shadow_map[mask > 0] = 1.0
    shadow_map = cv2.GaussianBlur(shadow_map, (15, 15), 0)
    shadow_map = np.clip(shadow_map, 0.0, 1.0)

    log.info(f"그림자 추출 완료 (base_ratio: {base_ratio:.3f}, "
             f"검증된 그림자: {np.sum(valid_shadow > 0)}px)")
    return shadow_map



def _bbox_xywh_to_xyxy(bbox):
    x, y, w, h = bbox
    return (x, y, x + w, y + h)


def _bbox_iou_xywh(a, b):
    ax1, ay1, ax2, ay2 = _bbox_xywh_to_xyxy(a)
    bx1, by1, bx2, by2 = _bbox_xywh_to_xyxy(b)
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    a_area = max(1, (ax2 - ax1) * (ay2 - ay1))
    b_area = max(1, (bx2 - bx1) * (by2 - by1))
    return inter / float(a_area + b_area - inter)


def _bbox_center_distance_norm(a, b, frame_w, frame_h):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    acx, acy = ax + aw * 0.5, ay + ah * 0.5
    bcx, bcy = bx + bw * 0.5, by + bh * 0.5
    dist = np.hypot(acx - bcx, acy - bcy)
    diag = max(1.0, np.hypot(frame_w, frame_h))
    return dist / diag


def _oversize_penalty(candidate_bbox, anchor_bbox):
    _, _, w, h = candidate_bbox
    _, _, aw, ah = anchor_bbox
    cand_area = max(1.0, float(w * h))
    anchor_area = max(1.0, float(aw * ah))
    ratio = cand_area / anchor_area
    if ratio <= 1.6:
        return 0.0
    return min(1.0, (ratio - 1.6) / 2.0)



def _bbox_intersection_ratio_to_candidate(candidate_bbox, region_bbox):
    cx1, cy1, cx2, cy2 = _bbox_xywh_to_xyxy(candidate_bbox)
    rx1, ry1, rx2, ry2 = _bbox_xywh_to_xyxy(region_bbox)
    ix1, iy1 = max(cx1, rx1), max(cy1, ry1)
    ix2, iy2 = min(cx2, rx2), min(cy2, ry2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    cand_area = max(1.0, float((cx2 - cx1) * (cy2 - cy1)))
    return inter / cand_area


def _expand_bbox(bbox, frame_w, frame_h, pad_ratio=0.10, min_pad=24):
    x, y, w, h = bbox
    pad = int(max(min_pad, max(w, h) * pad_ratio))
    nx = max(0, x - pad)
    ny = max(0, y - pad)
    nx2 = min(frame_w, x + w + pad)
    ny2 = min(frame_h, y + h + pad)
    return (nx, ny, max(1, nx2 - nx), max(1, ny2 - ny))


def _point_in_bbox(px, py, bbox):
    x, y, w, h = bbox
    return (x <= px <= x + w) and (y <= py <= y + h)


def _anchor_area_penalty(candidate_bbox, anchor_bbox):
    _, _, w, h = candidate_bbox
    _, _, aw, ah = anchor_bbox
    cand_area = max(1.0, float(w * h))
    anchor_area = max(1.0, float(aw * ah))
    ratio = cand_area / anchor_area
    if ratio <= 1.35:
        return 0.0
    if ratio <= 2.0:
        return (ratio - 1.35) * 0.9
    return 0.585 + min(1.8, (ratio - 2.0) * 1.25)



def _coarse_change_bbox(first_frame, generated_frame):
    """
    preview anchor용 coarse change bbox를 계산한다.
    자연스럽게 합성된 객체는 전역 diff가 약할 수 있으므로,
    완전한 정답 bbox가 아니라 DINO 후보를 고르는 prior로 사용한다.
    """
    h1, w1 = first_frame.shape[:2]
    h2, w2 = generated_frame.shape[:2]
    if (h1, w1) != (h2, w2):
        f1_align = cv2.resize(first_frame, (w2, h2), interpolation=cv2.INTER_AREA)
    else:
        f1_align = first_frame

    blur1 = cv2.GaussianBlur(f1_align, (9, 9), 0)
    blur2 = cv2.GaussianBlur(generated_frame, (9, 9), 0)
    lab1 = cv2.cvtColor(blur1, cv2.COLOR_BGR2Lab).astype(np.float32)
    lab2 = cv2.cvtColor(blur2, cv2.COLOR_BGR2Lab).astype(np.float32)

    diff_l = cv2.absdiff(lab1[:, :, 0], lab2[:, :, 0])
    diff_a = cv2.absdiff(lab1[:, :, 1], lab2[:, :, 1])
    diff_b = cv2.absdiff(lab1[:, :, 2], lab2[:, :, 2])
    diff_ab = cv2.magnitude(diff_a, diff_b)
    score = 0.15 * diff_l + 0.70 * diff_ab

    thr = max(8.0, float(np.percentile(score, 92)))
    binary = (score >= thr).astype(np.uint8) * 255
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=2)

    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    if n <= 1:
        return None

    img_area = float(w2 * h2)
    best_idx = -1
    best_score = -1e18
    center_x = w2 * 0.5
    center_y = h2 * 0.55
    diag = max(1.0, np.hypot(w2, h2))

    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < max(80, int(img_area * 0.0008)):
            continue
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]
        if w <= 0 or h <= 0:
            continue
        comp_cx = x + w * 0.5
        comp_cy = y + h * 0.5
        center_penalty = np.hypot(comp_cx - center_x, comp_cy - center_y) / diag
        edge_touch = int(x <= 2 or y <= 2 or x + w >= w2 - 2 or y + h >= h2 - 2)
        aspect = h / max(1.0, w)
        aspect_bonus = min(0.35, max(0.0, aspect - 0.9) * 0.18)
        area_ratio = area / img_area
        area_penalty = 0.0
        if area_ratio > 0.20:
            area_penalty = min(0.45, (area_ratio - 0.20) * 3.0)
        score_i = (area / 100.0) - center_penalty * 45.0 - edge_touch * 18.0 + aspect_bonus * 40.0 - area_penalty * 50.0
        if score_i > best_score:
            best_score = score_i
            best_idx = i

    if best_idx <= 0:
        return None

    x = stats[best_idx, cv2.CC_STAT_LEFT]
    y = stats[best_idx, cv2.CC_STAT_TOP]
    w = stats[best_idx, cv2.CC_STAT_WIDTH]
    h = stats[best_idx, cv2.CC_STAT_HEIGHT]
    pad = 18
    x = max(0, x - pad)
    y = max(0, y - pad)
    w = min(w2 - x, w + pad * 2)
    h = min(h2 - y, h + pad * 2)
    coarse_bbox = (x, y, w, h)
    log.info(f"coarse change bbox: {coarse_bbox}")
    return coarse_bbox


def _shape_prior_score(bb, frame_w, frame_h):
    x, y, w, h = bb
    if w <= 0 or h <= 0:
        return -1e9
    img_area = max(1.0, float(frame_w * frame_h))
    area_ratio = (w * h) / img_area
    aspect = h / max(1.0, w)
    cx = x + w * 0.5
    cy = y + h * 0.5
    diag = max(1.0, np.hypot(frame_w, frame_h))
    center_penalty = np.hypot(cx - frame_w * 0.5, cy - frame_h * 0.58) / diag

    score = 0.0
    if 0.01 <= area_ratio <= 0.18:
        score += 140.0
    else:
        score -= min(120.0, abs(area_ratio - 0.07) * 900.0)

    if aspect >= 1.15:
        score += min(95.0, (aspect - 1.15) * 70.0)
    else:
        score -= min(90.0, (1.15 - aspect) * 90.0)

    score -= center_penalty * 140.0

    if x <= 2 or y <= 2 or x + w >= frame_w - 2 or y + h >= frame_h - 2:
        score -= 40.0

    return score

def _compute_preview_anchor_bbox(first_frame, generated_frame, keyword):
    """
    selected preview 이미지에서 1차 anchor bbox를 계산한다.

    주 경로: DINO(keyword) + Diff map 겹침도 기반
    폴백: coarse diff bbox
    """
    log.info(f"preview anchor bbox 계산 중... (keyword='{keyword}')")
    try:
        # ── DINO + Diff 겹침으로 anchor 결정 ──
        diff_map, _ = _build_diff_map(first_frame, generated_frame)
        diff_thr = max(8.0, float(np.percentile(diff_map, 80)))
        diff_binary = (diff_map >= diff_thr).astype(np.uint8) * 255

        try:
            dino_bboxes = _dino_detect(generated_frame, keyword)
        except Exception:
            dino_bboxes = []

        best_bbox = None
        best_score = -1
        best_overlap = 0.0

        if dino_bboxes:
            for bbox in dino_bboxes:
                x, y, bw, bh = bbox
                if bw <= 0 or bh <= 0:
                    continue
                roi_diff_bin = diff_binary[y:y+bh, x:x+bw]
                overlap = cv2.countNonZero(roi_diff_bin)
                overlap_ratio = overlap / max(1, bw * bh)
                roi_diff = diff_map[y:y+bh, x:x+bw]
                mean_diff = float(roi_diff.mean()) if roi_diff.size > 0 else 0
                score = mean_diff * overlap_ratio * (max(1, bw * bh) ** 0.3)
                log.info(f"  anchor 후보: bbox={bbox}, diff_overlap={overlap_ratio:.2f}, "
                         f"mean_diff={mean_diff:.1f}, score={score:.0f}")
                if score > best_score:
                    best_score = score
                    best_bbox = bbox
                    best_overlap = overlap_ratio

        # DINO 후보의 diff 겹침이 충분하면 사용
        if best_bbox is not None and best_overlap >= 0.15:
            log.info(f"preview anchor bbox 확정(hybrid): {best_bbox}")
            return best_bbox

        # DINO 신뢰 불가 → coarse diff (가장 큰 변화 영역)
        if best_bbox is not None:
            log.info(f"DINO anchor diff_overlap={best_overlap:.2f} < 0.15 → coarse diff 폴백")

        coarse_bbox = _coarse_change_bbox(first_frame, generated_frame)
        if coarse_bbox is not None:
            log.info(f"preview anchor bbox fallback(coarse): {coarse_bbox}")
            return coarse_bbox

        return None
    except Exception as e:
        log.warning(f"preview anchor bbox 계산 실패: {e}")
        return None

# ══════════════════════════════════════════════════════════════
# Diff-First 파이프라인 (고도화)
# ══════════════════════════════════════════════════════════════

def _build_diff_map(first_frame, generated_frame):
    """
    원본 vs 합성 프레임의 고품질 차이 맵을 생성한다.
    LAB + Gray 가중 합산, multi-scale Gaussian으로 노이즈 억제.

    반환: (diff_map float32, f1_aligned)
    """
    h2, w2 = generated_frame.shape[:2]
    if first_frame.shape[:2] != (h2, w2):
        f1 = cv2.resize(first_frame, (w2, h2), interpolation=cv2.INTER_AREA)
    else:
        f1 = first_frame

    # Multi-scale: 작은 블러(디테일) + 큰 블러(구조) 합산
    scores = []
    for ksize in [(5, 5), (11, 11), (21, 21)]:
        b1 = cv2.GaussianBlur(f1, ksize, 0)
        b2 = cv2.GaussianBlur(generated_frame, ksize, 0)
        lab1 = cv2.cvtColor(b1, cv2.COLOR_BGR2Lab).astype(np.float32)
        lab2 = cv2.cvtColor(b2, cv2.COLOR_BGR2Lab).astype(np.float32)
        diff_l = cv2.absdiff(lab1[:, :, 0], lab2[:, :, 0])
        diff_ab = cv2.magnitude(
            cv2.absdiff(lab1[:, :, 1], lab2[:, :, 1]),
            cv2.absdiff(lab1[:, :, 2], lab2[:, :, 2]),
        )
        gray1 = cv2.cvtColor(b1, cv2.COLOR_BGR2GRAY).astype(np.float32)
        gray2 = cv2.cvtColor(b2, cv2.COLOR_BGR2GRAY).astype(np.float32)
        diff_gray = cv2.absdiff(gray1, gray2)
        s = 0.20 * diff_l + 0.56 * diff_ab + 0.24 * diff_gray
        scores.append(s)

    # 가중 합산: 큰 블러(구조)에 약간 더 무게
    diff_map = 0.25 * scores[0] + 0.35 * scores[1] + 0.40 * scores[2]
    return diff_map, f1



def _sam_segment_with_points(frame, fg_points, bg_points=None, bbox_hint=None):
    """
    SAM에 포인트 프롬프트(+ 선택적 bbox 힌트)를 전달하여 정밀 마스크를 추출한다.
    DINO bbox 없이도 동작한다.

    Args:
        frame: BGR 이미지
        fg_points: foreground 좌표 [(x,y), ...]
        bg_points: background 좌표 [(x,y), ...] (선택)
        bbox_hint: (x,y,w,h) bbox 힌트 (선택 — diff 영역 bbox 사용)

    반환: binary mask (uint8)
    """
    fh, fw = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    coords = []
    labels = []

    for px, py in fg_points:
        coords.append([np.clip(px, 0, fw - 1), np.clip(py, 0, fh - 1)])
        labels.append(1)

    if bg_points:
        for px, py in bg_points:
            coords.append([np.clip(px, 0, fw - 1), np.clip(py, 0, fh - 1)])
            labels.append(0)
    elif bbox_hint is not None:
        # bbox 바깥 4방향에 background 포인트 자동 생성
        bx, by, bw, bh = bbox_hint
        bcx, bcy = bx + bw // 2, by + bh // 2
        m = 25
        for bxp, byp in [
            (bcx, max(0, by - m)),
            (bcx, min(fh - 1, by + bh + m)),
            (max(0, bx - m), bcy),
            (min(fw - 1, bx + bw + m), bcy),
        ]:
            coords.append([bxp, byp])
            labels.append(0)

    coords_arr = np.array(coords)
    labels_arr = np.array(labels)

    box_arr = None
    if bbox_hint is not None:
        bx, by, bw, bh = bbox_hint
        box_arr = np.array([bx, by, bx + bw, by + bh])

    if SAM_VER == "sam2":
        predictor = SAM2ImagePredictor.from_pretrained(
            _SAM2_HF_MODEL_MAP[SAM_TYPE]
        )
        predictor.set_image(rgb)
        predict_kwargs = {"multimask_output": True}
        if box_arr is not None:
            predict_kwargs["box"] = box_arr
        if len(coords) > 0:
            predict_kwargs["point_coords"] = coords_arr
            predict_kwargs["point_labels"] = labels_arr
        masks, scores, _ = predictor.predict(**predict_kwargs)
    else:
        sam = sam_model_registry[SAM_TYPE](checkpoint=SAM_CKPT)
        sam.to(device)
        predictor = SamPredictor(sam)
        predictor.set_image(rgb)
        predict_kwargs = {"multimask_output": True}
        if len(coords) > 0:
            predict_kwargs["point_coords"] = coords_arr
            predict_kwargs["point_labels"] = labels_arr
        if box_arr is not None:
            predict_kwargs["box"] = box_arr[None, :]
        masks, scores, _ = predictor.predict(**predict_kwargs)

    best = (masks[np.argmax(scores)] * 255).astype(np.uint8)
    log.info(f"[DiffFirst] SAM ✅: score={scores.max():.4f}, "
             f"fg={len(fg_points)}pts, bg={len(bg_points) if bg_points else 0}pts")

    if SAM_VER != "sam2":
        del sam
    del predictor
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return _largest_cc(best)


def _diff_primary_extract(first_frame, generated_frame, keyword, anchor_bbox=None):
    """
    DINO + Diff 동등 결합 객체 추출 파이프라인.

    핵심 원리:
      - DINO가 keyword(냉장고)를 아는 후보를 찾음 → "뭘 찾아야 하는지"
      - Diff map이 실제 변화 영역을 보여줌 → "어디가 바뀌었는지"
      - 두 시그널이 겹치는 곳이 정답

    1단계: DINO로 키워드 기반 후보 탐지
    2단계: Diff map으로 변화량 측정
    3단계: 각 DINO 후보의 diff 겹침도 계산 → 복합 스코어
    4단계: 최고 스코어 후보 → SAM 정밀 세그먼트

    반환:
        (combined_mask, object_extent_bbox)  또는  None (실패 시)
    """
    h2, w2 = generated_frame.shape[:2]

    log.info("[Hybrid] ===== DINO+Diff 하이브리드 추출 시작 =====")

    # ── 1단계: DINO 키워드 탐지 ──
    try:
        dino_bboxes = _dino_detect(generated_frame, keyword)
        log.info(f"[Hybrid] DINO '{keyword}' 탐지: {len(dino_bboxes)}개")
    except Exception as e:
        log.warning(f"[Hybrid] DINO 실패: {e} → 폴백 필요")
        return None

    if not dino_bboxes:
        return None

    # ── 2단계: 고품질 Diff map ──
    diff_map, _ = _build_diff_map(first_frame, generated_frame)
    cv2.imwrite(os.path.join(OUTPUTS, "diff_map_normalized.png"),
                np.clip(diff_map / max(1, diff_map.max()) * 255, 0, 255).astype(np.uint8))

    # 변화 영역 이진화 (핫포인트 추출용)
    diff_thr = max(8.0, float(np.percentile(diff_map, 80)))
    diff_binary = (diff_map >= diff_thr).astype(np.uint8) * 255
    diff_binary = cv2.morphologyEx(diff_binary, cv2.MORPH_CLOSE,
                                   np.ones((5, 5), np.uint8), iterations=2)

    # ── 3단계: 각 DINO 후보에 대해 diff 겹침도 계산 ──
    scored_candidates = []

    for i, bbox in enumerate(dino_bboxes):
        x, y, bw, bh = bbox
        if bw <= 0 or bh <= 0:
            continue

        # bbox 내부의 diff 통계
        roi_diff = diff_map[y:y+bh, x:x+bw]
        if roi_diff.size == 0:
            continue

        # 상위 1/3 강한 변화의 평균 (전체 평균보다 robust)
        flat = np.sort(roi_diff.flatten())[::-1]
        top_k = max(1, len(flat) // 3)
        top_mean_diff = float(flat[:top_k].mean())

        # diff 영역과 bbox의 겹침 비율
        roi_diff_bin = diff_binary[y:y+bh, x:x+bw]
        diff_overlap_px = cv2.countNonZero(roi_diff_bin)
        diff_overlap_ratio = diff_overlap_px / max(1, bw * bh)

        # bbox 내부 diff 핫포인트 추출 (SAM용)
        hot_thr = max(diff_thr, float(np.percentile(roi_diff, 75)))
        hot_mask = roi_diff >= hot_thr
        ys, xs = np.where(hot_mask)
        hotpoints = []
        if len(xs) > 0:
            coords_arr = np.column_stack([xs, ys]).astype(np.float32)
            n_pts = min(5, len(coords_arr))
            if n_pts >= 2:
                criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
                            10, 1.0)
                _, _, centers = cv2.kmeans(
                    coords_arr, n_pts, None, criteria, 3, cv2.KMEANS_PP_CENTERS,
                )
                for cx, cy in centers:
                    hotpoints.append((int(x + cx), int(y + cy)))
            else:
                hotpoints.append((int(x + xs[0]), int(y + ys[0])))
        # 중심점 항상 포함
        hotpoints.insert(0, (x + bw // 2, y + bh // 2))

        # ── 복합 스코어 계산 ──
        # diff 겹침이 핵심: 실제로 변한 DINO 후보가 정답
        score = top_mean_diff * (diff_overlap_ratio ** 0.5) * (max(1, bw * bh) ** 0.3)

        # shape prior (적절한 크기/형태 보너스)
        area_ratio = (bw * bh) / (w2 * h2)
        if 0.01 <= area_ratio <= 0.20:
            score *= 1.3
        elif area_ratio > 0.40:
            score *= 0.4

        # 가장자리 패널티
        if x <= 2 or y <= 2 or x + bw >= w2 - 2 or y + bh >= h2 - 2:
            score *= 0.5

        # anchor 거리 보너스
        if anchor_bbox is not None:
            dist = _bbox_center_distance_norm(bbox, anchor_bbox, w2, h2)
            iou = _bbox_iou_xywh(bbox, anchor_bbox)
            score += iou * 3000.0
            if dist < 0.1:
                score *= 1.5
            elif dist > 0.35:
                score *= 0.4

        scored_candidates.append({
            "bbox": bbox,
            "score": score,
            "top_mean_diff": top_mean_diff,
            "diff_overlap": diff_overlap_ratio,
            "hotpoints": hotpoints,
            "area_ratio": area_ratio,
        })

        log.info(
            f"[Hybrid] 후보 {i+1}: bbox={bbox}, "
            f"diff_mean={top_mean_diff:.1f}, diff_overlap={diff_overlap_ratio:.2f}, "
            f"area={area_ratio:.3f}, score={score:.0f}"
        )

    if not scored_candidates:
        log.warning("[Hybrid] DINO 후보 없음 → diff-only 폴백")
        scored_candidates = []  # 아래 diff-only로 진행

    # ── 4단계: DINO 후보 신뢰도 확인 → 낮으면 diff-only 폴백 ──
    best = None
    if scored_candidates:
        scored_candidates.sort(key=lambda c: c["score"], reverse=True)
        best = scored_candidates[0]

        # DINO 후보의 diff 겹침이 너무 낮으면 → DINO가 잘못 잡은 것
        if best["diff_overlap"] < 0.15:
            log.warning(
                f"[Hybrid] DINO 최고 후보 diff_overlap={best['diff_overlap']:.2f} < 0.15 "
                f"→ DINO 신뢰 불가, diff-only 폴백"
            )
            best = None

    if best is not None:
        log.info(
            f"[Hybrid] ===== DINO+Diff 최종 선택 =====\n"
            f"  bbox={best['bbox']}, score={best['score']:.0f}, "
            f"diff_mean={best['top_mean_diff']:.1f}, "
            f"diff_overlap={best['diff_overlap']:.2f}"
        )
    else:
        # ── Diff-only 폴백 ──
        # anchor가 있으면 anchor를 직접 사용 (coarse_change_bbox가 이미 정확한 경우가 많음)
        if anchor_bbox is not None:
            ax, ay, aw, ah = anchor_bbox
            log.info(f"[Hybrid] Diff-only: anchor bbox 직접 사용 → {anchor_bbox}")

            # anchor 내부 diff 핫포인트 추출
            roi_diff = diff_map[ay:ay+ah, ax:ax+aw]
            hot_thr = max(8.0, float(np.percentile(roi_diff, 70))) if roi_diff.size > 0 else 8.0
            ys, xs = np.where(roi_diff >= hot_thr) if roi_diff.size > 0 else ([], [])
            hotpoints = []
            if len(xs) > 0:
                coords_arr = np.column_stack([xs, ys]).astype(np.float32)
                n_pts = min(5, len(coords_arr))
                if n_pts >= 2:
                    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
                                10, 1.0)
                    _, _, centers = cv2.kmeans(
                        coords_arr, n_pts, None, criteria, 3, cv2.KMEANS_PP_CENTERS,
                    )
                    for cx, cy in centers:
                        hotpoints.append((int(ax + cx), int(ay + cy)))
                else:
                    hotpoints.append((int(ax + xs[0]), int(ay + ys[0])))
            hotpoints.insert(0, (ax + aw // 2, ay + ah // 2))

            best = {
                "bbox": anchor_bbox,
                "score": 0,
                "top_mean_diff": float(roi_diff.mean()) if roi_diff.size > 0 else 0,
                "diff_overlap": 1.0,
                "hotpoints": hotpoints,
                "area_ratio": (aw * ah) / (w2 * h2),
            }
            log.info(
                f"[Hybrid] ===== Anchor-direct 최종 선택 =====\n"
                f"  bbox={anchor_bbox}, area={best['area_ratio']:.3f}, "
                f"hotpoints={len(hotpoints)}개"
            )
        else:
            log.info("[Hybrid] Diff-only 폴백: diff map에서 직접 객체 영역 추출 (anchor 없음)")

            # 적응적 이중 임계값으로 변화 영역 추출
            diff_thr_high = max(10.0, float(np.percentile(diff_map, 88)))
            diff_thr_low = max(6.0, diff_thr_high * 0.5)

            strong = (diff_map >= diff_thr_high).astype(np.uint8) * 255
            weak = (diff_map >= diff_thr_low).astype(np.uint8) * 255
            strong = cv2.morphologyEx(strong, cv2.MORPH_CLOSE,
                                      np.ones((5, 5), np.uint8), iterations=2)
            dilated = cv2.dilate(strong, np.ones((9, 9), np.uint8), iterations=2)
            expanded_mask = cv2.bitwise_or(strong, cv2.bitwise_and(dilated, weak))
            expanded_mask = cv2.morphologyEx(expanded_mask, cv2.MORPH_CLOSE,
                                             np.ones((7, 7), np.uint8), iterations=2)
            expanded_mask = cv2.morphologyEx(expanded_mask, cv2.MORPH_OPEN,
                                             np.ones((5, 5), np.uint8), iterations=1)

            n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(expanded_mask, 8)
            best_region_idx = -1
            best_region_score = -1
            img_area = float(w2 * h2)

            for ri in range(1, n_labels):
                area = stats[ri, cv2.CC_STAT_AREA]
                area_ratio = area / img_area
                if area_ratio < 0.002 or area_ratio > 0.45:
                    continue
                sx = stats[ri, cv2.CC_STAT_LEFT]
                sy = stats[ri, cv2.CC_STAT_TOP]
                sw = stats[ri, cv2.CC_STAT_WIDTH]
                sh = stats[ri, cv2.CC_STAT_HEIGHT]
                if sw > w2 * 0.85 and sh > h2 * 0.85:
                    continue
                comp_mask = (labels == ri)
                top_diff = float(np.percentile(diff_map[comp_mask], 90))
                rscore = top_diff * (min(area, img_area * 0.15) ** 0.35)
                if sx <= 2 or sy <= 2 or sx + sw >= w2 - 2 or sy + sh >= h2 - 2:
                    rscore *= 0.5
                if area_ratio > 0.10:
                    rscore *= max(0.2, 1.0 - (area_ratio - 0.10) * 5.0)
                log.info(f"  diff영역 {ri}: bbox=({sx},{sy},{sw},{sh}), "
                         f"area={area_ratio:.3f}, top_diff={top_diff:.1f}, score={rscore:.0f}")
                if rscore > best_region_score:
                    best_region_score = rscore
                    best_region_idx = ri

            if best_region_idx < 0:
                log.warning("[Hybrid] diff-only에서도 유효한 영역 없음 → 실패")
                return None

            rx = stats[best_region_idx, cv2.CC_STAT_LEFT]
            ry = stats[best_region_idx, cv2.CC_STAT_TOP]
            rw = stats[best_region_idx, cv2.CC_STAT_WIDTH]
            rh = stats[best_region_idx, cv2.CC_STAT_HEIGHT]
            diff_bbox = (rx, ry, rw, rh)

            region_mask = (labels == best_region_idx)
            region_diffs = diff_map.copy()
            region_diffs[~region_mask] = 0
            hot_thr = max(diff_thr_high, float(np.percentile(diff_map[region_mask], 75)))
            ys, xs = np.where(region_diffs >= hot_thr)
            hotpoints = []
            if len(xs) > 0:
                coords_arr = np.column_stack([xs, ys]).astype(np.float32)
                n_pts = min(5, len(coords_arr))
                if n_pts >= 2:
                    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
                                10, 1.0)
                    _, _, centers = cv2.kmeans(
                        coords_arr, n_pts, None, criteria, 3, cv2.KMEANS_PP_CENTERS,
                    )
                    for cx, cy in centers:
                        hotpoints.append((int(cx), int(cy)))
                else:
                    hotpoints.append((int(xs[0]), int(ys[0])))
            hotpoints.insert(0, (rx + rw // 2, ry + rh // 2))

            best = {
                "bbox": diff_bbox,
                "score": best_region_score,
                "top_mean_diff": float(np.percentile(diff_map[region_mask], 90)),
                "diff_overlap": 1.0,
                "hotpoints": hotpoints,
                "area_ratio": (rw * rh) / (w2 * h2),
            }
            log.info(
                f"[Hybrid] ===== Diff-only 최종 선택 =====\n"
                f"  bbox={diff_bbox}, score={best_region_score:.0f}, "
                f"area={best['area_ratio']:.3f}, hotpoints={len(hotpoints)}개"
            )

    # ── SAM 세그먼트 ──
    try:
        expanded = _expand_bbox(best["bbox"], w2, h2, pad_ratio=0.06, min_pad=10)
        mask = _sam_segment_with_points(
            generated_frame,
            fg_points=best["hotpoints"][:7],
            bbox_hint=expanded,
        )
        mask = _refine_mask(mask, generated_frame, expanded)
    except Exception as e:
        log.warning(f"[Hybrid] SAM 실패: {e} → bbox 기반 SAM 폴백")
        try:
            mask = _sam_segment(generated_frame, best["bbox"],
                                fg_points=best["hotpoints"][:5])
            mask = _refine_mask(mask, generated_frame, best["bbox"])
        except Exception as e2:
            log.error(f"[Hybrid] SAM 폴백도 실패: {e2}")
            return None

    mask_px = cv2.countNonZero(mask)
    if mask_px < 30:
        log.warning(f"[Hybrid] 마스크 너무 작음: {mask_px}px → 실패")
        return None

    # 마스크 bbox 재계산
    coords = cv2.findNonZero(mask)
    if coords is not None:
        final_bbox = cv2.boundingRect(coords)
    else:
        final_bbox = best["bbox"]

    log.info(f"[Hybrid] 최종 마스크: {mask_px}px, bbox={final_bbox}")
    cv2.imwrite(os.path.join(OUTPUTS, "hybrid_extract_mask.png"), mask)
    return mask, final_bbox


def _semantic_diff_analyze(first_frame, generated_frame, keyword, anchor_bbox=None):
    """
    [LEGACY] DINO 주도 의미론적 비교. diff_primary_extract의 fallback으로 사용.
    1. DINO를 사용하여 합성 이미지에서 객체 후보(BBox)들을 찾는다.
    2. 각 후보 BBox 내부에서만 원본 대비 픽셀 변화량을 측정한다.
    3. anchor_bbox가 있으면 그 근처 후보를 강하게 우선한다.
    """
    h1, w1 = first_frame.shape[:2]
    h2, w2 = generated_frame.shape[:2]
    if (h1, w1) != (h2, w2):
        f1_align = cv2.resize(first_frame, (w2, h2), interpolation=cv2.INTER_AREA)
    else:
        f1_align = first_frame

    log.info(f"의미론적 객체 탐색: '{keyword}' 후보 찾는 중...")
    if anchor_bbox is not None:
        log.info(f"anchor bbox prior 사용: {anchor_bbox}")

    try:
        bboxes = _dino_detect(generated_frame, keyword)
    except Exception as e:
        log.warning(f"DINO가 합성 프레임에서 '{keyword}' 탐지 실패: {e}")
        return None

    if not bboxes:
        return None

    blur1 = cv2.GaussianBlur(f1_align, (11, 11), 0)
    blur2 = cv2.GaussianBlur(generated_frame, (11, 11), 0)
    lab1 = cv2.cvtColor(blur1, cv2.COLOR_BGR2Lab).astype(np.float32)
    lab2 = cv2.cvtColor(blur2, cv2.COLOR_BGR2Lab).astype(np.float32)
    diff_map = np.sqrt(np.sum((lab1 - lab2) ** 2, axis=2))

    best_score = -1e18
    best_bbox = None
    best_fg_points = []
    coarse_region = _expand_bbox(anchor_bbox, w2, h2, pad_ratio=0.12, min_pad=28) if anchor_bbox is not None else None

    for i, bb in enumerate(bboxes):
        x, y, w, h = bb
        roi_diff = diff_map[y:y+h, x:x+w]
        if roi_diff.size == 0:
            continue

        flat_diff = np.sort(roi_diff.flatten())[::-1]
        top_k = max(1, len(flat_diff) // 3)
        mean_diff = float(flat_diff[:top_k].mean())
        diff_score = mean_diff * (max(1, w * h) ** 0.35)

        total_score = diff_score
        iou_bonus = 0.0
        center_bonus = 0.0
        size_penalty = 0.0
        coarse_bonus = 0.0
        coarse_overlap = 0.0
        shape_bonus = _shape_prior_score(bb, w2, h2)
        hard_reject = False

        # anchor가 없어도 shape prior를 항상 반영해서 선반/벽/바닥으로 튀는 것을 완화한다.
        total_score += shape_bonus

        if coarse_region is not None:
            coarse_overlap = _bbox_intersection_ratio_to_candidate(bb, coarse_region)
            cx = x + w * 0.5
            cy = y + h * 0.5
            center_inside = _point_in_bbox(cx, cy, coarse_region)

            # 사용자 ROI가 없을 때도 coarse diff region 밖 후보는 강하게 배제한다.
            if (not center_inside) and coarse_overlap < 0.18:
                hard_reject = True
            else:
                coarse_bonus = 700.0 * coarse_overlap + (180.0 if center_inside else 0.0)
                total_score += coarse_bonus

        if anchor_bbox is not None:
            iou = _bbox_iou_xywh(bb, anchor_bbox)
            center_dist = _bbox_center_distance_norm(bb, anchor_bbox, w2, h2)
            iou_bonus = 3600.0 * iou
            center_bonus = -2600.0 * center_dist
            size_penalty = -1950.0 * _oversize_penalty(bb, anchor_bbox) - 900.0 * _anchor_area_penalty(bb, anchor_bbox)

            # coarse 영역이 있어도 anchor와 너무 멀고 겹침도 약하면 버린다.
            if center_dist > 0.14 and iou < 0.05 and coarse_overlap < 0.22:
                hard_reject = True

            total_score += iou_bonus + center_bonus + size_penalty

        log.info(
            f"후보 {i+1} {bb} - 변화={mean_diff:.1f}, diff={diff_score:.0f}, "
            f"shape_bonus={shape_bonus:.0f}, coarse_bonus={coarse_bonus:.0f}, coarse_overlap={coarse_overlap:.2f}, "
            f"iou_bonus={iou_bonus:.0f}, center_bonus={center_bonus:.0f}, "
            f"size_penalty={size_penalty:.0f}, total={total_score:.0f}, reject={hard_reject}"
        )

        if hard_reject:
            continue

        if total_score > best_score:
            best_score = total_score
            best_bbox = bb

            hot_threshold = np.percentile(roi_diff, 85)
            ys, xs = np.where(roi_diff >= hot_threshold)
            fg = []
            if len(xs) > 0:
                p_count = min(5, len(xs))
                indices = np.linspace(0, len(xs)-1, p_count, dtype=int)
                for idx in indices:
                    fg.append((int(x + xs[idx]), int(y + ys[idx])))

            cx, cy = x + w // 2, y + h // 2
            if fg:
                fg[0] = (cx, cy)
            else:
                fg.append((cx, cy))
            best_fg_points = fg

    if best_bbox is None:
        log.warning("anchor prior 조건을 만족한 후보가 없습니다.")
        return None

    if best_score < 50:
        log.warning("감지된 객체들이 원본과 너무 동일합니다 (유의미한 추가 객체 아님).")
        return None

    log.info(f"선택 완료! 새로운 객체: BBox={best_bbox}, fg_points={len(best_fg_points)}개")
    return best_bbox, best_fg_points


# ── 사라진 전경 객체 복원 ──
_VANISHED_FG_KEYWORDS = (
    "chair . stool . bench . table . desk . "
    "shelf . cabinet . drawer . "
    "plant . pot . vase . lamp . "
    "box . basket . bag . bottle . cup . "
    "furniture . stand . rack"
)


def _extract_vanished_foreground_mask(first_frame, generated_frame,
                                      object_visible_mask, object_extent_bbox):
    """
    Gemini가 합성 과정에서 제거한 전경 객체(의자, 화분 등)를 감지한다.

    알고리즘:
      1) 원본 vs 생성 프레임의 고변화 영역에서 새 객체 마스크를 제외 → "사라진 영역"
      2) DINO로 원본 프레임에서 해당 영역의 객체를 탐지 → SAM으로 정밀 세그먼트
      3) Fallback: DINO 미검출 영역은 edge 기반 blob 추출로 보완

    반환:
      full-frame binary mask (uint8, 0/255) — 사라진 전경 객체 영역
    """
    gh, gw = generated_frame.shape[:2]
    if first_frame.shape[:2] != (gh, gw):
        first_aligned = cv2.resize(first_frame, (gw, gh), interpolation=cv2.INTER_AREA)
    else:
        first_aligned = first_frame

    if object_visible_mask.shape[:2] != (gh, gw):
        vis = cv2.resize(object_visible_mask, (gw, gh), interpolation=cv2.INTER_NEAREST)
        vis = (vis > 0).astype(np.uint8) * 255
    else:
        vis = object_visible_mask

    # ── 검색 영역: object bbox + margin ──
    x, y, bw, bh = object_extent_bbox
    margin = max(bw, bh) // 6
    rx1 = max(0, x - margin)
    ry1 = max(0, y - margin)
    rx2 = min(gw, x + bw + margin)
    ry2 = min(gh, y + bh + margin)
    if rx2 <= rx1 or ry2 <= ry1:
        return np.zeros((gh, gw), dtype=np.uint8)

    roi_orig = first_aligned[ry1:ry2, rx1:rx2]
    roi_gen = generated_frame[ry1:ry2, rx1:rx2]
    vis_roi = vis[ry1:ry2, rx1:rx2]

    # ── Step 1: LAB diff로 "사라진 영역" 검출 ──
    blur1 = cv2.GaussianBlur(roi_orig, (5, 5), 0)
    blur2 = cv2.GaussianBlur(roi_gen, (5, 5), 0)
    lab1 = cv2.cvtColor(blur1, cv2.COLOR_BGR2Lab).astype(np.float32)
    lab2 = cv2.cvtColor(blur2, cv2.COLOR_BGR2Lab).astype(np.float32)

    diff_l = cv2.absdiff(lab1[:, :, 0], lab2[:, :, 0])
    diff_ab = cv2.magnitude(
        cv2.absdiff(lab1[:, :, 1], lab2[:, :, 1]),
        cv2.absdiff(lab1[:, :, 2], lab2[:, :, 2]),
    )
    gray1 = cv2.cvtColor(blur1, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gray2 = cv2.cvtColor(blur2, cv2.COLOR_BGR2GRAY).astype(np.float32)
    diff_gray = cv2.absdiff(gray1, gray2)
    diff_score = 0.20 * diff_l + 0.56 * diff_ab + 0.24 * diff_gray

    # 고변화 임계: 변화가 큰 픽셀만 추출
    high_thr = max(12.0, float(np.percentile(diff_score, 75)))
    high_diff = (diff_score >= high_thr).astype(np.uint8) * 255

    # 새 객체(냉장고) 마스크 제외 — 살짝 dilate 하여 경계 아티팩트 방지
    obj_dilated = cv2.dilate(vis_roi, np.ones((7, 7), np.uint8), iterations=2)
    vanished_region = cv2.bitwise_and(high_diff, cv2.bitwise_not(obj_dilated))

    # 노이즈 제거
    vanished_region = cv2.morphologyEx(
        vanished_region, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1,
    )
    vanished_region = cv2.morphologyEx(
        vanished_region, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=1,
    )

    vanished_px = cv2.countNonZero(vanished_region)
    log.info(f"[VanishedFG] 사라진 영역: {vanished_px}px (thr={high_thr:.1f})")
    if vanished_px < 50:
        log.info("[VanishedFG] 사라진 영역 미미 → 스킵")
        return np.zeros((gh, gw), dtype=np.uint8)

    # ── Step 2: DINO+SAM으로 원본 프레임에서 사라진 객체 세그먼트 ──
    result_roi = np.zeros((ry2 - ry1, rx2 - rx1), dtype=np.uint8)

    try:
        dino_bboxes = _dino_detect(first_aligned, _VANISHED_FG_KEYWORDS)
        log.info(f"[VanishedFG] DINO 원본 프레임 탐지: {len(dino_bboxes)}개")

        for dbbox in dino_bboxes:
            dx, dy, dw, dh = dbbox
            lx1 = max(0, dx - rx1)
            ly1 = max(0, dy - ry1)
            lx2 = min(rx2 - rx1, dx + dw - rx1)
            ly2 = min(ry2 - ry1, dy + dh - ry1)
            if lx2 <= lx1 or ly2 <= ly1:
                continue

            bbox_patch = np.zeros_like(vanished_region)
            bbox_patch[ly1:ly2, lx1:lx2] = 255
            overlap = cv2.countNonZero(cv2.bitwise_and(vanished_region, bbox_patch))
            bbox_area = max(1, (lx2 - lx1) * (ly2 - ly1))
            overlap_ratio = overlap / bbox_area

            if overlap_ratio < 0.08:
                continue

            log.info(
                f"[VanishedFG] 후보 bbox=({dx},{dy},{dw},{dh}) "
                f"overlap={overlap_ratio:.2f}"
            )

            sam_mask = _sam_segment(first_aligned, dbbox)
            sam_roi = sam_mask[ry1:ry2, rx1:rx2]

            touch = cv2.countNonZero(cv2.bitwise_and(sam_roi, vanished_region))
            if touch < 20:
                continue

            sam_valid = cv2.bitwise_and(sam_roi, cv2.bitwise_not(obj_dilated))
            result_roi = cv2.bitwise_or(result_roi, sam_valid)
            log.info(
                f"[VanishedFG] DINO+SAM 채택: touch={touch}px, "
                f"added={cv2.countNonZero(sam_valid)}px"
            )
    except Exception as e:
        log.warning(f"[VanishedFG] DINO+SAM 실패 (fallback 진행): {e}")

    # ── Step 3: Diff 기반 fallback ──
    uncovered = cv2.bitwise_and(vanished_region, cv2.bitwise_not(result_roi))
    uncovered_px = cv2.countNonZero(uncovered)

    if uncovered_px > 100:
        log.info(f"[VanishedFG] Fallback: 미커버 {uncovered_px}px 처리 중")
        edge_orig = cv2.Canny(cv2.cvtColor(roi_orig, cv2.COLOR_BGR2GRAY), 40, 120)
        edge_orig = cv2.dilate(edge_orig, np.ones((3, 3), np.uint8), iterations=1)

        rh, rw = uncovered.shape[:2]
        n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(uncovered, 8)
        for i in range(1, n_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if area < 80:
                continue
            sw = stats[i, cv2.CC_STAT_WIDTH]
            sh = stats[i, cv2.CC_STAT_HEIGHT]
            fill_ratio = area / max(1, sw * sh)

            if sw > rw * 0.6 and sh > rh * 0.6 and fill_ratio > 0.5:
                continue

            comp = (labels == i).astype(np.uint8) * 255
            edge_support = cv2.countNonZero(cv2.bitwise_and(comp, edge_orig))
            edge_ratio = edge_support / max(1, area)

            if edge_ratio < 0.05:
                continue

            result_roi = cv2.bitwise_or(result_roi, comp)
            log.info(
                f"[VanishedFG] fallback blob: area={area}, "
                f"edge_ratio={edge_ratio:.2f}"
            )

    # ── 최종 정리 ──
    result_roi = cv2.morphologyEx(
        result_roi, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1,
    )

    out = np.zeros((gh, gw), dtype=np.uint8)
    out[ry1:ry2, rx1:rx2] = result_roi

    total_px = cv2.countNonZero(out)
    log.info(f"[VanishedFG] 최종 마스크: {total_px}px")
    cv2.imwrite(os.path.join(OUTPUTS, "step4_vanished_fg_mask.png"), out)
    return out


def _extract_static_occluder_mask(first_frame, generated_frame, object_extent_bbox, object_visible_mask):
    """
    첫 프레임에 이미 존재하는 정적 전경 오클루더(의자 다리, 테이블 다리, 선반 프레임 등)를 추정한다.

    사람 몸통처럼 넓고 채워진 blob이 정적 오클루더로 들어가면
    이후 합성에서 경계가 뜨거나 잘못된 hard restore가 발생할 수 있으므로,
    static mask는 '얇고 구조적인 전경'만 남기도록 더 타이트하게 제한한다.
    """
    gh, gw = generated_frame.shape[:2]
    if first_frame.shape[:2] != (gh, gw):
        first_aligned = cv2.resize(first_frame, (gw, gh), interpolation=cv2.INTER_AREA)
    else:
        first_aligned = first_frame

    if object_visible_mask.shape[:2] != (gh, gw):
        vis_aligned = cv2.resize(object_visible_mask, (gw, gh), interpolation=cv2.INTER_NEAREST)
        vis_aligned = (vis_aligned > 0).astype(np.uint8) * 255
    else:
        vis_aligned = object_visible_mask

    x, y, bw, bh = object_extent_bbox
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(gw, x + bw), min(gh, y + bh)
    if x2 <= x1 or y2 <= y1:
        return np.zeros((gh, gw), dtype=np.uint8)

    roi1 = first_aligned[y1:y2, x1:x2]
    roi2 = generated_frame[y1:y2, x1:x2]

    blur1 = cv2.GaussianBlur(roi1, (5, 5), 0)
    blur2 = cv2.GaussianBlur(roi2, (5, 5), 0)

    lab1 = cv2.cvtColor(blur1, cv2.COLOR_BGR2Lab).astype(np.float32)
    lab2 = cv2.cvtColor(blur2, cv2.COLOR_BGR2Lab).astype(np.float32)
    diff_l = cv2.absdiff(lab1[:, :, 0], lab2[:, :, 0])
    diff_a = cv2.absdiff(lab1[:, :, 1], lab2[:, :, 1])
    diff_b = cv2.absdiff(lab1[:, :, 2], lab2[:, :, 2])
    diff_ab = cv2.magnitude(diff_a, diff_b)

    gray1 = cv2.cvtColor(blur1, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gray2 = cv2.cvtColor(blur2, cv2.COLOR_BGR2GRAY).astype(np.float32)
    diff_gray = cv2.absdiff(gray1, gray2)

    diff_score = 0.20 * diff_l + 0.56 * diff_ab + 0.24 * diff_gray

    vis_roi = vis_aligned[y1:y2, x1:x2]

    # 기존 percentile 24는 몸통/팔처럼 넓은 저변화 blob도 남기기 쉬워 더 타이트하게 조정.
    unchanged_thr = max(4.6, float(np.percentile(diff_score, 16)))
    static_roi = ((diff_score <= unchanged_thr) & (vis_roi == 0)).astype(np.uint8) * 255

    # 정적 프레임 구조 edge 지원이 없는 영역은 제거한다.
    edge = cv2.Canny(cv2.cvtColor(roi1, cv2.COLOR_BGR2GRAY), 40, 120)
    edge = cv2.dilate(edge, np.ones((3, 3), np.uint8), iterations=1)

    static_roi = cv2.morphologyEx(static_roi, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(static_roi, 8)
    filtered = np.zeros_like(static_roi)
    cx = (x2 - x1) * 0.5
    cy = (y2 - y1) * 0.5
    max_center_dist = np.hypot(x2 - x1, y2 - y1) * 0.62

    for i in range(1, n_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < 10:
            continue

        sx = stats[i, cv2.CC_STAT_LEFT]
        sy = stats[i, cv2.CC_STAT_TOP]
        sw = stats[i, cv2.CC_STAT_WIDTH]
        sh = stats[i, cv2.CC_STAT_HEIGHT]
        comp = (labels == i).astype(np.uint8) * 255

        ccx = sx + sw * 0.5
        ccy = sy + sh * 0.5
        aspect = max(sw / max(1.0, sh), sh / max(1.0, sw))
        fill_ratio = area / max(1.0, float(sw * sh))
        min_side = min(sw, sh)
        edge_support = cv2.countNonZero(cv2.bitwise_and(comp, edge))
        edge_ratio = edge_support / max(1.0, float(area))
        center_dist = np.hypot(ccx - cx, ccy - cy)

        # 모서리 쪽 넓은 배경 patch 제거
        if center_dist > max_center_dist and area > 90:
            continue

        # 사람 몸통처럼 넓고 채워진 blob 제거
        if min_side >= 22 and fill_ratio > 0.50 and aspect < 3.2:
            continue

        # 얇은 구조가 아니고 edge support도 약하면 제거
        line_like = (min_side <= 18) or (aspect >= 2.4)
        if (not line_like) and edge_ratio < 0.10:
            continue

        # 넓은 사각 패치 제거
        if sw >= 20 and sh >= 20 and fill_ratio > 0.66 and aspect < 3.8:
            continue

        filtered[labels == i] = 255

    # 경계가 뜨지 않도록 아주 살짝만 타이트하게 정리
    filtered = cv2.erode(filtered, np.ones((3, 3), np.uint8), iterations=1)

    out = np.zeros((gh, gw), dtype=np.uint8)
    out[y1:y2, x1:x2] = filtered
    return out

def step4_extract(first_frame, generated_frame, keyword, anchor_bbox=None):
    """
    추가된 객체 추출.

    주 경로: Diff-First (diff map → SAM → DINO 검증)
    폴백 1: DINO-First (기존 semantic diff analyze)
    폴백 2: DINO 전체 객체 SAM

    반환:
      combined_mask: 실제 보이는 합성 객체 마스크
      shadow_map: 그림자 맵
      bbox: 그림자 포함 합성 bbox
      static_occ_mask: 첫 프레임에 이미 있던 정적 전경 오클루더 마스크
    """
    fh, fw = generated_frame.shape[:2]

    combined_mask = np.zeros((fh, fw), dtype=np.uint8)
    object_extent_bbox = anchor_bbox

    # ── 주 경로: DINO + Diff 하이브리드 ──
    log.info("=" * 55)
    log.info(f"객체 추출: DINO+Diff 하이브리드 (keyword='{keyword}')")
    log.info("=" * 55)
    hybrid_result = _diff_primary_extract(
        first_frame, generated_frame, keyword, anchor_bbox=anchor_bbox,
    )

    if hybrid_result is not None:
        combined_mask, object_extent_bbox = hybrid_result
        log.info(f"[Hybrid] 성공: bbox={object_extent_bbox}, "
                 f"mask={cv2.countNonZero(combined_mask)}px")
    else:
        # ── 폴백: 기존 DINO semantic diff analyze ──
        log.warning("[Hybrid] 실패 → DINO semantic diff 폴백 진행...")
        diff_result = _semantic_diff_analyze(
            first_frame, generated_frame, keyword, anchor_bbox=anchor_bbox,
        )

        if diff_result is not None:
            diff_bbox, fg_points = diff_result
            object_extent_bbox = diff_bbox
            log.info(f"[Fallback] 의미론적 추가 객체 발견 → SAM 세그먼트")
            combined_mask = _sam_segment(generated_frame, diff_bbox,
                                         fg_points=fg_points)
            combined_mask = _refine_mask(combined_mask, generated_frame,
                                         diff_bbox)
        else:
            # ── 최종 폴백: DINO 전체 객체 SAM ──
            log.warning("[Fallback] 실패 → DINO 전체 객체 SAM 폴백...")
            try:
                all_bboxes = _dino_detect(generated_frame, keyword)
                if anchor_bbox is not None:
                    scored = []
                    for bb in all_bboxes:
                        iou = _bbox_iou_xywh(bb, anchor_bbox)
                        center_dist = _bbox_center_distance_norm(
                            bb, anchor_bbox, fw, fh)
                        score = iou - center_dist
                        if center_dist <= 0.22 or iou > 0.01:
                            scored.append((score, bb))
                    if scored:
                        scored.sort(reverse=True, key=lambda x: x[0])
                        all_bboxes = [bb for _, bb in scored[:2]]
                        object_extent_bbox = all_bboxes[0]
                        log.info(f"anchor 기준 폴백 후보 축소: {all_bboxes}")
                elif all_bboxes:
                    object_extent_bbox = all_bboxes[0]
                for i, bb in enumerate(all_bboxes):
                    log.info(f"SAM 세그멘테이션 [{i+1}/{len(all_bboxes)}]: "
                             f"bbox={bb}")
                    mask_i = _sam_segment(generated_frame, bb)
                    mask_i = _refine_mask(mask_i, generated_frame, bb)
                    combined_mask = cv2.bitwise_or(combined_mask, mask_i)
                log.info(f"마스크 결합 완료: {len(all_bboxes)}개 객체")
            except Exception as e:
                log.error(f"폴백 DINO 탐지마저 실패했습니다: {e}")
                raise RuntimeError("객체를 추출할 수 없습니다.")

    if object_extent_bbox is None:
        coords0 = cv2.findNonZero(combined_mask)
        if coords0 is not None:
            object_extent_bbox = cv2.boundingRect(coords0)
        else:
            object_extent_bbox = (0, 0, fw, fh)

    static_occ_mask = _extract_static_occluder_mask(
        first_frame=first_frame,
        generated_frame=generated_frame,
        object_extent_bbox=object_extent_bbox,
        object_visible_mask=combined_mask,
    )

    # ── 사라진 전경 객체 감지 & static_occ에 병합 ──
    vanished_fg_mask = _extract_vanished_foreground_mask(
        first_frame=first_frame,
        generated_frame=generated_frame,
        object_visible_mask=combined_mask,
        object_extent_bbox=object_extent_bbox,
    )
    vanished_px = cv2.countNonZero(vanished_fg_mask)
    if vanished_px > 0:
        log.info(f"사라진 전경 객체 {vanished_px}px → static_occ에 병합")
        static_occ_mask = cv2.bitwise_or(static_occ_mask, vanished_fg_mask)

    # 그림자와 bbox 계산에서 객체 본체가 지나치게 줄지 않도록 erode를 완화한다.
    eroded_mask = cv2.erode(combined_mask, np.ones((3, 3), np.uint8), iterations=1)
    shadow_map = extract_shadow_map(first_frame, generated_frame, eroded_mask)

    shadow_binary = (shadow_map < 0.98).astype(np.uint8) * 255

    # static bbox support는 경계만 보조하고 넓은 보호 영역은 만들지 않도록 타이트하게 사용한다.
    static_bbox_support = cv2.dilate(static_occ_mask, np.ones((3, 3), np.uint8), iterations=1)
    merged = cv2.bitwise_or(combined_mask, shadow_binary)
    merged = cv2.bitwise_or(merged, static_bbox_support)

    coords = cv2.findNonZero(merged)
    bbox = (0, 0, fw, fh)
    if coords is not None:
        mx, my, mw, mh = cv2.boundingRect(coords)
        p = 14
        bbox = (max(0, mx - p), max(0, my - p),
                min(mw + 2 * p, fw - max(0, mx - p)),
                min(mh + 2 * p, fh - max(0, my - p)))

    log.info(f"최종 bbox(그림자 포함): {bbox}")
    log.info(f"정적 오클루더 마스크: {cv2.countNonZero(static_occ_mask)}px")
    cv2.imwrite(os.path.join(OUTPUTS, "step4_combined_mask.png"), combined_mask)
    cv2.imwrite(os.path.join(OUTPUTS, "step4_static_occ_mask.png"), static_occ_mask)
    cv2.imwrite(os.path.join(OUTPUTS, "step4_shadow_binary.png"), shadow_binary)
    return combined_mask, shadow_map, bbox, static_occ_mask


# ══════════════════════════════════════════════════════════════
# STEP 5 — 스케일링
# ══════════════════════════════════════════════════════════════
def step5_scale(f2, mask, shadow_map, bbox, vw, vh, static_occ_mask=None):
    gen_h, gen_w = f2.shape[:2]
    sx, sy = vw / gen_w, vh / gen_h
    gx, gy, gw, gh = bbox

    crop = f2[gy:gy + gh, gx:gx + gw].copy()
    mcrop = mask[gy:gy + gh, gx:gx + gw].copy()
    scrop = shadow_map[gy:gy + gh, gx:gx + gw].copy()
    ocrop = None if static_occ_mask is None else static_occ_mask[gy:gy + gh, gx:gx + gw].copy()

    crop = cv2.bitwise_and(crop, crop, mask=mcrop)

    vx, vy = int(gx * sx), int(gy * sy)
    vw_b, vh_b = max(1, int(gw * sx)), max(1, int(gh * sy))

    obj = cv2.resize(crop, (vw_b, vh_b), interpolation=cv2.INTER_LANCZOS4)
    ms = cv2.resize(mcrop, (vw_b, vh_b), interpolation=cv2.INTER_LINEAR)
    _, mr = cv2.threshold(ms, 128, 255, cv2.THRESH_BINARY)

    sr = cv2.resize(scrop, (vw_b, vh_b), interpolation=cv2.INTER_LINEAR)

    if ocrop is not None:
        osz = cv2.resize(ocrop, (vw_b, vh_b), interpolation=cv2.INTER_LINEAR)
        _, orr = cv2.threshold(osz, 128, 255, cv2.THRESH_BINARY)
    else:
        orr = np.zeros((vh_b, vw_b), dtype=np.uint8)

    log.info(f"스케일: 생성({gx},{gy},{gw},{gh}) → 영상({vx},{vy},{vw_b},{vh_b})")
    cv2.imwrite(os.path.join(OUTPUTS, "object_crop.png"), obj)
    cv2.imwrite(os.path.join(OUTPUTS, "mask_roi.png"), mr)
    cv2.imwrite(os.path.join(OUTPUTS, "static_occ_roi.png"), orr)
    return obj, mr, sr, orr, (vx, vy, vw_b, vh_b)



def _build_fridge_boundary_band(mask, outer_grow=7, inner_shrink=3):
    """냉장고 경계 중심의 좁은 band.
    오클루전 후보가 객체 전체를 덮어 aura처럼 퍼지지 않도록
    실제 접촉이 자주 일어나는 경계 부근만 우선 본다.
    """
    obj_bin = (mask > 0).astype(np.uint8) * 255
    k_out = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (outer_grow * 2 + 1, outer_grow * 2 + 1))
    k_in = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (inner_shrink * 2 + 1, inner_shrink * 2 + 1))
    outer = cv2.dilate(obj_bin, k_out, iterations=1)
    inner = cv2.erode(obj_bin, k_in, iterations=1)
    band = cv2.subtract(outer, inner)
    return band


def _merge_motion_with_edge_support(curr_roi, bg_roi, motion_mask):
    """사람/강아지 가장자리처럼 motion이 듬성듬성 끊기는 부분을 edge로 보강한다."""
    curr_gray = cv2.cvtColor(curr_roi, cv2.COLOR_BGR2GRAY)
    bg_gray = cv2.cvtColor(bg_roi, cv2.COLOR_BGR2GRAY)
    edge_curr = cv2.Canny(curr_gray, 60, 140)
    edge_bg = cv2.Canny(bg_gray, 60, 140)
    edge_diff = cv2.absdiff(edge_curr, edge_bg)
    edge_diff = cv2.dilate(edge_diff, np.ones((3, 3), np.uint8), iterations=1)
    supported = cv2.bitwise_or(motion_mask, cv2.bitwise_and(edge_diff, cv2.dilate(motion_mask, np.ones((9, 9), np.uint8), iterations=1)))
    supported = cv2.morphologyEx(supported, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=1)
    return supported


def _stabilize_small_fast_occluder(mask, near_obj_band, min_area=18):
    """강아지 다리/꼬리처럼 작은 component가 경계에서 사라지지 않게 보존한다."""
    if mask is None or mask.size == 0:
        return mask
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    out = np.zeros_like(mask)
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < min_area:
            continue
        comp = (labels == i).astype(np.uint8) * 255
        near = cv2.countNonZero(cv2.bitwise_and(comp, near_obj_band))
        if near <= 0 and area < 40:
            continue
        pad = 1 if area < 80 else 0
        if pad > 0:
            comp = cv2.dilate(comp, np.ones((3, 3), np.uint8), iterations=pad)
        out = cv2.bitwise_or(out, comp)
    return out


def _build_object_rings(mask, inner_erode=5, outer_dilate=14):
    """
    object mask 기준으로
    - inner_core: 실제 오클루전이 일어나야 하는 더 타이트한 객체 내부
    - enter_ring: 객체 바깥에서 안으로 들어오는지 보는 얇은 바깥 링
    - outer_expand: 디버깅용 외곽 확장 마스크
    를 만든다.
    """
    k_in = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (inner_erode * 2 + 1, inner_erode * 2 + 1)
    )
    k_out = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (outer_dilate * 2 + 1, outer_dilate * 2 + 1)
    )

    obj_bin = (mask > 0).astype(np.uint8) * 255
    inner_core = cv2.erode(obj_bin, k_in, iterations=1)
    outer_expand = cv2.dilate(obj_bin, k_out, iterations=1)
    enter_ring = cv2.subtract(outer_expand, obj_bin)

    return inner_core, enter_ring, outer_expand

def _build_dynamic_clip_mask(obj_mask, grow=8):
    """동적 오클루전 hard override용 clip mask.
    객체 경계 바로 바깥까지 약간 허용해 몸통이 경계에서 잘리지 않게 한다.
    """
    obj_bin = (obj_mask > 0).astype(np.uint8) * 255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (grow * 2 + 1, grow * 2 + 1))
    return cv2.dilate(obj_bin, k, iterations=1)


def _extract_motion_mask_from_static_bg(curr_roi, bg_roi):
    """
    고정 카메라 전제.
    뒤쪽 냉장고를 고정 자산처럼 두고, 앞을 지나는 사람/강아지만 뽑는 데 맞춘 motion mask.
    Lab 색차 + gray 차이 + edge support를 함께 사용해 torso hole과 작은 반려동물 경계를 덜 놓친다.
    """
    blur_curr = cv2.GaussianBlur(curr_roi, (5, 5), 0)
    blur_bg = cv2.GaussianBlur(bg_roi, (5, 5), 0)

    lab_curr = cv2.cvtColor(blur_curr, cv2.COLOR_BGR2Lab).astype(np.float32)
    lab_bg = cv2.cvtColor(blur_bg, cv2.COLOR_BGR2Lab).astype(np.float32)

    diff_l = cv2.absdiff(lab_curr[:, :, 0], lab_bg[:, :, 0])
    diff_a = cv2.absdiff(lab_curr[:, :, 1], lab_bg[:, :, 1])
    diff_b = cv2.absdiff(lab_curr[:, :, 2], lab_bg[:, :, 2])
    diff_ab = cv2.magnitude(diff_a, diff_b)

    gray_curr = cv2.cvtColor(blur_curr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gray_bg = cv2.cvtColor(blur_bg, cv2.COLOR_BGR2GRAY).astype(np.float32)
    diff_gray = cv2.absdiff(gray_curr, gray_bg)

    score = 0.18 * diff_l + 0.57 * diff_ab + 0.25 * diff_gray

    base = float(np.median(score))
    p88 = float(np.percentile(score, 88))
    thr = max(11.0, base + 5.2, p88 * 0.52)
    motion = (score >= thr).astype(np.uint8) * 255

    motion = cv2.morphologyEx(motion, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), iterations=1)
    motion = cv2.morphologyEx(motion, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=1)
    motion = _merge_motion_with_edge_support(curr_roi, bg_roi, motion)
    return motion


def _fill_holes_binary(mask, min_hole_area=12):
    """바이너리 마스크 내부 hole을 메운다. 동적 오클루더(사람/강아지) 전용."""
    if mask is None or mask.size == 0:
        return mask
    bin_mask = (mask > 0).astype(np.uint8) * 255
    h, w = bin_mask.shape[:2]
    ff = bin_mask.copy()
    flood = np.zeros((h + 2, w + 2), dtype=np.uint8)
    cv2.floodFill(ff, flood, (0, 0), 255)
    holes = cv2.bitwise_not(ff) & cv2.bitwise_not(bin_mask)

    if min_hole_area > 0:
        n, labels, stats, _ = cv2.connectedComponentsWithStats(holes, 8)
        keep = np.zeros_like(holes)
        for i in range(1, n):
            area = stats[i, cv2.CC_STAT_AREA]
            if area >= min_hole_area:
                keep[labels == i] = 255
        holes = keep

    filled = cv2.bitwise_or(bin_mask, holes)
    return filled


def _fill_component_solid(mask):
    """외곽 contour 기준으로 component 내부를 solid하게 채운다."""
    if mask is None or mask.size == 0:
        return mask
    bin_mask = (mask > 0).astype(np.uint8) * 255
    contours, _ = cv2.findContours(bin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(bin_mask)
    if contours:
        cv2.drawContours(filled, contours, -1, 255, thickness=cv2.FILLED)
    return filled


def _temporal_bridge_occ(prev_occ_bin, curr_occ_bin, motion_mask, dynamic_clip):
    """이전 프레임 오클루전을 이어주되, 현재 motion 근거가 있는 부분만 제한적으로 carry한다.
    핵심: 이전 오클루더가 객체 전체 위에 눌러앉아 냉장고 합성 자체가 풀리지 않게 한다.
    """
    if prev_occ_bin is None or prev_occ_bin.size == 0 or cv2.countNonZero(prev_occ_bin) == 0:
        return curr_occ_bin

    prev_grow = cv2.dilate(prev_occ_bin, np.ones((5, 5), np.uint8), iterations=1)
    curr_grow = cv2.dilate(curr_occ_bin, np.ones((5, 5), np.uint8), iterations=1) if cv2.countNonZero(curr_occ_bin) > 0 else np.zeros_like(prev_occ_bin)

    motion_near_prev = cv2.bitwise_and(
        cv2.dilate(motion_mask, np.ones((11, 11), np.uint8), iterations=1),
        cv2.dilate(prev_grow, np.ones((7, 7), np.uint8), iterations=1),
    )
    motion_support = cv2.bitwise_and(motion_mask, cv2.dilate(prev_grow, np.ones((9, 9), np.uint8), iterations=1))
    carry = cv2.bitwise_and(prev_grow, motion_near_prev)

    if cv2.countNonZero(curr_grow) > 0:
        carry = cv2.bitwise_and(carry, cv2.dilate(curr_grow, np.ones((11, 11), np.uint8), iterations=1))

    bridge = cv2.bitwise_or(curr_grow, motion_support)
    bridge = cv2.bitwise_or(bridge, carry)
    bridge = _fill_holes_binary(bridge, min_hole_area=10)
    bridge = cv2.morphologyEx(
        bridge,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
        iterations=1,
    )
    bridge = cv2.bitwise_and(bridge, dynamic_clip)
    return bridge


def _stabilize_dynamic_occ(prev_occ_bin, curr_occ_bin, motion_mask, dynamic_clip):
    """현재 마스크가 약해져도 이전 오클루더를 제한적으로만 유지한다.
    carry는 motion 근거가 있을 때만 허용해서 합성 객체 전체가 풀리는 것을 막는다.
    """
    if curr_occ_bin is None or curr_occ_bin.size == 0:
        return curr_occ_bin

    curr = (curr_occ_bin > 0).astype(np.uint8) * 255
    if prev_occ_bin is None or prev_occ_bin.size == 0 or cv2.countNonZero(prev_occ_bin) == 0:
        curr = _fill_component_solid(curr)
        curr = cv2.bitwise_and(curr, dynamic_clip)
        return curr

    prev = (prev_occ_bin > 0).astype(np.uint8) * 255
    overlap = cv2.bitwise_and(cv2.dilate(prev, np.ones((5, 5), np.uint8), iterations=1), curr)
    if cv2.countNonZero(overlap) > 0:
        carried = cv2.bitwise_and(
            cv2.dilate(prev, np.ones((3, 3), np.uint8), iterations=1),
            cv2.dilate(curr, np.ones((9, 9), np.uint8), iterations=1)
        )
        motion_gate = cv2.dilate(motion_mask, np.ones((9, 9), np.uint8), iterations=1)
        carried = cv2.bitwise_and(carried, motion_gate)
        motion_keep = cv2.bitwise_and(motion_mask, cv2.dilate(carried, np.ones((7, 7), np.uint8), iterations=1))
        curr = cv2.bitwise_or(curr, carried)
        curr = cv2.bitwise_or(curr, motion_keep)

    curr = _fill_holes_binary(curr, min_hole_area=10)
    curr = _fill_component_solid(curr)
    curr = cv2.bitwise_and(curr, dynamic_clip)
    return curr


def _expand_dynamic_components_locally(mask, max_expand=1, min_area=80):
    """큰 동적 component만 bbox 내부에서 1px 정도 국소 확장한다."""
    if mask is None or mask.size == 0:
        return mask
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    out = np.zeros_like(mask)
    k = np.ones((3, 3), np.uint8)
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < min_area:
            continue
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]
        comp = (labels == i).astype(np.uint8) * 255
        if area > 120 and max_expand > 0:
            roi = comp[y:y + h, x:x + w]
            roi = cv2.dilate(roi, k, iterations=max_expand)
            comp[y:y + h, x:x + w] = roi
        out = cv2.bitwise_or(out, comp)
    return out


def _select_occluder_mask(motion_mask, inner_core, enter_ring, obj_mask, min_area=120, boundary_band=None):
    """
    객체 바깥에서 안으로 실제로 진입하는 전경 컴포넌트만 채택한다.
    냉장고 앞을 지나는 사람/강아지에 맞춰 경계 부근 component를 우선하고,
    torso hole은 메우되 배경까지 넓게 퍼지지 않게 제한한다.
    """
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(motion_mask, 8)
    occ = np.zeros_like(motion_mask)

    obj_area = max(1, cv2.countNonZero(obj_mask))
    dyn_min_area = max(min_area, int(obj_area * 0.0012))
    obj_enter = cv2.dilate(obj_mask, np.ones((3, 3), np.uint8), iterations=1)
    obj_support = _build_dynamic_clip_mask(obj_mask, grow=FRIDGE_OCCLUSION_CFG["dynamic_clip_grow"])
    if boundary_band is None:
        boundary_band = _build_fridge_boundary_band(obj_mask, FRIDGE_OCCLUSION_CFG["boundary_band_outer"], FRIDGE_OCCLUSION_CFG["boundary_band_inner"])

    for i in range(1, n_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < dyn_min_area:
            continue

        comp = (labels == i).astype(np.uint8) * 255
        hit_outer = cv2.countNonZero(cv2.bitwise_and(comp, enter_ring))
        hit_inner = cv2.countNonZero(cv2.bitwise_and(comp, inner_core))
        hit_support = cv2.countNonZero(cv2.bitwise_and(comp, obj_enter))
        hit_band = cv2.countNonZero(cv2.bitwise_and(comp, boundary_band))
        if hit_outer < 1 or (hit_inner < 2 and hit_support < 6 and hit_band < 8):
            continue

        sx = stats[i, cv2.CC_STAT_LEFT]
        sy = stats[i, cv2.CC_STAT_TOP]
        sw = stats[i, cv2.CC_STAT_WIDTH]
        sh = stats[i, cv2.CC_STAT_HEIGHT]
        pad = 4
        x1 = max(0, sx - pad)
        y1 = max(0, sy - pad)
        x2 = min(comp.shape[1], sx + sw + pad)
        y2 = min(comp.shape[0], sy + sh + pad)

        comp_crop = comp[y1:y2, x1:x2]
        fill_area = max(8, int(area * 0.004))
        filled_crop = _fill_holes_binary(comp_crop, min_hole_area=fill_area)
        filled_crop = cv2.morphologyEx(filled_crop, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=1)

        comp_filled = np.zeros_like(comp)
        comp_filled[y1:y2, x1:x2] = filled_crop
        comp_supported = cv2.bitwise_and(comp_filled, obj_support)
        comp_supported = cv2.bitwise_or(comp_supported, cv2.bitwise_and(comp, obj_support))
        comp_supported = cv2.bitwise_or(comp_supported, cv2.bitwise_and(cv2.dilate(comp, np.ones((3, 3), np.uint8), iterations=1), boundary_band))
        if cv2.countNonZero(comp_supported) == 0:
            continue

        occ = cv2.bitwise_or(occ, comp_supported)

    occ = _stabilize_small_fast_occluder(occ, boundary_band, min_area=18)
    return occ


def _soften_occ_mask(occ_mask):
    # dynamic occ가 바깥으로 번지는 것을 줄이기 위해 soft blur를 더 타이트하게 적용
    occ_f = cv2.GaussianBlur(occ_mask.astype(np.float32) / 255.0, (5, 5), 0)
    occ_f = np.where(occ_f >= 0.070, occ_f, 0.0)
    occ_f = np.clip(occ_f, 0.0, 1.0)
    occ_f[occ_f < 0.050] = 0.0
    return occ_f


def _apply_hard_dynamic_occlusion(composited, original_roi, dyn_occ_bin):
    """동적 오클루전 복원.
    사람/강아지 실루엣을 충분히 되살리되, 객체 주변에 aura가 생기지 않도록 경계 feather 폭을 줄였다.
    """
    if dyn_occ_bin is None or dyn_occ_bin.size == 0 or cv2.countNonZero(dyn_occ_bin) == 0:
        return composited

    bin_mask = (dyn_occ_bin > 0).astype(np.uint8) * 255
    out = composited.astype(np.float32).copy()
    original_f = original_roi.astype(np.float32)

    solid_core = cv2.erode(bin_mask, np.ones((3, 3), np.uint8), iterations=1)
    out[solid_core > 0] = original_f[solid_core > 0]

    feather_band = cv2.dilate(bin_mask, np.ones((3, 3), np.uint8), iterations=1)
    feather_band = cv2.bitwise_and(feather_band, cv2.bitwise_not(solid_core))
    if cv2.countNonZero(feather_band) > 0:
        diff = np.mean(np.abs(original_f - composited.astype(np.float32)), axis=2)
        edge_penalty = np.clip(diff / 72.0, 0.0, 1.0)
        alpha = 0.18 + 0.42 * (1.0 - edge_penalty)
        alpha = np.clip(alpha, 0.16, 0.58)
        alpha *= (feather_band > 0).astype(np.float32)
        alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
        alpha = alpha[..., None]
        out = out * (1.0 - alpha) + original_f * alpha

    return np.clip(out, 0, 255).astype(np.uint8)


# ═══════════════════════════════════════════════════════════════════
# Semantic Occlusion: DINO+SAM per-keyframe + Optical Flow 보간
# ═══════════════════════════════════════════════════════════════════
_OCCLUDER_KEYWORDS = "person . people . dog . cat ."


def _detect_foreground_occluders(frame, roi_bbox, obj_mask_roi):
    """
    DINO+SAM으로 현재 프레임에서 전경 오클루더(사람, 동물 등)를 검출·세그멘테이션한다.
    원본 프레임에서 동작하므로 합성 객체를 잘못 검출할 위험이 없다.

    Args:
        frame:        전체 원본 프레임 (BGR)
        roi_bbox:     (x, y, w, h) — 합성 영역 (프레임 좌표계)
        obj_mask_roi: 합성 객체 바이너리 마스크 (ROI 로컬 좌표)

    Returns:
        occluder_mask: ROI 로컬 좌표의 오클루더 바이너리 마스크 (uint8, 0/255)
    """
    rx, ry, rw, rh = roi_bbox
    fh, fw = frame.shape[:2]
    roi_h, roi_w = obj_mask_roi.shape[:2]

    # 접근 중인 오클루더도 잡기 위해 검색 영역을 ROI보다 넓게 확장
    margin = max(rw, rh) // 3
    sx1, sy1 = max(0, rx - margin), max(0, ry - margin)
    sx2, sy2 = min(fw, rx + rw + margin), min(fh, ry + rh + margin)
    search_region = frame[sy1:sy2, sx1:sx2]
    sh, sw = search_region.shape[:2]

    # ── DINO 검출 ──
    model = _get_cached_dino_model()
    tmp_path = os.path.join(OUTPUTS, "_occ_dino_tmp.jpg")
    cv2.imwrite(tmp_path, search_region)
    _, tensor = gdino_load_image(tmp_path)
    try:
        os.remove(tmp_path)
    except OSError:
        pass

    boxes, logits, phrases = gdino_predict(
        model, tensor, _OCCLUDER_KEYWORDS,
        box_threshold=0.30, text_threshold=0.25,
    )

    if len(boxes) == 0:
        return np.zeros((roi_h, roi_w), dtype=np.uint8)

    # ROI bbox → search region 좌표계
    rix1, riy1 = rx - sx1, ry - sy1
    rix2, riy2 = rix1 + rw, riy1 + rh

    # ── SAM 세그멘테이션 ──
    predictor = _get_cached_sam_predictor()
    rgb = cv2.cvtColor(search_region, cv2.COLOR_BGR2RGB)
    predictor.set_image(rgb)

    combined = np.zeros((sh, sw), dtype=np.uint8)

    for i in range(len(boxes)):
        if logits[i].item() < 0.25:
            continue

        cx, cy, bw, bh = boxes[i].cpu().numpy()
        bx1 = max(0, int((cx - bw / 2) * sw))
        by1 = max(0, int((cy - bh / 2) * sh))
        bx2 = min(sw, int((cx + bw / 2) * sw))
        by2 = min(sh, int((cy + bh / 2) * sh))

        # ROI와 겹치지 않는 검출은 스킵 (불필요한 SAM 호출 방지)
        if min(bx2, rix2) <= max(bx1, rix1) or min(by2, riy2) <= max(by1, riy1):
            continue

        box_arr = np.array([bx1, by1, bx2, by2])

        if SAM_VER == "sam2":
            masks, scores, _ = predictor.predict(
                box=box_arr, multimask_output=True,
            )
        else:
            center_x, center_y = (bx1 + bx2) // 2, (by1 + by2) // 2
            masks, scores, _ = predictor.predict(
                point_coords=np.array([[center_x, center_y]]),
                point_labels=np.array([1]),
                box=box_arr[None, :],
                multimask_output=True,
            )

        best = (masks[np.argmax(scores)] * 255).astype(np.uint8)
        combined = cv2.bitwise_or(combined, best)

    # search region 좌표 → ROI 로컬 좌표로 크롭
    result = np.zeros((roi_h, roi_w), dtype=np.uint8)
    cy1 = max(0, riy1)
    cy2 = min(sh, riy1 + roi_h)
    cx1 = max(0, rix1)
    cx2 = min(sw, rix1 + roi_w)
    dy1, dy2 = cy1 - riy1, (cy1 - riy1) + (cy2 - cy1)
    dx1, dx2 = cx1 - rix1, (cx1 - rix1) + (cx2 - cx1)
    result[dy1:dy2, dx1:dx2] = combined[cy1:cy2, cx1:cx2]

    return result


def _warp_mask_optical_flow(prev_mask, prev_gray, curr_gray):
    """
    Dense optical flow(Farneback)로 이전 프레임의 마스크를 현재 프레임에 warp한다.
    keyframe 사이 프레임에서 마스크를 보간하는 데 사용.
    """
    if prev_mask is None or cv2.countNonZero(prev_mask) == 0:
        return np.zeros_like(prev_gray, dtype=np.uint8)

    # backward flow: curr의 각 픽셀이 prev의 어디에서 왔는지
    flow = cv2.calcOpticalFlowFarneback(
        curr_gray, prev_gray, None,
        pyr_scale=0.5, levels=4, winsize=15,
        iterations=3, poly_n=7, poly_sigma=1.5, flags=0,
    )
    h, w = curr_gray.shape[:2]
    map_y, map_x = np.mgrid[:h, :w].astype(np.float32)
    map_x += flow[:, :, 0]
    map_y += flow[:, :, 1]

    warped = cv2.remap(
        prev_mask, map_x, map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT, borderValue=0,
    )
    _, warped_bin = cv2.threshold(warped, 100, 255, cv2.THRESH_BINARY)
    # 작은 노이즈 제거
    warped_bin = cv2.morphologyEx(
        warped_bin, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
        iterations=1,
    )
    return warped_bin


def _build_soft_occlusion_alpha(occluder_mask, feather_px=5):
    """
    바이너리 오클루더 마스크 → distance-transform 기반 soft alpha.
    erode/dilate 대신 distance transform을 사용해 복잡한 형상(머리카락 등)의
    경계를 자연스럽게 처리한다.

    Returns:
        float32 [0, 1].  1.0 = 원본 복원(오클루더),  0.0 = 합성 유지
    """
    if occluder_mask is None or cv2.countNonZero(occluder_mask) == 0:
        return np.zeros(occluder_mask.shape[:2], dtype=np.float32)

    dist_in = cv2.distanceTransform(occluder_mask, cv2.DIST_L2, 5)
    dist_out = cv2.distanceTransform(255 - occluder_mask, cv2.DIST_L2, 5)
    signed = dist_in - dist_out

    alpha = np.clip((signed + feather_px) / (2.0 * feather_px), 0.0, 1.0)
    return alpha.astype(np.float32)


def _apply_semantic_occlusion(composited, original_roi, occ_alpha):
    """
    soft alpha를 사용하여 오클루더 영역에 원본 픽셀을 복원한다.

    composited:   합성된 ROI (float32, BGR)
    original_roi: 원본 프레임 ROI (float32, BGR)
    occ_alpha:    float32 [0,1]  —  0=합성유지, 1=원본복원
    """
    if occ_alpha is None or occ_alpha.max() < 0.01:
        return composited
    a3 = np.stack([occ_alpha] * 3, axis=-1)
    return composited * (1.0 - a3) + original_roi * a3


def _step6_composite_pixel_diff(vpath, obj, mr, sr, static_occ_r, vbbox, opath):
    """[LEGACY] 픽셀 diff 기반 동적 오클루전. step6_composite에서 대체됨."""
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

    roi_h, roi_w = y2 - y1, x2 - x1

    fg = obj[oy1:oy2, ox1:ox2].astype(np.float32)
    cm = mr[oy1:oy2, ox1:ox2].copy()
    clip_shadow = sr[oy1:oy2, ox1:ox2].copy()
    static_occ = static_occ_r[oy1:oy2, ox1:ox2].copy() if static_occ_r is not None else np.zeros((roi_h, roi_w), dtype=np.uint8)

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    ret, first_frame = cap.read()
    if not ret:
        cap.release()
        out.release()
        raise RuntimeError("첫 프레임 읽기 실패")

    bg_roi = first_frame[y1:y2, x1:x2].copy()

    alpha = cv2.GaussianBlur(cm.astype(np.float32) / 255.0, (0, 0), sigmaX=1.35)
    inner = cv2.erode(cm, np.ones((3, 3), np.uint8), iterations=2)
    alpha[inner > 0] = 1.0
    alpha = np.clip(alpha, 0.0, 1.0)
    a3 = np.stack([alpha] * 3, axis=-1)

    shadow = np.clip(clip_shadow.astype(np.float32), 0.0, 1.0)
    s3 = np.stack([shadow] * 3, axis=-1)

    static_occ_bin = (static_occ > 0).astype(np.float32)
    static_occ_3 = np.stack([static_occ_bin] * 3, axis=-1)

    inner_core, enter_ring, outer_expand = _build_object_rings(
        cm,
        inner_erode=FRIDGE_OCCLUSION_CFG["ring_inner_erode"],
        outer_dilate=FRIDGE_OCCLUSION_CFG["ring_outer_dilate"],
    )
    boundary_band = _build_fridge_boundary_band(
        cm,
        outer_grow=FRIDGE_OCCLUSION_CFG["boundary_band_outer"],
        inner_shrink=FRIDGE_OCCLUSION_CFG["boundary_band_inner"],
    )
    dynamic_clip = _build_dynamic_clip_mask(cm, grow=FRIDGE_OCCLUSION_CFG["dynamic_clip_grow"])

    log.info(f"합성: {vw}×{vh} {fps:.0f}fps {total}f")
    log.info("[OCCLUSION] fridge-behind-object mode: fixed fridge asset + front occluder restore")

    prev_occ_float = np.zeros((roi_h, roi_w), dtype=np.float32)
    prev_occ_bin = np.zeros((roi_h, roi_w), dtype=np.uint8)
    occ_active = False
    occ_on_count = 0
    occ_off_count = 0
    OCC_ON_FRAMES = FRIDGE_OCCLUSION_CFG["occ_on_frames"]
    OCC_OFF_FRAMES = FRIDGE_OCCLUSION_CFG["occ_off_frames"]

    n = 0
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        original_roi = frame[y1:y2, x1:x2].astype(np.float32)

        composited = original_roi * s3
        composited = fg * a3 + composited * (1.0 - a3)
        composited = composited * (1.0 - static_occ_3) + original_roi * static_occ_3

        curr_roi_u8 = frame[y1:y2, x1:x2]
        motion_mask = _extract_motion_mask_from_static_bg(curr_roi_u8, bg_roi)
        motion_mask = cv2.bitwise_and(
            motion_mask,
            cv2.dilate(outer_expand, np.ones((FRIDGE_OCCLUSION_CFG["motion_keep_near_obj_kernel"], FRIDGE_OCCLUSION_CFG["motion_keep_near_obj_kernel"]), np.uint8), iterations=1),
        )

        occ_mask = _select_occluder_mask(
            motion_mask=motion_mask,
            inner_core=inner_core,
            enter_ring=enter_ring,
            obj_mask=cm,
            min_area=FRIDGE_OCCLUSION_CFG["motion_min_area"],
            boundary_band=boundary_band,
        )

        static_protect = cv2.erode(static_occ, np.ones((3, 3), np.uint8), iterations=1)
        occ_mask = cv2.bitwise_and(occ_mask, cv2.bitwise_not(static_protect))
        occ_pixels = cv2.countNonZero(occ_mask)

        if occ_pixels > 0:
            occ_on_count += 1
            occ_off_count = 0
        else:
            occ_off_count += 1
            occ_on_count = 0

        if not occ_active and occ_on_count >= OCC_ON_FRAMES:
            occ_active = True
        if occ_active and occ_off_count >= OCC_OFF_FRAMES:
            occ_active = False

        curr_occ_float = np.zeros((roi_h, roi_w), dtype=np.float32)
        curr_occ_bin = np.zeros((roi_h, roi_w), dtype=np.uint8)
        occ_candidate = occ_active or (cv2.countNonZero(prev_occ_bin) > 0 and occ_off_count <= 1)

        if occ_candidate:
            curr_occ_float = _soften_occ_mask(occ_mask)
            curr_occ_bin = (curr_occ_float > 0.045).astype(np.uint8) * 255

            motion_support = cv2.bitwise_and(
                motion_mask,
                cv2.dilate(curr_occ_bin, np.ones((9, 9), np.uint8), iterations=1)
            )
            boundary_support = cv2.bitwise_and(
                cv2.dilate(motion_support, np.ones((3, 3), np.uint8), iterations=1),
                boundary_band
            )
            temporal_bridge = _temporal_bridge_occ(prev_occ_bin, curr_occ_bin, motion_mask, dynamic_clip)

            curr_occ_bin = cv2.bitwise_or(curr_occ_bin, motion_support)
            curr_occ_bin = cv2.bitwise_or(curr_occ_bin, boundary_support)
            curr_occ_bin = cv2.bitwise_or(curr_occ_bin, temporal_bridge)
            curr_occ_bin = _fill_holes_binary(curr_occ_bin, min_hole_area=8)
            curr_occ_bin = cv2.morphologyEx(curr_occ_bin, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=1)
            curr_occ_bin = _stabilize_small_fast_occluder(curr_occ_bin, boundary_band, min_area=18)
            curr_occ_bin = _stabilize_dynamic_occ(prev_occ_bin, curr_occ_bin, motion_mask, dynamic_clip)
            curr_occ_bin = cv2.bitwise_and(curr_occ_bin, dynamic_clip)
            curr_occ_float = _soften_occ_mask(curr_occ_bin)

        if cv2.countNonZero(curr_occ_bin) > 0:
            t_alpha = 0.82 if curr_occ_float.max() >= prev_occ_float.max() else 0.62
            occ_float = t_alpha * curr_occ_float + (1.0 - t_alpha) * prev_occ_float
        else:
            decay = FRIDGE_OCCLUSION_CFG["temporal_decay_hold"] if occ_off_count == 0 else FRIDGE_OCCLUSION_CFG["temporal_decay_release"]
            occ_float = prev_occ_float * decay

        clip_gate = cv2.GaussianBlur((dynamic_clip > 0).astype(np.float32), (5, 5), 0)
        occ_float = np.minimum(occ_float, clip_gate)
        occ_float[occ_float < 0.040] = 0.0

        prev_occ_float = occ_float.copy()
        prev_occ_bin = (occ_float > FRIDGE_OCCLUSION_CFG["occ_float_bin_thr"]).astype(np.uint8) * 255

        dyn_occ_bin_final = (occ_float > FRIDGE_OCCLUSION_CFG["occ_final_bin_thr"]).astype(np.uint8) * 255
        dyn_occ_bin_final = cv2.bitwise_or(dyn_occ_bin_final, curr_occ_bin)
        dyn_occ_bin_final = cv2.bitwise_or(
            dyn_occ_bin_final,
            cv2.bitwise_and(motion_mask, cv2.dilate(dyn_occ_bin_final, np.ones((5, 5), np.uint8), iterations=1))
        )
        dyn_occ_bin_final = _fill_holes_binary(dyn_occ_bin_final, min_hole_area=8)
        dyn_occ_bin_final = cv2.morphologyEx(dyn_occ_bin_final, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=1)
        dyn_occ_bin_final = _stabilize_small_fast_occluder(dyn_occ_bin_final, boundary_band, min_area=18)
        if cv2.countNonZero(curr_occ_bin) > 0:
            dyn_occ_bin_final = _stabilize_dynamic_occ(prev_occ_bin, dyn_occ_bin_final, motion_mask, dynamic_clip)
        dyn_occ_bin_final = cv2.bitwise_and(dyn_occ_bin_final, dynamic_clip)
        if cv2.countNonZero(dyn_occ_bin_final) > 0:
            dyn_occ_bin_final = _fill_holes_binary(dyn_occ_bin_final, min_hole_area=6)

        final_roi = _apply_hard_dynamic_occlusion(composited, original_roi, dyn_occ_bin_final)
        frame[y1:y2, x1:x2] = np.clip(final_roi, 0, 255).astype(np.uint8)
        out.write(frame)

        if n % 15 == 0:
            outer_px = cv2.countNonZero(cv2.bitwise_and(motion_mask, outer_expand))
            log.info(
                f"[f{n}] motion={cv2.countNonZero(motion_mask)}px, "
                f"near_obj={outer_px}px, static_occ={cv2.countNonZero(static_occ)}px, "
                f"occ={occ_pixels}px, active={occ_active}, on={occ_on_count}, off={occ_off_count}, "
                f"curr_dyn={cv2.countNonZero(curr_occ_bin)}px, final_dyn={cv2.countNonZero(dyn_occ_bin_final)}px"
            )

        n += 1

    cap.release()
    out.release()
    log.info(f"완료: {n}f → {opath}")


def step6_composite(vpath, obj, mr, sr, static_occ_r, vbbox, opath):
    """
    프레임별 합성 + Semantic 동적 오클루전.

    매 keyframe마다 DINO+SAM으로 전경 오클루더(사람, 동물)를 정밀 검출하고,
    중간 프레임은 optical flow로 마스크를 보간한다.
    경계는 distance-transform 기반 soft alpha로 자연스럽게 블렌딩한다.
    """
    cap = cv2.VideoCapture(vpath)
    vw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out = cv2.VideoWriter(opath, cv2.VideoWriter_fourcc(*'mp4v'), fps, (vw, vh))

    bx, by, bw, bh = vbbox
    y1, y2 = max(0, by), min(vh, by + bh)
    x1, x2 = max(0, bx), min(vw, bx + bw)
    oy1 = y1 - by
    oy2 = bh - (by + bh - y2)
    ox1 = x1 - bx
    ox2 = bw - (bx + bw - x2)

    roi_h, roi_w = y2 - y1, x2 - x1

    fg = obj[oy1:oy2, ox1:ox2].astype(np.float32)
    cm = mr[oy1:oy2, ox1:ox2].copy()
    clip_shadow = sr[oy1:oy2, ox1:ox2].copy()
    static_occ = (
        static_occ_r[oy1:oy2, ox1:ox2].copy()
        if static_occ_r is not None
        else np.zeros((roi_h, roi_w), dtype=np.uint8)
    )

    # ── 알파 / 그림자 / 정적 오클루전 (기존과 동일) ──
    alpha = cv2.GaussianBlur(cm.astype(np.float32) / 255.0, (0, 0), sigmaX=1.35)
    inner = cv2.erode(cm, np.ones((3, 3), np.uint8), iterations=2)
    alpha[inner > 0] = 1.0
    alpha = np.clip(alpha, 0.0, 1.0)
    a3 = np.stack([alpha] * 3, axis=-1)

    shadow = np.clip(clip_shadow.astype(np.float32), 0.0, 1.0)
    s3 = np.stack([shadow] * 3, axis=-1)

    static_occ_bin = (static_occ > 0).astype(np.float32)
    static_occ_3 = np.stack([static_occ_bin] * 3, axis=-1)

    # ── Semantic occlusion 설정 ──
    keyframe_interval = max(1, min(5, int(fps / 10)))
    feather_px = max(3, int(min(roi_w, roi_h) * 0.015))
    max_stale_frames = int(fps * 0.5)

    log.info(f"합성: {vw}×{vh} {fps:.1f}fps {total}f")
    log.info(
        f"[OCCLUSION] Semantic DINO+SAM mode: "
        f"keyframe_interval={keyframe_interval}, feather={feather_px}px, "
        f"max_stale={max_stale_frames}f"
    )

    # ── 상태 변수 ──
    prev_occ_mask = np.zeros((roi_h, roi_w), dtype=np.uint8)
    prev_occ_alpha = np.zeros((roi_h, roi_w), dtype=np.float32)
    prev_gray = None
    frames_since_detection = 999

    n = 0
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        original_roi = frame[y1:y2, x1:x2].astype(np.float32)
        curr_roi_u8 = frame[y1:y2, x1:x2]

        # ── 기본 합성 (객체 + 그림자 + 정적 오클루전) ──
        composited = original_roi * s3
        composited = fg * a3 + composited * (1.0 - a3)
        composited = composited * (1.0 - static_occ_3) + original_roi * static_occ_3

        # ── 동적 오클루전: Semantic 방식 ──
        curr_gray = cv2.cvtColor(curr_roi_u8, cv2.COLOR_BGR2GRAY)
        is_keyframe = (n % keyframe_interval == 0)

        if is_keyframe:
            # DINO+SAM 으로 정밀 검출
            try:
                detected = _detect_foreground_occluders(
                    frame, (x1, y1, roi_w, roi_h), cm,
                )
            except Exception as e:
                log.warning(f"[f{n}] DINO+SAM 오류 (스킵): {e}")
                detected = np.zeros((roi_h, roi_w), dtype=np.uint8)

            if cv2.countNonZero(detected) > 0:
                occluder_mask = detected
                frames_since_detection = 0
            elif cv2.countNonZero(prev_occ_mask) > 0 and prev_gray is not None:
                # keyframe이지만 미검출 → 이전 마스크를 flow로 유지
                occluder_mask = _warp_mask_optical_flow(
                    prev_occ_mask, prev_gray, curr_gray,
                )
                frames_since_detection += 1
            else:
                occluder_mask = np.zeros((roi_h, roi_w), dtype=np.uint8)
                frames_since_detection += 1
        else:
            # 비-keyframe: 이전 마스크를 optical flow로 warp
            if cv2.countNonZero(prev_occ_mask) > 0 and prev_gray is not None:
                occluder_mask = _warp_mask_optical_flow(
                    prev_occ_mask, prev_gray, curr_gray,
                )
                frames_since_detection += 1
            else:
                occluder_mask = np.zeros((roi_h, roi_w), dtype=np.uint8)
                frames_since_detection += 1

        # Stale mask decay: 장시간 미검출 시 마스크 축소
        if (
            frames_since_detection > max_stale_frames
            and cv2.countNonZero(occluder_mask) > 0
        ):
            occluder_mask = cv2.erode(
                occluder_mask,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
                iterations=1,
            )

        # ── Soft alpha 생성 + 시간적 스무딩 ──
        occ_alpha = _build_soft_occlusion_alpha(occluder_mask, feather_px=feather_px)

        if cv2.countNonZero(occluder_mask) > 0:
            # 오클루더 존재: 현재 alpha 우선, 이전 잔여와 max 병합
            occ_alpha = np.maximum(occ_alpha, prev_occ_alpha * 0.25)
        else:
            # 오클루더 사라짐: 빠르게 감쇠
            occ_alpha = prev_occ_alpha * 0.20

        prev_occ_alpha = occ_alpha.copy()
        prev_occ_mask = occluder_mask.copy()
        prev_gray = curr_gray.copy()

        # ── 오클루전 적용 ──
        final_roi = _apply_semantic_occlusion(composited, original_roi, occ_alpha)
        frame[y1:y2, x1:x2] = np.clip(final_roi, 0, 255).astype(np.uint8)
        out.write(frame)

        if n % 15 == 0:
            occ_px = cv2.countNonZero(occluder_mask)
            alpha_max = float(occ_alpha.max()) if occ_alpha is not None else 0.0
            log.info(
                f"[f{n}] {'KEY' if is_keyframe else 'flow'} "
                f"occ={occ_px}px alpha_max={alpha_max:.2f} "
                f"stale={frames_since_detection}f "
                f"static={cv2.countNonZero(static_occ)}px"
            )

        n += 1

    cap.release()
    out.release()
    _release_cached_models()
    log.info(f"완료: {n}f → {opath}")


# ══════════════════════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════════════════════
def main():
    user_prompt = step1_prompt()

    log.info("─" * 45)
    log.info("STEP 2 — 자동 파일 탐색 + 키워드 추출")
    try:
        vpath, obj_img_path, kw = step2_auto_detect(user_prompt)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return

    log.info("─" * 45)
    log.info("STEP 3 — Gemini API (changed_first_frame 생성)")
    try:
        f1, f2 = step3_gemini(vpath, obj_img_path, kw, user_prompt)
    except RuntimeError as e:
        print(f"❌ {e}")
        return

    cap = cv2.VideoCapture(vpath)
    vw, vh = int(cap.get(3)), int(cap.get(4))
    cap.release()

    log.info("─" * 45)
    log.info("STEP 4 — DINO + SAM 객체 추출")
    mask, shadow_map, bbox, static_occ_mask = step4_extract(f1, f2, kw)

    log.info("─" * 45)
    log.info("STEP 5 — 스케일링")
    obj, mr, sr, static_occ_r, vbbox = step5_scale(f2, mask, shadow_map, bbox, vw, vh, static_occ_mask=static_occ_mask)

    log.info("─" * 45)
    log.info("STEP 6 — 합성")
    opath = os.path.join(OUTPUTS, "output_composited.mp4")
    step6_composite(vpath, obj, mr, sr, static_occ_r, vbbox, opath)

    print()
    print("=" * 55)
    print("  ✅ 합성 완료!")
    print(f"  출력: {opath}")
    print("=" * 55)


def _call_gemini_once(first_pil, obj_pil, kw, w1, h1, user_prompt="", quality_desc=""):
    """Gemini API를 1회 호출하여 합성 이미지(cv2 ndarray)를 반환한다."""
    gemini_prompt = _build_gemini_prompt(kw, w1, h1, user_prompt, quality_desc)

    for attempt in range(5):
        log.info(f"Gemini API (시도 {attempt+1}/5)...")
        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[gemini_prompt, first_pil, obj_pil],
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                ),
            )
            result_pil = _extract_image_from_response(response)
            if result_pil is not None:
                return _pil_to_cv2(result_pil)
            raise RuntimeError("Gemini 응답에 이미지 없음")
        except Exception as e:
            err_str = str(e)
            log.warning(f"시도 {attempt+1} 실패: {err_str[:200]}")
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                is_daily, wait = _parse_rate_limit_error(err_str)
                if is_daily:
                    raise RuntimeError(
                        "❌ Gemini API 일일 무료 할당량이 소진되었습니다.\n"
                        "  해결 방법:\n"
                        "  1) 내일 다시 시도\n"
                        "  2) 다른 API Key 사용\n"
                        "  3) Google AI Studio에서 유료 플랜 활성화"
                    )
                log.info(f"분당 Rate limit — {wait:.0f}초 대기 후 재시도...")
                import time; time.sleep(wait)
            elif attempt < 4:
                import time; time.sleep(5)
    raise RuntimeError("Gemini API 5회 실패")


def generate_previews(video_path, obj_img_path, user_prompt, count=3, on_progress=None, dino_keyword=None):
    """
    Gemini를 count회 호출하여 프리뷰 이미지 리스트를 반환한다.

    Args:
        video_path: 영상 파일 경로
        obj_img_path: 합성할 객체 이미지 경로
        user_prompt: 사용자 프롬프트
        count: 생성할 프리뷰 개수 (기본 3)
        on_progress: 진행률 콜백 (stage, percent, message)
        dino_keyword: GMS에서 추출한 DINO용 영어 키워드 (None이면 기존 사전 폴백)

    Returns:
        list[str]: 저장된 프리뷰 이미지 경로 리스트
    """
    def _p(stage, percent, message):
        if on_progress:
            on_progress(stage, percent, message)

    if gemini_client is None:
        raise RuntimeError("Gemini API 미설정")

    # 키워드: GMS 추출 우선, 없으면 기존 사전 폴백
    if dino_keyword:
        kw = dino_keyword
        log.info(f"DINO 키워드 (GMS): '{kw}'")
    else:
        _, _, kw = step2_auto_detect(user_prompt)

    # 첫 프레임 추출
    cap = cv2.VideoCapture(video_path)
    ret, f1 = cap.read()
    cap.release()
    if not ret:
        raise IOError("첫 프레임 읽기 실패")

    h1, w1 = f1.shape[:2]
    first_pil = _cv2_to_pil(f1, max_side=1280)
    obj_pil = _load_obj_as_pil(obj_img_path, max_side=512)
    quality_desc = _analyze_frame_for_prompt(f1)

    preview_paths = []
    for i in range(count):
        pct = int(10 + (80 * i / count))
        _p("GEMINI", pct, f"Gemini 모델이 프리뷰 이미지를 생성하는 중입니다... ({i+1}/{count})")
        try:
            img = _call_gemini_once(first_pil, obj_pil, kw, w1, h1, user_prompt, quality_desc)
            path = os.path.join(OUTPUTS, f"preview_{i}.png")
            cv2.imwrite(path, img)
            preview_paths.append(path)
            log.info(f"프리뷰 {i+1}/{count} 생성 완료: {img.shape[1]}x{img.shape[0]}")
        except Exception as e:
            log.warning(f"프리뷰 {i+1}/{count} 생성 실패 (스킵): {e}")

    if not preview_paths:
        raise RuntimeError("모든 프리뷰 생성 실패")

    _p("GEMINI", 90, f"프리뷰 이미지 생성 완료 ({len(preview_paths)}/{count}장)")
    return preview_paths


def run_composite(video_path, selected_preview_path, user_prompt, output_path, on_progress=None, dino_keyword=None):
    """
    선택된 프리뷰 이미지를 기반으로 합성 파이프라인을 실행한다.

    Args:
        video_path: 원본 영상 경로
        selected_preview_path: 선택된 프리뷰 이미지 경로 (changed_first_frame)
        user_prompt: 사용자 프롬프트
        output_path: 결과 영상 저장 경로
        on_progress: 진행률 콜백 (stage, percent, message)
        dino_keyword: GMS에서 추출한 DINO용 영어 키워드 (None이면 기존 사전 폴백)
    """
    def _p(stage, percent, message):
        if on_progress:
            on_progress(stage, percent, message)

    # 키워드: GMS 추출 우선, 없으면 기존 사전 폴백
    if dino_keyword:
        kw = dino_keyword
        log.info(f"DINO 키워드 (GMS): '{kw}'")
    else:
        _, _, kw = step2_auto_detect(user_prompt)

    # 첫 프레임 + 선택된 프리뷰 이미지 로드
    cap = cv2.VideoCapture(video_path)
    ret, f1 = cap.read()
    vw, vh = int(cap.get(3)), int(cap.get(4))
    cap.release()
    if not ret:
        raise IOError("첫 프레임 읽기 실패")

    f2 = cv2.imread(selected_preview_path)
    if f2 is None:
        raise IOError(f"프리뷰 이미지 로드 실패: {selected_preview_path}")

    _p("DINO", 15, "Grounding DINO 모델이 객체를 탐지하는 중입니다...")
    preview_anchor_bbox = _compute_preview_anchor_bbox(f1, f2, kw)
    if preview_anchor_bbox is not None:
        log.info(f"preview anchor bbox 재사용: {preview_anchor_bbox}")
    _p("SAM", 25, "SAM 모델이 정밀 마스크를 추출하는 중입니다...")
    mask, shadow_map, bbox, static_occ_mask = step4_extract(f1, f2, kw, anchor_bbox=preview_anchor_bbox)

    _p("SHADOW", 35, "그림자 맵을 생성하는 중입니다...")
    _p("SCALE", 40, "객체 스케일링을 처리하는 중입니다...")
    obj, mr, sr, static_occ_r, vbbox = step5_scale(f2, mask, shadow_map, bbox, vw, vh, static_occ_mask=static_occ_mask)

    _p("DEPTH", 45, "DPT 모델이 깊이를 추정하는 중입니다...")
    _p("COMPOSITE", 50, "프레임별 합성을 진행하는 중입니다...")
    step6_composite(video_path, obj, mr, sr, static_occ_r, vbbox, output_path)
    _p("COMPOSITE", 85, "합성 완료")

    log.info(f"run_composite 완료 → {output_path}")


if __name__ == "__main__":
    main()
