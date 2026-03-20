package com.a401.reppl.controller.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 프리뷰 이미지 목록 응답 DTO
 *
 * GET /api/v1/jobs/{jobId}/previews
 */
@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PreviewListResponse {

    private String jobId;
    private List<PreviewItem> previews;

    @Getter
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class PreviewItem {
        private int index;
        private String key;
        private String url;
    }
}
