package com.a401.reppl.kafka;

import com.a401.reppl.domain.job.JobRedisRepository;
import com.a401.reppl.domain.job.JobStatus;
import com.a401.reppl.kafka.dto.JobProgressEvent;
import com.a401.reppl.service.WebSocketPushService;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
public class JobProgressConsumer {

    private final ObjectMapper objectMapper;
    private final JobRedisRepository jobRedisRepository;
    private final WebSocketPushService webSocketPushService;

    @KafkaListener(topics = "${kafka.topic.job-progress}", groupId = "${spring.kafka.consumer.group-id}")
    public void consume(String message) {
        try {
            JobProgressEvent event = objectMapper.readValue(message, JobProgressEvent.class);
            processEvent(event);
        } catch (Exception e) {
            log.error("Failed to process Kafka message: {}", message, e);
        }
    }

    private void processEvent(JobProgressEvent event) {
        String jobId = event.getJobId();
        JobStatus status = event.getStatus();

        switch (status) {
            case COMPLETED -> {
                if (event.getPreviewKeys() != null && !event.getPreviewKeys().isEmpty()) {
                    // 프리뷰 Job 완료 (dinoKeyword 포함)
                    jobRedisRepository.completePreviewJob(jobId, event.getPreviewKeys(), event.getDinoKeyword());
                    webSocketPushService.pushJobProgress(jobId, status, 100,
                            event.getStage(), event.getMessage(), event.getPreviewKeys());
                } else {
                    // 합성 Job 완료
                    jobRedisRepository.completeJob(jobId, event.getOutputKey());
                    webSocketPushService.pushJobProgress(jobId, status, 100,
                            event.getStage(), event.getMessage(), null);
                }
            }
            case FAILED -> {
                jobRedisRepository.failJob(jobId, event.getMessage());
                webSocketPushService.pushJobProgress(jobId, status, event.getPercent(),
                        event.getStage(), event.getMessage(), null);
            }
            default -> {
                jobRedisRepository.updateProgress(jobId, status, event.getPercent(), event.getStage(), event.getMessage());
                webSocketPushService.pushJobProgress(jobId, status, event.getPercent(),
                        event.getStage(), event.getMessage(), null);
            }
        }

        log.debug("Processed job progress event: jobId={}, status={}, stage={}, percent={}",
                jobId, status, event.getStage(), event.getPercent());
    }
}