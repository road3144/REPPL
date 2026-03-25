import json
import logging
from datetime import datetime, timezone

from kafka import KafkaConsumer, KafkaProducer

from config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_CONSUMER_GROUP_ID,
    KAFKA_TOPIC_JOB_PREVIEW,
    KAFKA_TOPIC_JOB_COMPOSITE,
    KAFKA_TOPIC_JOB_PROGRESS,
)

log = logging.getLogger(__name__)


class KafkaJobConsumer:
    """프리뷰 + 합성 두 토픽에서 작업 요청을 소비한다."""

    def __init__(self):
        self._topics = [KAFKA_TOPIC_JOB_PREVIEW, KAFKA_TOPIC_JOB_COMPOSITE]
        self._consumer = KafkaConsumer(
            *self._topics,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
            group_id=KAFKA_CONSUMER_GROUP_ID,
            auto_offset_reset="latest",
            enable_auto_commit=False,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        log.info(
            f"Kafka consumer started: topics={self._topics}, "
            f"group={KAFKA_CONSUMER_GROUP_ID}, servers={KAFKA_BOOTSTRAP_SERVERS}"
        )

    def flush_pending(self):
        """시작 시 밀린 메시지를 건너뛰고 최신 offset으로 이동한다."""
        self._consumer.poll(timeout_ms=5000)
        for tp in self._consumer.assignment():
            self._consumer.seek_to_end(tp)
        self._consumer.commit()
        log.info("밀린 메시지 스킵 — 최신 offset으로 이동 완료")

    def poll(self):
        """메시지를 (topic, value) 튜플로 yield 한다."""
        for message in self._consumer:
            self._consumer.commit()
            yield message.topic, message.value

    def close(self):
        self._consumer.close()


class KafkaProgressProducer:
    """reppl.job.progress.v1 토픽으로 진행률 이벤트를 발행한다."""

    def __init__(self):
        self._producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
        )
        self._seq = 0
        log.info(f"Kafka producer started: servers={KAFKA_BOOTSTRAP_SERVERS}")

    def send_progress(
        self,
        job_id: str,
        status: str,
        stage: str,
        percent: int,
        message: str,
        output_key: str = None,
        preview_keys: list = None,
    ):
        self._seq += 1
        event = {
            "schemaVersion": 1,
            "jobId": job_id,
            "status": status,
            "stage": stage,
            "percent": percent,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "seq": self._seq,
            "outputKey": output_key,
            "previewKeys": preview_keys,
        }
        self._producer.send(KAFKA_TOPIC_JOB_PROGRESS, key=job_id, value=event)
        self._producer.flush()
        log.info(f"Progress sent: jobId={job_id} status={status} stage={stage} {percent}%")

    def close(self):
        self._producer.close()
