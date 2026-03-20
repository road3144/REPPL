package com.a401.reppl.controller.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;

/**
 * 프리뷰 생성 요청 DTO
 *
 * POST /api/v1/jobs/preview
 * {
 *   "videoKey": "tmp/sess_abc/video/input.mp4",
 *   "refImageKeys": ["tmp/sess_abc/images/cola.png"],
 *   "options": { "placementPrompt": "책상 위 빈 공간에 콜라를 합성해줘" }
 * }
 */
@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PreviewCreateRequest {

    @NotBlank(message = "videoKey는 필수입니다.")
    private String videoKey;

    @NotEmpty(message = "refImageKeys는 최소 1개 이상이어야 합니다.")
    private List<String> refImageKeys;

    private Map<String, Object> options;
}
