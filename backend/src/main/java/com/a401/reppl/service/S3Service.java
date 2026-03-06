package com.a401.reppl.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import software.amazon.awssdk.services.s3.presigner.S3Presigner;
import software.amazon.awssdk.services.s3.presigner.model.GetObjectPresignRequest;
import software.amazon.awssdk.services.s3.presigner.model.PresignedGetObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.presigner.model.PresignedPutObjectRequest;
import software.amazon.awssdk.services.s3.presigner.model.PutObjectPresignRequest;

import java.time.Duration;
import java.time.Instant;

@Slf4j
@Service
@RequiredArgsConstructor
public class S3Service {

    private final S3Presigner s3Presigner;

    @Value("${cloud.aws.s3.bucket}")
    private String bucket;

    private static final Duration PRESIGNED_URL_DURATION = Duration.ofHours(24);
    private static final Duration PRESIGNED_UPLOAD_DURATION = Duration.ofMinutes(15);

    public PresignedDownload generateDownloadUrl(String key) {
        GetObjectRequest getObjectRequest = GetObjectRequest.builder()
                .bucket(bucket)
                .key(key)
                .build();

        GetObjectPresignRequest presignRequest = GetObjectPresignRequest.builder()
                .signatureDuration(PRESIGNED_URL_DURATION)
                .getObjectRequest(getObjectRequest)
                .build();

        PresignedGetObjectRequest presignedRequest = s3Presigner.presignGetObject(presignRequest);

        Instant expiresAt = Instant.now().plus(PRESIGNED_URL_DURATION);

        log.info("Generated presigned download URL: key={}, expiresAt={}", key, expiresAt);

        return new PresignedDownload(
                key,
                presignedRequest.url().toString(),
                "GET",
                expiresAt
        );
    }

    public record PresignedDownload(
            String key,
            String url,
            String method,
            Instant expiresAt
    ) {}

    public PresignedUpload generateUploadUrl(String key, String contentType) {
        PutObjectRequest putObjectRequest = PutObjectRequest.builder()
                .bucket(bucket)
                .key(key)
                .contentType(contentType)
                .build();

        PutObjectPresignRequest presignRequest = PutObjectPresignRequest.builder()
                .signatureDuration(PRESIGNED_UPLOAD_DURATION)
                .putObjectRequest(putObjectRequest)
                .build();

        PresignedPutObjectRequest presignedRequest = s3Presigner.presignPutObject(presignRequest);

        Instant expiresAt = Instant.now().plus(PRESIGNED_UPLOAD_DURATION);

        log.info("Generated presigned upload URL: key={}, expiresAt={}, contentType={}", key, expiresAt, contentType);

        return new PresignedUpload(
                key,
                presignedRequest.url().toString(),
                "PUT",
                expiresAt
        );
    }

    public record PresignedUpload(
            String key,
            String url,
            String method,
            Instant expiresAt
    ) {}
}
