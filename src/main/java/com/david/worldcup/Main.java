package com.david.worldcup;

import com.david.worldcup.data.MatchCsvParser;
import com.david.worldcup.elo.Backtest;
import com.david.worldcup.elo.BacktestResult;
import com.david.worldcup.elo.EloConfig;
import com.david.worldcup.elo.EloRatingSystem;
import com.david.worldcup.elo.Tuner;
import com.david.worldcup.elo.DrawModel;
import com.david.worldcup.goals.BivariatePoissonModel;
import com.david.worldcup.goals.Calibration;
import com.david.worldcup.goals.DixonColesModel;
import com.david.worldcup.goals.ValueAdjuster;
import com.david.worldcup.goals.FormAdjuster;
import com.david.worldcup.goals.EloDrawBaselineModel;
import com.david.worldcup.goals.EloPoissonModel;
import com.david.worldcup.goals.EnsembleModel;
import com.david.worldcup.goals.GoalModel;
import com.david.worldcup.goals.GoalModelBacktest;
import com.david.worldcup.goals.ValueTuner;
import com.david.worldcup.goals.ValueWeights;
import com.david.worldcup.betting.BettingConfig;
import com.david.worldcup.betting.Odds;
import com.david.worldcup.betting.OddsTable;
import com.david.worldcup.betting.ValueBet;
import com.david.worldcup.betting.ValueBetting;
import com.david.worldcup.model.Fixture;
import com.david.worldcup.model.Match;
import com.david.worldcup.rest.RestBacktest;
import com.david.worldcup.sim.TournamentSimulator;
import com.david.worldcup.value.MarketValueTable;
import com.david.worldcup.tracker.PredictionLedger;
import com.david.worldcup.tracker.Tracker;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.io.PrintWriter;
import java.io.FileWriter;

/**
 * CLI entry point.
 *
 * <ul>
 *   <li>{@code mvn compile exec:java} — replay history, print Elo top 15 + 2026 predictions</li>
 *   <li>{@code -Dexec.args="--backtest"} — evaluate on 2018/2022, baseline vs margin scaling</li>
 *   <li>{@code -Dexec.args="--tune"} — hyperparameter grid search (tuned 2018, validated 2022)</li>
 *   <li>{@code -Dexec.args="--track"} — live tracker: lock predictions for upcoming World Cup
 *       fixtures, score completed ones, update the README accuracy table</li>
 *   <li>{@code -Dexec.args="--draw-curve"} — reproduce {@link DrawModel}'s per-gap draw-rate
 *       curve from data (replays internationals since 1980) and compare against the
 *       hard-coded {@code DRAW_RATE_BY_GAP} table</li>
 *   <li>{@code -Dexec.args="--importance-export"} — finding "A1": re-run the verify-export
 *       pipeline with fixed match-importance tier weights (friendlies 0.5, World Cup finals
 *       1.25; a-priori, not tuned) and write {@code research/export_predictions_importance.csv}
 *       for a paired-Brier gate against the {@code --verify-export} baseline</li>
 *   <li>{@code -Dexec.args="--values-tune-loto"} — finding "A3c": leave-one-tournament-out
 *       re-tune of {@link ValueWeights}. The current {@code DEFAULT} came from a single
 *       train-2006/18, validate-2022 split; this cross-validates the tuning procedure by
 *       picking the best grid candidate on the other four World Cups per fold and scoring it
 *       on the held-out one, then pooling. Prints per-fold winners, the pooled honest LOTO
 *       Brier of the tuning procedure, {@code DEFAULT}'s pooled held-out Brier for comparison,
 *       the modal winner, and a plain-English adopt/keep recommendation. Read-only: does not
 *       change {@code DEFAULT} (a human makes that call after seeing the output)</li>
 * </ul>
 */
public final class Main {

    public static void main(String[] args) throws IOException {
        List<String> arguments = Arrays.asList(args);
        Path csv = arguments.stream()
                .filter(a -> !a.startsWith("--"))
                .findFirst()
                .map(Path::of)
                .orElse(Path.of("data/results.csv"));

        List<Match> matches = new MatchCsvParser().parse(csv);
        matches.sort(Comparator.comparing(Match::date));

        if (arguments.contains("--backtest")) {
            runBacktests(matches);
        } else if (arguments.contains("--tune")) {
            runTuning(matches);
        } else if (arguments.contains("--track")) {
            runTracker(matches, csv);
        } else if (arguments.contains("--simulate")) {
            runSimulation(matches, csv);
        } else if (arguments.contains("--upcoming")) {
            runUpcoming(matches, csv);
        } else if (arguments.contains("--goals")) {
            runGoalComparison(matches);
        } else if (arguments.contains("--rest")) {
            runRest(matches);
        } else if (arguments.contains("--bets")) {
            runBets(matches, csv);
        } else if (arguments.contains("--calibrate")) {
            runCalibration(matches);
        } else if (arguments.contains("--draw-curve")) {
            runDrawCurve(matches);
        } else if (arguments.contains("--verify-export")) {
            runVerifyExport(matches);
        } else if (arguments.contains("--importance-export")) {
            runImportanceExport(matches);
        } else if (arguments.contains("--values-tune")) {
            runValuesTune(matches);
        } else if (arguments.contains("--values-tune-loto")) {
            runValuesTuneLoto(matches);
        } else if (arguments.contains("--values")) {
            runValues(matches);
        } else if (arguments.stream().anyMatch(a -> a.startsWith("--predict="))) {
            runPredict(matches, arguments);
        } else {
            runRankings(matches);
        }
    }

    private static void runRankings(List<Match> matches) {
        EloRatingSystem elo = new EloRatingSystem();
        matches.forEach(elo::processMatch);

        System.out.printf("Processed %,d matches between %d teams (%s to %s)%n%n",
                elo.matchesProcessed(),
                elo.teamCount(),
                matches.get(0).date(),
                matches.get(matches.size() - 1).date());

        System.out.println("=== Elo Top 15 ===");
        int rank = 1;
        for (var entry : elo.topRatings(15)) {
            System.out.printf("%2d. %-20s %.0f%n", rank++, entry.getKey(), entry.getValue());
        }

        System.out.println();
        System.out.println("=== Sample 2026 group-stage predictions (neutral venue) ===");
        printPrediction(elo, "Panama", "England");
        printPrediction(elo, "Croatia", "Ghana");
        printPrediction(elo, "Brazil", "Morocco");
    }

