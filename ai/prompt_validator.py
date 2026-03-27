"""
프롬프트 검증 모듈
==================
GMS Gemini Flash를 사용하여 사용자 프롬프트가
영상 PPL 배치 요청으로 유효한지 검증한다.
"""

import os
import json
import logging
import requests

log = logging.getLogger(__name__)

GMS_API_KEY = os.environ.get("GMS_API_KEY", "")
GMS_BASE = "https://gms.ssafy.io/gmsapi/generativelanguage.googleapis.com/v1beta/models/"
GMS_FLASH_URL = GMS_BASE + "gemini-2.5-flash:generateContent"

_VALIDATION_PROMPT = """당신은 영상 PPL(Product Placement) AI 시스템의 프롬프트 검증기입니다.
사용자는 영상 속 어디에 제품을 배치할지 설명해야 합니다.

유효한 프롬프트 예시:
- "책상 위 빈 공간에 콜라를 놓아줘"
- "테이블 오른쪽 컵 옆에 배치해줘"
- "바닥 왼쪽에 자연스럽게 놓아줘"
- "선반 위에 올려줘"

무효한 프롬프트 예시:
- "안녕"
- "ㅋㅋㅋ"
- "hello world"
- "오늘 날씨 좋다"
- 제품 배치와 무관한 텍스트

다음 프롬프트가 영상 속 제품 배치 요청으로 유효한지 판단하세요.

추가 작업: 프롬프트가 유효하면, 프롬프트에서 배치할 **제품/객체**가 무엇인지 파악하고,
Grounding DINO 객체 검출 모델이 인식할 수 있는 **영어 키워드**로 변환하세요.
- 구체적이고 시각적으로 명확한 영어 단어/구문을 사용하세요.
- 예: 콜라 → "coca cola can", 맥주 → "beer can", 물병 → "water bottle", 커피 → "coffee cup", 꽃병 → "vase"
- 제품명이 명시되지 않은 경우 "object"로 설정하세요.

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요.

유효: {"valid": true, "dino_keyword": "english keyword for object detection"}
무효: {"valid": false, "reason": "무효한 이유를 한국어로 간단히"}

사용자 프롬프트: "{prompt}"
"""


class InvalidPromptError(Exception):
    """유효하지 않은 프롬프트일 때 발생하는 예외."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def validate_prompt(user_prompt: str):
    """
    GMS Gemini Flash로 프롬프트를 검증하고, DINO용 영어 키워드를 추출한다.

    Args:
        user_prompt: 사용자 입력 프롬프트

    Returns:
        str or None: DINO용 영어 키워드 (GMS 미설정 시 None)

    Raises:
        InvalidPromptError: 프롬프트가 유효하지 않을 때
    """
    if not user_prompt or not user_prompt.strip():
        raise InvalidPromptError("프롬프트가 비어 있습니다. 제품을 어디에 배치할지 설명해주세요.")

    if not GMS_API_KEY:
        log.warning("GMS_API_KEY 미설정 — 프롬프트 검증 건너뜀")
        return None

    prompt_text = _VALIDATION_PROMPT.replace("{prompt}", user_prompt)

    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 1024,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    headers = {"x-goog-api-key": GMS_API_KEY, "Content-Type": "application/json"}

    try:
        resp = requests.post(GMS_FLASH_URL, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        result = resp.json()

        log.info(f"GMS 응답 원본: {json.dumps(result, ensure_ascii=False)[:500]}")

        # 응답에서 텍스트 추출
        text = ""
        for cand in result.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                if "text" in part:
                    text += part["text"]

        text = text.strip()
        log.info(f"GMS 추출 텍스트: '{text}'")

        # JSON 블록 추출 (응답에 부가 텍스트가 섞일 수 있음)
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            text = text[start:end]
        parsed = json.loads(text)

        if not parsed.get("valid", True):
            reason = parsed.get("reason", "제품 배치와 관련된 프롬프트를 입력해주세요.")
            raise InvalidPromptError(reason)

        dino_keyword = parsed.get("dino_keyword", None)
        log.info(f"프롬프트 검증 통과: '{user_prompt[:30]}...' | DINO 키워드: '{dino_keyword}'")
        return dino_keyword

    except InvalidPromptError:
        raise
    except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
        log.error(f"프롬프트 검증 API 오류: {e}")
        raise RuntimeError(f"프롬프트 검증 서버 오류: {e}")
