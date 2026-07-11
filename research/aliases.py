"""
research/aliases.py - single source of truth for team-name canonicalization.

Historically four scripts (ingest_odds_history.py, odds_backtest.py,
fetch_odds_live.py, settle_bets.py) each carried their own ALIASES dict + canon()
and they had drifted apart, causing silent join failures (e.g. the live path did
not know "Czechia" / "Bosnia & Herzegovina"). This module is the union of all
four maps plus one shared canon(); every script imports from here.

Direction: odds-source / API team name -> data/results.csv (and
predictions.csv) canonical name.

NOTE: research/build_market_values.py has a SEPARATE ALIASES map that goes the
other direction (Transfermarkt country_of_citizenship -> results.csv name); it is
intentionally NOT merged here.
"""
import unicodedata

# odds-source / API team name (lowercased, NFKD-stripped) -> results.csv name.
# Union of the four scripts' maps; extend as the coverage reports flag gaps.
ALIASES = {
    # DR Congo (OddsPortal writes it "D.R. Congo")
    "d.r. congo": "DR Congo",
    "dr congo": "DR Congo",
    "democratic republic of congo": "DR Congo",
    "congo dr": "DR Congo",
    # Korea
    "korea republic": "South Korea",
    "south korea": "South Korea",
    # Iran
    "ir iran": "Iran",
    "iran": "Iran",
    # United States
    "usa": "United States",
    "united states of america": "United States",
    # Ivory Coast
    "cote d'ivoire": "Ivory Coast",
    "ivory coast": "Ivory Coast",
    # Czech Republic
    "czechia": "Czech Republic",
    # Turkey
    "turkiye": "Turkey",
    # Bosnia and Herzegovina
    "bosnia & herzegovina": "Bosnia and Herzegovina",
    "bosnia-herzegovina": "Bosnia and Herzegovina",
}


def canon(team):
    """Canonicalize a team name to the results.csv spelling.

    Fold curly apostrophes to straight, NFKD-strip to ASCII, then look the name up
    (case-insensitively) in ALIASES. On a miss, return the NFKD-stripped form (NOT
    the raw input) so callers on both sides of a join normalize identically. The
    apostrophe fold matters: a raw "Cote d'Ivoire" written with a curly U+2019 would
    otherwise lose its apostrophe in the ASCII strip and miss the "cote d'ivoire" key.
    """
    team = team.replace("’", "'").replace("‘", "'")
    t = unicodedata.normalize("NFKD", team).encode("ascii", "ignore").decode().strip()
    return ALIASES.get(t.lower(), t)
