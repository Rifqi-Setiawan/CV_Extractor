"""Canonical section labels and their known heading aliases (English + Indonesian).

The dictionary is only used to find *anchor* headings. Headings that are not in this
dictionary are still detected through their visual style (see services/heading_detector.py),
so the list does not need to be complete.
"""
from __future__ import annotations

SECTION_ALIASES: dict[str, list[str]] = {
    "summary": [
        "summary", "profile", "about", "about me", "professional summary", "career summary",
        "objective", "career objective", "personal statement", "description",
        "ringkasan", "profil", "profil singkat", "tentang saya", "tentang", "deskripsi",
        "deskripsi diri", "ringkasan profesional",
    ],
    "experience": [
        "experience", "experiences", "work experience", "work experiences",
        "professional experience", "employment", "employment history", "work history",
        "career history", "internship", "internships", "internship experience",
        "pengalaman", "pengalaman kerja", "riwayat pekerjaan", "pengalaman profesional",
        "pengalaman magang", "riwayat kerja", "pengalaman bekerja",
    ],
    "education": [
        "education", "education history", "educational background", "academic background",
        "academic history", "pendidikan", "riwayat pendidikan", "latar belakang pendidikan",
        "pendidikan formal",
    ],
    "skills": [
        "skills", "skill", "relevant skills", "technical skills", "hard skills", "soft skills",
        "core competencies", "competencies", "skills & others", "skills & tools",
        "skills & interests", "tools", "tech stack", "expertise",
        "keahlian", "kemampuan", "keterampilan", "kompetensi", "keahlian teknis",
    ],
    "projects": [
        "projects", "project", "personal projects", "academic projects", "portfolio",
        "proyek", "projek", "portofolio", "pengalaman proyek",
    ],
    "training": [
        "training", "trainings", "courses", "course", "professional training",
        "ai & professional training", "bootcamp", "activities", "activity",
        "pelatihan", "kursus", "kegiatan", "pelatihan & kursus",
    ],
    "certifications": [
        "certifications", "certification", "certificates", "certificate",
        "licenses & certifications", "licenses and certifications",
        "sertifikasi", "sertifikat", "lisensi & sertifikasi",
    ],
    "organizations": [
        "organization", "organizations", "organizational experience", "leadership",
        "leadership experience", "volunteer", "volunteering", "volunteer experience",
        "organisasi", "pengalaman organisasi", "kepanitiaan", "kegiatan organisasi",
    ],
    "awards": [
        "awards", "award", "achievements", "achievement", "honors", "honors & awards",
        "prestasi", "penghargaan", "pencapaian",
    ],
    "languages": ["languages", "language", "bahasa", "kemampuan bahasa"],
    "contact": [
        "contact", "contacts", "contact info", "contact information", "contact me",
        "kontak", "informasi kontak", "hubungi saya",
    ],
    "personal_info": [
        "personal information", "personal info", "personal details", "personal data",
        "data diri", "informasi pribadi", "biodata", "data pribadi",
    ],
    "publications": ["publications", "publication", "research", "publikasi", "penelitian"],
    "interests": ["interests", "hobbies", "hobby", "minat", "hobi"],
    "references": ["references", "reference", "referensi"],
    "additional_info": [
        "additional information", "additional info", "others", "other information",
        "informasi tambahan", "lainnya", "lain-lain",
    ],
}

# Labels produced without a visible heading or as a last resort.
SUMMARY_LABEL = "summary"
UNKNOWN_LABEL = "other"

ALL_LABELS: list[str] = list(SECTION_ALIASES) + [UNKNOWN_LABEL]
