"""Markdown rendering from Jinja2 templates."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

log = logging.getLogger(__name__)


def md_escape_link_text(text: str) -> str:
    """Escape markdown-special characters in text used inside link brackets.

    Handles characters that break [text](url) syntax in markdown parsers:
    - [ ] are escaped to prevent nested bracket confusion
    - ` is escaped to prevent inline code breaking the link
    - Trailing whitespace is stripped
    """
    text = text.strip()
    text = text.replace("[", "&#91;").replace("]", "&#93;")
    text = text.replace("`", "&#96;")
    return text


def render_markdown(
    metrics: dict,
    template_path: Path,
    period_label: str,
    start_date: str,
    end_date: str,
) -> str:
    """Render metrics to markdown using Jinja2 template."""
    template_dir = template_path.parent
    template_name = template_path.name

    env = Environment(loader=FileSystemLoader(template_dir))
    env.filters["md_escape"] = md_escape_link_text
    template = env.get_template(template_name)

    context = {
        **metrics,
        "period_label": period_label,
        "start_date": start_date,
        "end_date": end_date,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }

    log.debug(f"Rendering template: {template_name}")
    return template.render(**context)
