package com.a401.reppl.exception;

import lombok.Getter;

@Getter
public class JobNotCompletedException extends RuntimeException {

    private final String jobId;
    private final String status;

    public JobNotCompletedException(String jobId, String status) {
        super("Job이 아직 완료되지 않았습니다: " + jobId);
        this.jobId = jobId;
        this.status = status;
    }
}
