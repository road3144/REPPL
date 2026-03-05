package com.a401.reppl.service;

import com.a401.reppl.domain.job.JobStatus;
import lombok.RequiredArgsConstructor;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

import java.util.Map;

@Service
@RequiredArgsConstructor
public class WebSocketPushService {

    private final SimpMessagingTemplate messagingTemplate;

    public void pushJobProgress(String jobId, JobStatus status, int progress, String message) {
        Map<String, Object> payload = Map.of(
                "jobId", jobId,
                "status", status.name(),
                "progress", progress,
                "message", message != null ? message : ""
        );
        messagingTemplate.convertAndSend("/topic/jobs/" + jobId, payload);
    }
}
