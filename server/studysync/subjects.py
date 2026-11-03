"""Subjects and their spine colours (kept identical to the front end's src/utils/subjects.js)."""
SUBJECT_COLORS = {
    "Data Structures": "#0F7B70",
    "Databases": "#6446C9",
    "Operating Systems": "#B4540B",
    "Web Development": "#1D6FA5",
    "Placements": "#2F7D32",
    "AI and ML": "#B8325A",
    "Compilers": "#7A5C00",
    "Networks": "#3B5BA9",
}
SUBJECTS = list(SUBJECT_COLORS)


def subject_color(subject: str) -> str:
    return SUBJECT_COLORS.get(subject, "#4F5A73")
