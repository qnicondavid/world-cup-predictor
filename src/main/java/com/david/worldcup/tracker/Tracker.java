package com.david.worldcup.tracker;

import com.david.worldcup.elo.DrawModel;
import com.david.worldcup.goals.Calibration;
import com.david.worldcup.goals.FormAdjuster;
import com.david.worldcup.goals.GoalModel;
import com.david.worldcup.goals.ScorePredictor;
import com.david.worldcup.model.Fixture;
import com.david.worldcup.model.Match;
import com.david.worldcup.sim.TournamentSimulator;
import com.david.worldcup.tracker.PredictionLedger.Prediction;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/**
 * The live 2026 tracker: locks predictions for upcoming World Cup fixtures and
 * scores previously locked predictions against completed results.
 *
 * <p>Predictions are locked and scored three-way (win/draw/loss) using the
 * {@link DrawModel}. A "hit" means the model's single most likely outcome
 * matched the actual result; the Brier score is the multiclass Brier over the
 * three outcomes (0 = perfect, 2 = worst; a uniform 1/3-1/3-1/3 guess = 0.667).
 */
public final class Tracker {

    public static final String SECTION_START = "<!-- TRACKER:START -->";
    public static final String SECTION_END = "<!-- TRACKER:END -->";
    public static final String TITLE_SECTION_START = "<!-- TITLE:START -->";
    public static final String TITLE_SECTION_END = "<!-- TITLE:END -->";
    public static final String EARLY_SECTION_START = "<!-- EARLY:START -->";
    public static final String EARLY_SECTION_END = "<!-- EARLY:END -->";

    private static final String RESOLVED_HEADER =
            "| Date | Match | Winner | H/D/A % | Score (xG) | Result | Δ | Hit |\n"
                    + "|---|---|---|---|---|---|---|---|\n";

    private static final DateTimeFormatter DAY =
            DateTimeFormatter.ofPattern("MMM d", Locale.ENGLISH);

    /** How many days a fixture may shift after locking and still resolve to its result. */
    private static final long RESCHEDULE_WINDOW_DAYS = 3;

    public record ScoredPrediction(Prediction prediction, Match result,
                                   boolean correct, double brier) {}

    /**
     * Predictions for World Cup fixtures on/after {@code today} that are not in the ledger yet,
     * locked with the supplied {@link GoalModel} (Dixon-Coles in production).
     */
    public static List<Prediction> lockNewPredictions(GoalModel model,
                                                      List<Fixture> fixtures,
                                                      List<Prediction> ledger,
                                                      LocalDate today) {
        return lockNewPredictions(model, fixtures, ledger, today, null);
    }

    /**
     * As above, but nudges each locked prediction by recent defensive form when a
     * {@link FormAdjuster} is supplied (null leaves the model output unchanged).
     */
    public static List<Prediction> lockNewPredictions(GoalModel model,
                                                      List<Fixture> fixtures,
                                                      List<Prediction> ledger,
                                                      LocalDate today,
                                                      FormAdjuster form) {
        Set<String> alreadyLocked = new HashSet<>();
        for (Prediction p : ledger) {
            alreadyLocked.add(key(p.matchDate(), p.homeTeam(), p.awayTeam()));
        }

        return fixtures.stream()
                .filter(Fixture::isWorldCupFinals)
                .filter(fx -> !fx.date().isBefore(today))
                .filter(fx -> !alreadyLocked.contains(key(fx.date(), fx.homeTeam(), fx.awayTeam())))
                .map(fx -> {
                    DrawModel.Probabilities p = model.probabilities(
                            fx.homeTeam(), fx.awayTeam(), fx.neutralVenue());
                    if (form != null) {
                        p = form.adjust(fx.homeTeam(), fx.awayTeam(), fx.date(), p);
                        p = Calibration.transferDraw(p);
                    }
                    Optional<GoalModel.GoalRates> g = model.expectedGoals(
                            fx.homeTeam(), fx.awayTeam(), fx.neutralVenue());
                    double xgHome = g.map(GoalModel.GoalRates::home).orElse(Double.NaN);
                    double xgAway = g.map(GoalModel.GoalRates::away).orElse(Double.NaN);
                    return new Prediction(fx.date(), fx.homeTeam(), fx.awayTeam(),
                            fx.neutralVenue(), p.homeWin(), p.draw(), p.awayWin(),
                            xgHome, xgAway, today);
                })
                .sorted(Comparator.comparing(Prediction::matchDate))
                .toList();
    }

