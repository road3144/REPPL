package com.a401.reppl.config;

import org.apache.kafka.clients.admin.NewTopic;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.TopicBuilder;

@Configuration
public class KafkaConfig {

    @Value("${kafka.topic.job-request}")
    private String jobRequestTopic;

    @Value("${kafka.topic.job-request.partitions}")
    private int jobRequestPartitions;

    @Value("${kafka.topic.job-progress}")
    private String jobProgressTopic;

    @Value("${kafka.topic.job-progress.partitions}")
    private int jobProgressPartitions;

    @Bean
    public NewTopic jobRequestTopic() {
        return TopicBuilder.name(jobRequestTopic)
                .partitions(jobRequestPartitions)
                .replicas(1)
                .build();
    }

    @Bean
    public NewTopic jobProgressTopic() {
        return TopicBuilder.name(jobProgressTopic)
                .partitions(jobProgressPartitions)
                .replicas(1)
                .build();
    }
}
