package com.a401.reppl.controller;

import com.a401.reppl.common.dto.ApiResponse;
import com.a401.reppl.controller.dto.UrlUploadRequest;
import com.a401.reppl.controller.dto.UrlUploadResponse;
import com.a401.reppl.domain.session.SessionRedisRepository;
import com.a401.reppl.service.S3Service;

import jakarta.servlet.http.HttpSession;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Set;
import java.util.UUID;

@Slf4j
@RestController
@RequestMapping("/api/v1/url")
@RequiredArgsConstructor
public class UrlController {

    private final S3Service s3Service;
    private final SessionRedisRepository sessionRedisRepository;

    // 비디오/이미지 제한 크기 설정
    private static final long MAX_VIDEO_SIZE = 50L * 1024 * 1024; // 50MB
    private static final long MAX_IMAGE_SIZE = 10L * 1024 * 1024; // 10MB

    /**
     * 비디오 업로드용 S3 Presigned URL 발급
     */
    @PostMapping("/video")
    public ResponseEntity<ApiResponse<UrlUploadResponse>> getUploadUrlForVideo(
            @Valid @RequestBody UrlUploadRequest request,
            HttpSession session) {

        String sessionId = session.getId();
        log.info("비디오 업로드 URL 요청: sessionId={}, fileType={}, fileSize={}",
                sessionId, request.getFileType(), request.getFileSize());

        // 1. 파일 검증 (확장자, 용량)
        validateVideoRequest(request);

        // 2. S3 Object Key 생성 (난수화)
        String objectKey = "videos/" + UUID.randomUUID().toString() + "." + request.getFileType();
        String contentType = "video/" + request.getFileType();

        // 3. S3 Presigned URL (15분 기한) 생성
        S3Service.PresignedUpload presignedUpload = s3Service.generateUploadUrl(objectKey, contentType);

        // 4. 발급된 키를 Redis(sess:{sid}:keys)에 저장
        sessionRedisRepository.addFileKey(sessionId, objectKey);

        // 5. 프론트엔드에 URL과 Key 반환
        UrlUploadResponse response = UrlUploadResponse.builder()
                .uploadUrl(presignedUpload.url())
                .objectKey(objectKey)
                .build();

        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.success(response));
    }

    /**
     * 이미지 업로드용 S3 Presigned URL 발급
     */
    @PostMapping("/images")
    public ResponseEntity<ApiResponse<UrlUploadResponse>> getUploadUrlForImage(
            @Valid @RequestBody UrlUploadRequest request,
            HttpSession session) {

        String sessionId = session.getId();
        log.info("이미지 업로드 URL 요청: sessionId={}, fileType={}, fileSize={}",
                sessionId, request.getFileType(), request.getFileSize());

        // 1. 파일 검증 (확장자, 용량)
        validateImageRequest(request);

        // 2. S3 Object Key 생성 (난수화)
        String objectKey = "images/" + UUID.randomUUID().toString() + "." + request.getFileType();
        String contentType = "image/" + request.getFileType();

        // 3. S3 Presigned URL (15분 기한) 생성
        S3Service.PresignedUpload presignedUpload = s3Service.generateUploadUrl(objectKey, contentType);

        // 4. 발급된 키를 Redis(sess:{sid}:keys)에 저장
        sessionRedisRepository.addFileKey(sessionId, objectKey);

        // 5. 프론트엔드에 URL과 Key 반환
        UrlUploadResponse response = UrlUploadResponse.builder()
                .uploadUrl(presignedUpload.url())
                .objectKey(objectKey)
                .build();

        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.success(response));
    }

    // --- (기존의 세션 관련 테스트/조회 API 유지 원할 시 아래에 두기) ---
    @GetMapping("/sessions/{sessionId}/files")
    public ResponseEntity<Set<String>> getFiles(@PathVariable String sessionId) {
        Set<String> files = sessionRedisRepository.getFileKeys(sessionId);
        return ResponseEntity.ok(files);
    }

    @GetMapping("/sessions/{sessionId}/jobs")
    public ResponseEntity<List<String>> getJobs(@PathVariable String sessionId, @RequestParam int page,
            @RequestParam int size) {
        List<String> jobs = sessionRedisRepository.getJobs(sessionId, page, size);
        return ResponseEntity.ok(jobs);
    }

    // --- Helper Methods ---

    private void validateVideoRequest(UrlUploadRequest request) {
        String type = request.getFileType().toLowerCase();
        if (!type.equals("mp4") && !type.equals("mov") && !type.equals("avi")) {
            throw new IllegalArgumentException("지원하지 않는 비디오 파일 형식입니다. (mp4, mov, avi 만 가능)");
        }
        if (request.getFileSize() > MAX_VIDEO_SIZE) {
            throw new IllegalArgumentException("비디오 파일 크기는 50MB를 초과할 수 없습니다.");
        }
    }

    private void validateImageRequest(UrlUploadRequest request) {
        String type = request.getFileType().toLowerCase();
        if (!type.equals("jpg") && !type.equals("jpeg") && !type.equals("png")) {
            throw new IllegalArgumentException("지원하지 않는 이미지 파일 형식입니다. (jpg, jpeg, png 만 가능)");
        }
        if (request.getFileSize() > MAX_IMAGE_SIZE) {
            throw new IllegalArgumentException("이미지 파일 크기는 10MB를 초과할 수 없습니다.");
        }
    }
}
