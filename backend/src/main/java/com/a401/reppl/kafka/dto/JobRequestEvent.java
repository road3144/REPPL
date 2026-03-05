package com.a401.reppl.kafka.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * Kafka 작업 발행 이벤트
 * Topic: reppl.job.request.v1
 */
@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class JobRequestEvent {

    private int schemaVersion;
    private String jobId;
    private Instant requestedAt;

    private InputInfo input;
    private OutputInfo output;
    private RoiInfo roi;
    private Map<String, Object> options;

    @Getter
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class InputInfo {
        private S3Location video;
        private List<S3Location> replacementImages;
    }

    @Getter
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class OutputInfo {
        private String bucket;
        private String key;
    }

    @Getter
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class S3Location {
        private String bucket;
        private String key;
    }

    @Getter
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class RoiInfo {
        private RoiFrame frame;
        private String coordinateSystem;
        private List<RoiBox> boxes;
    }

    @Getter
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class RoiFrame {
        private String type;
        private Long timestampMs;
    }

    @Getter
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class RoiBox {
        private String id;
        private Double x;
        private Double y;
        private Double w;
        private Double h;
    }
}
