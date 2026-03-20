"""
REPPL AI Worker
===============
Kafka에서 작업 요청을 수신하여 AI 파이프라인을 실행하고,
진행률과 결과를 Kafka로 반환하는 서빙 워커.

실행: python worker.py
"""

import os
import logging
import traceback

from config import AWS_S3_BUCKET
from kafka_client import KafkaJobConsumer, KafkaProgressProducer
from s3_client import download_file, upload_file

# main.py의 통합 파이프라인 진입점
from main import INPUTS, OUTPUTS, run_pipeline

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


def process_job(event: dict, producer: KafkaProgressProducer):
    """단일 Job을 처리한다."""
    job_id = event["jobId"]
    inp = event["input"]
    out = event["output"]
    options = event.get("options") or {}

    video_s3 = inp["video"]
    images_s3 = inp.get("replacementImages", [])
    output_bucket = out["bucket"]
    output_key = out["key"]

    prompt = options.get("placementPrompt", "object")

    # 로컬 파일 경로
    video_local = os.path.join(INPUTS, os.path.basename(video_s3["key"]))
    img_local = os.path.join(INPUTS, os.path.basename(images_s3[0]["key"])) if images_s3 else None
    output_local = os.path.join(OUTPUTS, f"{job_id}_output.mp4")

    log.info(f"=== Job 시작: {job_id} ===")
    log.info(f"  video: s3://{video_s3['bucket']}/{video_s3['key']}")
    log.info(f"  prompt: {prompt}")

    try:
        # ── DOWNLOAD ──
        producer.send_progress(job_id, "RUNNING", "DOWNLOAD", 5, "영상 다운로드 중...")
        download_file(video_s3["bucket"], video_s3["key"], video_local)

        if images_s3:
            producer.send_progress(job_id, "RUNNING", "DOWNLOAD", 8, "참조 이미지 다운로드 중...")
            img = images_s3[0]
            download_file(img["bucket"], img["key"], img_local)

        producer.send_progress(job_id, "RUNNING", "DOWNLOAD", 10, "다운로드 완료")

        # ── 파이프라인 실행 (main.py의 run_pipeline) ──
        def on_progress(stage, percent, message):
            producer.send_progress(job_id, "RUNNING", stage, percent, message)

        run_pipeline(
            video_path=video_local,
            obj_img_path=img_local,
            user_prompt=prompt,
            output_path=output_local,
            on_progress=on_progress,
        )

        # ── UPLOAD ──
        producer.send_progress(job_id, "RUNNING", "UPLOAD", 90, "결과 업로드 중...")
        upload_file(output_local, output_bucket, output_key)
        producer.send_progress(job_id, "RUNNING", "UPLOAD", 95, "업로드 완료")

        # ── COMPLETED ──
        producer.send_progress(
            job_id, "COMPLETED", "UPLOAD", 100,
            "작업 완료", output_key=output_key,
        )
        log.info(f"=== Job 완료: {job_id} ===")

    except Exception as e:
        log.error(f"Job 실패: {job_id} — {e}")
        log.error(traceback.format_exc())
        producer.send_progress(
            job_id, "FAILED", "DETECT", 0, f"작업 실패: {str(e)[:200]}"
        )

    finally:
        _cleanup(video_local, img_local, output_local)


def run():
    """메인 워커 루프. Kafka에서 작업을 수신하여 순차 처리한다."""
    log.info("REPPL AI Worker 시작")
    consumer = KafkaJobConsumer()
    producer = KafkaProgressProducer()

    try:
        for event in consumer.poll():
            job_id = event.get("jobId", "unknown")
            log.info(f"작업 수신: {job_id}")
            process_job(event, producer)
    except KeyboardInterrupt:
        log.info("Worker 종료 (KeyboardInterrupt)")
    finally:
        consumer.close()
        producer.close()
        log.info("Worker 종료 완료")


if __name__ == "__main__":
    run()
