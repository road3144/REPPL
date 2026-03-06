package com.a401.reppl.service;

import com.a401.reppl.controller.dto.JobCreateResponse;
import com.a401.reppl.domain.job.JobRedisRepository;
import com.a401.reppl.domain.job.JobStatus;
import com.a401.reppl.domain.session.SessionRedisRepository;
import com.a401.reppl.exception.InvalidKeySelectionException;
import com.a401.reppl.kafka.JobRequestProducer;
import com.a401.reppl.service.dto.JobCreateCommand;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.BDDMockito.*;

@ExtendWith(MockitoExtension.class)
class JobServiceTest {

    @Mock JobRedisRepository jobRedisRepository;
    @Mock SessionRedisRepository sessionRedisRepository;
    @Mock JobRequestProducer jobRequestProducer;
    @Mock ObjectMapper objectMapper;
    @InjectMocks JobService jobService;

    @BeforeEach
    void setUp() {
        ReflectionTestUtils.setField(jobService, "s3Bucket", "test-bucket");
    }

    // ────────────────────────────────────────────────────────────
    // 성공 케이스
    // ────────────────────────────────────────────────────────────

    @Test
    void createJob_성공_응답에_jobId와_QUEUED상태_포함() throws Exception {
        given(sessionRedisRepository.getFileKeys("sess-1"))
                .willReturn(Set.of("videos/a.mp4", "images/b.jpg"));
        given(objectMapper.writeValueAsString(any())).willReturn("{}");

        JobCreateResponse response = jobService.createJob("sess-1", command("videos/a.mp4", "images/b.jpg"));

        assertThat(response.getJobId()).matches("job_\\d{8}_\\d{6}");
        assertThat(response.getStatus()).isEqualTo("QUEUED");
    }

    @Test
    void createJob_성공_Redis_저장과_Kafka_발행_호출됨() throws Exception {
        given(sessionRedisRepository.getFileKeys("sess-1"))
                .willReturn(Set.of("videos/a.mp4", "images/b.jpg"));
        given(objectMapper.writeValueAsString(any())).willReturn("{}");

        jobService.createJob("sess-1", command("videos/a.mp4", "images/b.jpg"));

        verify(jobRedisRepository).saveJobState(argThat(state ->
                state.getSessionId().equals("sess-1") &&
                state.getStatus() == JobStatus.QUEUED &&
                state.getProgress() == 0
        ));
        verify(sessionRedisRepository).addJob(eq("sess-1"), anyString());
        verify(jobRequestProducer).send(any());
    }

    @Test
    void createJob_jobId는_호출마다_다름() throws Exception {
        given(sessionRedisRepository.getFileKeys(any())).willReturn(Set.of("videos/a.mp4"));
        given(objectMapper.writeValueAsString(any())).willReturn("{}");
        JobCreateCommand cmd = command("videos/a.mp4");

        JobCreateResponse r1 = jobService.createJob("sess-1", cmd);
        JobCreateResponse r2 = jobService.createJob("sess-1", cmd);

        assertThat(r1.getJobId()).isNotEqualTo(r2.getJobId());
    }

    @Test
    void createJob_refImageKeys_비어있어도_성공() throws Exception {
        given(sessionRedisRepository.getFileKeys(any())).willReturn(Set.of("videos/a.mp4"));
        given(objectMapper.writeValueAsString(any())).willReturn("{}");

        assertThatCode(() -> jobService.createJob("sess-1", command("videos/a.mp4")))
                .doesNotThrowAnyException();
    }

    // ────────────────────────────────────────────────────────────
    // 키 유효성 검증 실패
    // ────────────────────────────────────────────────────────────

    @Test
    void createJob_videoKey가_세션에없으면_예외() throws Exception {
        given(sessionRedisRepository.getFileKeys(any()))
                .willReturn(Set.of("images/b.jpg")); // videoKey 빠짐

        assertThatThrownBy(() -> jobService.createJob("sess-1", command("videos/missing.mp4", "images/b.jpg")))
                .isInstanceOf(InvalidKeySelectionException.class)
                .satisfies(e -> {
                    InvalidKeySelectionException ex = (InvalidKeySelectionException) e;
                    assertThat(ex.getVideoKey()).isEqualTo("videos/missing.mp4");
                    assertThat(ex.getInvalidImageKeys()).isEmpty();
                });
    }

    @Test
    void createJob_imageKey_일부가_세션에없으면_예외() throws Exception {
        given(sessionRedisRepository.getFileKeys(any()))
                .willReturn(Set.of("videos/a.mp4", "images/valid.jpg"));

        assertThatThrownBy(() ->
                jobService.createJob("sess-1", command("videos/a.mp4", "images/valid.jpg", "images/missing.jpg")))
                .isInstanceOf(InvalidKeySelectionException.class)
                .satisfies(e -> {
                    InvalidKeySelectionException ex = (InvalidKeySelectionException) e;
                    assertThat(ex.getVideoKey()).isNull(); // videoKey는 유효
                    assertThat(ex.getInvalidImageKeys()).containsExactly("images/missing.jpg");
                });
    }

    @Test
    void createJob_videoKey와_imageKey_모두없으면_둘다_예외에_포함() throws Exception {
        given(sessionRedisRepository.getFileKeys(any())).willReturn(Set.of());

        assertThatThrownBy(() -> jobService.createJob("sess-1", command("videos/a.mp4", "images/b.jpg")))
                .isInstanceOf(InvalidKeySelectionException.class)
                .satisfies(e -> {
                    InvalidKeySelectionException ex = (InvalidKeySelectionException) e;
                    assertThat(ex.getVideoKey()).isEqualTo("videos/a.mp4");
                    assertThat(ex.getInvalidImageKeys()).containsExactly("images/b.jpg");
                });
    }

    @Test
    void createJob_키검증_실패시_Redis와_Kafka_호출_안됨() throws Exception {
        given(sessionRedisRepository.getFileKeys(any())).willReturn(Set.of());

        assertThatThrownBy(() -> jobService.createJob("sess-1", command("videos/a.mp4")));

        verify(jobRedisRepository, never()).saveJobState(any());
        verify(jobRequestProducer, never()).send(any());
    }

    // ────────────────────────────────────────────────────────────
    // JSON 변환 실패
    // ────────────────────────────────────────────────────────────

    @Test
    void createJob_ROI_JSON변환_실패시_RuntimeException() throws Exception {
        given(sessionRedisRepository.getFileKeys(any())).willReturn(Set.of("videos/a.mp4"));
        given(objectMapper.writeValueAsString(any()))
                .willThrow(new JsonProcessingException("serialize error") {});

        assertThatThrownBy(() -> jobService.createJob("sess-1", command("videos/a.mp4")))
                .isInstanceOf(RuntimeException.class)
                .hasMessageContaining("JSON 변환 실패");

        verify(jobRedisRepository, never()).saveJobState(any());
    }

    // ────────────────────────────────────────────────────────────
    // 헬퍼
    // ────────────────────────────────────────────────────────────

    private JobCreateCommand command(String videoKey, String... imageKeys) {
        return JobCreateCommand.builder()
                .videoKey(videoKey)
                .refImageKeys(List.of(imageKeys))
                .roi(JobCreateCommand.RoiInfo.builder()
                        .coordinateSystem("pixel")
                        .boxes(List.of(
                                JobCreateCommand.RoiBox.builder()
                                        .id("box1").x(0.1).y(0.1).w(0.5).h(0.5).build()
                        ))
                        .build())
                .build();
    }
}
