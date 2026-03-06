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
public class UrlUploadRequest {

    // 파일 타입(예: mp4, jpg, png 등) 검증용
    @NotBlank(message = "파일 타입(확장자)은 필수입니다.")
    private String fileType;

    // 파일 크기 제한 검증용 (바이트 단위)
    @NotNull(message = "파일 크기는 필수입니다.")
    @Positive(message = "파일 크기는 0보다 커야 합니다.")
    private Long fileSize;

}
