from pathlib import Path
import streamlit.components.v1 as components

_DRUM_DIR = Path(__file__).parent / "components" / "drum_picker"
_drum_component = components.declare_component("drum_picker", path=str(_DRUM_DIR))


def time_drum(label: str, options: list, value: str, key: str, help: str = "") -> str:
    """Drum-wheel picker. Returns the selected option string (e.g. '08:00').
    Falls back to `value` if the component hasn't fired yet."""
    result = _drum_component(label=label, options=options, value=value, key=key, default=value)
    return result if (result and result in options) else value
