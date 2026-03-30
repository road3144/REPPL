package com.a401.reppl.domain.job;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.Instant;
import java.util.List;

/**
 * Job 상태 스냅샷 (Redis HASH 저장용)
 *
 * Redis Key: job:{jobId}:state
 *
 * 필드 설명:
 * ┌──────────────┬──────────┬─────────────────────────────────────┐
 * │ 필드         │ 타입     │ 설명                                │
 * ├──────────────┼──────────┼─────────────────────────────────────┤
 * │ jobId        │ String   │ Job 고유 식별자                     │
 * │ sessionId    │ String   │ 소속 세션 ID                        │
 * │ status       │ String   │ QUEUED/RUNNING/COMPLETED/FAILED     │
 * │ progress     │ Integer  │ 진행률 0~100                        │
 * │ stage        │ String   │ DOWNLOAD/DETECT/REPLACE/ENCODE/UPLOAD│
 * │ message      │ String   │ UI 표시용 상태 메시지               │
 * │ videoKey     │ String   │ 원본 영상 S3 key                    │
 * │ refImageKeys │ List     │ 참조 이미지 S3 key 목록 (JSON)      │
 * │ resultKey    │ String   │ 결과 영상 S3 key (완료 시)          │
 * │ createdAt    │ Instant  │ Job 생성 시각                       │
 * │ updatedAt    │ Instant  │ 마지막 업데이트 시각                │
 * └──────────────┴──────────┴─────────────────────────────────────┘
 */
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class JobState {

    private String jobId;
    private String sessionId;
    private JobStatus status;
    private Integer progress;
    private JobStage stage;
    private String message;

    // Job 타입 (PREVIEW / COMPOSITE)
    private String jobType;

    // 입력 파일
    private String videoKey;
    private List<String> refImageKeys;

    // 프리뷰 이미지 (프리뷰 Job 완료 시)
    private List<String> previewKeys;

    // DINO 키워드 (프리뷰 완료 시 GMS가 추출)
    private String dinoKeyword;

    // 결과 파일 (합성 Job 완료 시)
    private String resultKey;

    // ROI 정보 (JSON 문자열로 저장)
    private String roiJson;

    // 옵션 (JSON 문자열로 저장)
    private String optionsJson;

    // 타임스탬프
    private Instant createdAt;
    private Instant updatedAt;
}
