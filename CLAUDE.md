# REPPL - AI 가상 PPL(Product Placement) SaaS 플랫폼

유튜브 영상을 쇼츠로 재가공할 때, 추가 촬영 없이 AI로 음료 PPL을 삽입하여 영상 1개당 추가 광고 수익을 창출하는 SaaS 플랫폼.

## 아키텍처 개요

```
[Browser/React SPA]
       │
       ▼
    [Nginx] ──── SSL (Let's Encrypt)
     /   \
    /     \
[Frontend]  [Backend (Spring Boot)]
              │         │
              ▼         ▼
           [Redis]   [Kafka]
                       │
                       ▼
              [AI GPU Server (FastAPI/Python)]
                       │
                       ▼
                   [AWS S3]
```

## 프로젝트 구조

```
S14P21A401/
├── frontend/          # React + TypeScript + Vite + Tailwind
├── backend/           # Spring Boot 4.0.3 (Java 21)
├── ai/                # Python AI 파이프라인 (PyTorch + CUDA)
├── nginx/             # 리버스 프록시 설정
├── scripts/           # EC2 배포 스크립트
├── docker-compose.yml          # 프로덕션 (이미지 기반)
└── docker-compose.local.yml    # 로컬 개발 (빌드 기반)
```

## 기술 스택

| 레이어 | 기술 | 버전 |
|--------|------|------|
| Frontend | React, TypeScript, Vite, Tailwind CSS | 18.3, 5.8, 5.4, 3.4 |
| Backend | Spring Boot, Java, Gradle | 4.0.3, 21, 9.3.1 |
| AI/ML | PyTorch (CUDA), Grounding DINO, SAM, DPT | 2.5+cu121 |
| Infra | Docker Compose, Nginx, Let's Encrypt | - |
| Message Queue | Apache Kafka, Zookeeper | 7.6.0 |
| Cache/Session | Redis | 7-alpine |
| Storage | AWS S3 (Presigned URL) | - |

## 핵심 워크플로우

1. 사용자가 영상 + 참조 이미지 업로드 (Presigned URL → S3 직접 업로드)
2. Job 생성 요청 → Redis에 상태 저장 → Kafka로 작업 발행
3. GPU 서버가 Kafka에서 작업 수신 → AI 파이프라인 처리
4. 진행률을 Kafka로 전송 → Spring이 수신 → WebSocket으로 프론트에 실시간 전달
5. 완료 시 결과 영상 S3 저장 → 다운로드 URL 발급

---

## Frontend (React + Vite)

### 주요 파일

| 파일 | 역할 |
|------|------|
| `src/pages/DemoStudioPage.tsx` | 메인 페이지 (히어로 + 파이프라인 시각화 + 워크스페이스) |
| `src/components/studio/JobCreateForm.tsx` | 파일 업로드 폼 (영상 + 참조 이미지 + 프롬프트) |
| `src/components/studio/JobListPanel.tsx` | 실시간 Job 상태/진행률 표시 |
| `src/hooks/useDemoJobs.ts` | Job 상태 관리 (생성, 폴링 3초 간격, 다운로드) |
| `src/services/demoApi.ts` | API 클라이언트 (Presigned URL 처리 포함) |

### 명령어

```bash
cd frontend
npm install
npm run dev      # 개발 서버
npm run build    # 프로덕션 빌드
```

---

## Backend (Spring Boot)

### 패키지 구조

```
com.a401.reppl/
├── config/           # WebSocket, Kafka, Redis, S3 설정
├── controller/       # REST API (JobController, UploadUrlController)
│   └── dto/          # 요청/응답 DTO
├── service/          # 비즈니스 로직 (JobService, S3Service, WebSocketPushService)
├── kafka/            # Kafka Producer/Consumer + DTO
├── domain/           # 도메인 모델 (JobState, JobStatus, Redis Repository)
├── exception/        # 커스텀 예외 + GlobalExceptionHandler
└── common/dto/       # 공통 응답 포맷 (ApiResponse, ApiError)
```

### API 엔드포인트

| Method | URI | 설명 |
|--------|-----|------|
| GET | `/api/v1/session` | 세션 초기화/확인 |
| POST | `/api/v1/url/video` | 동영상 업로드 Presigned URL 발급 |
| POST | `/api/v1/url/images` | 이미지 업로드 Presigned URL 발급 (다중) |
| POST | `/api/v1/jobs` | 작업 시작 (Job 생성 → Kafka 발행) |
| GET | `/api/v1/jobs` | Job 목록 조회 (페이지네이션) |
| GET | `/api/v1/jobs/{jobId}` | Job 상태 조회 |
| GET | `/api/v1/jobs/{jobId}/result` | 결과 다운로드 URL 발급 |
| WS | `/ws` → `/topic/jobs/{jobId}` | 실시간 진행률 WebSocket |

