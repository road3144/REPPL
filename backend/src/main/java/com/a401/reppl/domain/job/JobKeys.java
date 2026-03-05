package com.a401.reppl.domain.job;

/**
 * Job 관련 Redis Key 패턴 정의
 *
 * Redis Key Patterns:
 * - job:{jobId}:state (HASH)    : Job 상태 스냅샷
 * - job:{jobId}:session (STRING): Job → 세션 역참조
 * - jobs:cleanup (ZSET)         : 정리 대상 Job, score = 만료시간
 */
public class JobKeys {

    public static final String JOB_PREFIX = "job:";
    public static final String STATE_SUFFIX = ":state";
    public static final String SESSION_SUFFIX = ":session";
    public static final String CLEANUP_JOBS = "jobs:cleanup";

    /**
     * job:{jobId}:state
     */
    public static String jobState(String jobId) {
        return JOB_PREFIX + jobId + STATE_SUFFIX;
    }

    /**
     * job:{jobId}:session
     */
    public static String jobSession(String jobId) {
        return JOB_PREFIX + jobId + SESSION_SUFFIX;
    }
}