    /** Matches each ledger entry against completed results; unplayed entries are omitted. */
    public static List<ScoredPrediction> score(List<Prediction> ledger, List<Match> completed) {
        Map<String, Match> results = new HashMap<>();
        Map<String, List<Match>> byTeams = new HashMap<>();
        for (Match m : completed) {
            results.putIfAbsent(key(m.date(), m.homeTeam(), m.awayTeam()), m);
            byTeams.computeIfAbsent(teamKey(m.homeTeam(), m.awayTeam()),
                    k -> new ArrayList<>()).add(m);
        }

        List<ScoredPrediction> scored = new ArrayList<>();
        for (Prediction p : ledger) {
            Match result = results.get(key(p.matchDate(), p.homeTeam(), p.awayTeam()));
            if (result == null) {
                result = rescheduledResult(p, byTeams);
            }
            if (result == null) {
                continue;
            }
            Match.Outcome actual = result.outcome();
            scored.add(new ScoredPrediction(p, result,
                    p.predictedOutcome() == actual,
                    multiclassBrier(p, actual)));
        }
        return scored;
    }

    /**
     * Fallback for a fixture whose date changed after the prediction was locked: the same
     * fixture (same teams and home/away order) whose result date is within
     * {@link #RESCHEDULE_WINDOW_DAYS} of the locked date, closest date first. The tight
     * window stops it from matching the same pairing in a different tournament years apart.
     */
    private static Match rescheduledResult(Prediction p, Map<String, List<Match>> byTeams) {
        return byTeams.getOrDefault(teamKey(p.homeTeam(), p.awayTeam()), List.of()).stream()
                .filter(m -> Math.abs(ChronoUnit.DAYS.between(p.matchDate(), m.date()))
                        <= RESCHEDULE_WINDOW_DAYS)
                .min(Comparator.comparingLong(
                        m -> Math.abs(ChronoUnit.DAYS.between(p.matchDate(), m.date()))))
                .orElse(null);
    }

    /**
     * Multiclass Brier score for one prediction: the squared error summed over
     * the win, draw and loss probabilities against the one-hot actual outcome.
     */
    static double multiclassBrier(Prediction p, Match.Outcome actual) {
        return sq(p.pHome() - indicator(actual, Match.Outcome.HOME_WIN))
                + sq(p.pDraw() - indicator(actual, Match.Outcome.DRAW))
                + sq(p.pAway() - indicator(actual, Match.Outcome.AWAY_WIN));
    }

    private static double indicator(Match.Outcome actual, Match.Outcome target) {
        return actual == target ? 1.0 : 0.0;
    }

    private static double sq(double x) {
        return x * x;
    }

    /** Renders the README tracker section as Markdown. */
    public static String renderMarkdown(List<ScoredPrediction> scored,
                                        List<Prediction> pending,
                                        LocalDate today) {
        StringBuilder md = new StringBuilder();
        md.append("Δ is the total goal difference from the actual result ")
          .append("(🎯 = exact), and Brier is multiclass.\n\n");

        if (scored.isEmpty()) {
            md.append("**No locked predictions have been resolved yet.**\n");
        } else {
            long correct = scored.stream().filter(ScoredPrediction::correct).count();
            double brier = scored.stream().mapToDouble(ScoredPrediction::brier).average().orElse(0);
            double meanGoalError = scored.stream()
                    .mapToInt(s -> predictedScore(s.prediction())
                            .goalError(s.result().homeScore(), s.result().awayScore()))
                    .average().orElse(0);
            md.append(String.format(Locale.ROOT,
                    "**Record: %d/%d picks correct (%.1f%%), multiclass Brier %.3f, "
                            + "mean goal error %.1f** (uniform guess = 0.667)%n%n",
                    correct, scored.size(), 100.0 * correct / scored.size(), brier, meanGoalError));

            md.append(RESOLVED_HEADER);
            scored.stream()
                    .sorted(Comparator.comparing(
                            (ScoredPrediction s) -> s.prediction().matchDate()).reversed())
                    .forEach(s -> appendResolvedRow(md, s));
        }

        if (!pending.isEmpty()) {
            md.append("\n**Locked for upcoming matches:**\n\n");
            md.append("| Date | Match | Winner | H/D/A % | Score (xG) |\n");
            md.append("|---|---|---|---|---|\n");
            pending.stream()
                    .sorted(Comparator.comparing(Prediction::matchDate))
                    .forEach(p -> md.append(String.format(Locale.ROOT,
                            "| %s | %s vs %s | %s | %s | %s |%n",
                            DAY.format(p.matchDate()), p.homeTeam(), p.awayTeam(),
                            p.pick(), splitLabel(p), scoreLabel(predictedScore(p)))));
        }
        return md.toString();
    }

