package com.a401.reppl.controller;

import com.a401.reppl.common.dto.ApiResponse;
import com.a401.reppl.controller.dto.JobCreateRequest;
import com.a401.reppl.controller.dto.JobCreateResponse;
import com.a401.reppl.controller.dto.JobListResponse;
import com.a401.reppl.controller.dto.JobResultResponse;
import com.a401.reppl.controller.dto.JobStatusResponse;
import com.a401.reppl.service.JobService;
import jakarta.servlet.http.HttpSession;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Slf4j
@RestController
@RequestMapping("/api/v1/jobs")
@RequiredArgsConstructor
public class JobController {

    private final JobService jobService;

    @PostMapping
    public ResponseEntity<ApiResponse<JobCreateResponse>> createJob(
            @Valid @RequestBody JobCreateRequest request,
            HttpSession session) {

        String sessionId = session.getId();
        log.info("Create job request: sessionId={}, videoKey={}", sessionId, request.getVideoKey());

        JobCreateResponse response = jobService.createJob(sessionId, request.toCommand());

        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.success(response));
    }

    @GetMapping
    public ResponseEntity<ApiResponse<JobListResponse>> getJobs(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size,
            HttpSession session) {

        String sessionId = session.getId();
        log.info("Get jobs request: sessionId={}, page={}, size={}", sessionId, page, size);

        JobListResponse response = jobService.getJobs(sessionId, page, size);

        return ResponseEntity.ok(ApiResponse.success(response));
    }

    @GetMapping("/{jobId}")
    public ResponseEntity<ApiResponse<JobStatusResponse>> getJobStatus(
            @PathVariable String jobId) {

        log.info("Get job status request: jobId={}", jobId);

        JobStatusResponse response = jobService.getJobStatus(jobId);

        return ResponseEntity.ok(ApiResponse.success(response));
    }

    @GetMapping("/{jobId}/result")
    public ResponseEntity<ApiResponse<JobResultResponse>> getJobResult(
            @PathVariable String jobId) {

        log.info("Get job result request: jobId={}", jobId);

        JobResultResponse response = jobService.getJobResult(jobId);

        return ResponseEntity.ok(ApiResponse.success(response));
    }
}
