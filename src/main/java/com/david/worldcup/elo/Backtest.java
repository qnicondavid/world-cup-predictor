package com.david.worldcup.elo;

import com.david.worldcup.model.Match;

import java.time.LocalDate;
import java.util.Locale;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * Evaluates the Elo model on historical World Cups it has never "seen".
 *
 * <p>How it works: replay all matches in date order. Matches before
 * {@code evaluateFrom} are pure training. Inside the evaluation window
 * [{@code evaluateFrom}, {@code evaluateUntil}], every World Cup finals match
 * is <em>predicted first, then learned from</em> — the same information regime
 * the model would have faced in real time. Non-finals matches inside the window
 * (friendlies, other competitions) are still learned from but never scored.
 *
 * <p>Scoring:
 * <ul>
 *   <li><b>Accuracy</b> — the model's favorite is whichever side has expected
 *       score &ge; 0.5. A draw counts as a miss (the model never predicts draws —
 *       see the draw-modelling TODO in {@link EloRatingSystem}).</li>
 *   <li><b>Brier score</b> — mean of {@code (predicted − actual)²} with actual
 *       1 / 0.5 / 0. Punishes overconfidence; 0.25 is coin-flip level.</li>
 * </ul>
 */
public final class Backtest {

    /** A named evaluation window (one World Cup). */
    public record Window(String label, LocalDate from, LocalDate until) {}

    /** The five most recent completed World Cups. */
    public static final List<Window> WORLD_CUPS = List.of(
            new Window("World Cup 2006", LocalDate.of(2006, 6, 1), LocalDate.of(2006, 7, 31)),
            new Window("World Cup 2010", LocalDate.of(2010, 6, 1), LocalDate.of(2010, 7, 31)),
            new Window("World Cup 2014", LocalDate.of(2014, 6, 1), LocalDate.of(2014, 7, 31)),
            new Window("World Cup 2018", LocalDate.of(2018, 6, 1), LocalDate.of(2018, 7, 31)),
            new Window("World Cup 2022", LocalDate.of(2022, 11, 1), LocalDate.of(2022, 12, 31)));

    /** Windows used for tuning; 2022 is reserved for held-out validation. */
    public static final List<Window> TUNING_WINDOWS = WORLD_CUPS.subList(0, 4);

    /**
     * Tournaments that count as continental finals for the Phase 1 expanded validation surface:
     * the top-tier continental championships plus the inter-confederation Confederations Cup.
     * Sub-regional cups (AFF, EAFF, WAFF, CAFA) and non-FIFA events are deliberately excluded,
     * because they are lower-stakes and do not resemble World Cup conditions.
     */
    public static final java.util.Set<String> CONTINENTAL_FINALS = java.util.Set.of(
            "UEFA Euro", "Copa América", "African Cup of Nations", "AFC Asian Cup",
            "Gold Cup", "Oceania Nations Cup", "Confederations Cup");

    /** One continental-final edition: a tournament in a single year, with its date span. */
    public record TournamentWindow(String tournament, int year, Window window, int matchCount) {}

    /**
     * Build one window per continental-final edition since {@code sinceYear}, straight from the
     * match data. An edition is a {@link #CONTINENTAL_FINALS} tournament in a single calendar year;
     * its window spans that edition's matches (earliest to latest date). Ordered by start date.
     */
    public static List<TournamentWindow> continentalFinalWindows(List<Match> all, int sinceYear) {
        java.util.Map<String, List<Match>> byTournament = new java.util.HashMap<>();
        for (Match m : all) {
            if (CONTINENTAL_FINALS.contains(m.tournament())) {
                byTournament.computeIfAbsent(m.tournament(), k -> new ArrayList<>()).add(m);
            }
        }
        List<TournamentWindow> out = new ArrayList<>();
        for (java.util.Map.Entry<String, List<Match>> entry : byTournament.entrySet()) {
            String tournament = entry.getKey();
            List<Match> ms = entry.getValue();
            ms.sort(Comparator.comparing(Match::date));
            // Cluster into editions: consecutive matches within 180 days belong to the same edition.
            // 180 sits between the largest genuine within-edition gap (an Oceania Nations Cup spread
            // over months, about 125 days) and the smallest gap between distinct editions (back-to-back
            // Copa America 2015 and 2016, about 334 days), so a Dec-Jan edition or a spread-out one stays
            // a single window while two real editions never merge.
            int i = 0;
            while (i < ms.size()) {
                LocalDate from = ms.get(i).date();
                LocalDate until = from;
                int matchCount = 1;
                int j = i + 1;
                while (j < ms.size() && !ms.get(j).date().isAfter(until.plusDays(180))) {
                    until = ms.get(j).date();
                    matchCount++;
                    j++;
                }
                int year = from.getYear();
                if (year >= sinceYear) {
                    Window w = new Window(tournament + " " + year, from, until);
                    out.add(new TournamentWindow(tournament, year, w, matchCount));
                }
                i = j;
            }
        }
        out.sort(Comparator.comparing(tw -> tw.window().from()));
        return out;
    }

