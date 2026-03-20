package com.a401.reppl.config;

import org.apache.kafka.clients.admin.NewTopic;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.TopicBuilder;

@Configuration
public class KafkaConfig {

    @Value("${kafka.topic.job-preview}")
    private String jobPreviewTopic;

    @Value("${kafka.topic.job-preview.partitions}")
    private int jobPreviewPartitions;

    @Value("${kafka.topic.job-composite}")
    private String jobCompositeTopic;

    @Value("${kafka.topic.job-composite.partitions}")
    private int jobCompositePartitions;

    @Value("${kafka.topic.job-progress}")
    private String jobProgressTopic;

    @Value("${kafka.topic.job-progress.partitions}")
    private int jobProgressPartitions;

    @Bean
    public NewTopic jobPreviewTopic() {
        return TopicBuilder.name(jobPreviewTopic)
                .partitions(jobPreviewPartitions)
                .replicas(1)
                .build();
    }

    @Bean
    public NewTopic jobCompositeTopic() {
        return TopicBuilder.name(jobCompositeTopic)
                .partitions(jobCompositePartitions)
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
