package com.a401.reppl.domain.session;

/**
 * 세션 관련 Redis Key 패턴 정의
 *
 * Redis Key Patterns:
 * - sessions:active (ZSET)   : 활성 세션 목록, score = 마지막 활동시간
 * - sess:{sid}:keys (SET)    : 세션에 업로드된 S3 파일 키 목록
 * - sess:{sid}:jobs (LIST)   : 세션의 Job ID 목록 (최신순)
 */
public class SessionKeys {

    public static final String SESSION_PREFIX = "sess:";
    public static final String ACTIVE_SESSIONS = "sessions:active";
    public static final String KEYS_SUFFIX = ":keys";
    public static final String JOBS_SUFFIX = ":jobs";

    /**
     * sess:{sessionId}:keys
     */
    public static String sessionKeys(String sessionId) {
        return SESSION_PREFIX + sessionId + KEYS_SUFFIX;
    }

    /**
     * sess:{sessionId}:jobs
     */
    public static String sessionJobs(String sessionId) {
        return SESSION_PREFIX + sessionId + JOBS_SUFFIX;
    }
}
