"""Safe corrections to already-imported tournament scores."""

from __future__ import annotations

import sqlite3

from counties26.constants import require_division
from counties26.players import resolve_player_name
from counties26.results import recompute_fixture


def edit_score(
    conn: sqlite3.Connection,
    division: str,
    round_number: int,
    player_name: str,
    play_position: int,
    scratch_score: int,
) -> tuple[str, int, int]:
    """Replace one imported scratch score and recompute its fixture.

    Returns canonical player name, fixture id, and new score.
    """
    require_division(division)
    if play_position < 1:
        raise ValueError("position must be at least 1")
    if scratch_score < 0:
        raise ValueError("score must not be negative")

    fixtures = conn.execute(
        """
        SELECT f.id AS fixture_id, ta.id AS team_a_id, tb.id AS team_b_id
        FROM fixtures f
        JOIN rounds r ON r.id = f.round_id
        JOIN teams ta ON ta.id = f.team_a_id
        JOIN teams tb ON tb.id = f.team_b_id
        WHERE r.division = ? AND r.round_number = ?
        """,
        (division, round_number),
    ).fetchall()
    candidates: list[tuple[sqlite3.Row, int, str]] = []
    for fixture in fixtures:
        for team_id in (fixture["team_a_id"], fixture["team_b_id"]):
            canonical = resolve_player_name(conn, team_id, player_name)
            if canonical is None:
                continue
            score = conn.execute(
                """
                SELECT id FROM bowler_scores
                WHERE fixture_id = ? AND team_id = ? AND play_position = ?
                  AND bowler_name = ?
                """,
                (fixture["fixture_id"], team_id, play_position, canonical),
            ).fetchone()
            if score is not None:
                candidates.append((fixture, score["id"], canonical))

    if len(candidates) != 1:
        if not candidates:
            raise ValueError(
                f"No imported score found for {player_name!r} at position "
                f"{play_position} in {division} round {round_number}"
            )
        raise ValueError(
            f"Player {player_name!r} matches multiple imported scores in "
            f"{division} round {round_number}; use a more specific name"
        )

    fixture, score_id, canonical_name = candidates[0]
    conn.execute(
        "UPDATE bowler_scores SET scratch_score = ? WHERE id = ?",
        (scratch_score, score_id),
    )
    conn.commit()
    recompute_fixture(conn, fixture["fixture_id"])
    return canonical_name, fixture["fixture_id"], scratch_score


def swap_positions(
    conn: sqlite3.Connection,
    division: str,
    round_number: int,
    first_player: str,
    second_player: str,
) -> tuple[str, str, int, int, int]:
    """Swap two players' stored positions in one imported fixture."""
    require_division(division)
    if first_player.strip().casefold() == second_player.strip().casefold():
        raise ValueError("the two players must be different")

    fixtures = conn.execute(
        """
        SELECT f.id AS fixture_id, ta.id AS team_a_id, tb.id AS team_b_id
        FROM fixtures f
        JOIN rounds r ON r.id = f.round_id
        JOIN teams ta ON ta.id = f.team_a_id
        JOIN teams tb ON tb.id = f.team_b_id
        WHERE r.division = ? AND r.round_number = ?
        """,
        (division, round_number),
    ).fetchall()
    matches: list[tuple[str, int, int, int]] = []
    for fixture in fixtures:
        for team_id in (fixture["team_a_id"], fixture["team_b_id"]):
            first = resolve_player_name(conn, team_id, first_player)
            second = resolve_player_name(conn, team_id, second_player)
            if first is None or second is None or first == second:
                continue
            rows = conn.execute(
                """
                SELECT bowler_name, id, play_position
                FROM bowler_scores
                WHERE fixture_id = ? AND team_id = ? AND bowler_name IN (?, ?)
                """,
                (fixture["fixture_id"], team_id, first, second),
            ).fetchall()
            if len(rows) == 2:
                positions = {row["bowler_name"]: (row["id"], row["play_position"]) for row in rows}
                matches.append((first, second, fixture["fixture_id"], positions[first][0], positions[second][0]))

    if len(matches) != 1:
        raise ValueError(
            f"Could not uniquely find both players in {division} round {round_number}"
        )

    first, second, fixture_id, first_id, second_id = matches[0]
    first_position = conn.execute(
        "SELECT play_position FROM bowler_scores WHERE id = ?", (first_id,)
    ).fetchone()["play_position"]
    second_position = conn.execute(
        "SELECT play_position FROM bowler_scores WHERE id = ?", (second_id,)
    ).fetchone()["play_position"]
    conn.execute("UPDATE bowler_scores SET play_position = -1 WHERE id = ?", (first_id,))
    conn.execute("UPDATE bowler_scores SET play_position = ? WHERE id = ?", (first_position, second_id))
    conn.execute("UPDATE bowler_scores SET play_position = ? WHERE id = ?", (second_position, first_id))
    conn.commit()
    recompute_fixture(conn, fixture_id)
    return first, second, first_position, second_position, fixture_id


def clear_round(conn: sqlite3.Connection, division: str, round_number: int) -> tuple[int, int]:
    """Delete imported scores and derived points for one tournament round."""
    require_division(division)
    fixture_rows = conn.execute(
        """
        SELECT f.id
        FROM fixtures f
        JOIN rounds r ON r.id = f.round_id
        WHERE r.division = ? AND r.round_number = ?
        """,
        (division, round_number),
    ).fetchall()
    fixture_ids = [row["id"] for row in fixture_rows]
    if not fixture_ids:
        raise ValueError(f"No round {round_number} found in {division} division")

    placeholders = ",".join("?" for _ in fixture_ids)
    parameters = tuple(fixture_ids)
    score_count = conn.execute(
        f"SELECT COUNT(*) AS count FROM bowler_scores WHERE fixture_id IN ({placeholders})",
        parameters,
    ).fetchone()["count"]
    points_count = conn.execute(
        f"SELECT COUNT(*) AS count FROM match_points WHERE fixture_id IN ({placeholders})",
        parameters,
    ).fetchone()["count"]
    conn.execute(
        f"DELETE FROM bowler_scores WHERE fixture_id IN ({placeholders})", parameters
    )
    conn.execute(
        f"DELETE FROM match_points WHERE fixture_id IN ({placeholders})", parameters
    )
    conn.commit()
    return score_count, points_count
