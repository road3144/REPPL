package com.a401.reppl.controller.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.Map;

@Getter
@Builder
public class VideoUploadResponse {

    private Upload upload;

    @Getter
    @Builder
    public static class Upload {
        private Video video;
    }

    @Getter
    @Builder
    public static class Video {
        private String key;
        private String url;
        private String method;
        private Map<String, String> headers;
        private String expiresAt;
    }
}
