package com.a401.reppl.controller;

import com.a401.reppl.common.dto.ApiResponse;
import com.a401.reppl.controller.dto.JobCreateRequest;
import com.a401.reppl.controller.dto.JobCreateResponse;
import com.a401.reppl.service.JobService;
import jakarta.servlet.http.HttpSession;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
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
}