    /** One row of the resolved/retrospective table (shared so both render identically). */
    private static void appendResolvedRow(StringBuilder md, ScoredPrediction s) {
        Prediction p = s.prediction();
        Match r = s.result();
        ScorePredictor.PredictedScore ps = predictedScore(p);
        int err = ps.goalError(r.homeScore(), r.awayScore());
        String delta = err + (ps.exact(r.homeScore(), r.awayScore()) ? " 🎯" : "");
        md.append(String.format(Locale.ROOT,
                "| %s | %s vs %s | %s | %s | %s | %d-%d | %s | %s |%n",
                DAY.format(p.matchDate()), p.homeTeam(), p.awayTeam(),
                p.pick(), splitLabel(p), scoreLabel(ps),
                r.homeScore(), r.awayScore(),
                delta, s.correct() ? "✅" : "❌"));
    }

    /**
     * Renders matches played before the model existed, in the same format as the
     * locked table. These are retrospective: each is trained only on data from
     * before the match, but was not locked ahead of kickoff the way live
     * predictions are. Main.runTracker merges them into the scored record, so they
     * do count toward it. This standalone section renderer is currently unused.
     */
    public static String renderEarlyMatches(List<ScoredPrediction> early, LocalDate today) {
        StringBuilder md = new StringBuilder();
        if (early.isEmpty()) {
            md.append("No World Cup matches were played before the model was created.\n");
            return md.toString();
        }
        md.append("These matches were played before the model existed, so they were never ")
          .append("locked. Each is a retrospective prediction, trained only on data from ")
          .append("before the match (never peeking at the result), and is counted in the ")
          .append("record above. Shown for a complete tournament picture.\n\n");
        md.append(RESOLVED_HEADER);
        for (ScoredPrediction s : early) {
            appendResolvedRow(md, s);
        }
        return md.toString();
    }

    /** Compact "73/18/9%" home-win / draw / away-win label. */
    private static String splitLabel(Prediction p) {
        return String.format(Locale.ROOT, "%.0f/%.0f/%.0f%%",
                100 * p.pHome(), 100 * p.pDraw(), 100 * p.pAway());
    }

    /**
     * Predicted scoreline. Uses the goal model's locked expected goals when present;
     * otherwise falls back to the Elo-gap mapping implied by the win/draw/loss split.
     */
    private static ScorePredictor.PredictedScore predictedScore(Prediction p) {
        if (p.hasExpectedGoals()) {
            return ScorePredictor.fromExpectedGoals(p.xgHome(), p.xgAway());
        }
        return ScorePredictor.fromExpectedScore(p.pHome() + p.pDraw() / 2.0);
    }

    /** "2-1 (1.9–0.8)" — most likely scoreline with expected goals in brackets. */
    private static String scoreLabel(ScorePredictor.PredictedScore ps) {
        return String.format(Locale.ROOT, "%d-%d (%.1f–%.1f)",
                ps.modalHome(), ps.modalAway(), ps.homeGoals(), ps.awayGoals());
    }

    /**
     * Renders the live championship-odds table from the Monte Carlo simulator.
     *
     * @param topN number of teams to list, best title odds first
     * @param runs number of simulations behind the odds (for the caption)
     */
    public static String renderTitleOdds(List<TournamentSimulator.TeamOdds> odds,
                                         int topN, LocalDate today, int runs) {
        StringBuilder md = new StringBuilder();
        md.append(String.format(Locale.ROOT,
                "The model's championship odds from %,d Monte Carlo simulations, updated %s. "
                        + "They inherit the simulator's simplifications (knockout bracket paired "
                        + "in schedule order, games as neutral with no draws), so read them as "
                        + "the model's view, not a hard forecast.%n%n", runs, today));
        md.append("| # | Team | Title | Final | Semis |\n");
        md.append("|---|---|---|---|---|\n");
        // Only teams still able to win: drop eliminated sides (0% title odds), matching the site.
        List<TournamentSimulator.TeamOdds> alive = odds.stream()
                .filter(o -> o.titleShare() > 0).toList();
        int n = Math.min(topN, alive.size());
        for (int i = 0; i < n; i++) {
            TournamentSimulator.TeamOdds o = alive.get(i);
            md.append(String.format(Locale.ROOT, "| %d | %s | %.1f%% | %.1f%% | %.1f%% |%n",
                    i + 1, o.team(),
                    100 * o.titleShare(), 100 * o.finalShare(), 100 * o.semiShare()));
        }
        return md.toString();
    }