    private static void runBacktests(List<Match> matches) {
        System.out.println("=== Backtest: model evaluated on World Cups it has never seen ===");
        System.out.println();
        Backtest backtest = new Backtest();

        System.out.printf("%-16s | %-38s | %s%n", "Tournament", "Tuned model", "Baseline");
        for (Backtest.Window w : Backtest.WORLD_CUPS) {
            BacktestResult tuned = backtest.run(matches, w.from(), w.until(), EloConfig.DEFAULT);
            BacktestResult base = backtest.run(matches, w.from(), w.until(), EloConfig.BASELINE);
            System.out.printf("%-16s | %-38s | %s%n", w.label(), tuned.summary(), base.summary());
        }
        BacktestResult combinedTuned =
                backtest.runCombined(matches, Backtest.WORLD_CUPS, EloConfig.DEFAULT);
        BacktestResult combinedBase =
                backtest.runCombined(matches, Backtest.WORLD_CUPS, EloConfig.BASELINE);
        System.out.printf("%-16s | %-38s | %s%n", "Combined", combinedTuned.summary(),
                combinedBase.summary());

        System.out.println();
        System.out.println("--- Three-way (win/draw/loss) with the draw model, tuned config ---");
        for (Backtest.Window w : Backtest.WORLD_CUPS) {
            System.out.println(w.label() + ": "
                    + backtest.runThreeWay(matches, w.from(), w.until(), EloConfig.DEFAULT)
                            .summary());
        }
        System.out.println("Reference: predicting uniform thirds = multiclass Brier 0.667.");

        System.out.println();
        System.out.println("Reference points: coin flip = 50% accuracy, Brier 0.25.");
        System.out.println("Draws always count as misses in the binary rows, so accuracy is understated.");
    }

    private static void runGoalComparison(List<Match> matches) {
        System.out.println("=== Goal models vs Elo baseline: held-out World Cups (three-way) ===");
        System.out.println("Each model trains only on the 12 years before each tournament, then");
        System.out.println("predicts every finals match from that fit. Lower multiclass Brier is better.");
        System.out.println();

        record Entry(String name, GoalModelBacktest.Factory factory) {}
        List<Entry> models = List.of(
                new Entry("Dixon-Coles", (tr, asof) -> DixonColesModel.fit(tr, asof)),
                new Entry("Bivariate Poisson", (tr, asof) -> BivariatePoissonModel.fit(tr, asof)),
                new Entry("Elo-Poisson", (tr, asof) -> EloPoissonModel.fit(tr)),
                new Entry("Elo + DrawModel", (tr, asof) -> EloDrawBaselineModel.fit(tr)),
                new Entry("Elo+DC ensemble", (tr, asof) -> new EnsembleModel("Elo+DC ensemble",
                        List.of(DixonColesModel.fit(tr, asof), EloDrawBaselineModel.fit(tr)))));

        GoalModelBacktest bt = new GoalModelBacktest(12);
        System.out.printf("%-20s | %-13s | %s%n",
                "Model", "Combined", "per-tournament Brier (2006/10/14/18/22)");
        for (Entry e : models) {
            int evaluated = 0;
            int correct = 0;
            double brierSum = 0.0;
            StringBuilder per = new StringBuilder();
            for (Backtest.Window w : Backtest.WORLD_CUPS) {
                Backtest.ThreeWayResult r = bt.run(matches, w, e.factory());
                per.append(String.format(Locale.ROOT, " %.3f", r.multiclassBrier()));
                evaluated += r.matchesEvaluated();
                correct += r.correct();
                brierSum += r.multiclassBrier() * r.matchesEvaluated();
            }
            double combined = evaluated == 0 ? 0.0 : brierSum / evaluated;
            System.out.printf(Locale.ROOT, "%-20s | %3d/%-4d %.3f |%s%n",
                    e.name(), correct, evaluated, combined, per);
        }

        System.out.println();
        System.out.println("Reference: uniform thirds = multiclass Brier 0.667.");
    }

    private static void runBets(List<Match> matches, Path csv) throws IOException {
        System.out.println("=== Value bets vs the book (mock odds) ===");
        OddsTable odds = OddsTable.load(Path.of("data/odds_sample.csv"));
        if (odds.isEmpty()) {
            System.out.println("No data/odds_sample.csv found.");
            return;
        }
        LocalDate today = LocalDate.now();

        // Same production model as the live tracker: Dixon-Coles + tuned value prior.
        MarketValueTable values = MarketValueTable.load(Path.of("data/market_values.csv"));
        DixonColesModel model = values.isEmpty()
                ? DixonColesModel.fit(matches, today)
                : DixonColesModel.fitWithValues(matches, today, values, ValueWeights.DEFAULT);

        List<Fixture> upcoming = new MatchCsvParser().parseFixtures(csv).stream()
                .filter(Fixture::isWorldCupFinals)
                .filter(f -> !f.date().isBefore(today))
                .sorted(Comparator.comparing(Fixture::date))
                .toList();

        BettingConfig config = BettingConfig.DEFAULT;
        System.out.printf(Locale.ROOT,
                "Staking: min edge %.0f%%, %.2f Kelly, max %.0f%% of bankroll. Mock odds — "
                        + "wire a live feed for real use.%n%n",
                100 * config.minEdge(), config.kellyFraction(), 100 * config.maxStakeFraction());
        System.out.printf(Locale.ROOT, "%-10s %-32s %-14s %6s %6s %6s %6s %6s%n",
                "Date", "Match", "Bet", "model", "fair", "odds", "edge", "stake");

        int bets = 0;
        for (Fixture f : upcoming) {
            Optional<Odds> o = odds.oddsFor(f.date(), f.homeTeam(), f.awayTeam());
            if (o.isEmpty()) {
                continue;
            }
            DrawModel.Probabilities p =
                    model.probabilities(f.homeTeam(), f.awayTeam(), f.neutralVenue());
            Optional<ValueBet> bet = ValueBetting.evaluate(
                    new double[] {p.homeWin(), p.draw(), p.awayWin()}, o.get(), config);
            if (bet.isEmpty()) {
                continue;
            }
            ValueBet vb = bet.get();
            bets++;
            System.out.printf(Locale.ROOT, "%-10s %-32s %-14s %5.0f%% %5.0f%% %6.2f %5.1f%% %5.1f%%%n",
                    f.date(), f.homeTeam() + " vs " + f.awayTeam(), vb.outcomeLabel(),
                    100 * vb.modelProbability(), 100 * vb.fairProbability(), vb.offeredOdds(),
                    100 * vb.expectedValue(), 100 * vb.stakeFraction());
        }
        if (bets == 0) {
            System.out.println("No +EV bets at these odds.");
        }
    }

