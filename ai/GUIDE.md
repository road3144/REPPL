# 🎬 영상 이미지 합성 AI 파이프라인 — 설치 및 실행 가이드

## 📋 목차
1. [개요](#1-개요)
2. [시스템 요구사항](#2-시스템-요구사항)
3. [환경 설정 (Step-by-Step)](#3-환경-설정)
4. [모델 가중치 다운로드](#4-모델-가중치-다운로드)
5. [폴더 구조](#5-폴더-구조)
6. [실행 방법](#6-실행-방법)
7. [파이프라인 상세 설명](#7-파이프라인-상세-설명)
8. [트러블슈팅](#8-트러블슈팅)

---

## 1. 개요

영상 속 빈 공간에 AI가 생성한 제품 이미지를 자연스럽게 합성하는 **가상 PPL(Product Placement)** 파이프라인입니다.

**핵심 기술 스택:**
| 기술 | 역할 | 설명 |
|------|------|------|
| **Gemini Nano Banana** | 이미지 생성 | 영상 첫 프레임에 제품을 합성한 이미지 생성 |
| **Grounding DINO** | 객체 검출 | 텍스트 프롬프트로 합성된 제품의 BBox 검출 |
| **SAM (vit_h)** | 누끼 따기 | 검출된 BBox로 정밀 마스크 추출 |
| **Lucas-Kanade** | 카메라 추적 | 옵티컬 플로우로 카메라 이동에 따른 객체 위치 보정 |

---

## 2. 시스템 요구사항

| 항목 | 최소 | 권장 |
|------|------|------|
| **OS** | Windows 10 / Ubuntu 20.04 | Windows 11 / Ubuntu 22.04 |
| **Python** | 3.10 | **3.10** (3.12는 비호환) |
| **GPU** | NVIDIA GTX 1660 (6GB) | **RTX 4070+ (8GB+)** |
| **CUDA** | 11.8 | **12.1** |
| **RAM** | 16GB | 32GB |
| **디스크** | 5GB (가중치 포함) | 10GB |
| **[Windows] VS Build Tools** | 2019 이상 | **2022** |

> ⚠️ **AMD GPU / Apple Silicon은 지원하지 않습니다.** NVIDIA CUDA가 필수입니다.

---

## 3. 환경 설정

### 3-0. [Windows 필수] Visual Studio Build Tools 설치

> ⚠️ **Windows에서만 필요합니다.** `groundingdino-py` 패키지가 C++ 코드를 컴파일하기 때문에 필수입니다.
> 이미 Visual Studio가 설치되어 있다면 건너뛰세요.

1. 아래 링크에서 **Build Tools for Visual Studio 2022** 다운로드:
   > https://visualstudio.microsoft.com/ko/visual-cpp-build-tools/

2. 설치 프로그램 실행 → **"C++를 사용한 데스크톱 개발"** 워크로드 체크 → 설치

   ![워크로드 선택](https://learn.microsoft.com/en-us/cpp/build/media/vscpp-concurrency-build-tools.png)

   > 체크해야 하는 항목:
   > - ✅ **C++를 사용한 데스크톱 개발** (Desktop development with C++)
   > - 우측 옵션은 기본값 그대로 두면 됩니다

3. 설치 완료 후 **PC 재부팅**

4. 확인:
   ```bash
   # 명령 프롬프트에서
   cl
   ```
   `Microsoft (R) C/C++ Optimizing Compiler` 메시지가 나오면 정상.
   
   > 💡 `cl`이 인식 안 되어도 괜찮습니다. pip이 자동으로 찾습니다.
   > 설치만 되어 있으면 됩니다.

### 3-1. 가상환경 생성

**방법 A: venv (권장 — 간단)**
```bash
cd ~/Desktop/ai
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

**방법 B: conda**
```bash
conda create -n ppl python=3.10 -y
conda activate ppl
```

### 3-2. PyTorch CUDA 버전 설치 (⚠️ 가장 중요!)

> **반드시 이 명령어로 설치하세요.** `pip install torch`만 하면 CPU 버전이 설치됩니다!

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

**설치 확인:**
```bash
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
```
```
CUDA: True    ← 이렇게 나와야 정상
CUDA: False   ← GPU 미인식 → 3-2 다시 실행
```

### 3-3. 나머지 패키지 설치

```bash
pip install -r requirements.txt
```

이 한 줄로 다음이 모두 설치됩니다:
- `opencv-python` — 영상 처리
- `numpy` — 수치 연산
- `groundingdino-py` — Grounding DINO 객체 검출
- `segment-anything` — SAM 세그멘테이션
- `transformers==4.38.2` — DINO 의존성 (⚠️ 버전 고정 필수)
- `supervision`, `timm` — 기타 의존성

### 3-4. 최종 확인

```bash
python -c "
import torch, cv2
from groundingdino.util.inference import load_model
from segment_anything import sam_model_registry
print(f'PyTorch: {torch.__version__}')
print(f'CUDA: {torch.cuda.is_available()}')
print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"없음\"}')
print(f'OpenCV: {cv2.__version__}')
print('Grounding DINO: ✅')
print('SAM: ✅')
"
```

정상 출력 예시:
```
PyTorch: 2.5.1+cu121
CUDA: True
GPU: NVIDIA GeForce RTX 4070
OpenCV: 4.10.0
Grounding DINO: ✅
SAM: ✅
```

---

## 4. 모델 가중치 다운로드

`models/` 폴더에 2개의 가중치 파일이 필요합니다.

### 4-1. Grounding DINO (467MB)
```bash
mkdir -p models
curl -L -o models/groundingdino_swint_ogc.pth "https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0-alpha/groundingdino_swint_ogc.pth"
```

또는 브라우저에서 직접 다운로드:
> https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0-alpha/groundingdino_swint_ogc.pth

### 4-2. SAM vit_h (2.4GB)
```bash
curl -L -o models/sam_vit_h_4b8939.pth "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth"
```

또는 브라우저에서 직접 다운로드:
> https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth

### 4-3. 확인
```bash
ls -lh models/
```
```
467M  groundingdino_swint_ogc.pth
2.4G  sam_vit_h_4b8939.pth
```

---

## 5. 폴더 구조

```
ai/
├── main.py                          ← 메인 파이프라인
├── requirements.txt                 ← 패키지 목록
├── GUIDE.md                         ← 이 가이드
├── models/
│   ├── groundingdino_swint_ogc.pth  ← DINO 가중치 (467MB)
│   └── sam_vit_h_4b8939.pth         ← SAM 가중치 (2.4GB)
├── inputs/
│   ├── test_video.mp4               ← 원본 영상
│   └── changed_first_frame.png      ← Gemini가 합성한 첫 프레임
└── outputs/
    ├── output_composited.mp4        ← 합성 결과 영상
    ├── object_mask.png              ← 추출된 마스크
    ├── object_crop.png              ← 추출된 누끼
    ├── mask_roi.png                 ← 스케일링된 마스크
    └── shadow_map.png               ← 그림자 맵
```

---

## 6. 실행 방법

### 6-1. 입력 파일 준비

1. `inputs/` 폴더에 **원본 영상** (`.mp4`) 배치
2. `inputs/` 폴더에 **Gemini 합성 프레임** (`changed_first_frame.png`) 배치
   - 이 파일은 Gemini Nano Banana가 원본 첫 프레임에 제품을 합성한 이미지입니다.

### 6-2. 실행

```bash
python main.py
```

### 6-3. 프롬프트 입력

```
프롬프트: test_video.mp4 coca cola can
```

**프롬프트 형식:** `영상파일명 + 영어 객체 키워드`

| 입력 예시 | 설명 |
|-----------|------|
| `test_video.mp4 coca cola can` | 코카콜라 캔 검출 |
| `test_video.mp4 wall clock` | 벽시계 검출 |
| `test_video.mp4 water bottle` | 물병 검출 |
| `test_video.mp4 코카콜라` | 한국어도 가능 (자동 번역) |

> 💡 **팁:** 검출이 안 되면 더 구체적인 키워드를 사용하세요.
> `cola` → `red coca cola can` / `clock` → `round wall clock`

### 6-4. 실행 로그 예시

```
10:28:37 [INFO] DINO: ✅ groundingdino_swint_ogc.pth
10:28:37 [INFO] SAM:  ✅ sam1/vit_h (sam_vit_h_4b8939.pth)
10:28:37 [INFO] GPU:  ✅ NVIDIA GeForce RTX 4070

STEP 2 — 파싱
  영상: test_video.mp4  키워드: 'coca cola can'
STEP 3 — Gemini
  원본 1920×1080  생성 2702×1536
STEP 4 — DINO + SAM 객체 추출
  DINO ✅: (1203,1169,132,240) conf=0.47 'cola can'
  SAM1: vit_h on cuda
  SAM ✅: score=0.9847
STEP 5 — 스케일링
STEP 6 — 합성 (LK 옵티컬 플로우 추적)

✅ 합성 완료!
  출력: outputs/output_composited.mp4
```

---

## 7. 파이프라인 상세 설명

### 전체 흐름

```
┌─────────┐   ┌──────────┐   ┌────────────────┐   ┌───────────┐
│ 원본영상 │──→│  Gemini   │──→│ Grounding DINO │──→│    SAM    │
│ (MP4)   │   │ 합성프레임 │   │  BBox 검출     │   │  마스크   │
└─────────┘   └──────────┘   └────────────────┘   └───────────┘
                                                         │
     ┌──────────────────────────────────────────────────┘
     ▼
┌─────────────┐   ┌──────────────────────┐   ┌─────────────┐
│ 그림자 추출  │──→│  카메라 추적 합성     │──→│  출력 영상  │
│ (AI shadow) │   │  (LK 옵티컬 플로우)   │   │   (MP4)    │
└─────────────┘   └──────────────────────┘   └─────────────┘
```

### STEP 4: Grounding DINO → SAM

- **DINO**: 텍스트 프롬프트(예: "coca cola can.")로 이미지에서 객체 위치를 검출
  - 프롬프트 끝에 마침표(`.`)가 자동으로 추가됨 (DINO 특성)
  - 임계값을 0.35 → 0.25 → 0.15 → 0.10으로 단계적 하향하여 검출 보장
- **SAM vit_h**: DINO가 찾은 BBox를 프롬프트로 받아 정밀 마스크 추출
  - 내부 3×3 포인트 그리드(fg) + 외곽 4포인트(bg)로 정밀도 향상

### STEP 6: 카메라 추적 합성

- **Lucas-Kanade 옵티컬 플로우**: 프레임 간 특징점 추적
- **Affine Partial (4 DOF)**: 이동 + 회전 + 스케일만 허용 (흔들림 방지)
- **EMA 스무딩 (α=0.6)**: 프레임 간 떨림 제거
- 카메라가 움직여도 객체가 장면에 고정된 것처럼 합성됨

---

## 8. 트러블슈팅

### ❌ `error: Microsoft Visual C++ 14.0 or greater is required`

Windows에서 `groundingdino-py` 설치 시 발생합니다.
1. https://visualstudio.microsoft.com/ko/visual-cpp-build-tools/ 에서 Build Tools 다운로드
2. **"C++를 사용한 데스크톱 개발"** 워크로드 체크 → 설치
3. PC 재부팅 후 다시 `pip install -r requirements.txt`

### ❌ `GPU: ❌ CPU` / `CUDA: False`

PyTorch가 CPU 버전으로 설치된 상태입니다.
```bash
pip uninstall torch torchvision -y
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### ❌ `BertModel has no attribute 'get_head_mask'`

`transformers` 버전이 4.39 이상입니다.
```bash
pip install transformers==4.38.2
```

### ❌ `Grounding DINO가 'xxx'를 검출하지 못했습니다`

- 키워드를 더 구체적으로 변경: `cola` → `red coca cola can`
- `changed_first_frame.png`에 해당 객체가 실제로 있는지 확인

### ❌ `SAM 가중치를 찾을 수 없습니다`

`models/` 폴더에 `sam_vit_h_4b8939.pth` 파일이 있는지 확인:
```bash
ls models/sam_vit_h_4b8939.pth
```

### ❌ `CUDA out of memory`

SAM vit_h는 약 3GB VRAM을 사용합니다. VRAM이 부족하면:
1. 다른 GPU 프로세스 종료
2. 또는 더 작은 모델 사용: `sam_vit_b_01ec64.pth` (375MB, VRAM 1GB)

### ❌ 합성 영상에서 객체가 흔들림

카메라 이동이 큰 영상에서 발생할 수 있습니다. `step6_composite`의 `ema_alpha` 값을 조절:
```python
ema_alpha = 0.4  # 낮출수록 안정 (기본 0.6)
```

### ❌ Windows에서 `symlinks` 경고

무시해도 됩니다. 또는:
```bash
set HF_HUB_DISABLE_SYMLINKS_WARNING=1
```

---

## 빠른 시작 (전체 복사-붙여넣기)

```bash
# 0. [Windows] Visual Studio Build Tools 2022 먼저 설치!
#    https://visualstudio.microsoft.com/ko/visual-cpp-build-tools/
#    → "C++를 사용한 데스크톱 개발" 체크 → 설치 → 재부팅

# 1. 가상환경
cd ~/Desktop/ai
python -m venv venv && venv\Scripts\activate

# 2. PyTorch CUDA
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# 3. 나머지 패키지
pip install -r requirements.txt

# 4. 가중치 다운로드
mkdir models
curl -L -o models/groundingdino_swint_ogc.pth "https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0-alpha/groundingdino_swint_ogc.pth"
curl -L -o models/sam_vit_h_4b8939.pth "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth"

# 5. 실행
python main.py
```
