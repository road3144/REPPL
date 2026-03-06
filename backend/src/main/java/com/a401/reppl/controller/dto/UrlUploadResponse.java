package com.a401.reppl.controller.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UrlUploadResponse {

    private String uploadUrl; // 클라이언트가 파일을 직접 업로드할 S3 Presigned URL
    private String objectKey; // S3에 저장될 파일의 난수화된 키 (이후 Redis 등에 저장하기 위함)

}
