"""밀린 Kafka 메시지를 모두 스킵하는 유틸리티 스크립트.

사용법: python flush_kafka.py
주의: 워커가 꺼져있는 상태에서 실행해야 합니다.
"""
from kafka_client import KafkaJobConsumer

consumer = KafkaJobConsumer()
consumer.flush_pending()
consumer.close()
print("완료 — 모든 밀린 메시지 스킵됨")
