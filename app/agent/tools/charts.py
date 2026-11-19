"""Plotly chart generation for the agent.

Builds interactive Plotly charts from tabular data and writes them
into the agent workspace as HTML (and optionally PNG via kaleido).

The ``create_chart`` tool is approval-required: it writes a file
into the workspace, so the graph pauses for human approval before
generating the chart.
"""
from typing import Optional

import plotly.graph_objects as go

from app.config.settings import settings

CHART_TYPES = {"bar", "line", "scatter", "pie", "area", "donut"}


class ChartError(Exception):
    """Raised for invalid chart requests."""


def _workspace_root():
    from pathlib import Path

    return Path(settings.AGENT_WORKSPACE_ROOT).expanduser().resolve()


def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)


def create_chart(
    *,
    chart_type: str,
    x: list,
    y: list,
    title: Optional[str] = None,
    labels: Optional[dict] = None,
    filename: Optional[str] = None,
    as_png: bool = False,
) -> dict:
    """Generate a Plotly chart and persist it to the workspace.

    ``x`` and ``y`` must be non-empty lists of equal length. For
    pie/donut charts ``x`` is used as labels and ``y`` as values.
    Returns the written file paths so the caller can surface them
    to the user (and so the engine tracks them as run artifacts).
    """
    chart_type = (chart_type or "bar").lower()
    if chart_type not in CHART_TYPES:
        raise ChartError(
            f"unsupported chart type: {chart_type} "
            f"(choose from: {', '.join(sorted(CHART_TYPES))})"
        )
    if not x or not y:
        raise ChartError("x and y are required and must be non-empty")
    if len(x) != len(y):
        raise ChartError("x and y must have the same length")

    fig = go.Figure()
    if chart_type == "bar":
        fig.add_bar(x=x, y=y)
    elif chart_type == "line":
        fig.add_scatter(x=x, y=y, mode="lines+markers")
    elif chart_type == "scatter":
        fig.add_scatter(x=x, y=y, mode="markers")
    elif chart_type == "area":
        fig.add_scatter(x=x, y=y, mode="lines", fill="tozeroy")
    elif chart_type in ("pie", "donut"):
        hole = 0.5 if chart_type == "donut" else 0.0
        fig.add_pie(labels=list(x), values=list(y), hole=hole)

    if title:
        fig.update_layout(title=title)
    if labels:
        fig.update_layout(labels=labels)

    root = _workspace_root()
    root.mkdir(parents=True, exist_ok=True)
    base = _safe_filename(filename or f"chart_{chart_type}") or f"chart_{chart_type}"

    html_path = root / f"{base}.html"
    fig.write_html(str(html_path))

    result = {
        "chart_type": chart_type,
        "points": len(x),
        "path": str(html_path),
        "written": True,
    }
    if as_png:
        png_path = root / f"{base}.png"
        try:
            fig.write_image(str(png_path))
            result["png_path"] = str(png_path)
        except Exception as exc:  # kaleido may be unavailable
            result["png_error"] = str(exc)
    return result


def create_chart_fallback(
    *,
    chart_type: str,
    x: list,
    y: list,
    title: Optional[str] = None,
    filename: Optional[str] = None,
) -> dict:
    """Generate a chart with matplotlib.

    Used as a fallback when Plotly cannot render the
    chart (for example when kaleido or a renderer is
    unavailable). Writes a PNG into the workspace so
    the runner file endpoint can serve it inline.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    chart_type = (chart_type or "bar").lower()
    if chart_type not in CHART_TYPES:
        raise ChartError(
            f"unsupported chart type: {chart_type} "
            f"(choose from: {', '.join(sorted(CHART_TYPES))})"
        )
    if not x or not y:
        raise ChartError("x and y are required and must be non-empty")
    if len(x) != len(y):
        raise ChartError("x and y must have the same length")

    labels = [str(v) for v in x]
    values = [float(v) for v in y]

    root = _workspace_root()
    root.mkdir(parents=True, exist_ok=True)
    base = _safe_filename(filename or f"chart_{chart_type}") or f"chart_{chart_type}"
    png_path = root / f"{base}.png"

    fig, ax = plt.subplots()
    if chart_type == "bar":
        ax.bar(labels, values)
    elif chart_type == "line":
        ax.plot(labels, values, marker="o")
    elif chart_type == "scatter":
        ax.scatter(range(len(values)), values)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels)
    elif chart_type == "area":
        ax.fill_between(range(len(values)), values)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels)
    elif chart_type in ("pie", "donut"):
        ax.pie(values, labels=labels, autopct="%1.1f%%")
    else:
        ax.bar(labels, values)

    if title:
        ax.set_title(title)
    if chart_type not in ("pie", "donut"):
        fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(str(png_path))
    plt.close(fig)

    return {
        "chart_type": chart_type,
        "points": len(values),
        "path": str(png_path),
        "written": True,
        "renderer": "matplotlib",
    }
