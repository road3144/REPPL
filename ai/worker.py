"""
REPPL AI Worker
===============
Kafka에서 작업 요청을 수신하여 AI 파이프라인을 실행하고,
진행률과 결과를 Kafka로 반환하는 서빙 워커.

실행: python worker.py
"""

import os
import shutil
import logging
import traceback

import cv2

from config import AWS_S3_BUCKET
from kafka_client import KafkaJobConsumer, KafkaProgressProducer
from s3_client import download_file, upload_file

# main.py에서 파이프라인 함수 import (main.py 수정 없이 사용)
from main import (
    INPUTS,
    OUTPUTS,
    step3_gemini,
    step4_extract,
    step5_scale,
    step6_composite,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def _extract_filename(s3_key: str) -> str:
    """S3 key에서 파일명만 추출한다."""
    return os.path.basename(s3_key)


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

    keyword = options.get("placementPrompt", "object")

    video_filename = _extract_filename(video_s3["key"])
    video_local = os.path.join(INPUTS, video_filename)
    image_local = os.path.join(INPUTS, "changed_first_frame.png")
    output_local = os.path.join(OUTPUTS, f"{job_id}_output.mp4")

    log.info(f"=== Job 시작: {job_id} ===")
    log.info(f"  video: s3://{video_s3['bucket']}/{video_s3['key']}")
    log.info(f"  keyword: {keyword}")

    try:
        # ── DOWNLOAD ──
        producer.send_progress(job_id, "RUNNING", "DOWNLOAD", 5, "영상 다운로드 중...")
        download_file(video_s3["bucket"], video_s3["key"], video_local)

        if images_s3:
            producer.send_progress(job_id, "RUNNING", "DOWNLOAD", 8, "참조 이미지 다운로드 중...")
            img = images_s3[0]
            download_file(img["bucket"], img["key"], image_local)

        producer.send_progress(job_id, "RUNNING", "DOWNLOAD", 10, "다운로드 완료")

        # ── DETECT (step3 + step4) ──
        producer.send_progress(job_id, "RUNNING", "DETECT", 12, "프레임 로딩 중...")
        f1, f2 = step3_gemini(video_local, keyword)

        cap = cv2.VideoCapture(video_local)
        vw, vh = int(cap.get(3)), int(cap.get(4))
        cap.release()

        producer.send_progress(job_id, "RUNNING", "DETECT", 15, "객체 탐지 중 (DINO + SAM)...")
        mask, shadow_map, bbox = step4_extract(f1, f2, keyword)

        producer.send_progress(job_id, "RUNNING", "DETECT", 35, "객체 탐지 완료")

        # ── REPLACE (step5 + step6) ──
        producer.send_progress(job_id, "RUNNING", "REPLACE", 38, "스케일링 중...")
        obj, mr, sr, vbbox = step5_scale(f2, mask, shadow_map, bbox, vw, vh)

        producer.send_progress(job_id, "RUNNING", "REPLACE", 40, "영상 합성 중...")
        step6_composite(video_local, obj, mr, sr, vbbox, output_local)

        producer.send_progress(job_id, "RUNNING", "ENCODE", 85, "합성 완료")

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
        _cleanup(video_local, image_local, output_local)


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
