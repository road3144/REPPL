package com.a401.reppl.controller;

import com.a401.reppl.common.dto.ApiResponse;
import com.a401.reppl.controller.dto.*;
import com.a401.reppl.domain.session.SessionRedisRepository;
import com.a401.reppl.service.S3Service;
import jakarta.servlet.http.HttpSession;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.*;

@Slf4j
@RestController
@RequestMapping("/api/v1/url")
@RequiredArgsConstructor
public class UploadUrlController {

    private final S3Service s3Service;
    private final SessionRedisRepository sessionRedisRepository;

    private static final long MAX_VIDEO_SIZE = 50L * 1024 * 1024; // 업로드 파일 크기 제한 50MB
    private static final long MAX_IMAGE_SIZE = 10L * 1024 * 1024; // 업로드 파일 크기 제한 10MB

    /**
     * VIDEO 업로드 Presigned URL 발급 API
     *
     * 요청
     * POST /api/v1/url/video
     *
     * 역할
     * 1. 요청 검증
     * 2. S3 Object Key 생성
     * 3. Presigned URL 생성
     * 4. Redis 세션에 Key 저장
     * 5. URL 정보 반환
     */
    @PostMapping("/video")
    public ResponseEntity<ApiResponse<VideoUploadResponse>> getVideoUploadUrl(
            @Valid @RequestBody VideoUploadRequest request,
            HttpSession session) {

        // 현재 사용자 세션 ID
        String sessionId = session.getId();

        // 요청 body에서 영상 정보 추출
        String filename = request.getVideo().getFilename();
        String contentType = request.getVideo().getContentType();
        Long size = request.getVideo().getSizeBytes();

        log.info("영상 업로드 URL 요청: sessionId={}, filename={}, size={}",
                sessionId, filename, size);

        /**
         * 1. 요청 데이터 검증
         * - 파일 타입 검증
         * - 파일 크기 검증
         */
        validateVideoRequest(contentType, size);

        /**
         * 2. S3 Object Key 생성
         *
         * 예시:
         * tmp/{sessionId}/video/{uuid}_{filename}
         *
         * 목적
         * - 사용자별 파일 구분
         * - 파일 충돌 방지
         */
        String objectKey =
                "tmp/" + sessionId + "/video/" + UUID.randomUUID() + "_" + filename;

        /**
         * 3. Presigned URL 생성
         *
         * 클라이언트는 이 URL을 사용해 S3에 직접 PUT 업로드 수행
         */
        S3Service.PresignedUpload presigned =
                s3Service.generateUploadUrl(objectKey, contentType);

        /**
         * 4. Redis에 업로드 key 저장
         *
         * Job 생성 시 실제 업로드된 파일인지 검증
         */
        sessionRedisRepository.addFileKey(sessionId, objectKey);

        /**
         * 5. 응답 DTO 생성
         *
         * 명세 구조
         * data.upload.video
         */
        VideoUploadResponse.Video video =
                VideoUploadResponse.Video.builder()
                        .key(objectKey)
                        .url(presigned.url())
                        .method("PUT")
                        .headers(Map.of("Content-Type", contentType))
                        .expiresAt(Instant.now().plusSeconds(900).toString())
                        .build();

        VideoUploadResponse response =
                VideoUploadResponse.builder()
                        .upload(
                                VideoUploadResponse.Upload.builder()
                                        .video(video)
                                        .build()
                        )
                        .build();

        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.success(response));
    }


    /**
     * IMAGE 업로드 Presigned URL 발급 API
     *
     * 요청 POST /api/v1/url/images
     *
     * - 여러 이미지 업로드 가능
     * - refImages 리스트로 전달
     */
    @PostMapping("/images")
    public ResponseEntity<ApiResponse<ImageUploadResponse>> getImageUploadUrls(
            @Valid @RequestBody ImageUploadRequest request,
            HttpSession session) {

        String sessionId = session.getId();

        // 여러 이미지 업로드 결과 저장 리스트
        List<ImageUploadResponse.RefImage> result = new ArrayList<>();

        /**
         * 요청으로 받은 이미지 리스트 반복 처리
         */
        for (ImageUploadRequest.RefImage img : request.getRefImages()) {

            validateImageRequest(img.getContentType(), img.getSizeBytes());

            String objectKey =
                    "tmp/" + sessionId + "/images/" +
                            UUID.randomUUID() + "_" + img.getFilename();

            S3Service.PresignedUpload presigned =
                    s3Service.generateUploadUrl(objectKey, img.getContentType());

            // Redis에 업로드 파일 key 저장
            sessionRedisRepository.addFileKey(sessionId, objectKey);

            // 응답 DTO 생성
            ImageUploadResponse.RefImage refImage =
                    ImageUploadResponse.RefImage.builder()
                            .key(objectKey)
                            .url(presigned.url())
                            .method("PUT")
                            .headers(Map.of("Content-Type", img.getContentType()))
                            .expiresAt(Instant.now().plusSeconds(900).toString())
                            .build();

            result.add(refImage);
        }

        ImageUploadResponse response =
                ImageUploadResponse.builder()
                        .upload(
                                ImageUploadResponse.Upload.builder()
                                        .refImages(result)
                                        .build()
                        )
                        .build();

        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.success(response));
    }

    /**
     * VIDEO 요청 검증
     */

    private void validateVideoRequest(String type, Long size) {

        if (!type.equals("video/mp4"))
            throw new IllegalArgumentException("지원하지 않는 영상 형식");

        if (size > MAX_VIDEO_SIZE)
            throw new IllegalArgumentException("영상 크기 초과");
    }

    /**
     * IMAGE 요청 검증
     */
    private void validateImageRequest(String type, Long size) {

        if (!type.equals("image/jpeg") && !type.equals("image/png"))
            throw new IllegalArgumentException("지원하지 않는 이미지 형식");

        if (size > MAX_IMAGE_SIZE)
            throw new IllegalArgumentException("이미지 크기 초과");
    }
}