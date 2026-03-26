export async function downloadBlobFromUrl(
  url: string,
  fileName: string
): Promise<void> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error('다운로드 응답이 올바르지 않습니다.');
  }

  const blob = await response.blob();
  const blobUrl = URL.createObjectURL(blob);

  const anchor = document.createElement('a');
  anchor.href = blobUrl;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);

  URL.revokeObjectURL(blobUrl);
}
