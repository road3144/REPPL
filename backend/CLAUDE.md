# REPPL Backend

## 서비스 개요
유튜브 영상을 쇼츠로 재가공할 때, 추가 촬영 없이 음료 PPL을 삽입하여 영상 1개당 추가 광고 수익을 창출하는 SaaS 플랫폼의 백엔드 서버

## 기술 스택
- **Language**: Java 21
- **Framework**: Spring Boot 4.0.3
- **Session/Cache**: Redis (Spring Session Data Redis)
- **Message Queue**: Apache Kafka
- **Real-time**: WebSocket (STOMP)
- **Storage**: AWS S3 (Presigned URL 방식)
- **Build**: Gradle 9.3.1

## 아키텍처
```
[Browser] <-> [Spring Boot] <-> [Redis]
                   |
                   v
              [Kafka Queue]
                   |
                   v
            [FastAPI GPU Server]
                   |
                   v
                [S3 Storage]
```

## 프로젝트 구조
```
backend/
├── src/main/java/com/a401/reppl/
│   └── RepplApplication.java
├── claude/api/          # API 명세 문서
├── build.gradle
└── settings.gradle
```

## 주요 흐름
1. 사용자 접속 → 세션 쿠키 발급 (Redis 저장)
2. 파일 업로드 → Presigned URL 발급 → S3에 직접 업로드
3. 작업 시작 요청 → Job 생성 (Redis) → Kafka Queue 발행
4. GPU 서버 작업 처리 → 진행률 Kafka로 전송
5. Spring이 진행률 수신 → WebSocket으로 실시간 전달
6. 작업 완료 → 결과 다운로드 URL 발급

## API 엔드포인트

### 세션
| Method | URI | 설명 |
|--------|-----|------|
| GET | `/api/v1/session` | 세션 초기화/확인 |

### 파일 업로드
| Method | URI | 설명 |
|--------|-----|------|
| POST | `/api/v1/url/video` | 동영상 업로드 Presigned URL 발급 |
| POST | `/api/v1/url/images` | 이미지 업로드 Presigned URL 발급 (다중) |

### Job 관리
| Method | URI | 설명 |
|--------|-----|------|
| POST | `/api/v1/jobs` | 작업 시작 (Job 생성) |
| GET | `/api/v1/jobs` | Job 목록 조회 (페이지네이션) |
| GET | `/api/v1/jobs/{jobId}` | Job 상태 조회 |
| GET | `/api/v1/jobs/{jobId}/result` | 결과 다운로드 URL 발급 |

### 실시간 통신
| Type | Endpoint | 설명 |
|------|----------|------|
| WebSocket | `/ws` | 실시간 연결 |
| Subscribe | `/topic/jobs/{jobId}` | Job 진행률 구독 |

## Kafka Topics

### 작업 발행 (Spring → GPU)
- **Topic**: `reppl.job.request.v1`
- **Partition Key**: `jobId`
- **Producer**: Spring
- **Consumer**: FastAPI (GPU 서버)

### 진행률 이벤트 (GPU → Spring)
- **Topic**: `vppl.job.progress.v1`
- **Partition Key**: `jobId`
- **Status**: `QUEUED` | `RUNNING` | `COMPLETED` | `FAILED`
- **Stage**: `DOWNLOAD` | `DETECT` | `REPLACE` | `ENCODE` | `UPLOAD`

## 공통 응답 포맷
```json
// 성공
{
  "success": true,
  "data": { },
  "error": null
}

// 실패
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "에러 메시지",
    "details": { }
  }
}
```

## Job 상태
- `QUEUED`: 대기 중
- `RUNNING`: 처리 중
- `DONE` / `COMPLETED`: 완료
- `FAILED`: 실패

## 에러 코드
- `FILE_TOO_LARGE`: 파일 크기 초과
- `UNSUPPORTED_MEDIA_TYPE`: 지원하지 않는 파일 형식
- `INVALID_KEY_SELECTION`: 세션에 없는 S3 key 사용

## Redis 데이터 구조

### Key 설계

