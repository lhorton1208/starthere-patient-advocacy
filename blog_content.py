"""Blog and educational resource articles."""

ARTICLES = [
    {
        "slug": "why-every-family-should-consider-a-patient-advocate",
        "title": "Why Every Family Should Consider a Patient Advocate",
        "summary": (
            "Healthcare has never been more advanced, yet it has never been more "
            "complicated. Learn how a patient advocate helps families navigate "
            "care with confidence."
        ),
        "published": "2026-07-03",
    },
    {
        "slug": "10-signs-your-loved-one-may-need-a-patient-advocate",
        "title": "10 Signs Your Loved One May Need a Patient Advocate",
        "summary": (
            "Caring for an aging parent or family member can become overwhelming "
            "when medical appointments, medications, and insurance questions pile up. "
            "Here are ten signs a patient advocate may help."
        ),
        "published": "2026-07-03",
    },
    {
        "slug": "what-does-a-patient-advocate-actually-do",
        "title": "What Does a Patient Advocate Actually Do?",
        "summary": (
            "Many people hear the term patient advocate but are not sure what it means. "
            "Learn how StartHere helps patients understand, organize, and navigate healthcare."
        ),
        "published": "2026-07-04",
    },
    {
        "slug": "the-hidden-costs-of-navigating-healthcare-alone",
        "title": "The Hidden Costs of Navigating Healthcare Alone",
        "summary": (
            "Beyond doctor bills and copays, managing healthcare alone can bring stress, "
            "missed information, and caregiver burnout. See how an advocate can help."
        ),
        "published": "2026-07-04",
    },
]

ARTICLES_BY_SLUG = {article["slug"]: article for article in ARTICLES}


def get_article(slug: str):
    return ARTICLES_BY_SLUG.get(slug)
