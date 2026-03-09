package com.a401.reppl.controller.dto;

import lombok.Builder;
import lombok.Getter;

import java.util.List;
import java.util.Map;

@Getter
@Builder
public class ImageUploadResponse {

    private Upload upload;

    @Getter
    @Builder
    public static class Upload {
        private List<RefImage> refImages;
    }

    @Getter
    @Builder
    public static class RefImage {

        private String key;
        private String url;
        private String method;
        private Map<String, String> headers;
        private String expiresAt;
    }
}