| Key Pattern | Type | 설명 | TTL |
|-------------|------|------|-----|
| `sessions:active` | ZSET | 활성 세션 목록 (score = 마지막활동시간) | - |
| `sess:{sid}:keys` | SET | 세션에 업로드된 S3 파일 키 목록 | 세션 TTL |
| `sess:{sid}:jobs` | LIST | 세션의 Job ID 목록 (최신순) | 세션 TTL |
| `job:{jobId}:state` | HASH | Job 상태 스냅샷 | 24h |
| `job:{jobId}:session` | STRING | Job → 세션 역참조 | 24h |
| `jobs:cleanup` | ZSET | 정리 대상 Job (score = 만료시간) | - |

### 상세 스키마

#### `sessions:active` (ZSET)
```
ZADD sessions:active <lastActiveTimestamp> <sessionId>
```
- 세션 만료 확인 시 ZRANGEBYSCORE로 오래된 세션 조회

#### `sess:{sid}:keys` (SET)
```
SADD sess:{sid}:keys "tmp/sess_abc/video/2aa_input.mp4"
SADD sess:{sid}:keys "tmp/sess_abc/images/9f1_front.jpg"
```
- Presigned URL 발급 시 추가
- Job 생성 시 사용된 키 검증용

#### `sess:{sid}:jobs` (LIST)
```
LPUSH sess:{sid}:jobs "job_20260304_000123"
```
- Job 목록 조회 시 LRANGE로 페이지네이션

#### `job:{jobId}:state` (HASH)

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| jobId | String | O | Job 고유 식별자 |
| sessionId | String | O | 소속 세션 ID |
| status | String | O | `QUEUED` / `RUNNING` / `COMPLETED` / `FAILED` |
| progress | Integer | O | 진행률 0~100 |
| stage | String | - | `DOWNLOAD` / `DETECT` / `REPLACE` / `ENCODE` / `UPLOAD` |
| message | String | - | UI 표시용 상태 메시지 |
| videoKey | String | O | 원본 영상 S3 key |
| refImageKeys | JSON | O | 참조 이미지 S3 key 목록 (JSON array) |
| resultKey | String | - | 결과 영상 S3 key (완료 시) |
| roiJson | JSON | O | ROI 영역 정보 |
| optionsJson | JSON | - | 작업 옵션 |
| createdAt | ISO8601 | O | Job 생성 시각 |
| updatedAt | ISO8601 | O | 마지막 업데이트 시각 |

```
HSET job:{jobId}:state
  sessionId       "sess_abc"
  status          "RUNNING"
  progress        42
  stage           "REPLACE"
  message         "Replacing frames..."
  videoKey        "tmp/sess_abc/video/2aa_input.mp4"
  refImageKeys    "[\"tmp/.../1.jpg\",\"tmp/.../2.jpg\"]"
  resultKey       "results/job_xxx/output.mp4"
  roiJson         "{\"frame\":{...},\"boxes\":[...]}"
  optionsJson     "{\"mode\":\"PPL\",\"quality\":\"HIGH\"}"
  createdAt       "2026-03-04T01:00:00Z"
  updatedAt       "2026-03-04T01:10:22Z"
```

#### `job:{jobId}:session` (STRING)
```
SET job:{jobId}:session "sess_abc"
```
- Kafka 진행률 수신 시 세션 조회 없이 바로 WebSocket 전달 가능

#### `jobs:cleanup` (ZSET)
```
ZADD jobs:cleanup <expirationTimestamp> <jobId>
```
- 스케줄러가 주기적으로 만료된 Job 정리
- S3 결과물 삭제, Redis 데이터 삭제

### 세션 만료 처리
1. `sessions:active`에서 만료된 세션 조회
2. `sess:{sid}:keys` → S3 임시 파일 삭제
3. `sess:{sid}:jobs` → 각 Job을 `jobs:cleanup`에 추가
4. 세션 관련 키 삭제

## 개발 시 참고사항

### S3 Key 패턴
- 임시 업로드: `tmp/{sessionId}/video/{uuid}_{filename}`
- 이미지: `tmp/{sessionId}/images/{uuid}_{filename}`
- 결과물: `results/{jobId}/output.mp4`

### 파일 크기 제한
- 동영상: 최대 100MB (104857600 bytes)

### 지원 파일 형식
- 동영상: `video/mp4`
- 이미지: `image/jpeg`, `image/png`

## 명령어
```bash
# 빌드
./gradlew build

# 실행
./gradlew bootRun

# 테스트
./gradlew test
```
