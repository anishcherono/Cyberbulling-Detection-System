from transformers import pipeline

# Load the BERT bullying detection model
classifier = pipeline(
    "text-classification",
    model="Davephoenix/bert-bullying-detector",
    device=-1
)


def detect_with_ai(message):
    result = classifier(message)[0]

    label = result["label"]
    confidence = result["score"]

    if label == "LABEL_1":
        return "Cyberbullying", confidence
    else:
        return "Not Cyberbullying", confidence