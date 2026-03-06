package com.a401.reppl.controller.dto;

import com.a401.reppl.domain.job.JobState;
import com.a401.reppl.domain.job.JobStatus;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
@AllArgsConstructor
public class JobStatusResponse {

    private String jobId;
    private String status;
    private Integer progress;
    private String stage;
    private String message;
    private ResultInfo result;

    @Getter
    @Builder
    @AllArgsConstructor
    public static class ResultInfo {
        private String videoKey;
    }

    public static JobStatusResponse from(JobState state) {
        ResultInfo result = null;
        if (state.getStatus() == JobStatus.COMPLETED && state.getResultKey() != null) {
            result = ResultInfo.builder()
                    .videoKey(state.getResultKey())
                    .build();
        }

        return JobStatusResponse.builder()
                .jobId(state.getJobId())
                .status(state.getStatus() != null ? state.getStatus().name() : null)
                .progress(state.getProgress())
                .stage(state.getStage() != null ? state.getStage().name() : null)
                .message(state.getMessage())
                .result(result)
                .build();
    }
}
