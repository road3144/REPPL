package com.a401.reppl.kafka;

import com.a401.reppl.kafka.dto.JobRequestEvent;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
public class PreviewRequestProducer {

    private final KafkaTemplate<String, String> kafkaTemplate;
    private final ObjectMapper objectMapper;

    @Value("${kafka.topic.job-preview}")
    private String topic;

    public void send(JobRequestEvent event) {
        try {
            String message = objectMapper.writeValueAsString(event);
            kafkaTemplate.send(topic, event.getJobId(), message)
                    .whenComplete((result, ex) -> {
                        if (ex != null) {
                            log.error("Failed to send preview request: jobId={}", event.getJobId(), ex);
                        } else {
                            log.info("Preview request sent: jobId={}, topic={}, partition={}, offset={}",
                                    event.getJobId(),
                                    result.getRecordMetadata().topic(),
                                    result.getRecordMetadata().partition(),
                                    result.getRecordMetadata().offset());
                        }
                    });
        } catch (JsonProcessingException e) {
            log.error("Failed to serialize preview request: jobId={}", event.getJobId(), e);
            throw new RuntimeException("Failed to serialize preview request", e);
        }
    }
}
