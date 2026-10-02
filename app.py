"""Streamlit entry point:  streamlit run app.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from cv_extractor.presentation.streamlit_app import main  # noqa: E402

main()
