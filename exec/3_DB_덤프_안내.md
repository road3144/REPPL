# DB 덤프 파일 안내

## 1. RDB (관계형 데이터베이스) — 해당 없음

본 프로젝트는 **MySQL, PostgreSQL, MariaDB 등의 관계형 데이터베이스를 사용하지 않습니다.**

따라서 SQL 덤프 파일이 존재하지 않으며, ERD도 별도로 없습니다.

---

## 2. 데이터 저장소 현황

본 프로젝트는 다음과 같은 비-RDB 저장소를 사용합니다:

### 2-1. Redis (인메모리 Key-Value 스토어)

- **용도**: Spring Session 관리, 작업(Job) 상태 저장
- **데이터 특성**: 세션 데이터 (24시간 TTL), 작업 진행률/결과 임시 저장
- **영속성 설정**:
  - AOF: `appendonly yes`, `appendfsync everysec`
  - RDB 스냅샷: `save 900 1`, `save 300 10`
- **볼륨**: Docker Named Volume `redis_data`

> Redis는 인메모리 스토어로, 서비스 운영 데이터가 휘발성입니다. 
> 세션과 작업 상태는 재배포 시에도 볼륨을 통해 유지되지만, 
> 별도의 덤프 파일로 관리할 필요는 없습니다.

### 2-2. AWS S3 (오브젝트 스토리지)

- **용도**: 영상 파일, 제품 이미지, 프리뷰 이미지, 합성 결과 영상 저장
- **버킷 구조** (예시):
  ```
  s3://<버킷명>/
  ├── videos/            # 원본 영상
  ├── ref-images/        # 제품 이미지
  ├── previews/{jobId}/  # 프리뷰 이미지 (preview_0.png, preview_1.png, ...)
  └── outputs/{jobId}/   # 합성 결과 영상
  ```
- **데이터 관리**: AWS S3 콘솔에서 직접 관리

### 2-3. Kafka (메시지 큐)

- **용도**: Backend ↔ AI Worker 간 비동기 작업 요청/진행률 전달
- **데이터 특성**: 메시지 보존 기간 168시간 (7일)
- **볼륨**: Docker Named Volume `kafka_data`

---

## 3. Redis 데이터 백업/복원 방법 (참고)

### 백업

```bash
# EC2 서버에서 실행
docker exec redis redis-cli BGSAVE

# 백업 파일 복사
docker cp redis:/data/dump.rdb ./exec/redis_dump.rdb
```

### 복원

```bash
# Redis 중지 후 덤프 파일 교체
docker stop redis
docker cp ./exec/redis_dump.rdb redis:/data/dump.rdb
docker start redis
```

---

## 4. Redis 주요 데이터 구조

| Key 패턴 | 타입 | 설명 |
|----------|------|------|
| `spring:session:sessions:*` | Hash | Spring 세션 데이터 |
| 작업 관련 키 | String/Hash | Job 상태, 진행률, 결과 URL 등 |

> 참고: Redis의 구체적인 키 구조는 Spring Session 및 애플리케이션 로직에 의해 자동 관리됩니다.
