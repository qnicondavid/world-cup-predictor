package com.david.worldcup.tracker;

import com.david.worldcup.elo.EloRatingSystem;
import com.david.worldcup.goals.EloDrawBaselineModel;
import com.david.worldcup.model.Fixture;
import com.david.worldcup.model.Match;
import com.david.worldcup.sim.TournamentSimulator;
import com.david.worldcup.tracker.PredictionLedger.Prediction;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TrackerTest {

    private static final double EPSILON = 1e-9;
    private static final LocalDate TODAY = LocalDate.of(2026, 6, 12);

    @Test
    void locksOnlyUpcomingWorldCupFixturesNotAlreadyInLedger() {
        List<Fixture> fixtures = List.of(
                new Fixture(TODAY.plusDays(1), "A", "B", "FIFA World Cup", true),
                new Fixture(TODAY.plusDays(2), "C", "D", "FIFA World Cup", true),
                new Fixture(TODAY.minusDays(1), "E", "F", "FIFA World Cup", true), // past
                new Fixture(TODAY.plusDays(1), "G", "H", "Friendly", true));      // not WC

        List<Prediction> ledger = List.of(
                new Prediction(TODAY.plusDays(1), "A", "B", true, 0.5, TODAY)); // already locked

        List<Prediction> added = Tracker.lockNewPredictions(
                new EloDrawBaselineModel(new EloRatingSystem()), fixtures, ledger, TODAY);

        assertEquals(1, added.size());
        assertEquals("C", added.get(0).homeTeam());
        // Every locked prediction carries a normalised three-way split.
        Prediction c = added.get(0);
        assertEquals(1.0, c.pHome() + c.pDraw() + c.pAway(), EPSILON);
    }

    @Test
    void scoresPicksAndMulticlassBrier() {
        List<Prediction> ledger = List.of(
                // pick = home (0.8 is the max); home wins -> correct
                new Prediction(TODAY, "A", "B", true, 0.8, 0.1, 0.1, TODAY.minusDays(1)),
                // pick = away (0.7 is the max); home wins -> incorrect
                new Prediction(TODAY, "C", "D", true, 0.2, 0.1, 0.7, TODAY.minusDays(1)),
                // unplayed -> not scored
                new Prediction(TODAY.plusDays(5), "E", "F", true, 0.6, 0.2, 0.2, TODAY));

        List<Match> results = List.of(
                new Match(TODAY, "A", "B", 2, 0, "FIFA World Cup", true),  // HOME_WIN
                new Match(TODAY, "C", "D", 1, 0, "FIFA World Cup", true)); // HOME_WIN

        List<Tracker.ScoredPrediction> scored = Tracker.score(ledger, results);

        assertEquals(2, scored.size()); // unplayed match not scored
        assertTrue(scored.get(0).correct());
        assertFalse(scored.get(1).correct());
        // multiclass Brier = (pHome-1)^2 + (pDraw-0)^2 + (pAway-0)^2
        assertEquals(0.06, scored.get(0).brier(), EPSILON); // .04 + .01 + .01
        assertEquals(1.14, scored.get(1).brier(), EPSILON); // .64 + .01 + .49
    }

    @Test
    void aDrawCanBeAcorrectPickWhenItIsTheMostLikelyOutcome() {
        List<Prediction> ledger = List.of(
                new Prediction(TODAY, "X", "Y", true, 0.30, 0.40, 0.30, TODAY.minusDays(1)));
        List<Match> results = List.of(
                new Match(TODAY, "X", "Y", 1, 1, "FIFA World Cup", true)); // DRAW

        Tracker.ScoredPrediction s = Tracker.score(ledger, results).get(0);

        assertEquals("Draw", s.prediction().pick());
        assertTrue(s.correct());
        assertEquals(0.54, s.brier(), EPSILON); // .09 + .36 + .09
    }

    @Test
    void rescheduledFixtureResolvesWithinWindowButNotYearsApart() {
        List<Prediction> ledger = List.of(
                // locked for Jul 6; the fixture was moved and the result lands Jul 7
                new Prediction(LocalDate.of(2026, 7, 6), "Argentina", "Egypt", true,
                        0.7051, 0.1917, 0.1032, LocalDate.of(2026, 7, 4)),
                // same pairing but the only result is decades away -> must NOT resolve
                new Prediction(LocalDate.of(2026, 7, 6), "Brazil", "Sweden", true,
                        0.6, 0.2, 0.2, LocalDate.of(2026, 7, 4)));

        List<Match> results = List.of(
                new Match(LocalDate.of(2026, 7, 7), "Argentina", "Egypt", 3, 2, "FIFA World Cup", true),
                new Match(LocalDate.of(1958, 6, 29), "Brazil", "Sweden", 5, 2, "FIFA World Cup", false));

        List<Tracker.ScoredPrediction> scored = Tracker.score(ledger, results);

        assertEquals(1, scored.size()); // the year-apart pairing is not matched
        assertEquals("Argentina", scored.get(0).prediction().homeTeam());
        assertTrue(scored.get(0).correct()); // 3-2 is a home win and the pick was home
        assertEquals(LocalDate.of(2026, 7, 7), scored.get(0).result().date());
    }

    @Test
    void titleOddsTableOmitsEliminatedTeams() {
        List<TournamentSimulator.TeamOdds> odds = List.of(
                new TournamentSimulator.TeamOdds("Argentina", 0.286, 0.509, 0.755),
                new TournamentSimulator.TeamOdds("Switzerland", 0.027, 0.094, 0.245),
                new TournamentSimulator.TeamOdds("Mexico", 0.0, 0.0, 0.0)); // eliminated
        String md = Tracker.renderTitleOdds(odds, 16, TODAY, 10000);
        assertTrue(md.contains("Argentina"));
        assertTrue(md.contains("Switzerland"));
        assertFalse(md.contains("Mexico")); // 0% title -> dropped, matching the site
    }

    @Test
    void replaceSectionSwapsContentBetweenMarkers() {
        String readme = "# Title\n" + Tracker.SECTION_START + "\nold\n"
                + Tracker.SECTION_END + "\nfooter";
        String updated = Tracker.replaceSection(readme, "new content");
        assertTrue(updated.contains("new content"));
        assertFalse(updated.contains("old"));
        assertTrue(updated.contains("footer"));
    }

    @Test
    void replaceSectionAppendsWhenMarkersMissing() {
        String updated = Tracker.replaceSection("# Title", "new content");
        assertTrue(updated.contains(Tracker.SECTION_START));
        assertTrue(updated.contains("new content"));
    }

    @Test
    void ledgerRoundTripsThroughCsv() throws Exception {
        Path tmp = Files.createTempFile("ledger", ".csv");
        // Values already at the 4-decimal precision the CSV stores, so the round trip is exact.
        List<Prediction> original = List.of(
                new Prediction(TODAY, "Brazil", "Morocco", true, 0.5038, 0.2461, 0.2501, TODAY));
        PredictionLedger.save(tmp, original);
        List<Prediction> loaded = PredictionLedger.load(tmp);
        assertEquals(original, loaded);
        assertFalse(loaded.get(0).hasExpectedGoals()); // no goals locked -> blank, reads back NaN
        Files.deleteIfExists(tmp);
    }

    @Test
    void expectedGoalsRoundTripWhenLocked() throws Exception {
        Path tmp = Files.createTempFile("ledger-xg", ".csv");
        List<Prediction> original = List.of(new Prediction(
                TODAY, "Brazil", "Morocco", true, 0.5038, 0.2461, 0.2501, 1.6000, 1.1000, TODAY));
        PredictionLedger.save(tmp, original);
        List<Prediction> loaded = PredictionLedger.load(tmp);
        assertEquals(original, loaded);
        assertTrue(loaded.get(0).hasExpectedGoals());
        assertEquals(1.6000, loaded.get(0).xgHome(), EPSILON);
        Files.deleteIfExists(tmp);
    }

    @Test
    void legacyBinaryRowsExpandToANormalisedSplit() throws Exception {
        Path tmp = Files.createTempFile("legacy", ".csv");
        Files.writeString(tmp,
                "match_date,home_team,away_team,neutral,p_home,locked_on\n"
                        + "2026-06-12,Canada,Bosnia and Herzegovina,false,0.8429,2026-06-12\n");

        List<Prediction> loaded = PredictionLedger.load(tmp);

        assertEquals(1, loaded.size());
        Prediction p = loaded.get(0);
        assertEquals(1.0, p.pHome() + p.pDraw() + p.pAway(), EPSILON);
        // The original Elo expected score is preserved: E = P(win) + P(draw)/2.
        assertEquals(0.8429, p.pHome() + p.pDraw() / 2.0, EPSILON);
        assertEquals("Canada", p.pick());
        Files.deleteIfExists(tmp);
    }

    @Test
    void earlyMatchesRenderRetrospectivelyAndAreCounted() {
        List<Prediction> preds = List.of(new Prediction(
                LocalDate.of(2026, 6, 11), "X", "Y", true,
                0.60, 0.25, 0.15, 1.8, 0.9, LocalDate.of(2026, 6, 11)));
        List<Match> results = List.of(
                new Match(LocalDate.of(2026, 6, 11), "X", "Y", 2, 0, "FIFA World Cup", true));

        String md = Tracker.renderEarlyMatches(Tracker.score(preds, results), TODAY);

        assertTrue(md.contains("retrospective"));
        assertTrue(md.contains("counted in the"));
        assertTrue(md.contains("X vs Y"));
        assertTrue(md.contains("2-0")); // actual result shown
    }

    @Test
    void earlyMatchesTableIsEmptyWhenNoneprecedeTheModel() {
        assertTrue(Tracker.renderEarlyMatches(List.of(), TODAY)
                .contains("No World Cup matches were played before"));
    }
}
