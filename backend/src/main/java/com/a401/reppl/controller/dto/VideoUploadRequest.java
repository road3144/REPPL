package com.a401.reppl.controller.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
@AllArgsConstructor
public class VideoUploadRequest {

    @NotNull
    private Video video;

    @Getter
    public static class Video {

        @NotBlank
        private String filename;

        @NotBlank
        private String contentType;

        @Positive
        private Long sizeBytes;
    }
}