    /**
     * Serialises the tracker state to JSON for the static demo page: the record,
     * resolved matches, upcoming predictions and the top championship odds.
     */
    public static String renderJson(List<ScoredPrediction> scored, List<Prediction> pending,
                                    List<TournamentSimulator.TeamOdds> titleOdds, int topN,
                                    LocalDate today) {
        long correct = scored.stream().filter(ScoredPrediction::correct).count();
        double brier = scored.stream().mapToDouble(ScoredPrediction::brier).average().orElse(0);

        StringBuilder j = new StringBuilder();
        j.append("{\n");
        j.append("  \"updated\": \"").append(today).append("\",\n");
        j.append("  \"model\": \"Dixon-Coles + market-value prior\",\n");
        j.append("  \"record\": {\"correct\": ").append(correct)
         .append(", \"evaluated\": ").append(scored.size())
         .append(", \"brier\": ").append(num(brier)).append("},\n");

        j.append("  \"resolved\": [");
        for (int i = 0; i < scored.size(); i++) {
            ScoredPrediction s = scored.get(i);
            Prediction p = s.prediction();
            Match r = s.result();
            ScorePredictor.PredictedScore ps = predictedScore(p);
            j.append(i == 0 ? "\n    " : ",\n    ").append("{")
             .append("\"date\": \"").append(DAY.format(p.matchDate())).append("\", ")
             .append("\"home\": ").append(str(p.homeTeam())).append(", ")
             .append("\"away\": ").append(str(p.awayTeam())).append(", ")
             .append("\"pick\": ").append(str(p.pick())).append(", ")
             .append("\"pHome\": ").append(num(p.pHome())).append(", ")
             .append("\"pDraw\": ").append(num(p.pDraw())).append(", ")
             .append("\"pAway\": ").append(num(p.pAway())).append(", ")
             .append("\"predScore\": \"").append(ps.modalHome()).append("-").append(ps.modalAway())
             .append("\", \"result\": \"").append(r.homeScore()).append("-").append(r.awayScore())
             .append("\", \"hit\": ").append(s.correct()).append("}");
        }
        j.append(scored.isEmpty() ? "],\n" : "\n  ],\n");

        List<Prediction> upcoming = pending.stream()
                .sorted(Comparator.comparing(Prediction::matchDate)).limit(12).toList();
        j.append("  \"upcoming\": [");
        for (int i = 0; i < upcoming.size(); i++) {
            Prediction p = upcoming.get(i);
            ScorePredictor.PredictedScore ps = predictedScore(p);
            j.append(i == 0 ? "\n    " : ",\n    ").append("{")
             .append("\"date\": \"").append(DAY.format(p.matchDate())).append("\", ")
             .append("\"home\": ").append(str(p.homeTeam())).append(", ")
             .append("\"away\": ").append(str(p.awayTeam())).append(", ")
             .append("\"pick\": ").append(str(p.pick())).append(", ")
             .append("\"pHome\": ").append(num(p.pHome())).append(", ")
             .append("\"pDraw\": ").append(num(p.pDraw())).append(", ")
             .append("\"pAway\": ").append(num(p.pAway())).append(", ")
             .append("\"predScore\": \"").append(ps.modalHome()).append("-").append(ps.modalAway())
             .append("\"}");
        }
        j.append(upcoming.isEmpty() ? "],\n" : "\n  ],\n");

        int n = Math.min(topN, titleOdds.size());
        j.append("  \"titleOdds\": [");
        for (int i = 0; i < n; i++) {
            TournamentSimulator.TeamOdds o = titleOdds.get(i);
            j.append(i == 0 ? "\n    " : ",\n    ").append("{")
             .append("\"team\": ").append(str(o.team())).append(", ")
             .append("\"title\": ").append(num(100 * o.titleShare())).append(", ")
             .append("\"final\": ").append(num(100 * o.finalShare())).append(", ")
             .append("\"semis\": ").append(num(100 * o.semiShare())).append("}");
        }
        j.append(n == 0 ? "]\n}" : "\n  ]\n}");
        return j.toString();
    }

    private static String num(double v) {
        return String.format(Locale.ROOT, "%.4f", v);
    }

    private static String str(String s) {
        StringBuilder b = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '"' || c == '\\') {
                b.append('\\').append(c);
            } else if (c == '\n') {
                b.append("\\n");
            } else {
                b.append(c);
            }
        }
        return b.append('"').toString();
    }

    /** Replaces the content between the tracker markers; appends a section if absent. */
    public static String replaceSection(String readme, String newSection) {
        return replaceSection(readme, SECTION_START, SECTION_END, newSection);
    }

    /** Replaces the content between the given markers; appends a section if absent. */
    public static String replaceSection(String readme, String startMarker, String endMarker,
                                        String newSection) {
        int start = readme.indexOf(startMarker);
        int end = readme.indexOf(endMarker);
        if (start < 0 || end < 0 || end < start) {
            return readme + "\n" + startMarker + "\n" + newSection + "\n" + endMarker + "\n";
        }
        return readme.substring(0, start + startMarker.length())
                + "\n" + newSection + "\n"
                + readme.substring(end);
    }

    private static String key(LocalDate date, String home, String away) {
        return date + "|" + home + "|" + away;
    }

    private static String teamKey(String home, String away) {
        return home + "|" + away;
    }

    private Tracker() {
    }
}
