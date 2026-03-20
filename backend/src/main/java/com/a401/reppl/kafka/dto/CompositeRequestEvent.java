package com.a401.reppl.kafka.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.Map;

/**
 * Kafka 합성 작업 발행 이벤트
 * Topic: reppl.job.composite.v1
 *
 * 사용자가 프리뷰 이미지를 선택한 후 실제 합성 파이프라인을 시작할 때 발행.
 */
@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CompositeRequestEvent {

    private int schemaVersion;
    private String jobId;
    private Instant requestedAt;

    /** 원본 영상 S3 위치 */
    private JobRequestEvent.S3Location video;

    /** 사용자가 선택한 프리뷰 이미지 S3 위치 (changed_first_frame) */
    private JobRequestEvent.S3Location selectedPreview;

    /** 결과 영상 출력 위치 */
    private JobRequestEvent.OutputInfo output;

    /** 옵션 (placementPrompt 등) */
    private Map<String, Object> options;
}
