"""Small deterministic citizen-message catalogue for the MVP languages."""
from __future__ import annotations


def detect_language(text: str) -> str:
    return "ta" if any("\u0b80" <= char <= "\u0bff" for char in text) else "en"


def message(language: str, key: str, **values: object) -> str:
    catalogue = {
        "en": {
            "needs_location": "Please reply with the nearest street or landmark to the issue.",
            "need_photo": "Description received. Please send a photo of the issue.",
            "need_description": "Photo received. Please send a voice note or text description.",
            "created": "Logged as #{id}. Routed to {dept}. Target resolution by {date}.",
            "merged": "This is already tracked as #{id}.",
            "overdue": "Your report {id} is overdue and has been escalated. The ward office has been re-notified.",
        },
        "ta": {
            "needs_location": "பிரச்சினை உள்ள இடத்திற்கு அருகிலுள்ள தெரு அல்லது அடையாள இடத்தை அனுப்பவும்.",
            "need_photo": "விவரம் கிடைத்தது. பிரச்சினையின் புகைப்படத்தை அனுப்பவும்.",
            "need_description": "புகைப்படம் கிடைத்தது. குரல் பதிவு அல்லது உரை விவரத்தை அனுப்பவும்.",
            "created": "#{id} ஆக பதிவு செய்யப்பட்டது. {dept} துறைக்கு அனுப்பப்பட்டது. இலக்கு தேதி: {date}.",
            "merged": "இது ஏற்கனவே #{id} ஆக கண்காணிக்கப்படுகிறது.",
            "overdue": "உங்கள் புகார் {id} காலக்கெடுவை கடந்ததால் மேல்நிலைக்கு அனுப்பப்பட்டது.",
        },
    }
    template = catalogue.get(language, catalogue["en"]).get(key, catalogue["en"][key])
    return template.format(**values)
