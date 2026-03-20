package com.a401.reppl.domain.job;

import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.hash.Jackson2HashMapper;
import org.springframework.stereotype.Repository;

import java.time.Duration;
import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;

@Repository
@RequiredArgsConstructor
public class JobRedisRepository {

    private final StringRedisTemplate redisTemplate;
    private final Jackson2HashMapper hashMapper;

    private static final Duration JOB_TTL = Duration.ofHours(24);

    /**
     * Job 상태 저장
     */
    public void saveJobState(JobState state) {
        String key = JobKeys.jobState(state.getJobId());
        Map<String, Object> hash = hashMapper.toHash(state);
        redisTemplate.opsForHash().putAll(key, hash);
        redisTemplate.expire(key, JOB_TTL);

        // 역참조 저장
        redisTemplate.opsForValue().set(
                JobKeys.jobSession(state.getJobId()),
                state.getSessionId(),
                JOB_TTL
        );
    }

    /**
     * Job 상태 조회
     */
    public Optional<JobState> findJobState(String jobId) {
        String key = JobKeys.jobState(jobId);
        Map<Object, Object> entries = redisTemplate.opsForHash().entries(key);
        if (entries.isEmpty()) {
            return Optional.empty();
        }
        Map<String, Object> hash = entries.entrySet().stream()
                .collect(Collectors.toMap(
                        e -> e.getKey().toString(),
                        Map.Entry::getValue
                ));
        return Optional.of((JobState) hashMapper.fromHash(hash));
    }

    /**
     * Job 진행률 업데이트 (Kafka 이벤트 수신 시)
     */
    public void updateProgress(String jobId, JobStatus status, Integer progress, JobStage stage, String message) {
        String key = JobKeys.jobState(jobId);
        Map<String, String> updates = new HashMap<>();
        updates.put("status", status.name());
        updates.put("progress", String.valueOf(progress));
        if (stage != null) {
            updates.put("stage", stage.name());
        }
        if (message != null) {
            updates.put("message", message);
        }
        updates.put("updatedAt", Instant.now().toString());

        redisTemplate.opsForHash().putAll(key, updates);
    }

    /**
     * Job 완료 처리
     */
    public void completeJob(String jobId, String resultKey) {
        String key = JobKeys.jobState(jobId);
        Map<String, String> updates = new HashMap<>();
        updates.put("status", JobStatus.COMPLETED.name());
        updates.put("progress", "100");
        updates.put("resultKey", resultKey);
        updates.put("updatedAt", Instant.now().toString());

        redisTemplate.opsForHash().putAll(key, updates);

        // cleanup 대상에 추가
        long expirationTime = Instant.now().plus(JOB_TTL).toEpochMilli();
        redisTemplate.opsForZSet().add(JobKeys.CLEANUP_JOBS, jobId, expirationTime);
    }

    /**
     * 프리뷰 Job 완료 처리 (프리뷰 이미지 키 저장)
     */
    public void completePreviewJob(String jobId, List<String> previewKeys) {
        String key = JobKeys.jobState(jobId);
        Map<String, String> updates = new HashMap<>();
        updates.put("status", JobStatus.COMPLETED.name());
        updates.put("progress", "100");
        try {
            com.fasterxml.jackson.databind.ObjectMapper mapper = new com.fasterxml.jackson.databind.ObjectMapper();
            updates.put("previewKeys", mapper.writeValueAsString(previewKeys));
        } catch (com.fasterxml.jackson.core.JsonProcessingException e) {
            updates.put("previewKeys", "[]");
        }
        updates.put("updatedAt", Instant.now().toString());

        redisTemplate.opsForHash().putAll(key, updates);
    }

    /**
     * Job 실패 처리
     */
    public void failJob(String jobId, String errorMessage) {
        String key = JobKeys.jobState(jobId);
        Map<String, String> updates = new HashMap<>();
        updates.put("status", JobStatus.FAILED.name());
        updates.put("message", errorMessage);
        updates.put("updatedAt", Instant.now().toString());

        redisTemplate.opsForHash().putAll(key, updates);
    }

    /**
     * Job의 세션 ID 조회 (역참조)
     */
    public Optional<String> findSessionByJobId(String jobId) {
        return Optional.ofNullable(
                redisTemplate.opsForValue().get(JobKeys.jobSession(jobId))
        );
    }

    /**
     * Job 삭제
     */
    public void deleteJob(String jobId) {
        redisTemplate.delete(JobKeys.jobState(jobId));
        redisTemplate.delete(JobKeys.jobSession(jobId));
        redisTemplate.opsForZSet().remove(JobKeys.CLEANUP_JOBS, jobId);
    }

}
