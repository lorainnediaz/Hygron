"""Bridge the live simulator state to the local interactive board component."""
from pathlib import Path

import streamlit.components.v1 as components


hygron_board = components.declare_component(
    "hygron_virtual_board",
    path=str(Path(__file__).resolve().parent / "board_component"),
)
