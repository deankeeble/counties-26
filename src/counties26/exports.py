"""Export round scores in various formats."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path


def export_round_scores_csv(
    conn: sqlite3.Connection,
    division: str,
    round_number: int,
    players_csv: Path | str | None = None,
) -> str:
    """Export all players' scores from a round as CSV.
    
    Format: position,score for each player in roster order, with empty score
    for players who didn't play.
    
    If players_csv is provided, players are exported in the exact order they appear
    in that file. Otherwise, players are ordered by team_number then play_position.
    """
    # Verify the round exists
    round_id_row = conn.execute(
        "SELECT id FROM rounds WHERE division = ? AND round_number = ?",
        (division, round_number),
    ).fetchone()
    if round_id_row is None:
        raise ValueError(f"No such round: {division} round {round_number}")
    round_id = round_id_row["id"]

    # Get all fixtures for this round
    fixtures = conn.execute(
        """
        SELECT id FROM fixtures
        WHERE round_id = ?
        """,
        (round_id,),
    ).fetchall()

    fixture_ids = [f["id"] for f in fixtures]

    # Build a map of (player_name, team_number) -> (play_position, scratch_score)
    # This uses actual game data from bowler_scores
    scores_by_player: dict[tuple[str, int], tuple[int, int]] = {}
    if fixture_ids:
        placeholders = ",".join("?" * len(fixture_ids))
        score_rows = conn.execute(
            f"""
            SELECT bs.bowler_name, t.team_number, bs.play_position, bs.scratch_score
            FROM bowler_scores bs
            JOIN teams t ON t.id = bs.team_id
            WHERE bs.fixture_id IN ({placeholders})
            """,
            fixture_ids,
        ).fetchall()

        for score_row in score_rows:
            bowler_name = score_row["bowler_name"]
            team_number = score_row["team_number"]
            play_position = score_row["play_position"]
            scratch_score = score_row["scratch_score"]
            scores_by_player[(bowler_name, team_number)] = (play_position, scratch_score)

    # Get player order from CSV if provided
    if players_csv:
        # Read players in CSV order
        players = []
        with open(players_csv, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                team_number = int(row["team_number"])
                player_name = row["player_name"].strip()
                players.append((player_name, team_number))
    else:
        # Use default order: by team_number, then play_position
        players = conn.execute(
            """
            SELECT p.name, t.team_number
            FROM players p
            JOIN teams t ON t.id = p.team_id
            WHERE t.division = ?
            ORDER BY t.team_number, p.play_position
            """,
            (division,),
        ).fetchall()
        players = [(row["name"], row["team_number"]) for row in players]

    if not players:
        raise ValueError(f"No players found for division {division}")

    # Build CSV output
    lines = []
    for player_name, team_number in players:
        # Look up this player's actual score in this round
        score_data = scores_by_player.get((player_name, team_number))

        if score_data:
            position, scratch_score = score_data
            lines.append(f"{position},{scratch_score}")
        else:
            # Player didn't play in this round
            lines.append("")

    return "\n".join(lines)
