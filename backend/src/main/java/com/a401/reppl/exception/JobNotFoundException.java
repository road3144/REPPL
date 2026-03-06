package com.a401.reppl.exception;

import lombok.Getter;

@Getter
public class JobNotFoundException extends RuntimeException {

    private final String jobId;

    public JobNotFoundException(String jobId) {
        super("Job을 찾을 수 없습니다: " + jobId);
        this.jobId = jobId;
    }
}
