package com.a401.reppl.controller.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;

import java.util.List;

@Getter
@Builder
@AllArgsConstructor
public class JobListResponse {

    private List<JobItemResponse> items;
    private int page;
    private int size;
    private long totalCount;
    private int totalPages;
}