    private static void runCalibration(List<Match> matches) throws IOException {
        System.out.println("=== Calibration audit: production model on held-out World Cups ===");
        MarketValueTable values = MarketValueTable.load(Path.of("data/market_values.csv"));
        ValueTuner tuner = new ValueTuner(12, values);
        Backtest.Window wc2022 = Backtest.WORLD_CUPS.get(4);

        List<Calibration.Outcome> all = new ArrayList<>();
        List<Calibration.Outcome> tuning = new ArrayList<>();   // 2006-2018
        List<Calibration.Outcome> validation = new ArrayList<>(); // 2022
        for (Backtest.Window w : Backtest.WORLD_CUPS) {
            ValueTuner.Prepared p = tuner.prepare(matches, w);
            var strength = values.isEmpty() ? p.base()
                    : ValueAdjuster.adjust(p.base(), p.counts(), values, p.asof(), ValueWeights.DEFAULT);
            DixonColesModel model = new DixonColesModel(strength);
            for (Match m : p.test()) {
                DrawModel.Probabilities pr =
                        model.probabilities(m.homeTeam(), m.awayTeam(), m.neutralVenue());
                int actual = switch (m.outcome()) {
                    case HOME_WIN -> 0;
                    case DRAW -> 1;
                    case AWAY_WIN -> 2;
                };
                Calibration.Outcome o =
                        new Calibration.Outcome(new double[] {pr.homeWin(), pr.draw(), pr.awayWin()}, actual);
                all.add(o);
                (w.equals(wc2022) ? validation : tuning).add(o);
            }
        }

        System.out.printf(Locale.ROOT,
                "Across %d held-out matches: log-loss %.4f, multiclass Brier %.4f, ECE %.4f%n%n",
                all.size(), Calibration.logLoss(all), Calibration.brier(all),
                Calibration.expectedCalibrationError(all, 10));
        System.out.println("Reliability (one-vs-rest, by predicted probability):");
        System.out.printf(Locale.ROOT, "%-13s %10s %10s %8s%n", "bin", "predicted", "observed", "n");
        for (Calibration.Bin b : Calibration.reliability(all, 10)) {
            System.out.printf(Locale.ROOT, "%4.0f-%3.0f%%     %9.1f%% %9.1f%% %8d%n",
                    100 * b.low(), 100 * b.high(),
                    100 * b.meanPredicted(), 100 * b.observedFrequency(), b.count());
        }

        double t = Calibration.fitTemperature(tuning);
        System.out.println();
        System.out.printf(Locale.ROOT,
                "Fitted temperature on 2006-2018: T=%.2f (>1 softens overconfidence, <1 sharpens).%n", t);
        System.out.printf(Locale.ROOT, "Held-out 2022 log-loss: raw %.4f -> tempered %.4f%n",
                Calibration.logLoss(validation),
                Calibration.logLoss(Calibration.rescale(validation, t)));
        System.out.printf(Locale.ROOT, "Held-out 2022 Brier:    raw %.4f -> tempered %.4f%n",
                Calibration.brier(validation),
                Calibration.brier(Calibration.rescale(validation, t)));
        System.out.printf(Locale.ROOT, "Held-out 2022 ECE:      raw %.4f -> tempered %.4f%n",
                Calibration.expectedCalibrationError(validation, 10),
                Calibration.expectedCalibrationError(Calibration.rescale(validation, t), 10));
    }

    private static void runValuesTune(List<Match> matches) throws IOException {
        MarketValueTable values = MarketValueTable.load(Path.of("data/market_values.csv"));
        System.out.println("=== Tuning the market-value prior (train 2006-2018, validate 2022) ===");
        if (values.isEmpty()) {
            System.out.println("No data/market_values.csv found — see the README for how to build it.");
            return;
        }
        ValueTuner tuner = new ValueTuner(12, values);
        ValueWeights baseline = new ValueWeights(0.0, 0.0, 5.0, 0.2); // (0,0,*) == plain Dixon-Coles

        List<ValueTuner.Prepared> tuning = tuner.prepareAll(matches, Backtest.TUNING_WINDOWS);
        List<ValueTuner.Scored> ranked = new ArrayList<>();
        for (ValueWeights w : ValueTuner.defaultGrid()) {
            ranked.add(tuner.score(tuning, w));
        }
        ranked.sort(Comparator.comparingDouble(ValueTuner.Scored::brier));
        ValueTuner.Scored baseTuning = tuner.score(tuning, baseline);

        System.out.println("Tuning-set leaderboard (pooled WC 2006-2018), best first:");
        for (ValueTuner.Scored s : ranked.subList(0, Math.min(8, ranked.size()))) {
            System.out.println("  " + s.summary());
        }
        System.out.println("  baseline plain DC: " + baseTuning.summary());

        // Validate the tuning winner once on the held-out 2022 World Cup.
        ValueWeights best = ranked.get(0).weights();
        List<ValueTuner.Prepared> validation =
                tuner.prepareAll(matches, List.of(Backtest.WORLD_CUPS.get(4)));
        ValueTuner.Scored bestVal = tuner.score(validation, best);
        ValueTuner.Scored baseVal = tuner.score(validation, baseline);

        System.out.println();
        System.out.println("Held-out World Cup 2022:");
        System.out.println("  plain Dixon-Coles:  " + baseVal.summary());
        System.out.println("  tuned value prior:  " + bestVal.summary());
        System.out.println();
        if (bestVal.brier() < baseVal.brier()) {
            System.out.printf(Locale.ROOT,
                    "Verdict: the tuned prior improves held-out Brier (%.4f -> %.4f). Worth keeping.%n",
                    baseVal.brier(), bestVal.brier());
        } else {
            System.out.println("Verdict: even tuned, the value prior does not beat plain Dixon-Coles "
                    + "out of sample. Treat as a negative finding.");
        }
    }

