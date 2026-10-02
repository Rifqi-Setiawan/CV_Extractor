"""Streamlit UI: upload CVs, run the extractor, inspect sections, preview and JSON."""
from __future__ import annotations

import json
from dataclasses import dataclass

import streamlit as st

from cv_extractor.application.config import LlmConfig, OcrConfig, PipelineConfig
from cv_extractor.bootstrap import build_service, ollama_available
from cv_extractor.domain.models import ParsedCV
from cv_extractor.infrastructure.pdf_reader import render_pdf_pages
from cv_extractor.presentation.preview import annotate_pages, hex_color

PREVIEW_DPI = 110

LABEL_NAMES = {
    "summary": "Ringkasan / Summary",
    "experience": "Pengalaman Kerja / Experience",
    "education": "Pendidikan / Education",
    "skills": "Keahlian / Skills",
    "projects": "Proyek / Projects",
    "training": "Pelatihan / Training",
    "certifications": "Sertifikasi / Certifications",
    "organizations": "Organisasi / Organizations",
    "awards": "Prestasi / Awards",
    "languages": "Bahasa / Languages",
    "contact": "Kontak / Contact",
    "personal_info": "Data Diri / Personal Info",
    "publications": "Publikasi / Publications",
    "interests": "Minat / Interests",
    "references": "Referensi / References",
    "additional_info": "Informasi Tambahan / Additional Info",
    "header": "Header (tanpa heading)",
    "other": "Lainnya / Other",
}

_CSS = """
<style>
.section-chip {display:inline-block; padding:2px 10px; border-radius:999px; color:#fff;
               font-size:0.78rem; font-weight:600; letter-spacing:0.02em; margin-right:8px;}
.raw-heading {color:#64748b; font-size:0.85rem;}
.section-text {white-space:pre-wrap; font-size:0.92rem; line-height:1.5;
               border-left:3px solid var(--chip); padding:4px 0 4px 12px; margin:4px 0 18px 0;}
</style>
"""


@dataclass(frozen=True)
class UiSettings:
    languages: str
    dpi: int
    llm_enabled: bool
    ollama_url: str
    llm_model: str
    llm_threshold: float

    def to_config(self) -> PipelineConfig:
        return PipelineConfig(
            ocr=OcrConfig(languages=self.languages, dpi=self.dpi),
            llm=LlmConfig(
                enabled=self.llm_enabled,
                base_url=self.ollama_url,
                model=self.llm_model,
                confidence_threshold=self.llm_threshold,
            ),
        )


# ------------------------------------------------------------------ cached work


@st.cache_resource(show_spinner=False)
def _service(settings: UiSettings):
    return build_service(settings.to_config())


@st.cache_data(show_spinner=False, max_entries=64)
def _extract(data: bytes, file_name: str, settings: UiSettings) -> ParsedCV:
    return _service(settings).extract(data, file_name)


@st.cache_data(show_spinner=False, max_entries=32)
def _pages(data: bytes):
    return render_pdf_pages(data, PREVIEW_DPI)


# ------------------------------------------------------------------ sidebar


def _sidebar() -> UiSettings:
    st.sidebar.header("⚙️ Pengaturan")

    st.sidebar.subheader("OCR (untuk PDF hasil scan / gambar)")
    langs = st.sidebar.multiselect(
        "Bahasa OCR", ["eng", "ind"], default=["eng", "ind"],
        help="Kode bahasa Tesseract. Data bahasa harus sudah terpasang.",
    )
    dpi = st.sidebar.select_slider("Resolusi OCR (DPI)", options=[200, 250, 300, 350], value=300,
                                   help="Lebih tinggi = lebih akurat tapi lebih lambat.")

    st.sidebar.subheader("LLM lokal (opsional)")
    llm_enabled = st.sidebar.toggle(
        "Aktifkan fallback Ollama", value=False,
        help="Hanya dipanggil jika skor kepercayaan rendah atau ada heading yang tidak dikenali.",
    )
    ollama_url, model, threshold = "http://localhost:11434", "qwen2.5:3b", 0.6
    if llm_enabled:
        ollama_url = st.sidebar.text_input("URL Ollama", ollama_url)
        model = st.sidebar.text_input("Model", model)
        threshold = st.sidebar.slider("Panggil LLM jika confidence <", 0.3, 0.9, threshold, 0.05)
        if ollama_available(ollama_url):
            st.sidebar.success("Ollama terhubung")
        else:
            st.sidebar.error("Ollama tidak dapat dihubungi — hasil tetap memakai aturan Python.")

    return UiSettings("+".join(langs) or "eng", dpi, llm_enabled, ollama_url, model, threshold)


# ------------------------------------------------------------------ views


