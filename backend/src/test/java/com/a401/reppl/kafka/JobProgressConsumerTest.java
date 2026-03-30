package com.a401.reppl.kafka;

import com.a401.reppl.domain.job.JobRedisRepository;
import com.a401.reppl.domain.job.JobStage;
import com.a401.reppl.domain.job.JobStatus;
import com.a401.reppl.service.WebSocketPushService;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.BDDMockito.*;

@ExtendWith(MockitoExtension.class)
class JobProgressConsumerTest {

    @Mock JobRedisRepository jobRedisRepository;
    @Mock WebSocketPushService webSocketPushService;

    JobProgressConsumer consumer;

    @BeforeEach
    void setUp() {
        ObjectMapper objectMapper = new ObjectMapper()
                .registerModule(new JavaTimeModule())
                .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
        consumer = new JobProgressConsumer(objectMapper, jobRedisRepository, webSocketPushService);
    }

    // ────────────────────────────────────────────────────────────
    // COMPLETED (합성 Job)
    // ────────────────────────────────────────────────────────────

    @Test
    void COMPLETED_이벤트_completeJob_호출하고_progress_100으로_push() {
        String message = """
                {"jobId":"job-1","status":"COMPLETED","percent":100,
                 "outputKey":"results/job-1/output.mp4","message":"Done","seq":5}
                """;

        consumer.consume(message);

        verify(jobRedisRepository).completeJob("job-1", "results/job-1/output.mp4");
        verify(webSocketPushService).pushJobProgress(eq("job-1"), eq(JobStatus.COMPLETED), eq(100),
                any(), eq("Done"), isNull());
        verify(jobRedisRepository, never()).failJob(any(), any());
        verify(jobRedisRepository, never()).updateProgress(any(), any(), any(), any(), any());
    }

    // ────────────────────────────────────────────────────────────
    // COMPLETED (프리뷰 Job - previewKeys 포함)
    // ────────────────────────────────────────────────────────────

    @Test
    void COMPLETED_프리뷰_이벤트_completePreviewJob_호출() {
        String message = """
                {"jobId":"job-p1","status":"COMPLETED","percent":100,
                 "previewKeys":["previews/job-p1/preview_0.png","previews/job-p1/preview_1.png"],
                 "message":"Preview done","seq":5}
                """;

        consumer.consume(message);

        verify(jobRedisRepository).completePreviewJob(eq("job-p1"), anyList(), any());
        verify(jobRedisRepository, never()).completeJob(any(), any());
    }

    // ────────────────────────────────────────────────────────────
    // FAILED
    // ────────────────────────────────────────────────────────────

    @Test
    void FAILED_이벤트_failJob_호출하고_현재_percent로_push() {
        String message = """
                {"jobId":"job-2","status":"FAILED","percent":30,
                 "message":"GPU out of memory","seq":3}
                """;

        consumer.consume(message);

        verify(jobRedisRepository).failJob("job-2", "GPU out of memory");
        verify(webSocketPushService).pushJobProgress(eq("job-2"), eq(JobStatus.FAILED), eq(30),
                any(), eq("GPU out of memory"), isNull());
        verify(jobRedisRepository, never()).completeJob(any(), any());
        verify(jobRedisRepository, never()).updateProgress(any(), any(), any(), any(), any());
    }

    // ────────────────────────────────────────────────────────────
    // RUNNING
    // ────────────────────────────────────────────────────────────

    @Test
    void RUNNING_이벤트_updateProgress_호출하고_push() {
        String message = """
                {"jobId":"job-3","status":"RUNNING","stage":"DINO",
                 "percent":42,"message":"Detecting objects","seq":2}
                """;

        consumer.consume(message);

        verify(jobRedisRepository).updateProgress("job-3", JobStatus.RUNNING, 42, JobStage.DINO, "Detecting objects");
        verify(webSocketPushService).pushJobProgress(eq("job-3"), eq(JobStatus.RUNNING), eq(42),
                eq(JobStage.DINO), eq("Detecting objects"), isNull());
        verify(jobRedisRepository, never()).completeJob(any(), any());
        verify(jobRedisRepository, never()).failJob(any(), any());
    }

    // ────────────────────────────────────────────────────────────
    // 에러 처리
    // ────────────────────────────────────────────────────────────

    @Test
    void 잘못된_JSON_수신시_예외_전파_안됨() {
        assertThatCode(() -> consumer.consume("not-a-json"))
                .doesNotThrowAnyException();

        verify(jobRedisRepository, never()).updateProgress(any(), any(), any(), any(), any());
        verify(jobRedisRepository, never()).completeJob(any(), any());
        verify(jobRedisRepository, never()).failJob(any(), any());
    }

    @Test
    void 빈_문자열_수신시_예외_전파_안됨() {
        assertThatCode(() -> consumer.consume(""))
                .doesNotThrowAnyException();
    }
}
