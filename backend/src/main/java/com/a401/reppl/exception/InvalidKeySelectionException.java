package com.a401.reppl.exception;

import lombok.Getter;

import java.util.List;

@Getter
public class InvalidKeySelectionException extends RuntimeException {

    private final String videoKey;
    private final List<String> invalidImageKeys;

    public InvalidKeySelectionException(String videoKey, List<String> invalidImageKeys) {
        super("세션에 존재하지 않는 업로드 key가 포함되어 있습니다.");
        this.videoKey = videoKey;
        this.invalidImageKeys = invalidImageKeys;
    }
}