    /**
     * Finding "A3c": leave-one-tournament-out re-tune of {@link ValueWeights}.
     *
     * <p>{@code ValueWeights.DEFAULT} was chosen by a single split ({@code --values-tune}
     * grid-searches 2006-2018, validates once on 2022). The project's gate demands LOTO for
     * tunables, so here we cross-validate the whole tuning procedure: for each held-out World
     * Cup we pick the grid winner on the other four, score it on the held-out one, and pool
     * match-weighted across the five folds. That pooled number is the honest out-of-sample
     * Brier of "run the value-weight grid search". We also break out the current {@code DEFAULT}
     * the same way for comparison, and recommend adopting a new default only if a single
     * weighting wins a majority of folds and its pooled held-out Brier beats {@code DEFAULT}.
     *
     * <p>Read-only w.r.t. models: reuses {@link ValueTuner#prepareAll}, {@link ValueTuner#score}
     * and {@link ValueTuner#defaultGrid} unchanged and does not touch {@code DEFAULT}.
     */
    private static void runValuesTuneLoto(List<Match> matches) throws IOException {
        MarketValueTable values = MarketValueTable.load(Path.of("data/market_values.csv"));
        System.out.println("=== A3c: leave-one-tournament-out re-tune of the market-value prior ===");
        if (values.isEmpty()) {
            System.out.println("No data/market_values.csv found — see the README for how to build it.");
            return;
        }

        // Default (1.0/1.0) tier weights: this is the value-weight tune, independent of the A1
        // importance weights. Fit the five World Cup windows once; scoring many weightings is cheap.
        ValueTuner tuner = new ValueTuner(12, values);
        List<ValueTuner.Prepared> prepared = tuner.prepareAll(matches, Backtest.WORLD_CUPS);
        List<ValueWeights> grid = ValueTuner.defaultGrid();
        int folds = Backtest.WORLD_CUPS.size();

        // Per-fold held-out results for the tuning procedure (winner picked on the other four).
        List<ValueTuner.Scored> foldWinnerHeldOut = new ArrayList<>();
        List<ValueWeights> foldWinnerWeights = new ArrayList<>();
        // Per-fold held-out results for the current DEFAULT.
        List<ValueTuner.Scored> defaultHeldOut = new ArrayList<>();

        for (int h = 0; h < folds; h++) {
            List<ValueTuner.Prepared> tuning = new ArrayList<>();
            for (int i = 0; i < folds; i++) {
                if (i != h) {
                    tuning.add(prepared.get(i));
                }
            }
            // Pick the grid winner on the four tuning folds; deterministic, lowest index on ties.
            ValueTuner.Scored best = null;
            for (ValueWeights w : grid) {
                ValueTuner.Scored s = tuner.score(tuning, w);
                if (best == null || s.brier() < best.brier()) {
                    best = s;
                }
            }
            ValueWeights winner = best.weights();
            foldWinnerWeights.add(winner);
            List<ValueTuner.Prepared> held = List.of(prepared.get(h));
            foldWinnerHeldOut.add(tuner.score(held, winner));
            defaultHeldOut.add(tuner.score(held, ValueWeights.DEFAULT));
        }

        // Per-fold table for the tuning procedure's winners.
        System.out.println();
        System.out.println("Per-fold tuning winners (winner tuned on the other four World Cups):");
        System.out.printf(Locale.ROOT, "  %-16s | %-30s | %-11s | %s%n",
                "Held-out fold", "winning weights", "held Brier", "held accuracy");
        for (int h = 0; h < folds; h++) {
            ValueWeights w = foldWinnerWeights.get(h);
            ValueTuner.Scored s = foldWinnerHeldOut.get(h);
            System.out.printf(Locale.ROOT,
                    "  %-16s | global %.2f sparse %.2f scale %.2f | %-11.4f | %d/%d (%.1f%%)%n",
                    Backtest.WORLD_CUPS.get(h).label(),
                    w.globalWeight(), w.sparseWeight(), w.valueScale(),
                    s.brier(), s.correct(), s.evaluated(),
                    s.evaluated() == 0 ? 0.0 : 100.0 * s.correct() / s.evaluated());
        }

        // Pooled (match-weighted) held-out numbers for the tuning procedure.
        double procBrierSum = 0.0;
        int procEval = 0;
        int procCorrect = 0;
        for (ValueTuner.Scored s : foldWinnerHeldOut) {
            procBrierSum += s.brier() * s.evaluated();
            procEval += s.evaluated();
            procCorrect += s.correct();
        }
        double procBrier = procEval == 0 ? 0.0 : procBrierSum / procEval;
        double procAcc = procEval == 0 ? 0.0 : 100.0 * procCorrect / procEval;

        System.out.println();
        System.out.printf(Locale.ROOT,
                "POOLED held-out (honest LOTO-CV of the tuning procedure): Brier %.4f, %d/%d correct (%.1f%%)%n",
                procBrier, procCorrect, procEval, procAcc);

        // Current DEFAULT, per fold + pooled, for comparison.
        System.out.println();
        System.out.printf(Locale.ROOT, "Current DEFAULT = (global %.2f, sparse %.2f, kappa %.2f, scale %.2f) held out per fold:%n",
                ValueWeights.DEFAULT.globalWeight(), ValueWeights.DEFAULT.sparseWeight(),
                ValueWeights.DEFAULT.kappa(), ValueWeights.DEFAULT.valueScale());
        double defBrierSum = 0.0;
        int defEval = 0;
        int defCorrect = 0;
        for (int h = 0; h < folds; h++) {
            ValueTuner.Scored s = defaultHeldOut.get(h);
            System.out.printf(Locale.ROOT, "  %-16s | Brier %.4f | %d/%d (%.1f%%)%n",
                    Backtest.WORLD_CUPS.get(h).label(), s.brier(), s.correct(), s.evaluated(),
                    s.evaluated() == 0 ? 0.0 : 100.0 * s.correct() / s.evaluated());
            defBrierSum += s.brier() * s.evaluated();
            defEval += s.evaluated();
            defCorrect += s.correct();
        }
        double defBrier = defEval == 0 ? 0.0 : defBrierSum / defEval;
        double defAcc = defEval == 0 ? 0.0 : 100.0 * defCorrect / defEval;
        System.out.printf(Locale.ROOT,
                "POOLED held-out DEFAULT: Brier %.4f, %d/%d correct (%.1f%%)%n",
                defBrier, defCorrect, defEval, defAcc);

        // Modal winner: the single weighting that won the most folds (deterministic).
        List<ValueWeights> distinct = new ArrayList<>();
        List<Integer> distinctCount = new ArrayList<>();
        for (ValueWeights w : foldWinnerWeights) {
            int idx = -1;
            for (int i = 0; i < distinct.size(); i++) {
                if (valueWeightsEqual(distinct.get(i), w)) {
                    idx = i;
                    break;
                }
            }
            if (idx < 0) {
                distinct.add(w);
                distinctCount.add(1);
            } else {
                distinctCount.set(idx, distinctCount.get(idx) + 1);
            }
        }
        int modalIdx = 0;
        for (int i = 1; i < distinct.size(); i++) {
            if (distinctCount.get(i) > distinctCount.get(modalIdx)) {
                modalIdx = i;
            }
        }
        ValueWeights modal = distinct.get(modalIdx);
        int modalCount = distinctCount.get(modalIdx);
        System.out.println();
        System.out.printf(Locale.ROOT,
                "Modal winner: global %.2f sparse %.2f kappa %.2f scale %.2f won %d/%d folds.%n",
                modal.globalWeight(), modal.sparseWeight(), modal.kappa(), modal.valueScale(),
                modalCount, folds);

        // Recommendation: adopt only if a single weighting wins a majority of folds AND its
        // pooled held-out Brier is no worse than DEFAULT's. Compute the modal winner's own pooled
        // held-out Brier (over every fold, so it is comparable to DEFAULT's pooled number).
        double modalBrierSum = 0.0;
        int modalEval = 0;
        int modalCorrect = 0;
        for (int h = 0; h < folds; h++) {
            ValueTuner.Scored s = tuner.score(List.of(prepared.get(h)), modal);
            modalBrierSum += s.brier() * s.evaluated();
            modalEval += s.evaluated();
            modalCorrect += s.correct();
        }
        double modalBrier = modalEval == 0 ? 0.0 : modalBrierSum / modalEval;

        System.out.println();
        boolean majority = modalCount >= 3;
        boolean beatsDefault = modalBrier <= defBrier;
        if (majority && beatsDefault) {
            System.out.printf(Locale.ROOT,
                    "RECOMMENDATION: ADOPT. The modal weighting wins %d/5 folds and its pooled held-out "
                            + "Brier %.4f <= DEFAULT's %.4f. Set:%n", modalCount, modalBrier, defBrier);
            System.out.printf(Locale.ROOT,
                    "  new ValueWeights(%.2f, %.2f, %.1f, %.2f)%n",
                    modal.globalWeight(), modal.sparseWeight(), modal.kappa(), modal.valueScale());
        } else {
            System.out.print("RECOMMENDATION: KEEP DEFAULT. ");
            if (!majority) {
                System.out.printf(Locale.ROOT,
                        "No single weighting wins a majority (modal only %d/5). ", modalCount);
            } else {
                System.out.printf(Locale.ROOT,
                        "Modal weighting's pooled held-out Brier %.4f does not beat DEFAULT's %.4f. ",
                        modalBrier, defBrier);
            }
            System.out.printf(Locale.ROOT,
                    "Honest LOTO-CV Brier of the tuning procedure is %.4f (vs DEFAULT %.4f).%n",
                    procBrier, defBrier);
        }
    }

