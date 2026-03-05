package com.a401.reppl.domain.session;

import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Repository;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Set;

@Repository
@RequiredArgsConstructor
public class SessionRedisRepository {

    private final StringRedisTemplate redisTemplate;

    private static final Duration SESSION_TTL = Duration.ofHours(24);

    // ==================== 세션 활성 관리 ====================

    /**
     * 세션 활성화 (마지막 활동시간 갱신)
     */
    public void touchSession(String sessionId) {
        double timestamp = Instant.now().toEpochMilli();
        redisTemplate.opsForZSet().add(SessionKeys.ACTIVE_SESSIONS, sessionId, timestamp);
    }

    /**
     * 만료된 세션 목록 조회
     */
    public Set<String> findExpiredSessions(Duration maxAge) {
        double expiredBefore = Instant.now().minus(maxAge).toEpochMilli();
        return redisTemplate.opsForZSet().rangeByScore(SessionKeys.ACTIVE_SESSIONS, 0, expiredBefore);
    }

    /**
     * 활성 세션 목록에서 제거
     */
    public void removeFromActiveSessions(String sessionId) {
        redisTemplate.opsForZSet().remove(SessionKeys.ACTIVE_SESSIONS, sessionId);
    }

    // ==================== 파일 키 관리 ====================

    /**
     * 업로드된 파일 키 추가
     */
    public void addFileKey(String sessionId, String fileKey) {
        String key = SessionKeys.sessionKeys(sessionId);
        redisTemplate.opsForSet().add(key, fileKey);
        redisTemplate.expire(key, SESSION_TTL);
    }

    /**
     * 업로드된 파일 키 목록 조회
     */
    public Set<String> getFileKeys(String sessionId) {
        return redisTemplate.opsForSet().members(SessionKeys.sessionKeys(sessionId));
    }

    /**
     * 파일 키 존재 여부 확인
     */
    public boolean hasFileKey(String sessionId, String fileKey) {
        return Boolean.TRUE.equals(
                redisTemplate.opsForSet().isMember(SessionKeys.sessionKeys(sessionId), fileKey)
        );
    }

    /**
     * 파일 키 제거
     */
    public void removeFileKey(String sessionId, String fileKey) {
        redisTemplate.opsForSet().remove(SessionKeys.sessionKeys(sessionId), fileKey);
    }

    /**
     * 모든 파일 키 삭제
     */
    public void clearFileKeys(String sessionId) {
        redisTemplate.delete(SessionKeys.sessionKeys(sessionId));
    }

    // ==================== Job 목록 관리 ====================

    /**
     * 세션에 Job 추가
     */
    public void addJob(String sessionId, String jobId) {
        String key = SessionKeys.sessionJobs(sessionId);
        redisTemplate.opsForList().leftPush(key, jobId);
        redisTemplate.expire(key, SESSION_TTL);
    }

    /**
     * 세션의 Job 목록 조회 (페이지네이션)
     */
    public List<String> getJobs(String sessionId, int page, int size) {
        String key = SessionKeys.sessionJobs(sessionId);
        long start = (long) page * size;
        long end = start + size - 1;
        return redisTemplate.opsForList().range(key, start, end);
    }

    /**
     * 세션의 전체 Job 수
     */
    public long getJobCount(String sessionId) {
        Long size = redisTemplate.opsForList().size(SessionKeys.sessionJobs(sessionId));
        return size != null ? size : 0;
    }

    /**
     * 세션의 모든 Job ID 조회
     */
    public List<String> getAllJobs(String sessionId) {
        return redisTemplate.opsForList().range(SessionKeys.sessionJobs(sessionId), 0, -1);
    }

    // ==================== 세션 정리 ====================

    /**
     * 세션 관련 모든 데이터 삭제
     */
    public void deleteSession(String sessionId) {
        redisTemplate.delete(SessionKeys.sessionKeys(sessionId));
        redisTemplate.delete(SessionKeys.sessionJobs(sessionId));
        removeFromActiveSessions(sessionId);
    }
}
