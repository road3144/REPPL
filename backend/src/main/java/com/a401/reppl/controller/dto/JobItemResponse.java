package com.a401.reppl.controller.dto;

import com.a401.reppl.domain.job.JobState;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;

import java.time.Instant;

@Getter
@Builder
@AllArgsConstructor
public class JobItemResponse {

    private String jobId;
    private String jobType;
    private String status;
    private Integer progress;
    private String stage;
    private String message;
    private Instant createdAt;

    public static JobItemResponse from(JobState state) {
        return JobItemResponse.builder()
                .jobId(state.getJobId())
                .jobType(state.getJobType())
                .status(state.getStatus() != null ? state.getStatus().name() : null)
                .progress(state.getProgress())
                .stage(state.getStage() != null ? state.getStage().name() : null)
                .message(state.getMessage())
                .createdAt(state.getCreatedAt())
                .build();
    }
}