    /** Exact-field equality for {@link ValueWeights} (a record; grid values are shared literals). */
    private static boolean valueWeightsEqual(ValueWeights a, ValueWeights b) {
        return a.globalWeight() == b.globalWeight()
                && a.sparseWeight() == b.sparseWeight()
                && a.kappa() == b.kappa()
                && a.valueScale() == b.valueScale();
    }

    private static void runValues(List<Match> matches) throws IOException {
        MarketValueTable values = MarketValueTable.load(Path.of("data/market_values.csv"));
        System.out.println("=== Squad market value as a Dixon-Coles prior: held-out World Cups ===");
        if (values.isEmpty()) {
            System.out.println("No data/market_values.csv found — see the README for how to build it");
            System.out.println("from the Transfermarkt datasets.");
            return;
        }
        System.out.println("Plain Dixon-Coles vs the value-adjusted model, same train-before-each-");
        System.out.println("tournament regime. Needs historical value snapshots covering each World");
        System.out.println("Cup; with only a current snapshot the historical rows are identical.");
        System.out.println();

        record Entry(String name, GoalModelBacktest.Factory factory) {}
        List<Entry> models = List.of(
                new Entry("Dixon-Coles", (tr, asof) -> DixonColesModel.fit(tr, asof)),
                new Entry("DC + market value",
                        (tr, asof) -> DixonColesModel.fitWithValues(tr, asof, values, ValueWeights.DEFAULT)));

        GoalModelBacktest bt = new GoalModelBacktest(12);
        System.out.printf("%-20s | %-13s | %s%n",
                "Model", "Combined", "per-tournament Brier (2006/10/14/18/22)");
        for (Entry e : models) {
            int evaluated = 0;
            int correct = 0;
            double brierSum = 0.0;
            StringBuilder per = new StringBuilder();
            for (Backtest.Window w : Backtest.WORLD_CUPS) {
                Backtest.ThreeWayResult r = bt.run(matches, w, e.factory());
                per.append(String.format(Locale.ROOT, " %.3f", r.multiclassBrier()));
                evaluated += r.matchesEvaluated();
                correct += r.correct();
                brierSum += r.multiclassBrier() * r.matchesEvaluated();
            }
            double combined = evaluated == 0 ? 0.0 : brierSum / evaluated;
            System.out.printf(Locale.ROOT, "%-20s | %3d/%-4d %.3f |%s%n",
                    e.name(), correct, evaluated, combined, per);
        }
        System.out.println();
        System.out.println("Reference: uniform thirds = multiclass Brier 0.667.");
    }

    private static void runRest(List<Match> matches) {
        System.out.println("=== Rest-days differential: does extra recovery beat the plain rating? ===");
        System.out.println("Adds rating points per day of rest advantage; 0 = Elo + DrawModel baseline.");
        System.out.println();

        RestBacktest bt = new RestBacktest();
        double[] coeffs = {0, 5, 10, 15, 20, 30};

        System.out.printf("%-9s | %s%n", "pts/day", "pooled WC 2006-2018 (three-way)");
        double bestCoeff = 0;
        double bestBrier = Double.MAX_VALUE;
        for (double c : coeffs) {
            int evaluated = 0;
            int correct = 0;
            double brierSum = 0.0;
            for (Backtest.Window w : Backtest.TUNING_WINDOWS) {
                RestBacktest.Result r = bt.run(matches, w.from(), w.until(), c);
                evaluated += r.evaluated();
                correct += r.correct();
                brierSum += r.multiclassBrier() * r.evaluated();
            }
            double brier = evaluated == 0 ? 0.0 : brierSum / evaluated;
            System.out.printf(Locale.ROOT, "%-9.0f | %d/%d correct, Brier %.4f%n",
                    c, correct, evaluated, brier);
            if (brier < bestBrier) {
                bestBrier = brier;
                bestCoeff = c;
            }
        }

        Backtest.Window validation = Backtest.WORLD_CUPS.get(4); // 2022, held out
        RestBacktest.Result base = bt.run(matches, validation.from(), validation.until(), 0);
        RestBacktest.Result tuned = bt.run(matches, validation.from(), validation.until(), bestCoeff);
        System.out.println();
        System.out.printf(Locale.ROOT,
                "Best on tuning: %.0f points per rest-day. Held-out World Cup 2022:%n", bestCoeff);
        System.out.println("  baseline (0):       " + base.summary());
        System.out.printf(Locale.ROOT, "  rest-adjusted (%.0f): %s%n", bestCoeff, tuned.summary());
        if (bestCoeff == 0) {
            System.out.println("Verdict: rest differential did not improve on the baseline.");
        }
    }

    private static void runTuning(List<Match> matches) {
        System.out.println("=== Hyperparameter grid search ===");
        System.out.println("Tuning metric: pooled Brier over WC 2006-2018 (256 matches).");
        System.out.println("World Cup 2022 is held out for final validation.");
        System.out.println();

        Tuner tuner = new Tuner();
        List<Tuner.Candidate> candidates = tuner.search(matches);

        System.out.printf("%-7s %-9s %-10s %-7s %-7s | %s%n",
                "kWC", "homeAdv", "kFriendly", "margin", "regr", "pooled 2006-2018 result");
        for (Tuner.Candidate c : candidates.subList(0, 8)) {
            EloConfig cfg = c.config();
            System.out.printf("%-7.0f %-9.0f %-10.0f %-7s %-7.2f | %s%n",
                    cfg.kWorldCup(), cfg.homeAdvantage(), cfg.kFriendly(),
                    cfg.goalMarginScaling() ? "on" : "off",
                    cfg.annualRegression(),
                    c.tuningResult().summary());
        }

        EloConfig best = candidates.get(0).config();
        System.out.println();
        System.out.println("Held-out validation of the winner on World Cup 2022:");
        System.out.println("  " + tuner.validate(matches, best).summary());
        System.out.println();
        System.out.println("Current EloConfig.DEFAULT on 2022 for comparison:");
        System.out.println("  " + tuner.validate(matches, EloConfig.DEFAULT).summary());
    }

