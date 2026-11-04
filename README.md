# County Championships 2026 — Bowling Scorer

Local scoring tool for a round-robin ten-pin bowling tournament using Petersen-style points.
Imports the organizer-supplied lane draw, then imports lane-software score exports after each
round, computes standings, and builds a static site for publishing to GitHub Pages.

## Scoring rules

- Round-robin, one game per team pairing.
- Positional 1v1 matchups (bowler vs their opposite number on the other team) are worth 10 bonus
  points each, split 5/5 on a tie.
- The team with the higher total pinfall for the match also gets a team bonus (40 for women's
  4-a-side, 50 for men's 5-a-side), split evenly on a tie.
- A team's match total = sum of bowler scratch scores + individual bonuses won + team bonus.

## Usage

```bash
pip install -e ".[test]"

# One-time: import the draw for each division
counties26 import-draw men_draw.csv men_teams.csv --players men_players.csv --division men --first-lane 1
counties26 import-draw women_draw.csv women_teams.csv --players women_players.csv --division women --first-lane 11

# Add a centre-export abbreviation for a registered player
counties26 add-alias "Laura M" --division women --team-number 15 \
  --player "Laura Morgan"

# After each tournament game is bowled. `--round` is the tournament game/fixture;
# `--game` selects that game within the centre's cumulative export block.
counties26 import scores.csv --round 4 --game 1 --division men \
  --unknown-aliases unknown_players.csv

# If roster matching is unavailable and this game used the opposite lane side
counties26 import scores.csv --round 5 --game 2 --division men --swap-lanes

# After editing unknown_players.csv to fill in player_name values
counties26 add-aliases unknown_players.csv

# Correct one already-imported score after making a database backup
cp counties26.db counties26-before-correction.db
counties26 edit-score --division women --round 2 \
  --player "Gareth Jones" --position 3 --score 214

# Correct a lineup order mistake without moving either player's score
counties26 swap-positions --division women --round 2 \
  --first "Laura Marcham" --second "Laura Ivory"

# Clear one imported round and start that round again
cp counties26.db counties26-before-round-reset.db
counties26 clear-round --division women --round 2

# Anytime
counties26 show-standings --division men
counties26 build-site --output docs
```

## Local Testing

After building the site with `counties26 build-site --output docs`, you can test it locally without publishing:

```bash
# Serve the docs directory on http://localhost:8000
cd docs
python -m http.server

# Or specify a different port
python -m http.server 8080
```

Then open your browser to `http://localhost:8000` (or your chosen port) to view the site. Changes can be previewed by rebuilding the site with `counties26 build-site --output docs` and refreshing your browser.

## Development

Known centre-export names and abbreviations are resolved automatically using the
registered roster and aliases. Matching tries known aliases, a unique first name,
a unique first name plus second-name initial, then a unique surname. Unknown or
ambiguous names are reported and excluded when a team roster exists, rather than
guessed. `--unknown-aliases` writes those names to an editable CSV.

When teams swap the two physical lanes in a match, the importer uses the resolved
player names and the selected draw to assign each score to the correct team; lane
side does not determine team identity. This is evaluated independently for each
fixture. Use `--swap-lanes` only as a forced override when roster matching cannot
resolve the orientation.

```bash
pytest
```
