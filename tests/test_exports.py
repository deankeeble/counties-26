import sqlite3

from counties26 import db
from counties26.draw_import import import_draw
from counties26.exports import export_round_scores_csv
from counties26.importer import build_import_report, commit_import


def _setup_draw(tmp_path, conn, division, team_numbers):
    """A minimal round robin: N teams on lanes 1..N, using the standard team size
    for the division (5 for men, 4 for women)."""
    grid_path = tmp_path / f"{division}_grid.csv"
    teams_path = tmp_path / f"{division}_teams.csv"
    players_path = tmp_path / f"{division}_players.csv"
    grid_path.write_text(",".join(str(n) for n in team_numbers))
    lines = ["team_number,team_name"] + [f"{n},Team {n}" for n in team_numbers]
    teams_path.write_text("\n".join(lines))
    
    # Create players roster
    players_lines = ["team_number,player_name"]
    team_size = 4 if division == "women" else 5
    for team_num in team_numbers:
        for pos in range(1, team_size + 1):
            players_lines.append(f"{team_num},Team {team_num} P{pos}")
    players_path.write_text("\n".join(players_lines))
    
    return import_draw(conn, grid_path, teams_path, division, players_path)


def _score_csv_rows(team_lane, team_name, scores, start_date="2026-06-01 10:00"):
    rows = []
    for position, score in enumerate(scores, start=1):
        rows.append(
            {
                "Lane number": str(team_lane),
                "Team name": team_name,
                "Bowler name": f"Team {team_name} P{position}",
                "Play position": str(position),
                "Scratch": str(score),
                "Start date": start_date,
                "End date": "2026-06-01 10:30",
            }
        )
    return rows


def _write_csv(path, rows):
    header = ["Lane number", "Team name", "Bowler name", "Play position", "Scratch", "Start date", "End date"]
    lines = [",".join(header)]
    for row in rows:
        lines.append(",".join(row[col] for col in header))
    path.write_text("\n".join(lines))


def test_export_round_scores_csv_men(tmp_path):
    """Test exporting scores for a men's round with complete lineups."""
    conn = db.connect(":memory:")
    db.init_db(conn)
    _setup_draw(tmp_path, conn, "men", [1, 2])
    
    # Import scores for round 1: teams 1 and 2 play each other
    csv_path = tmp_path / "scores.csv"
    rows = (
        _score_csv_rows(1, "1", [100, 110, 120, 130, 140])  # Team 1 on lane 1
        + _score_csv_rows(2, "2", [150, 160, 170, 180, 190])  # Team 2 on lane 2
    )
    _write_csv(csv_path, rows)
    
    report = build_import_report(conn, csv_path, "men", round_number=1, block_game=1)
    commit_import(conn, csv_path, report)
    
    # Export the round
    csv_output = export_round_scores_csv(conn, "men", 1)
    
    lines = csv_output.split("\n")
    assert len(lines) == 10  # 5 players from team 1 + 5 players from team 2
    
    # Team 1 scores should be in order
    assert lines[0] == "1,100"
    assert lines[1] == "2,110"
    assert lines[2] == "3,120"
    assert lines[3] == "4,130"
    assert lines[4] == "5,140"
    
    # Team 2 scores should follow
    assert lines[5] == "1,150"
    assert lines[6] == "2,160"
    assert lines[7] == "3,170"
    assert lines[8] == "4,180"
    assert lines[9] == "5,190"


def test_export_round_scores_with_custom_player_order(tmp_path):
    """Test exporting scores respecting a custom player order from CSV."""
    conn = db.connect(":memory:")
    db.init_db(conn)
    _setup_draw(tmp_path, conn, "men", [1, 2])
    
    # Import scores for round 1
    csv_path = tmp_path / "scores.csv"
    rows = (
        _score_csv_rows(1, "1", [100, 110, 120, 130, 140])
        + _score_csv_rows(2, "2", [150, 160, 170, 180, 190])
    )
    _write_csv(csv_path, rows)
    
    report = build_import_report(conn, csv_path, "men", round_number=1, block_game=1)
    commit_import(conn, csv_path, report)
    
    # Create a custom player order CSV with team 2 first, then team 1
    players_csv = tmp_path / "custom_players.csv"
    players_lines = [
        "team_number,player_name",
        "2,Team 2 P1",
        "2,Team 2 P2",
        "2,Team 2 P3",
        "2,Team 2 P4",
        "2,Team 2 P5",
        "1,Team 1 P1",
        "1,Team 1 P2",
        "1,Team 1 P3",
        "1,Team 1 P4",
        "1,Team 1 P5",
    ]
    players_csv.write_text("\n".join(players_lines))
    
    # Export using custom player order
    csv_output = export_round_scores_csv(conn, "men", 1, players_csv)
    
    lines = csv_output.split("\n")
    assert len(lines) == 10
    
    # Team 2 should come first now (with their actual game positions and scores)
    assert lines[0] == "1,150"
    assert lines[1] == "2,160"
    assert lines[2] == "3,170"
    assert lines[3] == "4,180"
    assert lines[4] == "5,190"
    
    # Then team 1
    assert lines[5] == "1,100"
    assert lines[6] == "2,110"
    assert lines[7] == "3,120"
    assert lines[8] == "4,130"
    assert lines[9] == "5,140"


def test_export_round_with_missing_players(tmp_path):
    """Test exporting scores when some players didn't play."""
    conn = db.connect(":memory:")
    db.init_db(conn)
    _setup_draw(tmp_path, conn, "men", [1, 2])
    
    # Create a players CSV to test export with missing players
    players_csv = tmp_path / "players.csv"
    players_csv.write_text(
        "team_number,player_name\n"
        "1,Team 1 P1\n"
        "1,Team 1 P2\n"
        "1,Team 1 P3\n"
        "1,Team 1 P4\n"
        "1,Team 1 P5\n"
        "2,Team 2 P1\n"
        "2,Team 2 P2\n"
        "2,Team 2 P3\n"
        "2,Team 2 P4\n"
        "2,Team 2 P5\n"
    )
    
    # Export with no scores imported
    csv_output = export_round_scores_csv(conn, "men", 1, players_csv)
    lines = csv_output.split("\n")
    
    # All lines should be empty (no scores imported)
    assert len(lines) == 10
    for line in lines:
        assert line == ""


def test_export_round_nonexistent_round_raises_error(tmp_path):
    """Test that exporting a nonexistent round raises an error."""
    conn = db.connect(":memory:")
    db.init_db(conn)
    _setup_draw(tmp_path, conn, "men", [1, 2])
    
    try:
        export_round_scores_csv(conn, "men", 999)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "No such round" in str(e)
