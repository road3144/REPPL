<div align="center">

# RePPL

### AI 가상 PPL(Product Placement) 영상 합성 SaaS 플랫폼

유튜브 영상을 쇼츠로 재가공할 때, **추가 촬영 없이 AI로 제품 PPL을 삽입**하여
영상 1개당 추가 광고 수익을 창출하는 SaaS 플랫폼입니다.

`React` · `Spring Boot` · `Python(PyTorch/CUDA)` · `Kafka` · `Redis` · `AWS S3` · `Docker`

> SSAFY 14기 서울 4반 401팀 (자율 프로젝트)

</div>

---

## 목차

1. [서비스 소개](#1-서비스-소개)
2. [주요 기능](#2-주요-기능)
3. [시스템 아키텍처](#3-시스템-아키텍처)
4. [핵심 워크플로우](#4-핵심-워크플로우)
5. [기술 스택](#5-기술-스택)
6. [프로젝트 구조](#6-프로젝트-구조)
7. [실행 방법](#7-실행-방법)
8. [API 명세](#8-api-명세)
9. [AI 파이프라인](#9-ai-파이프라인)
10. [배포](#10-배포)

---

## 1. 서비스 소개

크리에이터가 긴 영상을 **쇼츠로 재가공**할 때, 이미 촬영이 끝난 영상에는 PPL을 새로 넣기 어렵습니다.
RePPL은 원본 영상과 광고할 **제품 이미지**만 업로드하면, AI가 영상 속 적절한 위치에 제품을
**자연스럽게 합성**해줍니다. 추가 촬영·재편집 없이 영상 1개당 새로운 광고 수익을 만들 수 있습니다.

- **추가 촬영 불필요** — 기존 영상에 AI로 PPL 삽입
- **자연스러운 합성** — 객체 검출 → 마스크 → 그림자 → 깊이 기반 가려짐 처리까지 자동
- **실시간 진행률** — 업로드부터 완료까지 WebSocket으로 단계별 진행 상황 제공

---

## 2. 주요 기능

| 기능 | 설명 |
|------|------|
| **영상 / 제품 이미지 업로드** | Presigned URL을 통해 브라우저에서 S3로 직접 업로드 (서버 부하 최소화) |
| **AI 합성 이미지 미리보기** | Gemini 기반으로 제품이 삽입된 첫 프레임을 생성하여 합성 결과를 미리 확인 |
| **AI 영상 합성** | 미리보기에서 확정한 이미지를 기준으로 영상 전체 프레임에 제품을 추적·합성 |
| **실시간 진행률** | DOWNLOAD → DETECT → REPLACE → ENCODE → UPLOAD 단계를 WebSocket으로 실시간 표시 |
| **결과 다운로드** | 합성 완료 영상을 Presigned URL로 다운로드 |
| **세션 기반 작업 관리** | 로그인 없이 세션 단위로 업로드 파일 / Job 목록 관리 (Redis) |

### 화면

| 랜딩 | 스튜디오 |
|------|----------|
| ![home](exec/images/homeview.png) | ![studio](exec/images/studioview.png) |

| 옵션 설정 | 작업 진행 |
|-----------|-----------|
| ![option](exec/images/optionview.png) | ![work](exec/images/workview.png) |

---

## 3. 시스템 아키텍처

```
                           [ Browser / React SPA ]
                                     │
                                     ▼
                            [ Nginx ] ── SSL (Let's Encrypt)
                            /          \
                           ▼            ▼
                    [ Frontend ]   [ Backend (Spring Boot) ]
                                    │      │        │
                            Presigned│   Redis    Kafka
                                URL  │ (세션/상태)   │ reppl.job.request.v1
                                     │              ▼
                                     │     [ AI GPU Server (Python) ]
                                     │       Grounding DINO + SAM + DPT
                                     │              │ reppl.job.progress.v1
                                     ▼              ▼
                                  [ AWS S3 ] ◄──────┘
                              (영상 / 이미지 / 결과물)
```

- **Frontend ↔ Backend**: REST API + STOMP WebSocket(`/ws`)
- **Backend ↔ AI Server**: Kafka (요청/진행률 토픽으로 비동기 통신)
- **파일**: 브라우저 → Presigned URL → S3 직접 업로드/다운로드
- **상태 저장소**: Redis (세션·Job 상태), RDB 미사용

---

## 4. 핵심 워크플로우

```
1. 사용자가 영상 + 제품 이미지 업로드 (Presigned URL → S3 직접 업로드)
2. 미리보기 요청 → Gemini가 제품 삽입 첫 프레임 생성 → 사용자가 결과 확정
3. 합성 작업 요청 → Job 생성(Redis) → Kafka로 작업 발행
4. GPU 서버가 Kafka에서 작업 수신 → AI 파이프라인 실행
5. 진행률을 Kafka로 전송 → Spring 수신 → WebSocket으로 프론트에 실시간 전달
6. 완료 시 결과 영상 S3 저장 → 다운로드 URL 발급
```

**Job 상태**: `QUEUED` → `RUNNING` → `COMPLETED` / `FAILED`
**처리 단계**: `DOWNLOAD` → `DETECT` → `REPLACE` → `ENCODE` → `UPLOAD`

---

## 5. 기술 스택

| 레이어 | 기술 | 버전 |
|--------|------|------|
| **Frontend** | React, TypeScript, Vite, Tailwind CSS, STOMP.js | 18.3 / 5.8 / 5.4 / 3.4 |
| **Backend** | Spring Boot, Java, Gradle | 3.4.3 / 21 / 9.3.1 |
| **AI / ML** | PyTorch(CUDA), Grounding DINO, SAM, Intel DPT-Large, Gemini | 2.5.1+cu121 |
| **Message Queue** | Apache Kafka, Zookeeper | 7.6.0 (Confluent) |
| **Cache / Session** | Redis | 7-alpine |
| **Storage** | AWS S3 (Presigned URL) | ap-northeast-2 |
| **Infra** | Docker Compose, Nginx, Certbot(Let's Encrypt) | 3.8 / alpine |
| **CI/CD** | GitLab CI/CD + Docker Hub | - |

---

## 6. 프로젝트 구조

```
S14P21A401/
├── frontend/                # React + TypeScript + Vite + Tailwind
│   └── src/
│       ├── pages/           # LandingPage, WorkspacePage
│       ├── components/      # studio/(JobCreateForm, JobListPanel, JobStagePanel, PreviewSelectModal)
│       ├── hooks/           # useJobs (생성·폴링·다운로드)
│       └── services/        # api, s3, ws(STOMP), download
│
├── backend/                 # Spring Boot 3.4.3 (Java 21)
│   └── src/main/java/com/a401/reppl/
│       ├── config/          # WebSocket, Kafka, Redis, S3, Session
│       ├── controller/      # Job / Upload / Session + DTO
│       ├── service/         # JobService, S3Service, WebSocketPushService
│       ├── kafka/           # Producer / Consumer + 이벤트 DTO
│       ├── domain/          # job(Redis Repository), session
│       └── exception/       # 커스텀 예외 + GlobalExceptionHandler
│
├── ai/                      # Python AI 파이프라인 (PyTorch + CUDA)
│   ├── main.py              # 합성 파이프라인 핵심 로직
│   ├── worker.py            # Kafka 워커 (서빙 진입점)
│   ├── kafka_client.py      # Kafka Consumer/Producer 래퍼
│   ├── s3_client.py         # S3 다운로드/업로드
│   └── prompt_validator.py  # 프롬프트 검증
│
├── nginx/                   # 리버스 프록시 + SSL 설정
├── scripts/                 # EC2 배포 스크립트 (ec2-setup.sh)
├── docs/                    # 와이어프레임 / 연동 가이드
├── exec/                    # 빌드·배포 가이드, 외부 서비스 정보, 시연 시나리오
├── docker-compose.yml       # 프로덕션 (이미지 기반)
└── .gitlab-ci.yml           # CI/CD 파이프라인
```

---

## 7. 실행 방법

### 사전 준비

루트에 `.env`, `ai/.env` 환경변수 파일이 필요합니다. 자세한 항목은
[`exec/1_빌드_및_배포_가이드.md`](exec/1_빌드_및_배포_가이드.md)를 참고하세요.

### Frontend

```bash
cd frontend
npm install
npm run dev      # 개발 서버 (Vite)
npm run build    # 프로덕션 빌드 → dist/
```

### Backend

```bash
cd backend
./gradlew bootRun   # 실행 (포트 8080)
./gradlew build     # 빌드
./gradlew test      # 테스트
```

> Backend 실행에는 Redis와 Kafka가 필요합니다. 로컬에서는 `docker compose up -d redis zookeeper kafka`로 인프라만 먼저 띄우세요.

### AI Worker (GPU 서버)

```bash
cd ai
python -m venv venv
source venv/bin/activate          # Windows: .\venv\Scripts\Activate.ps1

# CUDA PyTorch 먼저 설치
pip install torch==2.5.1+cu121 torchvision==0.20.1+cu121 \
  --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt

python worker.py                   # Kafka 워커 실행
```

> 모델 가중치(`groundingdino_swint_ogc.pth` 467MB, `sam_vit_h_4b8939.pth` 2.4GB)는 git에 포함되지 않습니다.
> 다운로드 방법은 [`ai/README.md`](ai/README.md)를 참고하세요. **GPU(NVIDIA, CUDA 12.1, VRAM 8GB+) 필요.**

---

## 8. API 명세

공통 응답 포맷:

```json
{ "success": true,  "data": { ... }, "error": null }
{ "success": false, "data": null, "error": { "code": "ERROR_CODE", "message": "..." } }
```

| Method | URI | 설명 |
|--------|-----|------|
| `GET`  | `/api/v1/session` | 세션 초기화/확인 |
| `POST` | `/api/v1/url/video` | 동영상 업로드 Presigned URL 발급 |
| `POST` | `/api/v1/url/images` | 이미지 업로드 Presigned URL 발급 (다중) |
| `POST` | `/api/v1/jobs` | 작업 시작 (Job 생성 → Kafka 발행) |
| `GET`  | `/api/v1/jobs` | Job 목록 조회 (페이지네이션) |
| `GET`  | `/api/v1/jobs/{jobId}` | Job 상태 조회 |
| `GET`  | `/api/v1/jobs/{jobId}/result` | 결과 다운로드 URL 발급 |
| `WS`   | `/ws` → `/topic/jobs/{jobId}` | 실시간 진행률 (STOMP) |

### Kafka Topics

| Topic | 방향 | 용도 |
|-------|------|------|
| `reppl.job.request.v1` | Spring → GPU | 작업 요청 발행 |
| `reppl.job.progress.v1` | GPU → Spring | 진행률 / 완료 이벤트 |

> 데이터 모델(Redis Key 설계, Job 상태 스키마)은 [`backend/CLAUDE.md`](backend/CLAUDE.md)에 정리되어 있습니다.

---

## 9. AI 파이프라인

```
원본 영상 + AI 합성 첫 프레임
  → Grounding DINO (SwinT)   : 텍스트 프롬프트 기반 객체 BBox 검출
  → SAM (vit_h)              : 픽셀 단위 정밀 마스크 추출
  → Shadow Map (HSV 기반)    : 그림자 추출
  → Intel DPT-Large          : 깊이 추정 → 거리 기반 가려짐(occlusion) 처리
  → 프레임별 합성             : Optical Flow 추적 + Alpha Blending + Gaussian Feathering
  → 결과 영상 출력 (S3 업로드)
```

| 기술 | 역할 |
|------|------|
| Grounding DINO (SwinT) | 텍스트 프롬프트 기반 객체 검출 |
| SAM (vit_h) | 픽셀 단위 정밀 마스크 추출 |
| Intel DPT-Large | 깊이 추정 → 거리 기반 가려짐 처리 |
| OpenCV | 영상 처리·합성, Optical Flow 추적 |
| Gemini | 미리보기용 제품 삽입 이미지 생성 |

자세한 설치/실행/트러블슈팅은 [`ai/README.md`](ai/README.md)를 참고하세요.

---

## 10. 배포

- **인프라**: EC2(Ubuntu 22.04) + Docker Compose로 nginx / frontend / backend / redis / kafka / zookeeper / certbot 운영
- **AI Worker**: Docker 외부의 별도 GPU 서버에서 실행, Kafka(포트 80 외부 노출)로 Backend와 통신
- **CI/CD**: `master` push 시 GitLab CI/CD가 이미지 빌드 → Docker Hub push → EC2 pull/재시작
- **SSL**: Let's Encrypt 인증서를 certbot 컨테이너가 12시간마다 자동 갱신

```bash
# EC2 초기 셋업
ssh -i J14A401T.pem ubuntu@<EC2_IP> "bash -s" < scripts/ec2-setup.sh

# 프로덕션 실행
docker compose up -d
```

전체 배포 절차와 환경변수 목록은 [`exec/1_빌드_및_배포_가이드.md`](exec/1_빌드_및_배포_가이드.md)에 정리되어 있습니다.

---

## 브랜치 / 커밋 컨벤션

- **브랜치**: `master`(프로덕션) · `dev`(개발 통합) · `ai/*` · `fe/*`(기능 브랜치)
- **커밋**: `[파트] type: 설명` — 예) `[AI] feat: 거리 기반 객체 가려짐 기능 구현`

<div align="center">

**SSAFY 14기 서울 4반 401팀**

</div>