def _overview(results: list[ParsedCV]) -> None:
    rows = [
        {
            "File": cv.meta.file_name,
            "Nama": cv.name or "—",
            "Email": ", ".join(cv.contact.emails) or "—",
            "Section": len([s for s in cv.sections if s.label != "header"]),
            "Confidence": round(cv.meta.confidence, 2),
            "Perlu dicek": "⚠️" if cv.meta.needs_review else "✅",
            "Sumber teks": ", ".join(sorted({p.source.value for p in cv.meta.pages})),
            "Waktu (s)": round(cv.meta.seconds, 1),
        }
        for cv in results
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    all_json = json.dumps([cv.to_dict() for cv in results], ensure_ascii=False, indent=2)
    st.download_button("⬇️ Unduh semua hasil (JSON)", all_json, "hasil_ekstraksi.json", "application/json")


def _identity(cv: ParsedCV) -> None:
    c = cv.contact
    col1, col2, col3 = st.columns(3)
    col1.metric("Section terdeteksi", len([s for s in cv.sections if s.label != "header"]))
    col2.metric("Confidence", f"{cv.meta.confidence:.2f}", "perlu dicek" if cv.meta.needs_review else "ok",
                delta_color="inverse" if cv.meta.needs_review else "normal")
    col3.metric("Waktu proses", f"{cv.meta.seconds:.1f} s")

    details = {
        "Headline": cv.headline,
        "Email": ", ".join(c.emails),
        "Telepon": ", ".join(c.phones),
        "LinkedIn": c.linkedin,
        "Lokasi": c.location,
        "URL lain": ", ".join(c.urls),
    }
    st.table({k: [v] for k, v in details.items() if v})

    pages = ", ".join(f"hal. {p.number + 1}: {p.source.value}, {p.columns} kolom" for p in cv.meta.pages)
    st.caption(f"Strategi heading: **{cv.meta.heading_strategy}** · LLM dipakai: "
               f"**{'ya' if cv.meta.llm_used else 'tidak'}** · {pages}")
    for warning in cv.meta.warnings:
        st.warning(warning)


def _sections(cv: ParsedCV) -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    for section in cv.sections:
        color = hex_color(section.label)
        heading = f"“{section.raw_heading}”" if section.raw_heading else "tanpa heading (disimpulkan)"
        st.markdown(
            f'<span class="section-chip" style="background:{color}">{LABEL_NAMES.get(section.label, section.label)}'
            f'</span><span class="raw-heading">{heading} · sumber label: {section.label_source}</span>',
            unsafe_allow_html=True,
        )
        text = section.text or "(kosong)"
        st.markdown(
            f'<div class="section-text" style="--chip:{color}">{_escape(text)}</div>',
            unsafe_allow_html=True,
        )


def _preview(cv: ParsedCV, data: bytes) -> None:
    st.caption("Kotak bergaris = heading yang terdeteksi; arsiran = isi section (warna sesuai label).")
    legend = " ".join(
        f'<span class="section-chip" style="background:{hex_color(lbl)}">{lbl}</span>'
        for lbl in dict.fromkeys(s.label for s in cv.sections)
    )
    st.markdown(_CSS + legend, unsafe_allow_html=True)
    images = annotate_pages(cv, _pages(data), PREVIEW_DPI)
    cols = st.columns(min(len(images), 2))
    for i, image in enumerate(images):
        cols[i % len(cols)].image(image, caption=f"Halaman {i + 1}", use_container_width=True)


def _json(cv: ParsedCV) -> None:
    payload = cv.to_dict()
    st.download_button(
        "⬇️ Unduh JSON", json.dumps(payload, ensure_ascii=False, indent=2),
        f"{cv.meta.file_name.rsplit('.', 1)[0]}.json", "application/json",
    )
    st.json(payload, expanded=2)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ------------------------------------------------------------------ page


def main() -> None:
    st.set_page_config(page_title="CV Section Extractor", page_icon="📄", layout="wide")
    st.title("📄 CV Section Extractor")
    st.write(
        "Ekstrak **nama, kontak, dan section** (pengalaman, pendidikan, keahlian, dst.) dari CV PDF "
        "berbahasa Indonesia maupun Inggris. Berjalan lokal di CPU, tanpa biaya API."
    )

    settings = _sidebar()
    uploads = st.file_uploader("Unggah satu atau beberapa CV (PDF)", type=["pdf"], accept_multiple_files=True)
    if not uploads:
        st.info("Unggah file PDF untuk memulai. PDF tanpa lapisan teks (hasil scan / Canva gambar) "
                "otomatis diproses dengan OCR — butuh ±20–60 detik per CV.")
        return

    results: list[ParsedCV] = []
    files: dict[str, bytes] = {}
    progress = st.progress(0.0, text="Memproses…")
    for i, upload in enumerate(uploads):
        data = upload.getvalue()
        progress.progress(i / len(uploads), text=f"Memproses {upload.name} ({i + 1}/{len(uploads)})…")
        try:
            results.append(_extract(data, upload.name, settings))
            files[upload.name] = data
        except Exception as exc:  # one broken file must not stop the batch
            st.error(f"Gagal memproses {upload.name}: {exc}")
    progress.empty()
    if not results:
        return

    if len(results) > 1:
        st.subheader("Ringkasan")
        _overview(results)
        st.divider()

    chosen = st.selectbox("Lihat detail CV", [cv.meta.file_name for cv in results]) if len(results) > 1 \
        else results[0].meta.file_name
    cv = next(r for r in results if r.meta.file_name == chosen)

    st.subheader(cv.name or chosen)
    _identity(cv)
    tab_sections, tab_preview, tab_json = st.tabs(["📑 Section", "🖼️ Preview", "🧾 JSON"])
    with tab_sections:
        _sections(cv)
    with tab_preview:
        _preview(cv, files[chosen])
    with tab_json:
        _json(cv)
