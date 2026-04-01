export const STAGE_LABEL: Record<string, string> = {
  VALIDATE: '프롬프트 검증',
  GEMINI: '이미지 생성',
  DOWNLOAD: '파일 다운로드',
  DINO: '객체 검출',
  SAM: '마스크 추출',
  SHADOW: '그림자 생성',
  SCALE: '크기 조정',
  DEPTH: '깊이 추정',
  COMPOSITE: '프레임 합성',
  UPLOAD: '결과물 업로드',
};

export function formatStage(stage: string | null): string | null {
  if (!stage) return null;
  return STAGE_LABEL[stage] ?? stage;
}
