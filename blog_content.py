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
]

ARTICLES_BY_SLUG = {article["slug"]: article for article in ARTICLES}


def get_article(slug: str):
    return ARTICLES_BY_SLUG.get(slug)
