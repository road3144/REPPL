package com.a401.reppl.controller.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;

import java.time.Instant;

@Getter
@Builder
@AllArgsConstructor
public class JobResultResponse {

    private DownloadInfo download;

    @Getter
    @Builder
    @AllArgsConstructor
    public static class DownloadInfo {
        private String key;
        private String url;
        private String method;
        private Instant expiresAt;
    }
}
