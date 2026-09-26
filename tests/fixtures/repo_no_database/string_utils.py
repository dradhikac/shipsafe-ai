def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    return text.lower().strip().replace(" ", "-")


def capitalize_words(text: str) -> str:
    """Capitalize each word in text."""
    return " ".join(w.capitalize() for w in text.split())