    /** Pools several windows into one match-weighted result. */
    public BacktestResult runCombined(List<Match> matches, List<Window> windows,
                                      EloConfig config) {
        int evaluated = 0;
        int correct = 0;
        double brierSum = 0.0;
        for (Window w : windows) {
            BacktestResult r = run(matches, w.from(), w.until(), config);
            evaluated += r.matchesEvaluated();
            correct += r.correctPredictions();
            brierSum += r.brierScore() * r.matchesEvaluated();
        }
        return new BacktestResult(evaluated, correct,
                evaluated == 0 ? 0.0 : (double) correct / evaluated,
                evaluated == 0 ? 0.0 : brierSum / evaluated);
    }

    public BacktestResult run(List<Match> matches, LocalDate evaluateFrom, LocalDate evaluateUntil) {
        return run(matches, evaluateFrom, evaluateUntil, EloConfig.DEFAULT);
    }

    public BacktestResult run(List<Match> matches, LocalDate evaluateFrom,
                              LocalDate evaluateUntil, EloConfig config) {
        List<Match> ordered = new ArrayList<>(matches);
        ordered.sort(Comparator.comparing(Match::date));

        EloRatingSystem elo = new EloRatingSystem(config);
        int evaluated = 0;
        int correct = 0;
        double brierSum = 0.0;

        for (Match match : ordered) {
            if (match.date().isAfter(evaluateUntil)) {
                break; // sorted, so nothing after this matters
            }
            if (isEvaluated(match, evaluateFrom)) {
                double predicted = elo.winProbability(
                        match.homeTeam(), match.awayTeam(), match.neutralVenue());

                double actual = switch (match.outcome()) {
                    case HOME_WIN -> 1.0;
                    case DRAW -> 0.5;
                    case AWAY_WIN -> 0.0;
                };
                brierSum += (predicted - actual) * (predicted - actual);

                Match.Outcome favored = predicted >= 0.5
                        ? Match.Outcome.HOME_WIN
                        : Match.Outcome.AWAY_WIN;
                if (match.outcome() == favored) {
                    correct++;
                }
                evaluated++;
            }
            // Predict BEFORE learning: only now does the model see the result.
            elo.processMatch(match);
        }

        return new BacktestResult(
                evaluated,
                correct,
                evaluated == 0 ? 0.0 : (double) correct / evaluated,
                evaluated == 0 ? 0.0 : brierSum / evaluated);
    }

    /**
     * Result of a three-way (win/draw/loss) backtest using the draw model.
     *
     * @param multiclassBrier mean of sum((p_i - actual_i)^2) over the three
     *                        outcomes; 0.667 = always predicting uniform thirds
     */
    public record ThreeWayResult(
            int matchesEvaluated,
            int correct,
            double accuracy,
            double multiclassBrier,
            int drawsPredicted,
            int actualDraws) {

        public String summary() {
            return String.format(Locale.ROOT,
                    "%d/%d correct (%.1f%%), multiclass Brier %.4f "
                            + "(predicted %d draws; %d actually occurred)",
                    correct, matchesEvaluated, accuracy * 100, multiclassBrier,
                    drawsPredicted, actualDraws);
        }
    }

    /**
     * Like {@link #run}, but predicts one of three outcomes (home/draw/away)
     * via the draw model and scores with the multi-class Brier score.
     */
    public ThreeWayResult runThreeWay(List<Match> matches, LocalDate evaluateFrom,
                                      LocalDate evaluateUntil, EloConfig config) {
        List<Match> ordered = new ArrayList<>(matches);
        ordered.sort(Comparator.comparing(Match::date));

        EloRatingSystem elo = new EloRatingSystem(config);
        int evaluated = 0;
        int correct = 0;
        int drawsPredicted = 0;
        int actualDraws = 0;
        double brierSum = 0.0;

        for (Match match : ordered) {
            if (match.date().isAfter(evaluateUntil)) {
                break;
            }
            if (isEvaluated(match, evaluateFrom)) {
                DrawModel.Probabilities p = elo.outcomeProbabilities(
                        match.homeTeam(), match.awayTeam(), match.neutralVenue());
                double[] probs = {p.homeWin(), p.draw(), p.awayWin()};

                int actual = switch (match.outcome()) {
                    case HOME_WIN -> 0;
                    case DRAW -> 1;
                    case AWAY_WIN -> 2;
                };
                for (int i = 0; i < 3; i++) {
                    double target = i == actual ? 1.0 : 0.0;
                    brierSum += (probs[i] - target) * (probs[i] - target);
                }

                int predicted = 0;
                if (probs[1] > probs[predicted]) predicted = 1;
                if (probs[2] > probs[predicted]) predicted = 2;

                if (predicted == actual) correct++;
                if (predicted == 1) drawsPredicted++;
                if (actual == 1) actualDraws++;
                evaluated++;
            }
            elo.processMatch(match);
        }

        return new ThreeWayResult(
                evaluated,
                correct,
                evaluated == 0 ? 0.0 : (double) correct / evaluated,
                evaluated == 0 ? 0.0 : brierSum / evaluated,
                drawsPredicted,
                actualDraws);
    }

    private static boolean isEvaluated(Match match, LocalDate evaluateFrom) {
        return match.isWorldCupFinals() && !match.date().isBefore(evaluateFrom);
    }
}
