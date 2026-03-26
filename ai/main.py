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

def _semantic_diff_analyze(first_frame, generated_frame, keyword):
    """
    단순 전역 픽셀 비교가 아닌 의미론적(Semantic) 비교를 수행한다.
    1. DINO를 사용하여 합성 이미지에서 객체 후보(BBox)들을 찾는다.
    2. 각 후보 BBox 내부에서만 원본 대비 픽셀 변화량을 측정한다.
    3. 전역 조명 변화/배경 노이즈를 무시하고 실질적으로 '새롭게 등장한' 객체를 확정한다.
    """
    h1, w1 = first_frame.shape[:2]
    h2, w2 = generated_frame.shape[:2]
    if (h1, w1) != (h2, w2):
        f1_align = cv2.resize(first_frame, (w2, h2), interpolation=cv2.INTER_AREA)
    else:
        f1_align = first_frame

    log.info(f"의미론적 객체 탐색: '{keyword}' 후보 찾는 중...")
    try:
        bboxes = _dino_detect(generated_frame, keyword)
    except Exception as e:
        log.warning(f"DINO가 합성 프레임에서 '{keyword}' 탐지 실패: {e}")
        return None

    if not bboxes:
        return None

    # 미세 노이즈 무시를 위해 약간의 블러 적용 후 Lab 색 공간 비교
    blur1 = cv2.GaussianBlur(f1_align, (11, 11), 0)
    blur2 = cv2.GaussianBlur(generated_frame, (11, 11), 0)
    lab1 = cv2.cvtColor(blur1, cv2.COLOR_BGR2Lab).astype(np.float32)
    lab2 = cv2.cvtColor(blur2, cv2.COLOR_BGR2Lab).astype(np.float32)
    diff_map = np.sqrt(np.sum((lab1 - lab2) ** 2, axis=2))

    best_score = -1
    best_bbox = None
    best_fg_points = []

    for i, bb in enumerate(bboxes):
        x, y, w, h = bb
        roi_diff = diff_map[y:y+h, x:x+w]
        if roi_diff.size == 0:
            continue

        # 해당 BBox 내에서 픽셀 변화가 가장 큰 상위 30% 영역의 평균 변화량 계산
        flat_diff = np.sort(roi_diff.flatten())[::-1]
        top_k = max(1, len(flat_diff) // 3)
        mean_diff = flat_diff[:top_k].mean()

        # 작은 노이즈가 높은 평균을 가지는 것을 막기 위해 면적 가중치 추가
        score = mean_diff * np.sqrt(w * h)
        log.info(f"후보 {i+1} {bb} - 상위 변화율: {mean_diff:.1f}, 스코어: {score:.0f}")

        if score > best_score:
            best_score = score
            best_bbox = bb

            # Foreground 힌트 포인트 추출 (가장 뚜렷하게 변한 픽셀들)
            hot_threshold = np.percentile(roi_diff, 85)
            ys, xs = np.where(roi_diff >= hot_threshold)
            fg = []
            if len(xs) > 0:
                p_count = min(5, len(xs))
                indices = np.linspace(0, len(xs)-1, p_count, dtype=int)
                for idx in indices:
                    fg.append((int(x + xs[idx]), int(y + ys[idx])))

            # 중앙점 하나를 확실하게 추가
            cx, cy = x + w // 2, y + h // 2
            if fg:
                fg[0] = (cx, cy)
            else:
                fg.append((cx, cy))
            best_fg_points = fg

    # 원본 대비 유의미한 변화가 없다면(기존 배경의 객체를 잡았다면) 무시
    if best_score < 50:
        log.warning("감지된 객체들이 원본과 너무 동일합니다 (유의미한 추가 객체 아님).")
        return None

    log.info(f"선택 완료! 새로운 객체: BBox={best_bbox}, fg_points={len(best_fg_points)}개")
    return best_bbox, best_fg_points


def step4_extract(first_frame, generated_frame, keyword):
    """
    추가된 객체 추출.
    DINO를 이용해 의미론적 후보를 찾은 뒤, 원본과 변화량이 가장 큰 객체를 추출.
    """
    fh, fw = generated_frame.shape[:2]

    log.info("객체 추출: 의미론적 객체 비교(Semantic Diff) 진행 중...")
    diff_result = _semantic_diff_analyze(first_frame, generated_frame, keyword)

    combined_mask = np.zeros((fh, fw), dtype=np.uint8)

    if diff_result is not None:
        diff_bbox, fg_points = diff_result
        log.info(f"의미론적 추가 객체 발견 → SAM에 힌트 포인트 전달...")
        combined_mask = _sam_segment(generated_frame, diff_bbox, fg_points=fg_points)
        combined_mask = _refine_mask(combined_mask, generated_frame, diff_bbox)
    else:
        log.warning("의미론적 객체 비교 실패 — DINO 전체 객체 SAM 폴백 진행...")
        try:
            all_bboxes = _dino_detect(generated_frame, keyword)
            for i, bb in enumerate(all_bboxes):
                log.info(f"SAM 세그멘테이션 [{i+1}/{len(all_bboxes)}]: bbox={bb}")
                mask_i = _sam_segment(generated_frame, bb)
                mask_i = _refine_mask(mask_i, generated_frame, bb)
                combined_mask = cv2.bitwise_or(combined_mask, mask_i)
            log.info(f"마스크 결합 완료: {len(all_bboxes)}개 객체")
        except Exception as e:
            log.error(f"폴백 DINO 탐지마저 실패했습니다: {e}")
            raise RuntimeError("객체를 추출할 수 없습니다.")

    # 그림자 추출
    eroded_mask = cv2.erode(combined_mask, np.ones((5, 5), np.uint8), iterations=1)
    shadow_map = extract_shadow_map(first_frame, generated_frame, eroded_mask)

    # bbox를 결합된 영역(마스크 + 그림자) 기준으로 재계산
    shadow_binary = (shadow_map < 0.98).astype(np.uint8) * 255
    merged = cv2.bitwise_or(combined_mask, shadow_binary)

    coords = cv2.findNonZero(merged)
    bbox = (0, 0, fw, fh)
    if coords is not None:
        mx, my, mw, mh = cv2.boundingRect(coords)
        p = 20
        bbox = (max(0, mx - p), max(0, my - p),
                min(mw + 2 * p, fw - max(0, mx - p)),
                min(mh + 2 * p, fh - max(0, my - p)))

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


def step6_composite(vpath, obj, mr, sr, vbbox, opath):
    """
    영상 합성 + Y축 기반 가림(Occlusion).

    원리: 화면 아래쪽에 있는 물체 = 카메라에 가까움.
    사람의 발(바닥 Y)이 합성 객체의 바닥 Y보다 아래에 있으면 → 사람이 앞에 있음 → 가림.

    가림 마스크는 0 또는 1 (이진). 중간값 없음 → 반투명 현상 원천 차단.
    경계만 3px 블러로 살짝 부드럽게.
    """
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

    alpha = cv2.GaussianBlur(cm.astype(np.float32) / 255, (0, 0), sigmaX=1.5)
    inner = cv2.erode(cm, np.ones((3, 3), np.uint8), iterations=2)
    alpha[inner > 0] = 1.0
    alpha = np.clip(alpha, 0, 1)
    a3 = np.stack([alpha] * 3, axis=-1)

    clip_shadow = sr[oy1:oy2, ox1:ox2]
    s3 = np.stack([clip_shadow] * 3, axis=-1)

    roi_h, roi_w = y2 - y1, x2 - x1

    log.info(f"합성: {vw}×{vh} {fps:.0f}fps {total}f")

    # ── 합성 객체의 바닥 Y좌표 (영상 좌표계) ──
    mask_rows = np.where(cm.max(axis=1) > 128)[0]
    if len(mask_rows) > 0:
        obj_bottom_y_in_roi = mask_rows[-1]
        obj_bottom_y_global = y1 + obj_bottom_y_in_roi
    else:
        obj_bottom_y_in_roi = roi_h
        obj_bottom_y_global = y2

    log.info(f"합성 객체 바닥 Y: {obj_bottom_y_global} (영상), {obj_bottom_y_in_roi} (ROI내)")

    # ── MOG2 배경 모델 — 전체 프레임에서 실행 ──
    bg_sub = cv2.createBackgroundSubtractorMOG2(
        history=60, varThreshold=30, detectShadows=False
    )
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    for _ in range(min(60, total)):
        ret, lf = cap.read()
        if not ret:
            break
        bg_sub.apply(lf, learningRate=0.03)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    # ── 파라미터 ──
    MIN_COMPONENT = max(2000, int(vw * vh * 0.005))
    OCC_ON_THRESH = 0.02
    OCC_OFF_FRAMES = 5

    log.info(f"Occlusion: 전체 프레임 MOG2 + 히스테리시스 "
             f"(min_comp={MIN_COMPONENT}px, ROI={roi_w}x{roi_h})")

    n = 0
    occ_active = False
    no_occ_count = 0
    last_occ_mask = np.zeros((roi_h, roi_w), dtype=np.uint8)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        roi = frame[y1:y2, x1:x2].astype(np.float32)

        # ── 1) 합성 객체를 완전히 합성 (가림 무관) ──
        composited = roi * s3
        composited = fg * a3 + composited * (1.0 - a3)

        # ── 2) 전체 프레임에서 MOG2 전경 검출 ──
        fg_mask_full = bg_sub.apply(frame, learningRate=0.001)

        k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask_full = cv2.morphologyEx(fg_mask_full, cv2.MORPH_OPEN, k_open, iterations=1)
        k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
        fg_mask_full = cv2.morphologyEx(fg_mask_full, cv2.MORPH_CLOSE, k_close, iterations=2)

        # ── 3) 전체 프레임에서 큰 전경 컴포넌트 찾기 + ROI 교차 ──
        curr_occ = np.zeros((roi_h, roi_w), dtype=np.uint8)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(fg_mask_full, 8)
        for lbl in range(1, num_labels):
            if stats[lbl, cv2.CC_STAT_AREA] < MIN_COMPONENT:
                continue

            comp_bottom_y = stats[lbl, cv2.CC_STAT_TOP] + stats[lbl, cv2.CC_STAT_HEIGHT]

            if comp_bottom_y >= obj_bottom_y_global * 0.7:
                comp_full = (labels == lbl).astype(np.uint8) * 255
                comp_roi = comp_full[y1:y2, x1:x2]

                if cv2.countNonZero(comp_roi) > 0:
                    contours, _ = cv2.findContours(
                        comp_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                    )
                    cv2.drawContours(curr_occ, contours, -1, 255, cv2.FILLED)

        curr_occ = cv2.bitwise_and(curr_occ, cm)
        curr_occ_ratio = (curr_occ > 0).sum() / max(1, (cm > 128).sum())

        # ── 4) 히스테리시스 상태 관리 ──
        if not occ_active:
            if curr_occ_ratio >= OCC_ON_THRESH:
                occ_active = True
                no_occ_count = 0
                last_occ_mask = curr_occ.copy()
        else:
            if curr_occ_ratio >= OCC_ON_THRESH:
                last_occ_mask = curr_occ.copy()
                no_occ_count = 0
            else:
                no_occ_count += 1
                if no_occ_count >= OCC_OFF_FRAMES:
                    occ_active = False
                    last_occ_mask = np.zeros((roi_h, roi_w), dtype=np.uint8)

        # ── 5) 가림 마스크 적용 ──
        if occ_active:
            occ_float = last_occ_mask.astype(np.float32) / 255.0
            occ_float = cv2.GaussianBlur(occ_float, (5, 5), 0)
            occ_float = np.where(occ_float > 0.3, 1.0, 0.0)
        else:
            occ_float = np.zeros((roi_h, roi_w), dtype=np.float32)

        occ_3 = np.stack([occ_float] * 3, axis=-1)

        # ── 6) 최종 합성 ──
        original_roi = frame[y1:y2, x1:x2].astype(np.float32)
        final_roi = composited * (1.0 - occ_3) + original_roi * occ_3

        frame[y1:y2, x1:x2] = np.clip(final_roi, 0, 255).astype(np.uint8)
        out.write(frame)
        n += 1

    cap.release()
    out.release()
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


def generate_previews(video_path, obj_img_path, user_prompt, count=3, on_progress=None):
    """
    Gemini를 count회 호출하여 프리뷰 이미지 리스트를 반환한다.

    Args:
        video_path: 영상 파일 경로
        obj_img_path: 합성할 객체 이미지 경로
        user_prompt: 사용자 프롬프트
        count: 생성할 프리뷰 개수 (기본 3)
        on_progress: 진행률 콜백 (stage, percent, message)

    Returns:
        list[str]: 저장된 프리뷰 이미지 경로 리스트
    """
    def _p(stage, percent, message):
        if on_progress:
            on_progress(stage, percent, message)

    if gemini_client is None:
        raise RuntimeError("Gemini API 미설정")

    # 키워드 추출
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


def run_composite(video_path, selected_preview_path, user_prompt, output_path, on_progress=None):
    """
    선택된 프리뷰 이미지를 기반으로 합성 파이프라인을 실행한다.

    Args:
        video_path: 원본 영상 경로
        selected_preview_path: 선택된 프리뷰 이미지 경로 (changed_first_frame)
        user_prompt: 사용자 프롬프트
        output_path: 결과 영상 저장 경로
        on_progress: 진행률 콜백 (stage, percent, message)
    """
    def _p(stage, percent, message):
        if on_progress:
            on_progress(stage, percent, message)

    # 키워드 추출
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
    _p("SAM", 25, "SAM 모델이 정밀 마스크를 추출하는 중입니다...")
    mask, shadow_map, bbox = step4_extract(f1, f2, kw)

    _p("SHADOW", 35, "그림자 맵을 생성하는 중입니다...")
    _p("SCALE", 40, "객체 스케일링을 처리하는 중입니다...")
    obj, mr, sr, vbbox = step5_scale(f2, mask, shadow_map, bbox, vw, vh)

    _p("DEPTH", 45, "DPT 모델이 깊이를 추정하는 중입니다...")
    _p("COMPOSITE", 50, "프레임별 합성을 진행하는 중입니다...")
    step6_composite(video_path, obj, mr, sr, vbbox, output_path)
    _p("COMPOSITE", 85, "합성 완료")

    log.info(f"run_composite 완료 → {output_path}")


if __name__ == "__main__":
    main()
