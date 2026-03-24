package com.a401.reppl.domain.job;

/**
 * Job 처리 단계 정의
 */
public enum JobStage {
    // 프롬프트 검증
    VALIDATE,    // 프롬프트 유효성 검증 중

    // 프리뷰 생성 단계
    GEMINI,      // Gemini 모델이 합성 이미지를 생성하는 중

    // 합성 파이프라인 단계
    DOWNLOAD,    // S3에서 파일 다운로드
    DINO,        // Grounding DINO 모델이 객체를 탐지하는 중
    SAM,         // SAM 모델이 정밀 마스크를 추출하는 중
    SHADOW,      // 그림자 맵 생성 중
    SCALE,       // 객체 스케일링 처리 중
    DEPTH,       // DPT 모델이 깊이를 추정하는 중
    COMPOSITE,   // 프레임별 합성 진행 중
    UPLOAD       // 결과 업로드 중
}
