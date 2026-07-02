package com.david.worldcup.goals;

import com.david.worldcup.elo.Backtest;
import com.david.worldcup.elo.DrawModel;
import com.david.worldcup.model.Match;
import com.david.worldcup.value.MarketValueTable;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Grid-searches {@link ValueWeights} for the market-value prior.
 *
 * <p>Crucially, the Dixon-Coles fit does not depend on the weights — only the
 * post-fit {@link ValueAdjuster} does — so each window's base ratings are fit
 * once and every candidate weighting is applied to that cached fit. That makes a
 * large grid cheap (a handful of fits total, not one per candidate).
 *
 * <p>Tune on a set of windows, then validate the winner once on a held-out
 * window, exactly like the Elo {@code Tuner}. The weighting {@code (0, 0, *)}
 * reproduces plain Dixon-Coles, so it serves as the baseline inside the grid.
 */
public final class ValueTuner {

    public record Scored(ValueWeights weights, int evaluated, int correct, double brier) {
        public String summary() {
            return String.format(Locale.ROOT,
                    "global %.2f sparse %.2f scale %.2f | %d/%d correct, Brier %.4f",
                    weights.globalWeight(), weights.sparseWeight(), weights.valueScale(),
                    correct, evaluated, brier);
        }
    }

    /** Per-window cache: base ratings, match counts and the matches to score. */
    public record Prepared(TeamStrength base, Map<String, Integer> counts,
                           LocalDate asof, List<Match> test) {}

    private final int trainingYears;
    private final MarketValueTable values;
    // Match-importance tier weights forwarded to the internal PoissonRatingsFitter.
    // Both default to 1.0 so every existing caller keeps the decay-only fit unchanged;
    // only an explicit opt-in path passes non-default values.
    private final double wFriendly;
    private final double wFinals;

    public ValueTuner(int trainingYears, MarketValueTable values) {
        this(trainingYears, values, 1.0, 1.0);
    }

    public ValueTuner(int trainingYears, MarketValueTable values,
                      double wFriendly, double wFinals) {
        this.trainingYears = trainingYears;
        this.values = values;
        this.wFriendly = wFriendly;
        this.wFinals = wFinals;
    }

    /**
     * Grid over {@link ValueWeights}; (0,0,*) is the plain Dixon-Coles baseline.
     * Widened toward stronger value weights (global up to 0.8, scale up to 0.6):
     * held-out testing on the production export showed the value prior is
     * under-exploited, and the previous optimum sat at the grid's scale edge.
     */
    public static List<ValueWeights> defaultGrid() {
        List<ValueWeights> grid = new ArrayList<>();
        for (double global : new double[] {0.0, 0.1, 0.2, 0.4, 0.6, 0.8}) {
            for (double sparse : new double[] {0.0, 0.3, 0.6, 1.0}) {
                for (double scale : new double[] {0.1, 0.2, 0.3, 0.4, 0.5, 0.6}) {
                    grid.add(new ValueWeights(global, sparse, 5.0, scale));
                }
            }
        }
        return grid;
    }

    public Prepared prepare(List<Match> all, Backtest.Window window) {
        LocalDate start = window.from();
        LocalDate trainStart = start.minusYears(trainingYears);
        List<Match> training = all.stream()
                .filter(m -> m.date().isBefore(start) && !m.date().isBefore(trainStart))
                .sorted(Comparator.comparing(Match::date))
                .toList();
        TeamStrength base = new PoissonRatingsFitter()
                .wFriendly(wFriendly)
                .wFinals(wFinals)
                .fit(training, start);
        Map<String, Integer> counts = new HashMap<>();
        for (Match m : training) {
            counts.merge(m.homeTeam(), 1, Integer::sum);
            counts.merge(m.awayTeam(), 1, Integer::sum);
        }
        List<Match> test = all.stream()
                .filter(Match::isWorldCupFinals)
                .filter(m -> !m.date().isBefore(start) && !m.date().isAfter(window.until()))
                .toList();
        return new Prepared(base, counts, start, test);
    }

    public List<Prepared> prepareAll(List<Match> all, List<Backtest.Window> windows) {
        List<Prepared> prepared = new ArrayList<>();
        for (Backtest.Window w : windows) {
            prepared.add(prepare(all, w));
        }
        return prepared;
    }

    /** Scores one weighting across the prepared windows (pooled, match-weighted). */
    public Scored score(List<Prepared> windows, ValueWeights weights) {
        int evaluated = 0;
        int correct = 0;
        double brierSum = 0.0;
        for (Prepared p : windows) {
            TeamStrength adjusted = ValueAdjuster.adjust(p.base(), p.counts(), values, p.asof(), weights);
            DixonColesModel model = new DixonColesModel(adjusted);
            for (Match m : p.test()) {
                DrawModel.Probabilities pr =
                        model.probabilities(m.homeTeam(), m.awayTeam(), m.neutralVenue());
                double[] probs = {pr.homeWin(), pr.draw(), pr.awayWin()};
                int actual = switch (m.outcome()) {
                    case HOME_WIN -> 0;
                    case DRAW -> 1;
                    case AWAY_WIN -> 2;
                };
                for (int i = 0; i < 3; i++) {
                    double target = i == actual ? 1.0 : 0.0;
                    brierSum += (probs[i] - target) * (probs[i] - target);
                }
                int pick = 0;
                if (probs[1] > probs[pick]) {
                    pick = 1;
                }
                if (probs[2] > probs[pick]) {
                    pick = 2;
                }
                if (pick == actual) {
                    correct++;
                }
                evaluated++;
            }
        }
        return new Scored(weights, evaluated, correct,
                evaluated == 0 ? 0.0 : brierSum / evaluated);
    }

    /** Ranks the grid on the tuning windows, best (lowest Brier) first. */
    public List<Scored> search(List<Match> all, List<Backtest.Window> tuningWindows) {
        List<Prepared> prepared = prepareAll(all, tuningWindows);
        List<Scored> results = new ArrayList<>();
        for (ValueWeights w : defaultGrid()) {
            results.add(score(prepared, w));
        }
        results.sort(Comparator.comparingDouble(Scored::brier));
        return results;
    }
}
