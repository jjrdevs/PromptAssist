"""PromptAssist — lightweight Windows desktop prompt utility.

A single-purpose tool for triggering a multi-stage AI-coding workflow.
This Python package is the CLI + core shared with the GUI (Tauri 2 Rust
app). See `passist/__main__.py` for the CLI entry point.
"""

__version__ = "0.1.0"
__all__ = ["__version__"]

from passist.models import (  # noqa: E402,F401
    Feature,
    HotkeyBindings,
    Stage,
    StageOrder,
)
from passist.render import render_stage, render_all, substitute  # noqa: F401
from passist.hotkeys import (  # noqa: F401
    is_valid,
    normalize_combination,
    parse,
    suggest_safe_fallback,
)
from passist.storage import (  # noqa: F401
    default_config,
    load_features,
    load_prompts,
    load_settings,
    save_features,
    save_settings,
)
