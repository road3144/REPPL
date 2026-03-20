package com.a401.reppl.controller.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * 프리뷰 선택 → 합성 Job 생성 응답 DTO
 */
@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PreviewSelectResponse {

    /** 새로 생성된 합성 Job ID */
    private String compositeJobId;
    private String status;
}
