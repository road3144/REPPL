package com.a401.reppl.service;

import com.a401.reppl.controller.dto.JobCreateResponse;
import com.a401.reppl.domain.job.JobRedisRepository;
import com.a401.reppl.domain.job.JobState;
import com.a401.reppl.domain.job.JobStatus;
import com.a401.reppl.domain.session.SessionRedisRepository;
import com.a401.reppl.exception.InvalidKeySelectionException;
import com.a401.reppl.kafka.JobRequestProducer;
import com.a401.reppl.kafka.dto.JobRequestEvent;
import com.a401.reppl.service.dto.JobCreateCommand;
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
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class JobService {

    private final JobRedisRepository jobRedisRepository;
    private final SessionRedisRepository sessionRedisRepository;
    private final JobRequestProducer jobRequestProducer;
    private final ObjectMapper objectMapper;

    @Value("${cloud.aws.s3.bucket}")
    private String s3Bucket;

    private static final AtomicInteger JOB_COUNTER = new AtomicInteger(0);
    private static final DateTimeFormatter DATE_FORMAT = DateTimeFormatter.ofPattern("yyyyMMdd");

    public JobCreateResponse createJob(String sessionId, JobCreateCommand command) {
        // 1. 키 유효성 검증
        validateKeys(sessionId, command.getVideoKey(), command.getRefImageKeys());

        // 2. JobId 생성
        String jobId = generateJobId();

        // 3. ROI와 options를 JSON 문자열로 변환
        String roiJson = toJson(command.getRoi());
        String optionsJson = command.getOptions() != null ? toJson(command.getOptions()) : null;

        // 4. JobState 생성 및 Redis 저장
        Instant now = Instant.now();
        JobState jobState = JobState.builder()
                .jobId(jobId)
                .sessionId(sessionId)
                .status(JobStatus.QUEUED)
                .progress(0)
                .videoKey(command.getVideoKey())
                .refImageKeys(command.getRefImageKeys())
                .roiJson(roiJson)
                .optionsJson(optionsJson)
                .createdAt(now)
                .updatedAt(now)
                .build();

        jobRedisRepository.saveJobState(jobState);

        // 5. 세션에 Job 추가
        sessionRedisRepository.addJob(sessionId, jobId);

        // 6. Kafka 이벤트 발행
        JobRequestEvent event = buildJobRequestEvent(jobId, command, now);
        jobRequestProducer.send(event);

        log.info("Job created: jobId={}, sessionId={}", jobId, sessionId);

        return JobCreateResponse.builder()
                .jobId(jobId)
                .status(JobStatus.QUEUED.name())
                .build();
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
        int counter = JOB_COUNTER.incrementAndGet();
        return String.format("job_%s_%06d", date, counter);
    }

    private JobRequestEvent buildJobRequestEvent(String jobId, JobCreateCommand command, Instant requestedAt) {
        // Input 설정
        JobRequestEvent.S3Location videoLocation = JobRequestEvent.S3Location.builder()
                .bucket(s3Bucket)
                .key(command.getVideoKey())
                .build();

        List<JobRequestEvent.S3Location> imageLocations = command.getRefImageKeys().stream()
                .map(key -> JobRequestEvent.S3Location.builder()
                        .bucket(s3Bucket)
                        .key(key)
                        .build())
                .collect(Collectors.toList());

        JobRequestEvent.InputInfo input = JobRequestEvent.InputInfo.builder()
                .video(videoLocation)
                .replacementImages(imageLocations)
                .build();

        // Output 설정
        JobRequestEvent.OutputInfo output = JobRequestEvent.OutputInfo.builder()
                .bucket(s3Bucket)
                .key("results/" + jobId + "/output.mp4")
                .build();

        // ROI 변환
        JobRequestEvent.RoiInfo roi = convertRoi(command.getRoi());

        return JobRequestEvent.builder()
                .schemaVersion(1)
                .jobId(jobId)
                .requestedAt(requestedAt)
                .input(input)
                .output(output)
                .roi(roi)
                .options(command.getOptions())
                .build();
    }

    private JobRequestEvent.RoiInfo convertRoi(JobCreateCommand.RoiInfo commandRoi) {
        if (commandRoi == null) {
            return null;
        }

        JobRequestEvent.RoiFrame frame = null;
        if (commandRoi.getFrame() != null) {
            frame = JobRequestEvent.RoiFrame.builder()
                    .type(commandRoi.getFrame().getType())
                    .timestampMs(commandRoi.getFrame().getTimestampMs())
                    .build();
        }

        List<JobRequestEvent.RoiBox> boxes = null;
        if (commandRoi.getBoxes() != null) {
            boxes = commandRoi.getBoxes().stream()
                    .map(box -> JobRequestEvent.RoiBox.builder()
                            .id(box.getId())
                            .x(box.getX())
                            .y(box.getY())
                            .w(box.getW())
                            .h(box.getH())
                            .build())
                    .collect(Collectors.toList());
        }

        return JobRequestEvent.RoiInfo.builder()
                .frame(frame)
                .coordinateSystem(commandRoi.getCoordinateSystem())
                .boxes(boxes)
                .build();
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
