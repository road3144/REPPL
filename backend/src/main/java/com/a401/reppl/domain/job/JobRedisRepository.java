package com.a401.reppl.domain.job;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Repository;

import java.time.Duration;
import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Repository
@RequiredArgsConstructor
public class JobRedisRepository {

    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;

    private static final Duration JOB_TTL = Duration.ofHours(24);

    /**
     * Job 상태 저장
     */
    public void saveJobState(JobState state) {
        String key = JobKeys.jobState(state.getJobId());
        Map<String, String> hash = toStringHash(state);
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
        return Optional.of(fromStringHash(entries));
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
    public void completePreviewJob(String jobId, List<String> previewKeys, String dinoKeyword) {
        String key = JobKeys.jobState(jobId);
        Map<String, String> updates = new HashMap<>();
        updates.put("status", JobStatus.COMPLETED.name());
        updates.put("progress", "100");
        try {
            updates.put("previewKeys", objectMapper.writeValueAsString(previewKeys));
        } catch (JsonProcessingException e) {
            updates.put("previewKeys", "[]");
        }
        if (dinoKeyword != null) {
            updates.put("dinoKeyword", dinoKeyword);
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

    // ── 수동 직렬화/역직렬화 ──

    private Map<String, String> toStringHash(JobState state) {
        Map<String, String> hash = new HashMap<>();
        hash.put("jobId", state.getJobId());
        hash.put("sessionId", state.getSessionId());
        hash.put("status", state.getStatus().name());
        hash.put("progress", String.valueOf(state.getProgress()));
        if (state.getJobType() != null) hash.put("jobType", state.getJobType());
        if (state.getStage() != null) hash.put("stage", state.getStage().name());
        if (state.getMessage() != null) hash.put("message", state.getMessage());
        if (state.getVideoKey() != null) hash.put("videoKey", state.getVideoKey());
        if (state.getRefImageKeys() != null) {
            try {
                hash.put("refImageKeys", objectMapper.writeValueAsString(state.getRefImageKeys()));
            } catch (JsonProcessingException ignored) {}
        }
        if (state.getPreviewKeys() != null) {
            try {
                hash.put("previewKeys", objectMapper.writeValueAsString(state.getPreviewKeys()));
            } catch (JsonProcessingException ignored) {}
        }
        if (state.getDinoKeyword() != null) hash.put("dinoKeyword", state.getDinoKeyword());
        if (state.getResultKey() != null) hash.put("resultKey", state.getResultKey());
        if (state.getRoiJson() != null) hash.put("roiJson", state.getRoiJson());
        if (state.getOptionsJson() != null) hash.put("optionsJson", state.getOptionsJson());
        if (state.getCreatedAt() != null) hash.put("createdAt", state.getCreatedAt().toString());
        if (state.getUpdatedAt() != null) hash.put("updatedAt", state.getUpdatedAt().toString());
        return hash;
    }

    private JobState fromStringHash(Map<Object, Object> entries) {
        JobState.JobStateBuilder builder = JobState.builder();
        String val;

        val = str(entries, "jobId");       if (val != null) builder.jobId(val);
        val = str(entries, "sessionId");   if (val != null) builder.sessionId(val);
        val = str(entries, "status");      if (val != null) builder.status(JobStatus.valueOf(val));
        val = str(entries, "progress");    if (val != null) builder.progress(Integer.valueOf(val));
        val = str(entries, "jobType");     if (val != null) builder.jobType(val);
        val = str(entries, "stage");       if (val != null) builder.stage(JobStage.valueOf(val));
        val = str(entries, "message");     if (val != null) builder.message(val);
        val = str(entries, "videoKey");    if (val != null) builder.videoKey(val);
        val = str(entries, "dinoKeyword"); if (val != null) builder.dinoKeyword(val);
        val = str(entries, "resultKey");   if (val != null) builder.resultKey(val);
        val = str(entries, "roiJson");     if (val != null) builder.roiJson(val);
        val = str(entries, "optionsJson"); if (val != null) builder.optionsJson(val);
        val = str(entries, "createdAt");   if (val != null) builder.createdAt(Instant.parse(val));
        val = str(entries, "updatedAt");   if (val != null) builder.updatedAt(Instant.parse(val));

        val = str(entries, "refImageKeys");
        if (val != null) {
            try {
                builder.refImageKeys(objectMapper.readValue(val, new TypeReference<List<String>>() {}));
            } catch (JsonProcessingException ignored) {}
        }

        val = str(entries, "previewKeys");
        if (val != null) {
            try {
                builder.previewKeys(objectMapper.readValue(val, new TypeReference<List<String>>() {}));
            } catch (JsonProcessingException ignored) {}
        }

        return builder.build();
    }

    private static String str(Map<Object, Object> map, String key) {
        Object v = map.get(key);
        return v != null ? v.toString() : null;
    }
}
