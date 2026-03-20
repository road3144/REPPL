package com.a401.reppl.controller.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * 프리뷰 선택 및 합성 시작 요청 DTO
 *
 * POST /api/v1/jobs/{jobId}/select
 * { "selectedIndex": 0 }
 */
@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PreviewSelectRequest {

    @NotNull(message = "selectedIndex는 필수입니다.")
    @Min(value = 0, message = "selectedIndex는 0 이상이어야 합니다.")
    @Max(value = 2, message = "selectedIndex는 2 이하여야 합니다.")
    private Integer selectedIndex;
}
