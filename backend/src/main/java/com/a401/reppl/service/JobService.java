package com.a401.reppl.service;

import com.a401.reppl.controller.dto.JobItemResponse;
import com.a401.reppl.controller.dto.JobListResponse;
import com.a401.reppl.controller.dto.JobResultResponse;
import com.a401.reppl.controller.dto.JobStatusResponse;
import com.a401.reppl.controller.dto.PreviewCreateRequest;
import com.a401.reppl.controller.dto.PreviewCreateResponse;
import com.a401.reppl.controller.dto.PreviewListResponse;
import com.a401.reppl.controller.dto.PreviewSelectResponse;
import com.a401.reppl.domain.job.JobRedisRepository;
import com.a401.reppl.domain.job.JobState;
import com.a401.reppl.domain.job.JobStatus;
import com.a401.reppl.domain.session.SessionRedisRepository;
import com.a401.reppl.exception.InvalidKeySelectionException;
import com.a401.reppl.exception.JobNotCompletedException;
import com.a401.reppl.exception.JobNotFoundException;
import com.a401.reppl.kafka.CompositeRequestProducer;
import com.a401.reppl.kafka.PreviewRequestProducer;
import com.a401.reppl.kafka.dto.CompositeRequestEvent;
import com.a401.reppl.kafka.dto.JobRequestEvent;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class JobService {

    private final JobRedisRepository jobRedisRepository;
    private final SessionRedisRepository sessionRedisRepository;
    private final PreviewRequestProducer previewRequestProducer;
    private final CompositeRequestProducer compositeRequestProducer;
    private final S3Service s3Service;
    private final ObjectMapper objectMapper;
    private final org.springframework.data.redis.core.StringRedisTemplate redisTemplate;

    @Value("${cloud.aws.s3.bucket}")
    private String s3Bucket;

    private static final String JOB_COUNTER_KEY = "job:counter";
    private static final DateTimeFormatter DATE_FORMAT = DateTimeFormatter.ofPattern("yyyyMMdd");

    public JobListResponse getJobs(String sessionId, int page, int size) {
        // 1. 세션의 Job ID 목록 조회 (페이지네이션)
        List<String> jobIds = sessionRedisRepository.getJobs(sessionId, page, size);
        long totalCount = sessionRedisRepository.getJobCount(sessionId);

        // 2. 각 Job의 상태 조회
        List<JobItemResponse> items = jobIds.stream()
                .map(jobRedisRepository::findJobState)
                .filter(opt -> opt.isPresent())
                .map(opt -> JobItemResponse.from(opt.get()))
                .collect(Collectors.toList());

        // 3. 페이지 정보 계산
        int totalPages = (int) Math.ceil((double) totalCount / size);

        return JobListResponse.builder()
                .items(items)
                .page(page)
                .size(size)
                .totalCount(totalCount)
                .totalPages(totalPages)
                .build();
    }

    public JobStatusResponse getJobStatus(String jobId) {
        JobState state = jobRedisRepository.findJobState(jobId)
                .orElseThrow(() -> new JobNotFoundException(jobId));

        return JobStatusResponse.from(state);
    }

    public JobResultResponse getJobResult(String jobId) {
        JobState state = jobRedisRepository.findJobState(jobId)
                .orElseThrow(() -> new JobNotFoundException(jobId));

        if (state.getStatus() != JobStatus.COMPLETED) {
            throw new JobNotCompletedException(jobId, state.getStatus().name());
        }

        if (state.getResultKey() == null) {
            throw new JobNotCompletedException(jobId, state.getStatus().name());
        }

        S3Service.PresignedDownload download = s3Service.generateDownloadUrl(state.getResultKey());

        return JobResultResponse.builder()
                .download(JobResultResponse.DownloadInfo.builder()
                        .key(download.key())
                        .url(download.url())
                        .method(download.method())
                        .expiresAt(download.expiresAt())
                        .build())
                .build();
    }

    // ══════════════════════════════════════════════════════════
    // 프리뷰 Job
    // ══════════════════════════════════════════════════════════

    public PreviewCreateResponse createPreviewJob(String sessionId, PreviewCreateRequest request) {
        // 키 유효성 검증
        validateKeys(sessionId, request.getVideoKey(), request.getRefImageKeys());

        String jobId = generateJobId();
        Instant now = Instant.now();

        // JobState 생성 (jobType = PREVIEW)
        JobState jobState = JobState.builder()
                .jobId(jobId)
                .sessionId(sessionId)
                .jobType("PREVIEW")
                .status(JobStatus.QUEUED)
                .progress(0)
                .videoKey(request.getVideoKey())
                .refImageKeys(request.getRefImageKeys())
                .optionsJson(request.getOptions() != null ? toJson(request.getOptions()) : null)
                .createdAt(now)
                .updatedAt(now)
                .build();

        jobRedisRepository.saveJobState(jobState);
        sessionRedisRepository.addJob(sessionId, jobId);

        // Kafka 프리뷰 요청 발행
        JobRequestEvent event = buildPreviewRequestEvent(jobId, request, now);
        previewRequestProducer.send(event);

        log.info("Preview job created: jobId={}, sessionId={}", jobId, sessionId);

        return PreviewCreateResponse.builder()
                .jobId(jobId)
                .status(JobStatus.QUEUED.name())
                .build();
    }

    public PreviewListResponse getPreviewUrls(String jobId) {
        JobState state = jobRedisRepository.findJobState(jobId)
                .orElseThrow(() -> new JobNotFoundException(jobId));

        if (!"PREVIEW".equals(state.getJobType())) {
            throw new IllegalArgumentException("프리뷰 Job이 아닙니다: " + jobId);
        }

        if (state.getStatus() != JobStatus.COMPLETED) {
            throw new JobNotCompletedException(jobId, state.getStatus().name());
        }

        List<String> previewKeys = state.getPreviewKeys();
        if (previewKeys == null || previewKeys.isEmpty()) {
            throw new JobNotCompletedException(jobId, "PREVIEW_KEYS_EMPTY");
        }

        List<PreviewListResponse.PreviewItem> items = new ArrayList<>();
        for (int i = 0; i < previewKeys.size(); i++) {
            String key = previewKeys.get(i);
            S3Service.PresignedDownload download = s3Service.generateDownloadUrl(key);
            items.add(PreviewListResponse.PreviewItem.builder()
                    .index(i)
                    .key(key)
                    .url(download.url())
                    .build());
        }

        return PreviewListResponse.builder()
                .jobId(jobId)
                .previews(items)
                .build();
    }

    public PreviewSelectResponse selectPreviewAndStartComposite(String sessionId, String previewJobId, int selectedIndex) {
        // 프리뷰 Job 검증
        JobState previewState = jobRedisRepository.findJobState(previewJobId)
                .orElseThrow(() -> new JobNotFoundException(previewJobId));

        if (!"PREVIEW".equals(previewState.getJobType())) {
            throw new IllegalArgumentException("프리뷰 Job이 아닙니다: " + previewJobId);
        }

        if (previewState.getStatus() != JobStatus.COMPLETED) {
            throw new JobNotCompletedException(previewJobId, previewState.getStatus().name());
        }

        List<String> previewKeys = previewState.getPreviewKeys();
        if (previewKeys == null || selectedIndex >= previewKeys.size()) {
            throw new IllegalArgumentException("유효하지 않은 프리뷰 인덱스: " + selectedIndex);
        }

        String selectedPreviewKey = previewKeys.get(selectedIndex);

        // 합성 Job 생성
        String compositeJobId = generateJobId();
        Instant now = Instant.now();

        Map<String, Object> options = previewState.getOptionsJson() != null
                ? fromJson(previewState.getOptionsJson(), Map.class)
                : Map.of();

        JobState compositeState = JobState.builder()
                .jobId(compositeJobId)
                .sessionId(sessionId)
                .jobType("COMPOSITE")
                .status(JobStatus.QUEUED)
                .progress(0)
                .videoKey(previewState.getVideoKey())
                .refImageKeys(List.of(selectedPreviewKey))
                .optionsJson(toJson(options))
                .createdAt(now)
                .updatedAt(now)
                .build();

        jobRedisRepository.saveJobState(compositeState);
        sessionRedisRepository.addJob(sessionId, compositeJobId);

        // Kafka 합성 요청 발행
        CompositeRequestEvent event = CompositeRequestEvent.builder()
                .schemaVersion(1)
                .jobId(compositeJobId)
                .requestedAt(now)
                .video(JobRequestEvent.S3Location.builder()
                        .bucket(s3Bucket)
                        .key(previewState.getVideoKey())
                        .build())
                .selectedPreview(JobRequestEvent.S3Location.builder()
                        .bucket(s3Bucket)
                        .key(selectedPreviewKey)
                        .build())
                .output(JobRequestEvent.OutputInfo.builder()
                        .bucket(s3Bucket)
                        .key("results/" + compositeJobId + "/output.mp4")
                        .build())
                .options(options)
                .build();

        compositeRequestProducer.send(event);

        log.info("Composite job created: jobId={}, previewJobId={}, selectedIndex={}",
                compositeJobId, previewJobId, selectedIndex);

        return PreviewSelectResponse.builder()
                .compositeJobId(compositeJobId)
                .status(JobStatus.QUEUED.name())
                .build();
    }

    private JobRequestEvent buildPreviewRequestEvent(String jobId, PreviewCreateRequest request, Instant requestedAt) {
        JobRequestEvent.S3Location videoLocation = JobRequestEvent.S3Location.builder()
                .bucket(s3Bucket)
                .key(request.getVideoKey())
                .build();

        List<JobRequestEvent.S3Location> imageLocations = request.getRefImageKeys().stream()
                .map(key -> JobRequestEvent.S3Location.builder()
                        .bucket(s3Bucket)
                        .key(key)
                        .build())
                .collect(Collectors.toList());

        JobRequestEvent.InputInfo input = JobRequestEvent.InputInfo.builder()
                .video(videoLocation)
                .replacementImages(imageLocations)
                .build();

        JobRequestEvent.OutputInfo output = JobRequestEvent.OutputInfo.builder()
                .bucket(s3Bucket)
                .key("previews/" + jobId + "/")
                .build();

        return JobRequestEvent.builder()
                .schemaVersion(1)
                .jobId(jobId)
                .requestedAt(requestedAt)
                .input(input)
                .output(output)
                .options(request.getOptions())
                .build();
    }

    private <T> T fromJson(String json, Class<T> clazz) {
        try {
            return objectMapper.readValue(json, clazz);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("JSON 파싱 실패", e);
        }
    }

    private void validateKeys(String sessionId, String videoKey, List<String> imageKeys) {
        Set<String> sessionKeys = sessionRedisRepository.getFileKeys(sessionId);

        List<String> invalidKeys = new ArrayList<>();

        // 비디오 키 검증
        boolean videoKeyValid = sessionKeys.contains(videoKey);

        // 이미지 키 검증
        List<String> invalidImageKeys = imageKeys.stream()
                .filter(key -> !sessionKeys.contains(key))
                .collect(Collectors.toList());

        if (!videoKeyValid || !invalidImageKeys.isEmpty()) {
            throw new InvalidKeySelectionException(
                    videoKeyValid ? null : videoKey,
                    invalidImageKeys
            );
        }
    }

    private String generateJobId() {
        String date = LocalDate.now().format(DATE_FORMAT);
        Long counter = redisTemplate.opsForValue().increment(JOB_COUNTER_KEY);
        return String.format("job_%s_%06d", date, counter);
    }

    private String toJson(Object obj) {
        try {
            return objectMapper.writeValueAsString(obj);
        } catch (JsonProcessingException e) {
            log.error("Failed to convert object to JSON", e);
            throw new RuntimeException("JSON 변환 실패", e);
        }
    }
}
