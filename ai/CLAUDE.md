# REPPL AI — 가상 PPL 파이프라인 & 서빙 워커

## 개요

영상 속 빈 공간에 AI가 생성한 제품 이미지를 자연스럽게 합성하는 가상 PPL 파이프라인.
GPU 서버에서 Kafka 기반 워커로 동작하며, Spring Boot 백엔드와 연동된다.

## 기술 스택

| 기술 | 역할 |
|------|------|
| Python 3.10 | 런타임 (3.12 비호환) |
| PyTorch 2.5 + CUDA 12.1 | GPU 연산 |
| Grounding DINO (SwinT) | 텍스트 기반 객체 BBox 검출 |
| SAM (vit_h) | 픽셀 단위 정밀 마스크 추출 |
| Intel DPT-Large | 깊이 추정 (거리 기반 가려짐 처리) |
| Kafka (kafka-python) | 작업 수신 / 진행률 발행 |
| boto3 | AWS S3 다운로드/업로드 |

## 파일 구조

```
ai/
├── main.py              # AI 파이프라인 핵심 로직 (수정 금지 — 별도 담당자)
├── worker.py            # Kafka 워커 (서빙 진입점)
├── kafka_client.py      # Kafka Consumer/Producer 래퍼
├── s3_client.py         # S3 다운로드/업로드 유틸
├── config.py            # 환경변수 기반 설정
├── requirements.txt     # Python 의존성
├── GUIDE.md             # 설치 가이드 (환경 세팅, 모델 다운로드)
├── models/              # 모델 가중치 (git 미포함)
│   ├── groundingdino_swint_ogc.pth   (467MB)
│   └── sam_vit_h_4b8939.pth          (2.4GB)
└── inputs/              # 임시 파일 (워커가 S3에서 다운로드)
```

## 아키텍처

```
Spring Boot (EC2)                    GPU Server (Python)
    │                                      │
    ├─ Kafka: reppl.job.request.v1 ──────> worker.py
    │                                      │  ├─ S3 다운로드 (영상 + 이미지)
    │                                      │  ├─ main.py 파이프라인 실행
    │                                      │  │   ├─ step3: 프레임 로드
    │                                      │  │   ├─ step4: DINO + SAM 객체 추출
    │                                      │  │   ├─ step5: 스케일링
    │                                      │  │   └─ step6: 합성 (Depth Occlusion)
    │                                      │  ├─ S3 업로드 (결과 영상)
    │  Kafka: reppl.job.progress.v1 <──────┤  └─ 진행률 발행
    │                                      │
```

## 환경변수

```bash
# Kafka (EC2 Kafka 외부 포트로 연결)
export KAFKA_BOOTSTRAP_SERVERS="<EC2_HOST>:29092"
export KAFKA_CONSUMER_GROUP_ID="reppl-gpu"
export KAFKA_TOPIC_JOB_REQUEST="reppl.job.request.v1"
export KAFKA_TOPIC_JOB_PROGRESS="reppl.job.progress.v1"

# AWS S3
export AWS_ACCESS_KEY="..."
export AWS_SECRET_KEY="..."
export AWS_REGION="ap-northeast-2"
export AWS_S3_BUCKET="..."
```

## 실행 방법

### GPU 서버 (Jupyter 노트북)

```python
# 셀 1: 환경변수 설정
import os
os.environ["KAFKA_BOOTSTRAP_SERVERS"] = "<EC2_HOST>:29092"
os.environ["AWS_ACCESS_KEY"] = "..."
os.environ["AWS_SECRET_KEY"] = "..."
os.environ["AWS_REGION"] = "ap-northeast-2"
os.environ["AWS_S3_BUCKET"] = "..."

# 셀 2: 워커 실행
!python worker.py
```

또는 터미널:
```bash
python worker.py
```

## Kafka 메시지 스키마

### 수신: reppl.job.request.v1

```json
{
  "schemaVersion": 1,
  "jobId": "job_20260304_000123",
  "requestedAt": "2026-03-04T01:00:00Z",
  "input": {
    "video": { "bucket": "reppl-bucket", "key": "tmp/sess_abc/video/input.mp4" },
    "replacementImages": [{ "bucket": "reppl-bucket", "key": "tmp/sess_abc/images/ref.png" }]
  },
  "output": { "bucket": "reppl-bucket", "key": "results/job_xxx/output.mp4" },
  "roi": { "frame": { "type": "FIRST" }, "boxes": [] },
  "options": { "placementPrompt": "테이블 위 컵 옆" }
}
```

### 발신: reppl.job.progress.v1

```json
{
  "schemaVersion": 1,
  "jobId": "job_20260304_000123",
  "status": "RUNNING",
  "stage": "DETECT",
  "percent": 25,
  "message": "객체 탐지 중...",
  "timestamp": "2026-03-04T01:05:00Z",
  "seq": 1,
  "outputKey": null
}
```

**status**: `QUEUED` | `RUNNING` | `COMPLETED` | `FAILED`
**stage**: `DOWNLOAD` | `DETECT` | `REPLACE` | `ENCODE` | `UPLOAD`

### 진행률 단계

| 구간 | stage | percent | 설명 |
|------|-------|---------|------|
| S3 다운로드 | DOWNLOAD | 5→10 | 영상 + 이미지 |
| 프레임 로드 | DETECT | 12→15 | step3 |
| DINO + SAM | DETECT | 15→35 | step4 |
| 스케일링 | REPLACE | 38→40 | step5 |
| 영상 합성 | REPLACE | 40→85 | step6 (가장 오래 걸림) |
| 결과 업로드 | UPLOAD | 90→95 | S3 업로드 |
| 완료 | - | 100 | COMPLETED |

## 주요 제약사항

- **main.py 수정 금지**: 별도 담당자가 관리. worker.py에서 import하여 호출만 함
- **GPU 필수**: NVIDIA GPU + CUDA 12.1 (RTX 4070+ 권장)
- **Jupyter 배포**: CI/CD 없이 코드 복붙으로 배포
- **순차 처리**: 워커가 한 번에 1개 Job만 처리 (GPU 메모리 제약)

## 명령어

```bash
# 의존성 설치 (PyTorch CUDA 먼저!)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt

# 워커 실행
python worker.py
```