### 공통 응답 포맷

```json
{ "success": true, "data": { }, "error": null }
{ "success": false, "data": null, "error": { "code": "ERROR_CODE", "message": "..." } }
```

### Kafka Topics

| Topic | Direction | 용도 |
|-------|-----------|------|
| `reppl.job.request.v1` | Spring → GPU | 작업 요청 발행 |
| `reppl.job.progress.v1` | GPU → Spring | 진행률/완료 이벤트 |

### Redis Key 설계

| Key Pattern | Type | 설명 |
|-------------|------|------|
| `sess:{sid}:keys` | SET | 세션에 업로드된 S3 파일 키 목록 |
| `sess:{sid}:jobs` | LIST | 세션의 Job ID 목록 |
| `job:{jobId}:state` | HASH | Job 상태 (status, progress, stage 등) |
| `job:{jobId}:session` | STRING | Job → 세션 역참조 |

### Job 상태/단계

- **Status**: `QUEUED` → `RUNNING` → `COMPLETED` / `FAILED`
- **Stage**: `DOWNLOAD` → `DETECT` → `REPLACE` → `ENCODE` → `UPLOAD`

### 명령어

```bash
cd backend
./gradlew build     # 빌드
./gradlew bootRun   # 실행
./gradlew test      # 테스트
```

---

## AI 파이프라인 (Python)

### 파이프라인 흐름

```
원본 영상 + AI 합성 프레임
    → Grounding DINO (객체 BBox 검출)
    → SAM (정밀 마스크 추출)
    → Shadow Map 추출 (HSV 기반)
    → Depth Estimation (Intel DPT-Large, 거리 기반 가려짐 처리)
    → 프레임별 합성 (Alpha Blending + Gaussian Feathering)
    → 결과 영상 출력
```

### 핵심 기술

| 기술 | 역할 |
|------|------|
| Grounding DINO (SwinT) | 텍스트 프롬프트 기반 객체 검출 |
| SAM (vit_h) | 픽셀 단위 정밀 마스크 추출 |
| Intel DPT-Large | 깊이 추정 → 거리 기반 가려짐(occlusion) 처리 |
| OpenCV | 영상 처리, 합성 |

### 시스템 요구사항

- Python 3.10, NVIDIA GPU (RTX 4070+ 권장), CUDA 12.1
- 모델 가중치: `models/groundingdino_swint_ogc.pth` (467MB), `models/sam_vit_h_4b8939.pth` (2.4GB)

### 명령어

```bash
cd ai
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
python main.py
```

---

## 인프라/배포

### Docker Compose 서비스

| 서비스 | 이미지 | 포트 |
|--------|--------|------|
| nginx | nginx:alpine | 80, 443 |
| frontend | 커스텀 빌드 | 내부 80 |
| backend | 커스텀 빌드 | 내부 8080 |
| redis | redis:7-alpine | 내부 6379 |
| kafka | cp-kafka:7.6.0 | 내부 9092, 외부 29092 |
| zookeeper | cp-zookeeper:7.6.0 | 내부 2181 |

### 로컬 실행

```bash
# docker-compose.local.yml 사용 (빌드 포함)
docker compose -f docker-compose.local.yml up --build
```

### EC2 배포

```bash
# 초기 서버 셋업
ssh -i J14A401T.pem ubuntu@<EC2_IP> "bash -s" < scripts/ec2-setup.sh

# 프로덕션 배포
docker compose up -d
```

### 환경 변수 (프로덕션)

- `EC2_HOST` - 도메인
- `AWS_ACCESS_KEY`, `AWS_SECRET_KEY`, `AWS_REGION`, `AWS_S3_BUCKET` - S3 설정
- `FRONTEND_IMAGE`, `BACKEND_IMAGE`, `TAG` - 컨테이너 이미지

---

## 브랜치 전략

- `master` - 프로덕션
- `dev` - 개발 통합
- `ai/*` - AI 파트 기능 브랜치
- `fe/*` / `[FE]` - 프론트엔드 기능 브랜치

## 커밋 컨벤션

```
[파트] type: 설명
예: [AI] feat: 거리 기반 객체 가려짐 기능 구현
    [FE] feat: 프론트 단일 작업 페이지와 밝은 워크스페이스 UI 적용
    [AI] chore: AI 파트 .gitignore 설정
```
