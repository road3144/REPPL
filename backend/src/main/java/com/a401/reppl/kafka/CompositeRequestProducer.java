package com.a401.reppl.kafka;

import com.a401.reppl.kafka.dto.CompositeRequestEvent;
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
public class CompositeRequestProducer {

    private final KafkaTemplate<String, String> kafkaTemplate;
    private final ObjectMapper objectMapper;

    @Value("${kafka.topic.job-composite}")
    private String topic;

    public void send(CompositeRequestEvent event) {
        try {
            String message = objectMapper.writeValueAsString(event);
            kafkaTemplate.send(topic, event.getJobId(), message)
                    .whenComplete((result, ex) -> {
                        if (ex != null) {
                            log.error("Failed to send composite request: jobId={}", event.getJobId(), ex);
                        } else {
                            log.info("Composite request sent: jobId={}, topic={}, partition={}, offset={}",
                                    event.getJobId(),
                                    result.getRecordMetadata().topic(),
                                    result.getRecordMetadata().partition(),
                                    result.getRecordMetadata().offset());
                        }
                    });
        } catch (JsonProcessingException e) {
            log.error("Failed to serialize composite request: jobId={}", event.getJobId(), e);
            throw new RuntimeException("Failed to serialize composite request", e);
        }
    }
}
