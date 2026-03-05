package com.a401.reppl.kafka.dto;

import com.a401.reppl.domain.job.JobStage;
import com.a401.reppl.domain.job.JobStatus;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.Instant;

@Getter
@NoArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class JobProgressEvent {

    private int schemaVersion;
    private String jobId;
    private JobStatus status;
    private JobStage stage;
    private int percent;
    private String message;
    private Instant timestamp;
    private long seq;

    /** COMPLETED 상태일 때 GPU가 업로드한 S3 output key */
    private String outputKey;
}