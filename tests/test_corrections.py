from counties26 import db
from counties26.corrections import clear_round, edit_score, swap_positions
from counties26.draw_import import import_draw
from counties26.importer import build_import_report, commit_import


def test_edit_score_resolves_player_and_recomputes_fixture(tmp_path):
    conn = db.connect(":memory:")
    db.init_db(conn)
    grid = tmp_path / "grid.csv"
    teams = tmp_path / "teams.csv"
    players = tmp_path / "players.csv"
    scores = tmp_path / "scores.csv"
    grid.write_text("1,2")
    teams.write_text("team_number,team_name,team_size\n1,Team 1,2\n2,Team 2,2\n")
    players.write_text(
        "team_number,player_name\n1,Alice One\n1,Bob One\n"
        "2,Carol Two\n2,Dan Two\n"
    )
    import_draw(conn, grid, teams, "men", players)
    scores.write_text(
        "Lane number,Team name,Bowler name,Play position,Scratch,Start date,End date\n"
        "1,ignored,Alice One,1,200,2026-06-01 10:00,2026-06-01 10:30\n"
        "1,ignored,Bob One,2,190,2026-06-01 10:00,2026-06-01 10:30\n"
        "2,ignored,Carol Two,1,180,2026-06-01 10:00,2026-06-01 10:30\n"
        "2,ignored,Dan Two,2,170,2026-06-01 10:00,2026-06-01 10:30\n"
    )
    report = build_import_report(conn, scores, "men", 1)
    commit_import(conn, scores, report)

    canonical, fixture_id, new_score = edit_score(conn, "men", 1, "Alice", 1, 210)

    assert (canonical, fixture_id, new_score) == ("Alice One", 1, 210)
    saved = conn.execute(
        "SELECT scratch_score FROM bowler_scores WHERE bowler_name = 'Alice One'"
    ).fetchone()
    assert saved["scratch_score"] == 210


def test_swap_positions_moves_players_without_moving_scores(tmp_path):
    conn = db.connect(":memory:")
    db.init_db(conn)
    grid = tmp_path / "grid.csv"
    teams = tmp_path / "teams.csv"
    players = tmp_path / "players.csv"
    scores = tmp_path / "scores.csv"
    grid.write_text("1,2")
    teams.write_text("team_number,team_name,team_size\n1,Team 1,2\n2,Team 2,2\n")
    players.write_text(
        "team_number,player_name\n1,Alice One\n1,Bob One\n"
        "2,Carol Two\n2,Dan Two\n"
    )
    import_draw(conn, grid, teams, "men", players)
    scores.write_text(
        "Lane number,Team name,Bowler name,Play position,Scratch,Start date,End date\n"
        "1,ignored,Alice One,1,200,2026-06-01 10:00,2026-06-01 10:30\n"
        "1,ignored,Bob One,2,190,2026-06-01 10:00,2026-06-01 10:30\n"
        "2,ignored,Carol Two,1,180,2026-06-01 10:00,2026-06-01 10:30\n"
        "2,ignored,Dan Two,2,170,2026-06-01 10:00,2026-06-01 10:30\n"
    )
    commit_import(conn, scores, build_import_report(conn, scores, "men", 1))

    result = swap_positions(conn, "men", 1, "Alice", "Bob")

    assert result[:2] == ("Alice One", "Bob One")
    rows = conn.execute(
        "SELECT bowler_name, play_position, scratch_score FROM bowler_scores "
        "WHERE team_id = (SELECT id FROM teams WHERE team_number = 1) "
        "ORDER BY play_position"
    ).fetchall()
    assert [(row["bowler_name"], row["scratch_score"]) for row in rows] == [
        ("Bob One", 190),
        ("Alice One", 200),
    ]


def test_clear_round_removes_scores_and_points_but_keeps_draw_and_roster(tmp_path):
    conn = db.connect(":memory:")
    db.init_db(conn)
    grid = tmp_path / "grid.csv"
    teams = tmp_path / "teams.csv"
    players = tmp_path / "players.csv"
    scores = tmp_path / "scores.csv"
    grid.write_text("1,2")
    teams.write_text("team_number,team_name,team_size\n1,Team 1,2\n2,Team 2,2\n")
    players.write_text("team_number,player_name\n1,Alice One\n1,Bob One\n2,Carol Two\n2,Dan Two\n")
    import_draw(conn, grid, teams, "men", players)
    scores.write_text(
        "Lane number,Team name,Bowler name,Play position,Scratch,Start date,End date\n"
        "1,ignored,Alice One,1,200,2026-06-01 10:00,2026-06-01 10:30\n"
        "1,ignored,Bob One,2,190,2026-06-01 10:00,2026-06-01 10:30\n"
        "2,ignored,Carol Two,1,180,2026-06-01 10:00,2026-06-01 10:30\n"
        "2,ignored,Dan Two,2,170,2026-06-01 10:00,2026-06-01 10:30\n"
    )
    commit_import(conn, scores, build_import_report(conn, scores, "men", 1))

    assert clear_round(conn, "men", 1) == (4, 2)
    assert conn.execute("SELECT COUNT(*) AS n FROM bowler_scores").fetchone()["n"] == 0
    assert conn.execute("SELECT COUNT(*) AS n FROM match_points").fetchone()["n"] == 0
    assert conn.execute("SELECT COUNT(*) AS n FROM fixtures").fetchone()["n"] == 1
    assert conn.execute("SELECT COUNT(*) AS n FROM players").fetchone()["n"] == 4
