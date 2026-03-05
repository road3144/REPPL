package com.a401.reppl.domain.job;

/**
 * Job 처리 단계 정의
 */
public enum JobStage {
    DOWNLOAD,    // 영상 다운로드
    DETECT,      // 객체 탐지
    REPLACE,     // 이미지 교체
    ENCODE,      // 영상 인코딩
    UPLOAD       // 결과 업로드
}