    private static void runTracker(List<Match> matches, Path csv) throws IOException {
        LocalDate today = LocalDate.now();
        Path ledgerPath = Path.of("predictions/predictions.csv");
        Path readmePath = Path.of("README.md");

        // Train on everything that has been played (Elo still drives the title-odds simulation).
        EloRatingSystem elo = new EloRatingSystem();
        matches.forEach(elo::processMatch);

        // Production prediction model: Dixon-Coles (best performer in the held-out
        // comparison), fit on all history as of today and folded with squad market
        // value as a prior when data/market_values.csv is present.
        MarketValueTable marketValues = MarketValueTable.load(Path.of("data/market_values.csv"));
        DixonColesModel predictionModel = marketValues.isEmpty()
                ? DixonColesModel.fit(matches, today)
                : DixonColesModel.fitWithValues(matches, today, marketValues, ValueWeights.DEFAULT);

        // Lock predictions for upcoming World Cup fixtures not yet in the ledger.
        List<Fixture> fixtures = new MatchCsvParser().parseFixtures(csv);
        List<PredictionLedger.Prediction> ledger =
                new ArrayList<>(PredictionLedger.load(ledgerPath));
        FormAdjuster form = new FormAdjuster(matches);
        List<PredictionLedger.Prediction> added =
                Tracker.lockNewPredictions(predictionModel, fixtures, ledger, today, form);
        ledger.addAll(added);
        ledger.sort(Comparator.comparing(PredictionLedger.Prediction::matchDate));
        PredictionLedger.save(ledgerPath, ledger);

        // Retrospective predictions for World Cup matches played before the model
        // existed. They are merged into the main record (counted), each trained only
        // on data from before its match, so no result is ever peeked at.
        LocalDate modelBirth = ledger.stream()
                .map(PredictionLedger.Prediction::lockedOn)
                .min(Comparator.naturalOrder())
                .orElse(today);
        List<Match> earlyMatches = matches.stream()
                .filter(Match::isWorldCupFinals)
                .filter(mt -> mt.date().getYear() == 2026)
                .filter(mt -> mt.date().isBefore(modelBirth))
                .sorted(Comparator.comparing(Match::date))
                .toList();
        List<PredictionLedger.Prediction> earlyPredictions = new ArrayList<>();
        for (Match mt : earlyMatches) {
            List<Match> before = matches.stream().filter(x -> x.date().isBefore(mt.date())).toList();
            DixonColesModel retro = marketValues.isEmpty()
                    ? DixonColesModel.fit(before, mt.date())
                    : DixonColesModel.fitWithValues(before, mt.date(), marketValues, ValueWeights.DEFAULT);
            DrawModel.Probabilities pr = Calibration.transferDraw(
                    form.adjust(mt.homeTeam(), mt.awayTeam(), mt.date(),
                            retro.probabilities(mt.homeTeam(), mt.awayTeam(), mt.neutralVenue())));
            var goals = retro.expectedGoals(mt.homeTeam(), mt.awayTeam(), mt.neutralVenue());
            earlyPredictions.add(new PredictionLedger.Prediction(
                    mt.date(), mt.homeTeam(), mt.awayTeam(), mt.neutralVenue(),
                    pr.homeWin(), pr.draw(), pr.awayWin(),
                    goals.map(GoalModel.GoalRates::home).orElse(Double.NaN),
                    goals.map(GoalModel.GoalRates::away).orElse(Double.NaN),
                    mt.date()));
        }

        // Score everything that now has a result: ledger predictions plus the merged
        // retrospective ones. Pending = locked predictions still awaiting a result.
        List<Tracker.ScoredPrediction> scored = new ArrayList<>(Tracker.score(ledger, matches));
        scored.addAll(Tracker.score(earlyPredictions, matches));
        List<PredictionLedger.Prediction> pending = new ArrayList<>(ledger);
        scored.forEach(s -> pending.remove(s.prediction()));

        // Rewrite the README prediction-accuracy section (most recent matches first).
        String readme = Files.readString(readmePath);
        readme = Tracker.replaceSection(readme, Tracker.renderMarkdown(scored, pending, today));

        // Rewrite the live championship-odds section from a fresh simulation.
        List<Match> played2026 = matches.stream()
                .filter(Match::isWorldCupFinals)
                .filter(mt -> mt.date().getYear() == 2026)
                .toList();
        List<Fixture> remainingWorldCup = fixtures.stream()
                .filter(Fixture::isWorldCupFinals)
                .toList();
        int runs = 10_000;
        List<TournamentSimulator.TeamOdds> odds =
                new TournamentSimulator(elo).simulate(played2026, remainingWorldCup, runs, 2026L);
        readme = Tracker.replaceSection(readme,
                Tracker.TITLE_SECTION_START, Tracker.TITLE_SECTION_END,
                Tracker.renderTitleOdds(odds, 16, today, runs));

        Files.writeString(readmePath, readme);

        // Structured data for the static demo page (GitHub Pages reads docs/data/tracker.json).
        Path trackerJson = Path.of("docs/data/tracker.json");
        Files.createDirectories(trackerJson.getParent());
        Files.writeString(trackerJson, Tracker.renderJson(scored, pending, odds, 16, today));

        System.out.printf("Locked %d new prediction(s); ledger holds %d.%n",
                added.size(), ledger.size());
        long correct = scored.stream().filter(Tracker.ScoredPrediction::correct).count();
        if (!scored.isEmpty()) {
            System.out.printf("Scored %d: %d correct (%.1f%%), multiclass Brier %.4f%n",
                    scored.size(), correct, 100.0 * correct / scored.size(),
                    scored.stream().mapToDouble(Tracker.ScoredPrediction::brier)
                            .average().orElse(0));
        } else {
            System.out.println("No locked predictions resolved yet.");
        }
        System.out.println("README updated.");
    }

    private static void runSimulation(List<Match> matches, Path csv) throws IOException {
        EloRatingSystem elo = new EloRatingSystem();
        matches.forEach(elo::processMatch);

        List<Match> playedGroup = matches.stream()
                .filter(Match::isWorldCupFinals)
                .filter(m -> m.date().getYear() == 2026)
                .toList();
        List<Fixture> remaining = new MatchCsvParser().parseFixtures(csv).stream()
                .filter(Fixture::isWorldCupFinals)
                .toList();

        int runs = 10_000;
        TournamentSimulator simulator = new TournamentSimulator(elo);
        List<TournamentSimulator.TeamOdds> odds =
                simulator.simulate(playedGroup, remaining, runs, 2026L);

        System.out.printf("=== Monte Carlo: %,d simulations of the remaining tournament ===%n", runs);
        System.out.printf("Group results so far: %d played, %d fixtures remaining.%n%n",
                playedGroup.size(), remaining.size());
        System.out.printf("%4s %-22s %7s %7s %7s%n", "", "Team", "Title", "Final", "Semis");
        int rank = 1;
        for (TournamentSimulator.TeamOdds o : odds.subList(0, Math.min(15, odds.size()))) {
            System.out.printf("%3d. %-22s %6.1f%% %6.1f%% %6.1f%%%n",
                    rank++, o.team(),
                    100 * o.titleShare(), 100 * o.finalShare(), 100 * o.semiShare());
        }
        System.out.println();
        System.out.println("Simplifications: Elo tie-breaks instead of goal difference; seeded");
        System.out.println("knockout pairings; knockout draws folded into the win probability.");
    }

