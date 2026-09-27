BULLYING_WORDS = {
    "stupid",
    "idiot",
    "dumb",
    "loser",
    "fool",
    "shut up",
    "hate you",
    "worthless",
    "useless"
}

THREAT_WORDS = {
    "kill you",
    "hurt you",
    "i will find you",
    "you will regret this"
}

HARASSMENT_WORDS = {
    "leave me alone",
    "nobody likes you",
    "go away"
}


def detect_cyberbullying(message):
    text = message.lower()

    bullying_matches = [
        word for word in BULLYING_WORDS
        if word in text
    ]

    threat_matches = [
        word for word in THREAT_WORDS
        if word in text
    ]

    harassment_matches = [
        word for word in HARASSMENT_WORDS
        if word in text
    ]

    if threat_matches:
        confidence = min(0.70 + (0.05 * len(threat_matches)), 0.95)
        return "Cyberbullying - Threat", confidence

    if bullying_matches:
        confidence = min(0.50 + (0.10 * len(bullying_matches)), 0.95)
        return "Cyberbullying - Insult", confidence

    if harassment_matches:
        confidence = min(0.60 + (0.05 * len(harassment_matches)), 0.95)
        return "Cyberbullying - Harassment", confidence

    return "Not Cyberbullying", 0.05