package com.a401.reppl.domain.job;

/**
 * Job 상태 정의
 */
public enum JobStatus {
    QUEUED,      // 대기 중
    RUNNING,     // 처리 중
    COMPLETED,   // 완료
    FAILED       // 실패
}
