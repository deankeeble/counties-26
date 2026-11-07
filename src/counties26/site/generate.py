"""Static site builder — renders standings/bowler stats for gh-pages publishing."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from counties26.site.data import division_page_data, team_page_data

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

DIVISION_TITLES = {"men": "Men's", "women": "Women's"}


def build_site(conn: sqlite3.Connection, output_dir: str | Path) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / ".nojekyll").touch()

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    index_template = env.get_template("index.html")
    (output_path / "index.html").write_text(
        index_template.render(generated_at=generated_at, divisions=DIVISION_TITLES)
    )

    division_template = env.get_template("division.html")
    team_template = env.get_template("team.html")
    for division, title in DIVISION_TITLES.items():
        page_data = division_page_data(conn, division)
        html = division_template.render(
            division_title=title,
            division=division,
            **page_data,
            generated_at=generated_at,
        )
        html = html.replace('<details class="game" open>', '<details class="game">')
        (output_path / f"{division}.html").write_text(html)
        for team_id, team in page_data["team_links"].items():
            team_html = team_template.render(
                    division_title=title,
                    division=division,
                    generated_at=generated_at,
                    **team_page_data(conn, team_id),
            )
            team_html = team_html.replace('<details class="game" open>', '<details class="game">')
            (output_path / team["href"]).write_text(team_html)

    bigscreen_template = env.get_template("bigscreen.html")
    women_data = division_page_data(conn, "women")
    men_data = division_page_data(conn, "men")
    bigscreen_html = bigscreen_template.render(
        women_standings=women_data["standings"],
        men_standings=men_data["standings"],
    )
    (output_path / "bigscreen.html").write_text(bigscreen_html)

    shutil.copy(STATIC_DIR / "style.css", output_path / "style.css")