    private static void runUpcoming(List<Match> matches, Path csv) throws IOException {
        EloRatingSystem elo = new EloRatingSystem();
        matches.forEach(elo::processMatch);

        List<Fixture> upcoming = new MatchCsvParser().parseFixtures(csv).stream()
                .filter(Fixture::isWorldCupFinals)
                .sorted(Comparator.comparing(Fixture::date))
                .toList();

        System.out.printf("=== Upcoming World Cup fixtures: model view (%d matches) ===%n%n",
                upcoming.size());
        System.out.printf("%-10s %-44s %5s %6s %5s%n", "Date", "Match (with current Elo)",
                "Win", "Draw", "Loss");
        for (Fixture f : upcoming) {
            DrawModel.Probabilities p =
                    elo.outcomeProbabilities(f.homeTeam(), f.awayTeam(), f.neutralVenue());
            String label = String.format("%s (%.0f) vs %s (%.0f)%s",
                    f.homeTeam(), elo.ratingOf(f.homeTeam()),
                    f.awayTeam(), elo.ratingOf(f.awayTeam()),
                    f.neutralVenue() ? "" : " [home]");
            System.out.printf("%-10s %-44s %4.0f%% %5.0f%% %4.0f%%%n",
                    f.date(), label,
                    100 * p.homeWin(), 100 * p.draw(), 100 * p.awayWin());
        }
    }

    /** Usage: {@code --predict=TeamA,TeamB} (add {@code ,home} if TeamA hosts). */
    private static void runPredict(List<Match> matches, List<String> arguments) {
        String spec = arguments.stream()
                .filter(a -> a.startsWith("--predict="))
                .findFirst().orElseThrow()
                .substring("--predict=".length());
        String[] parts = spec.split(",");
        if (parts.length < 2) {
            System.out.println("Usage: --predict=TeamA,TeamB[,home]");
            return;
        }
        String home = parts[0].trim();
        String away = parts[1].trim();
        boolean neutral = parts.length < 3 || !parts[2].trim().equalsIgnoreCase("home");

        EloRatingSystem elo = new EloRatingSystem();
        matches.forEach(elo::processMatch);

        DrawModel.Probabilities p = elo.outcomeProbabilities(home, away, neutral);
        System.out.printf("%s (Elo %.0f) vs %s (Elo %.0f)%s%n",
                home, elo.ratingOf(home), away, elo.ratingOf(away),
                neutral ? " — neutral venue" : " — " + home + " at home");
        System.out.printf("  %s win: %.1f%%%n", home, 100 * p.homeWin());
        System.out.printf("  Draw:   %.1f%%%n", 100 * p.draw());
        System.out.printf("  %s win: %.1f%%%n", away, 100 * p.awayWin());
    }

    private static void printPrediction(EloRatingSystem elo, String teamA, String teamB) {
        double p = elo.winProbability(teamA, teamB, true);
        System.out.printf("%s (%.0f) vs %s (%.0f): %s expected to win with score %.2f%n",
                teamA, elo.ratingOf(teamA),
                teamB, elo.ratingOf(teamB),
                p >= 0.5 ? teamA : teamB,
                p >= 0.5 ? p : 1 - p);
    }

    private static void runVerifyExport(List<Match> matches) throws IOException {
        System.out.println("=== Verify export: writing held-out per-match predictions ===");
        // Default weights 1.0/1.0: this is the committed baseline. The tier weighting is
        // a pure no-op here, so research/export_predictions_form.csv reproduces unchanged.
        ValueTuner tuner = new ValueTuner(12, MarketValueTable.load(Path.of("data/market_values.csv")));
        writeExportCsvs(matches, tuner,
                Path.of("research/export_predictions.csv"),
                Path.of("research/export_predictions_form.csv"));
    }

    /**
     * Same pipeline as {@link #runVerifyExport} but with fixed match-importance tier
     * weights (finding "A1"): friendlies down-weighted to 0.5, World Cup finals
     * up-weighted to 1.25 in the Poisson ratings fit. These are FIXED prior-belief
     * hyperparameters — deliberately NOT grid-searched — so the variant carries no
     * tuning-overfit. Writes to a separate file; the default export is untouched.
     */
    private static void runImportanceExport(List<Match> matches) throws IOException {
        System.out.println("=== Importance export: tier-weighted per-match predictions (A1) ===");
        // 0.5 (friendly) and 1.25 (finals) are a-priori judgment values, NOT tuned.
        ValueTuner tuner = new ValueTuner(12,
                MarketValueTable.load(Path.of("data/market_values.csv")), 0.5, 1.25);
        writeExportCsvs(matches, tuner,
                Path.of("research/export_predictions_importance_value.csv"),
                Path.of("research/export_predictions_importance.csv"));
    }

    /**
     * Shared export pipeline: per-window ValueTuner.prepare -> ValueAdjuster ->
     * DixonColesModel, then FormAdjuster + Calibration.transferDraw for the form
     * output. The value-prior CSV goes to {@code outPath}, the form-adjusted CSV to
     * {@code formPath}. Behaviour depends only on the supplied {@code tuner}, so the
     * default caller (1.0/1.0 weights) reproduces the committed baseline byte-for-byte.
     */
    private static void writeExportCsvs(List<Match> matches, ValueTuner tuner,
                                        Path outPath, Path formPath) throws IOException {
        MarketValueTable values = MarketValueTable.load(Path.of("data/market_values.csv"));
        FormAdjuster form = new FormAdjuster(matches);
        try (PrintWriter pw = new PrintWriter(new FileWriter(outPath.toFile()));
             PrintWriter fw = new PrintWriter(new FileWriter(formPath.toFile()))) {
            pw.println("tournament,home,away,date,p_home,p_draw,p_away,actual");
            fw.println("tournament,home,away,date,p_home,p_draw,p_away,actual");
            for (Backtest.Window w : Backtest.WORLD_CUPS) {
                ValueTuner.Prepared p = tuner.prepare(matches, w);
                var strength = values.isEmpty() ? p.base()
                        : ValueAdjuster.adjust(p.base(), p.counts(), values, p.asof(), ValueWeights.DEFAULT);
                DixonColesModel model = new DixonColesModel(strength);
                // Label matches the WINDOWS keys used in research/verify.py
                String label = "WC" + w.from().getYear();
                for (Match m : p.test()) {
                    DrawModel.Probabilities pr =
                            model.probabilities(m.homeTeam(), m.awayTeam(), m.neutralVenue());
                    String actual = switch (m.outcome()) {
                        case HOME_WIN -> "home";
                        case DRAW    -> "draw";
                        case AWAY_WIN -> "away";
                    };
                    writeExportRow(pw, label, m, pr, actual);
                    DrawModel.Probabilities adjusted = Calibration.transferDraw(
                            form.adjust(m.homeTeam(), m.awayTeam(), m.date(), pr));
                    writeExportRow(fw, label, m, adjusted, actual);
                }
            }
        }
        System.out.printf("Written %s (value prior) and %s (value prior + recent form)%n",
                outPath.toAbsolutePath(), formPath.toAbsolutePath());
    }

