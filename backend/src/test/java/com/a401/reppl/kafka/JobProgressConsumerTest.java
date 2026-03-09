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
    // COMPLETED
    // ────────────────────────────────────────────────────────────

    @Test
    void COMPLETED_이벤트_completeJob_호출하고_progress_100으로_push() {
        String message = """
                {"jobId":"job-1","status":"COMPLETED","percent":100,
                 "outputKey":"results/job-1/output.mp4","message":"Done","seq":5}
                """;

        consumer.consume(message);

        verify(jobRedisRepository).completeJob("job-1", "results/job-1/output.mp4");
        verify(webSocketPushService).pushJobProgress("job-1", JobStatus.COMPLETED, 100, "Done");
        verify(jobRedisRepository, never()).failJob(any(), any());
        verify(jobRedisRepository, never()).updateProgress(any(), any(), any(), any(), any());
    }

    @Test
    void COMPLETED_이벤트_outputKey_null이어도_completeJob_호출됨() {
        String message = """
                {"jobId":"job-1","status":"COMPLETED","percent":100,"seq":5}
                """;

        consumer.consume(message);

        verify(jobRedisRepository).completeJob("job-1", null);
        verify(webSocketPushService).pushJobProgress("job-1", JobStatus.COMPLETED, 100, null);
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
        verify(webSocketPushService).pushJobProgress("job-2", JobStatus.FAILED, 30, "GPU out of memory");
        verify(jobRedisRepository, never()).completeJob(any(), any());
        verify(jobRedisRepository, never()).updateProgress(any(), any(), any(), any(), any());
    }

    // ────────────────────────────────────────────────────────────
    // RUNNING (default 분기)
    // ────────────────────────────────────────────────────────────

    @Test
    void RUNNING_이벤트_updateProgress_호출하고_push() {
        String message = """
                {"jobId":"job-3","status":"RUNNING","stage":"DETECT",
                 "percent":42,"message":"Detecting objects","seq":2}
                """;

        consumer.consume(message);

        verify(jobRedisRepository).updateProgress("job-3", JobStatus.RUNNING, 42, JobStage.DETECT, "Detecting objects");
        verify(webSocketPushService).pushJobProgress("job-3", JobStatus.RUNNING, 42, "Detecting objects");
        verify(jobRedisRepository, never()).completeJob(any(), any());
        verify(jobRedisRepository, never()).failJob(any(), any());
    }

    @Test
    void QUEUED_이벤트_updateProgress_호출됨() {
        String message = """
                {"jobId":"job-4","status":"QUEUED","percent":0,"seq":1}
                """;

        consumer.consume(message);

        verify(jobRedisRepository).updateProgress("job-4", JobStatus.QUEUED, 0, null, null);
        verify(webSocketPushService).pushJobProgress("job-4", JobStatus.QUEUED, 0, null);
    }

    @Test
    void RUNNING_stage_없으면_null로_updateProgress() {
        String message = """
                {"jobId":"job-5","status":"RUNNING","percent":10,"seq":1}
                """;

        consumer.consume(message);

        verify(jobRedisRepository).updateProgress("job-5", JobStatus.RUNNING, 10, null, null);
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
        verify(webSocketPushService, never()).pushJobProgress(any(), any(), anyInt(), any());
    }

    @Test
    void 빈_문자열_수신시_예외_전파_안됨() {
        assertThatCode(() -> consumer.consume(""))
                .doesNotThrowAnyException();
    }

    @Test
    void 알수없는_status_필드_포함시_역직렬화_실패해도_예외_전파_안됨() {
        // status가 enum에 없는 값
        String message = """
                {"jobId":"job-6","status":"UNKNOWN_STATUS","percent":50,"seq":1}
                """;

        assertThatCode(() -> consumer.consume(message))
                .doesNotThrowAnyException();
    }
}
