package com.a401.reppl.common.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
@AllArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ApiResponse<T> {

    private boolean success;
    private T data;
    private ApiError error;

    public static <T> ApiResponse<T> success(T data) {
        return ApiResponse.<T>builder()
                .success(true)
                .data(data)
                .error(null)
                .build();
    }

    public static <T> ApiResponse<T> error(ApiError error) {
        return ApiResponse.<T>builder()
                .success(false)
                .data(null)
                .error(error)
                .build();
    }

    public static <T> ApiResponse<T> error(String code, String message) {
        return error(ApiError.of(code, message));
    }

    public static <T> ApiResponse<T> error(String code, String message, Object details) {
        return error(ApiError.of(code, message, details));
    }
}
