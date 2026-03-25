"""
REPPL AI Worker
===============
Kafka에서 프리뷰/합성 작업 요청을 수신하여 처리하고,
진행률과 결과를 Kafka로 반환하는 서빙 워커.

토픽:
  - reppl.job.preview.v1   → 프리뷰 이미지 3장 생성 (Gemini)
  - reppl.job.composite.v1 → 합성 파이프라인 실행 (DINO+SAM+합성)

실행: python worker.py
"""

import os
import logging
import subprocess
import traceback

from config import (
    KAFKA_TOPIC_JOB_PREVIEW,
    KAFKA_TOPIC_JOB_COMPOSITE,
)
from kafka_client import KafkaJobConsumer, KafkaProgressProducer
from s3_client import download_file, upload_file

from main import INPUTS, OUTPUTS, generate_previews, run_composite
from prompt_validator import validate_prompt, InvalidPromptError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def _cleanup(*paths):
    """임시 파일들을 삭제한다."""
    for p in paths:
        try:
            if p and os.path.isfile(p):
                os.remove(p)
        except OSError:
            pass


def _get_ffmpeg_path() -> str:
    """imageio-ffmpeg에서 ffmpeg 바이너리 경로를 가져온다."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"  # 시스템 ffmpeg 폴백


def _reencode_for_web(input_path: str) -> str:
    """mp4v 코덱 영상을 H.264 + faststart로 재인코딩한다."""
    output_path = input_path.replace(".mp4", "_web.mp4")
    ffmpeg = _get_ffmpeg_path()
    cmd = [
        ffmpeg, "-y", "-i", input_path,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-movflags", "+faststart",
        "-an",
        output_path,
    ]
    log.info(f"ffmpeg 재인코딩: {input_path} → {output_path}")
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


# ══════════════════════════════════════════════════════════
# 프리뷰 Job 처리
# ══════════════════════════════════════════════════════════
def process_preview(event: dict, producer: KafkaProgressProducer):
    """프리뷰 이미지 3장을 생성하여 S3에 업로드한다."""
    job_id = event["jobId"]
    inp = event["input"]
    out = event["output"]
    options = event.get("options") or {}

    video_s3 = inp["video"]
    images_s3 = inp.get("replacementImages", [])
    output_bucket = out["bucket"]
    output_prefix = out["key"]  # "previews/{jobId}/"

    prompt = options.get("placementPrompt", "object")

    video_local = os.path.join(INPUTS, os.path.basename(video_s3["key"]))
    img_local = os.path.join(INPUTS, os.path.basename(images_s3[0]["key"])) if images_s3 else None

    log.info(f"=== 프리뷰 Job 시작: {job_id} ===")

    # ── 프롬프트 검증 ──
    try:
        validate_prompt(prompt)
    except InvalidPromptError as e:
        log.warning(f"프롬프트 검증 실패: {job_id} — {e.reason}")
        producer.send_progress(
            job_id, "FAILED", "VALIDATE", 0,
            f"프롬프트가 유효하지 않습니다: {e.reason}"
        )
        return
    except RuntimeError as e:
        log.error(f"프롬프트 검증 서버 오류: {job_id} — {e}")
        producer.send_progress(
            job_id, "FAILED", "VALIDATE", 0,
            "프롬프트 검증 서버에 문제가 발생했습니다. 잠시 후 다시 시도해주세요."
        )
        return

    local_files = [video_local]
    if img_local:
        local_files.append(img_local)

    try:
        # ── DOWNLOAD ──
        producer.send_progress(job_id, "RUNNING", "DOWNLOAD", 5, "S3에서 파일을 다운로드하는 중입니다...")
        download_file(video_s3["bucket"], video_s3["key"], video_local)

        if images_s3:
            img = images_s3[0]
            download_file(img["bucket"], img["key"], img_local)

        producer.send_progress(job_id, "RUNNING", "DOWNLOAD", 10, "다운로드 완료")

        # ── GEMINI 프리뷰 생성 ──
        def on_progress(stage, percent, message):
            producer.send_progress(job_id, "RUNNING", stage, percent, message)

        preview_paths = generate_previews(
            video_path=video_local,
            obj_img_path=img_local,
            user_prompt=prompt,
            count=3,
            on_progress=on_progress,
        )

        # ── S3 업로드 ──
        producer.send_progress(job_id, "RUNNING", "UPLOAD", 92, "프리뷰 이미지를 업로드하는 중입니다...")
        preview_keys = []
        for i, path in enumerate(preview_paths):
            s3_key = f"{output_prefix}preview_{i}.png"
            upload_file(path, output_bucket, s3_key)
            preview_keys.append(s3_key)
            local_files.append(path)

        # ── COMPLETED (previewKeys 포함) ──
        producer.send_progress(
            job_id, "COMPLETED", "UPLOAD", 100,
            "프리뷰 생성 완료",
            preview_keys=preview_keys,
        )
        log.info(f"=== 프리뷰 Job 완료: {job_id} ({len(preview_keys)}장) ===")

    except Exception as e:
        log.error(f"프리뷰 Job 실패: {job_id} — {e}")
        log.error(traceback.format_exc())
        producer.send_progress(
            job_id, "FAILED", "GEMINI", 0, f"프리뷰 생성 실패: {str(e)[:200]}"
        )

    finally:
        _cleanup(*local_files)


# ══════════════════════════════════════════════════════════
# 합성 Job 처리
# ══════════════════════════════════════════════════════════
def process_composite(event: dict, producer: KafkaProgressProducer):
    """선택된 프리뷰 이미지를 기반으로 합성 파이프라인을 실행한다."""
    job_id = event["jobId"]
    video_s3 = event["video"]
    preview_s3 = event["selectedPreview"]
    out = event["output"]
    options = event.get("options") or {}

    output_bucket = out["bucket"]
    output_key = out["key"]

    prompt = options.get("placementPrompt", "object")

    video_local = os.path.join(INPUTS, os.path.basename(video_s3["key"]))
    preview_local = os.path.join(INPUTS, f"{job_id}_selected_preview.png")
    output_local = os.path.join(OUTPUTS, f"{job_id}_output.mp4")

    log.info(f"=== 합성 Job 시작: {job_id} ===")

    try:
        # ── DOWNLOAD ──
        producer.send_progress(job_id, "RUNNING", "DOWNLOAD", 5, "S3에서 파일을 다운로드하는 중입니다...")
        download_file(video_s3["bucket"], video_s3["key"], video_local)
        download_file(preview_s3["bucket"], preview_s3["key"], preview_local)
        producer.send_progress(job_id, "RUNNING", "DOWNLOAD", 10, "다운로드 완료")

        # ── 합성 파이프라인 ──
        def on_progress(stage, percent, message):
            producer.send_progress(job_id, "RUNNING", stage, percent, message)

        run_composite(
            video_path=video_local,
            selected_preview_path=preview_local,
            user_prompt=prompt,
            output_path=output_local,
            on_progress=on_progress,
        )

        # ── ENCODE (H.264 + faststart) ──
        producer.send_progress(job_id, "RUNNING", "ENCODE", 88, "웹 재생용 인코딩 중...")
        web_output = _reencode_for_web(output_local)

        # ── UPLOAD ──
        producer.send_progress(job_id, "RUNNING", "UPLOAD", 90, "결과를 업로드하는 중입니다...")
        upload_file(web_output, output_bucket, output_key)
        producer.send_progress(job_id, "RUNNING", "UPLOAD", 95, "업로드 완료")

        # ── COMPLETED ──
        producer.send_progress(
            job_id, "COMPLETED", "UPLOAD", 100,
            "합성 완료", output_key=output_key,
        )
        log.info(f"=== 합성 Job 완료: {job_id} ===")

    except Exception as e:
        log.error(f"합성 Job 실패: {job_id} — {e}")
        log.error(traceback.format_exc())
        producer.send_progress(
            job_id, "FAILED", "COMPOSITE", 0, f"합성 실패: {str(e)[:200]}"
        )

    finally:
        web_path = output_local.replace(".mp4", "_web.mp4")
        _cleanup(video_local, preview_local, output_local, web_path)


# ══════════════════════════════════════════════════════════
# 메인 워커 루프
# ══════════════════════════════════════════════════════════
def run():
    """Kafka에서 프리뷰/합성 작업을 수신하여 순차 처리한다."""
    log.info("REPPL AI Worker 시작 (프리뷰 + 합성)")
    consumer = KafkaJobConsumer()
    producer = KafkaProgressProducer()

    try:
        for topic, event in consumer.poll():
            job_id = event.get("jobId", "unknown")

            if topic == KAFKA_TOPIC_JOB_PREVIEW:
                log.info(f"프리뷰 작업 수신: {job_id}")
                process_preview(event, producer)
            elif topic == KAFKA_TOPIC_JOB_COMPOSITE:
                log.info(f"합성 작업 수신: {job_id}")
                process_composite(event, producer)
            else:
                log.warning(f"알 수 없는 토픽: {topic}, jobId={job_id}")

    except KeyboardInterrupt:
        log.info("Worker 종료 (KeyboardInterrupt)")
    finally:
        consumer.close()
        producer.close()
        log.info("Worker 종료 완료")


if __name__ == "__main__":
    run()
