package com.a401.reppl.exception;

import com.a401.reppl.common.dto.ApiResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.HashMap;
import java.util.Map;
import java.util.stream.Collectors;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(JobNotFoundException.class)
    public ResponseEntity<ApiResponse<Void>> handleJobNotFound(JobNotFoundException e) {
        log.warn("Job not found: jobId={}", e.getJobId());

        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(ApiResponse.error("JOB_NOT_FOUND", e.getMessage()));
    }

    @ExceptionHandler(JobNotCompletedException.class)
    public ResponseEntity<ApiResponse<Void>> handleJobNotCompleted(JobNotCompletedException e) {
        log.warn("Job not completed: jobId={}, status={}", e.getJobId(), e.getStatus());

        Map<String, Object> details = new HashMap<>();
        details.put("jobId", e.getJobId());
        details.put("currentStatus", e.getStatus());

        return ResponseEntity.badRequest()
                .body(ApiResponse.error("JOB_NOT_COMPLETED", e.getMessage(), details));
    }

    @ExceptionHandler(InvalidKeySelectionException.class)
    public ResponseEntity<ApiResponse<Void>> handleInvalidKeySelection(InvalidKeySelectionException e) {
        log.warn("Invalid key selection: videoKey={}, invalidImageKeys={}",
                e.getVideoKey(), e.getInvalidImageKeys());

        Map<String, Object> details = new HashMap<>();
        details.put("videoKey", e.getVideoKey());
        details.put("invalidImageKeys", e.getInvalidImageKeys());

        return ResponseEntity.badRequest()
                .body(ApiResponse.error("INVALID_KEY_SELECTION", e.getMessage(), details));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiResponse<Void>> handleValidationException(MethodArgumentNotValidException e) {
        String message = e.getBindingResult().getFieldErrors().stream()
                .map(error -> error.getField() + ": " + error.getDefaultMessage())
                .collect(Collectors.joining(", "));

        log.warn("Validation failed: {}", message);

        return ResponseEntity.badRequest()
                .body(ApiResponse.error("VALIDATION_ERROR", message));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> handleException(Exception e) {
        log.error("Unexpected error occurred", e);

        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ApiResponse.error("INTERNAL_ERROR", "서버 내부 오류가 발생했습니다."));
    }
}