    /**
     * Reproduces {@link DrawModel}'s per-gap draw-rate curve directly from data, so the
     * hard-coded {@code DRAW_RATE_BY_GAP} table and the post-1980 international count in the
     * DrawModel javadoc become checkable rather than asserted. (As of writing the replay
     * reproduces the curve in shape to within ~0.015 and counts ~37,400 matches; the shipped
     * table is rounded and lightly smoothed, so it is close, not bit-exact.)
     *
     * <p>Methodology (matching the production draw model exactly): replay every match dated
     * 1980-01-01 or later through a fresh {@link EloRatingSystem} using {@link EloConfig#DEFAULT}
     * (the config {@code new EloRatingSystem()} uses in production), in chronological order,
     * predict-then-update. For each match, before updating ratings, compute the SAME effective
     * rating gap {@link EloRatingSystem#outcomeProbabilities} feeds to {@link DrawModel}:
     * {@code gap = (homeRating + (neutral ? 0 : homeAdvantage)) - awayRating}. Bin by
     * {@code |gap|} with the identical rule {@link DrawModel#drawProbability} uses — bins of
     * width 50 via {@code floor(|gap|/50)}, with everything at {@code |gap| >= 600} collapsed
     * into the top bin. Tally draws vs. total per bin, then compare the observed rate against
     * the shipped table value.
     *
     * <p>This is a REPORTING command: it never asserts or fails, because the point is to surface
     * whether the shipped array reproduces, not to enforce that it does.
     */
    private static void runDrawCurve(List<Match> matches) {
        final int binCount = 13;              // gap = 0, 50, ..., 600
        final double binWidth = 50.0;         // mirrors DrawModel.BIN_WIDTH
        final double maxGap = (binCount - 1) * binWidth; // 600, the top-bin threshold
        final LocalDate since = LocalDate.of(1980, 1, 1);
        final EloConfig config = EloConfig.DEFAULT; // production config used by new EloRatingSystem()

        long[] draws = new long[binCount];
        long[] totals = new long[binCount];

        EloRatingSystem elo = new EloRatingSystem(config);
        int replayed = 0;
        // matches arrive sorted by date from main(); replay in that order.
        for (Match m : matches) {
            if (m.date().isBefore(since)) {
                continue;
            }
            // PRE-match ratings and the exact effective gap the DrawModel is indexed by.
            double home = elo.ratingOf(m.homeTeam())
                    + (m.neutralVenue() ? 0.0 : config.homeAdvantage());
            double away = elo.ratingOf(m.awayTeam());
            double gap = Math.abs(home - away);

            int bin = gap >= maxGap ? binCount - 1 : (int) (gap / binWidth);

            totals[bin]++;
            if (m.outcome() == Match.Outcome.DRAW) {
                draws[bin]++;
            }
            replayed++;

            // Now let the model learn from this match (predict-then-update).
            elo.processMatch(m);
        }

        System.out.println("=== Draw-rate curve: reproducing DrawModel.DRAW_RATE_BY_GAP from data ===");
        System.out.println("Replaying internationals since 1980 through EloConfig.DEFAULT,");
        System.out.println("binning each match by the same effective home-adjusted rating gap the");
        System.out.println("draw model uses (|gap|, 50-point bins, >=600 in the top bin).");
        System.out.println();
        System.out.printf(Locale.ROOT,
                "Matches replayed (dated 1980-01-01 or later): %,d  (grows as the dataset does)%n%n",
                replayed);

        System.out.printf(Locale.ROOT, "%-9s %8s %10s %10s %10s%n",
                "gap bin", "n", "observed", "shipped", "diff");

        double maxAbsDiff = 0.0;
        int comparedBins = 0;
        int matchingBins = 0;
        final double tolerance = 0.005;
        for (int b = 0; b < binCount; b++) {
            double centerGap = b * binWidth;
            // Shipped table value: drawProbability at the exact bin gap returns
            // DRAW_RATE_BY_GAP[b] (interpolation weight t=0), and >=600 returns the last entry.
            double shipped = DrawModel.drawProbability(centerGap);
            String binLabel = b == binCount - 1
                    ? (int) centerGap + "+"
                    : (int) centerGap + "-" + (int) (centerGap + binWidth);

            if (totals[b] == 0) {
                System.out.printf(Locale.ROOT, "%-9s %8d %10s %10.3f %10s%n",
                        binLabel, 0L, "-", shipped, "-");
                continue;
            }
            double observed = (double) draws[b] / totals[b];
            double diff = observed - shipped;
            maxAbsDiff = Math.max(maxAbsDiff, Math.abs(diff));
            comparedBins++;
            if (Math.abs(diff) <= tolerance) {
                matchingBins++;
            }
            System.out.printf(Locale.ROOT, "%-9s %8d %10.3f %10.3f %+10.3f%n",
                    binLabel, totals[b], observed, shipped, diff);
        }

        System.out.println();
        System.out.printf(Locale.ROOT,
                "Max abs difference across %d populated bin(s): %.4f%n", comparedBins, maxAbsDiff);
        boolean allMatch = comparedBins > 0 && matchingBins == comparedBins;
        System.out.printf(Locale.ROOT,
                "Bins matching within +/-%.3f: %d/%d%s%n",
                tolerance, matchingBins, comparedBins,
                allMatch ? "  -> shipped array reproduces from data." : "");
        if (!allMatch) {
            System.out.println("Shipped array does NOT reproduce within tolerance from this replay.");
            System.out.println("This is a reporting command; nothing is asserted. See the notes in");
            System.out.println("DrawModel's javadoc about how the table was derived.");
        }
    }

    private static void writeExportRow(PrintWriter pw, String label, Match m,
                                       DrawModel.Probabilities pr, String actual) {
        pw.printf(Locale.ROOT, "%s,%s,%s,%s,%.8f,%.8f,%.8f,%s%n",
                label,
                m.homeTeam().replace(",", ";"),
                m.awayTeam().replace(",", ";"),
                m.date(),
                pr.homeWin(), pr.draw(), pr.awayWin(),
                actual);
    }

    private Main() {
    }
}
