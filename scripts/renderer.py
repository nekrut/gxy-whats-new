"""Markdown rendering from Jinja2 templates."""

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


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
    template = env.get_template(template_name)

    context = {
        **metrics,
        "period_label": period_label,
        "start_date": start_date,
        "end_date": end_date,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }

    return template.render(**context)
