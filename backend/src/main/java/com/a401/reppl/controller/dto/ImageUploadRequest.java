package com.a401.reppl.controller.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Positive;
import lombok.Getter;

import java.util.List;

@Getter
public class ImageUploadRequest {

    private List<RefImage> refImages;

    @Getter
    public static class RefImage {

        @NotBlank
        private String filename;

        @NotBlank
        private String contentType;

        @Positive
        private Long sizeBytes;
    }
}