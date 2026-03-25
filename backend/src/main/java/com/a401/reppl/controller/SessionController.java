package com.a401.reppl.controller;

import com.a401.reppl.common.dto.ApiResponse;
import jakarta.servlet.http.HttpSession;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/api/v1/session")
public class SessionController {

    @GetMapping
    public ResponseEntity<ApiResponse<Map<String, String>>> initSession(HttpSession session) {
        String sessionId = session.getId();
        log.info("Session initialized: sessionId={}", sessionId);

        return ResponseEntity.ok(ApiResponse.success(
                Map.of("sessionId", sessionId)
        ));
    }
}
