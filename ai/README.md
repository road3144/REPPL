# AI PPL Video Compositing Pipeline

Grounding DINO + SAM 기반으로, 영상의 특정 객체를 교체된 첫 프레임 결과에 맞춰 전체 프레임에 재합성하는 프로젝트입니다.

`main.py` 하나로 실행되는 파이프라인이며, 입력 영상과 교체된 첫 프레임 이미지를 사용해 객체 검출, 마스크 생성, 스케일 보정, 프레임 추적 합성을 수행합니다.

## 1. 프로젝트 소개

이 프로젝트는 다음 상황을 목표로 합니다.

- 원본 영상은 그대로 유지
- 첫 프레임에서만 객체가 교체된 이미지(`changed_first_frame.png`)를 준비
- 교체된 객체를 영상 전체에 자연스럽게 따라가도록 합성

핵심 처리 단계:

1. 프롬프트에서 영상 파일명과 객체 키워드 파싱
2. 영상 1프레임 + 교체된 프레임 로드
3. Grounding DINO로 객체 박스 탐지
4. SAM으로 객체 마스크 생성 및 정제
5. 그림자 맵/객체 스케일 계산
6. Optical Flow 기반 추적 합성
7. `outputs/output_composited.mp4` 저장

## 2. 프로젝트 구조

```text
ai/
├─ main.py
├─ README.md
├─ requirements.txt
├─ inputs/
│  ├─ test_video.mp4
│  ├─ changed_first_frame.png
│  ├─ first_frame.png
│  └─ test_video_ref.jpg
├─ models/
│  ├─ groundingdino_swint_ogc.pth
│  └─ sam_vit_h_4b8939.pth
└─ outputs/
   ├─ output_composited.mp4
   ├─ object_mask.png
   ├─ object_crop.png
   ├─ shadow_map.png
   └─ 기타 중간 산출물
```

실행 필수 입력은 `inputs/test_video.mp4`, `inputs/first_frame.png`, `inputs/changed_first_frame.png`입니다.

## 3. 실행 환경

- OS: Windows 10/11 권장 (Linux/macOS도 가능)
- Python: 3.10~3.11 권장
- GPU: NVIDIA CUDA 환경 권장
- 메모리: 최소 16GB, 권장 32GB
- VRAM: 최소 8GB 권장 (SAM `vit_h` 사용 시)

참고:

- 이 저장소의 `requirements.txt`는 `torch==2.5.1+cu121`, `torchvision==0.20.1+cu121` 기준입니다.
- CUDA 환경이 아니면 설치/실행이 제한될 수 있습니다.

## 4. 가상환경 세팅

### Windows PowerShell

```powershell
cd c:\Users\SSAFY\Desktop\ai

python -m venv venv
.\venv\Scripts\Activate.ps1

python -m pip install --upgrade pip

# CUDA PyTorch 먼저 설치
pip install torch==2.5.1+cu121 torchvision==0.20.1+cu121 --index-url https://download.pytorch.org/whl/cu121

# 나머지 의존성 설치
pip install -r requirements.txt
```

`Activate.ps1` 실행이 막히면 현재 세션에서만 우회:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

### Linux/macOS (bash/zsh)

```bash
cd ~/Desktop/ai

python3 -m venv venv
source venv/bin/activate

python -m pip install --upgrade pip
pip install torch==2.5.1+cu121 torchvision==0.20.1+cu121 --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
```

## 5. 모델 파일 준비

`models/` 폴더에 아래 파일이 있어야 합니다.

- `groundingdino_swint_ogc.pth`
- `sam_vit_h_4b8939.pth`

PowerShell 예시:

```powershell
New-Item -ItemType Directory -Force models | Out-Null

curl.exe -L -o models/groundingdino_swint_ogc.pth `
  https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0-alpha/groundingdino_swint_ogc.pth

curl.exe -L -o models/sam_vit_h_4b8939.pth `
  https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth
```

## 6. 입력 데이터 준비

`inputs/` 폴더에 아래를 배치하세요.

- 원본 영상: `test_video.mp4` (파일명은 자유, 실행 시 프롬프트에 동일하게 입력)
- 원본 영상 첫 프레임: `first_frame.png`
- 교체된 첫 프레임: `changed_first_frame.png`

권장 조건:

- `changed_first_frame.png`는 원본 영상 첫 프레임과 같은 구도/시점
- 해상도는 동일 권장 (코드에서 다르면 리사이즈 처리)
- 교체 대상 객체가 명확히 보이도록 편집

## 7. 실행 방법

가상환경 활성화 후:

```bash
python main.py
```

프롬프트 입력 형식:

```text
<video_filename> <object keyword>
```

예시:

```text
test_video.mp4 coca cola can
test_video.mp4 wall clock
```

키워드는 영어 구체 명사로 넣는 것이 안정적입니다.

## 8. 출력 결과

실행이 끝나면 `outputs/`에 저장됩니다.

- 최종 결과: `outputs/output_composited.mp4`
- 마스크: `outputs/object_mask.png`
- 객체 크롭: `outputs/object_crop.png`
- 그림자 맵: `outputs/shadow_map.png`
- 기타 디버그 중간 파일: `object_1_*`, `shadow_1_*`, `mask_roi.png` 등

## 9. 빠른 점검 체크리스트

```bash
python -c "import torch; print(torch.cuda.is_available())"
python -c "import cv2; print(cv2.__version__)"
python -c "from groundingdino.util.inference import load_model; print('dino ok')"
python -c "from segment_anything import sam_model_registry; print('sam ok')"
```

## 10. 트러블슈팅

`Microsoft Visual C++ 14.0 or greater is required`:

- Windows에서 Build Tools 미설치 상태입니다.
- Visual Studio Build Tools 2022 설치 후, C++ 워크로드를 포함해 다시 `pip install -r requirements.txt`를 실행하세요.

`CUDA: False` 또는 GPU 미인식:

- NVIDIA 드라이버/CUDA/PyTorch(CUDA 빌드) 조합을 점검하세요.
- 먼저 `pip install torch==2.5.1+cu121 torchvision==0.20.1+cu121 --index-url https://download.pytorch.org/whl/cu121`를 재실행하세요.

`Grounding DINO ... .pth 파일을 찾을 수 없습니다`:

- `models/groundingdino_swint_ogc.pth` 경로와 파일명을 확인하세요.

`SAM 가중치 파일을 찾을 수 없습니다`:

- `models/sam_vit_h_4b8939.pth` 경로와 파일명을 확인하세요.

`Grounding DINO가 객체를 못 찾습니다`:

- 키워드를 더 구체적으로 입력하세요. 예: `cola` 대신 `red coca cola can`.
