from functools import lru_cache

from transformers import pipeline

MODEL_NAME = "Davephoenix/bert-bullying-detector"
MAX_MESSAGE_LENGTH = 2000
MAX_TOKENS = 512


@lru_cache(maxsize=1)
def get_classifier():
    return pipeline(
        "text-classification",
        model=MODEL_NAME,
        device=-1,
    )


def detect_with_ai(message):
    if not isinstance(message, str):
        raise TypeError("Message must be text.")

    message = message.strip()
    if not message:
        raise ValueError("Message cannot be empty.")

    result = get_classifier()(
        message[:MAX_MESSAGE_LENGTH],
        truncation=True,
        max_length=MAX_TOKENS,
    )[0]

    label = str(result.get("label", "")).upper()
    confidence = float(result.get("score", 0.0))

    if label == "LABEL_1":
        return "Cyberbullying", confidence

    return "Not Cyberbullying", confidence