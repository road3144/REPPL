package com.a401.reppl.service;

import com.a401.reppl.domain.job.JobStage;
import com.a401.reppl.domain.job.JobStatus;
import lombok.RequiredArgsConstructor;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class WebSocketPushService {

    private final SimpMessagingTemplate messagingTemplate;

    public void pushJobProgress(String jobId, JobStatus status, int progress, String message) {
        pushJobProgress(jobId, status, progress, null, message, null);
    }

    public void pushJobProgress(String jobId, JobStatus status, int progress,
                                JobStage stage, String message, List<String> previewKeys) {
        Map<String, Object> payload = new HashMap<>();
        payload.put("jobId", jobId);
        payload.put("status", status.name());
        payload.put("progress", progress);
        payload.put("message", message != null ? message : "");
        if (stage != null) {
            payload.put("stage", stage.name());
        }
        if (previewKeys != null && !previewKeys.isEmpty()) {
            payload.put("previewKeys", previewKeys);
        }
        messagingTemplate.convertAndSend("/topic/jobs/" + jobId, payload);
    }
}
