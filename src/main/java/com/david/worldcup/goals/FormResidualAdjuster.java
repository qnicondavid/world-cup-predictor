package com.david.worldcup.goals;

import com.david.worldcup.elo.DrawModel;
import com.david.worldcup.model.Match;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Opponent-adjusted variant of {@link FormAdjuster} (Phase 3 Candidate 4, research bet).
 *
 * <p>The shipped {@link FormAdjuster} averages each side's raw goals conceded over its last
 * {@value #WINDOW} matches. That figure is confounded by schedule strength: conceding to a
 * strong opponent and to a weak one count the same. This variant replaces the raw quantity
 * with the opponent-adjusted residual
 *
 * <pre>
 *   residual = expectedConceded - actualConceded
 * </pre>
 *
 * where {@code expectedConceded} is the fitted model's expected goals against that specific
 * opponent in that specific fixture, from the same per-window {@link TeamStrength} used for
 * prediction. For a match the team played at home it is {@code strength.lambdaAway(team,
 * opponent, neutral)}; for a match it played away it is {@code strength.lambdaHome(opponent,
 * team, neutral)}. A positive residual means the team conceded fewer than its fixtures
 * implied, i.e. defended better than expected.
 *
 * <p>Everything else matches the shipped feature: a simple mean over the last {@value #WINDOW}
 * matches strictly before kickoff, the same fewer-than-window guard, and the same
 * home-versus-away log-odds shift with the draw untouched and a positive shift favouring the
 * home side. At {@code lambda == 0} no shift is applied, so the output equals the form-off
 * baseline exactly.
 *
 * <p>Leakage-safe: the strength is fit only on matches before the tournament window, and the
 * recent matches are strictly before the prediction date, so the fit never sees a test outcome.
 * This class is opt-in and does not touch any shipped path.
 */
public final class FormResidualAdjuster {

    /** Number of recent matches averaged for the form figure. */
    public static final int WINDOW = 5;

    /** Default nudge strength, matching the shipped {@link FormAdjuster#LAMBDA}. */
    public static final double LAMBDA = 0.20;

    private record Entry(LocalDate date, String opponent, boolean teamWasHome,
                         boolean neutral, int goalsConceded) {}

    private final Map<String, List<Entry>> history = new HashMap<>();
    private final double lambda;

    public FormResidualAdjuster(List<Match> matches) {
        this(matches, LAMBDA);
    }

    public FormResidualAdjuster(List<Match> matches, double lambda) {
        this.lambda = lambda;
        List<Match> ordered = new ArrayList<>(matches);
        ordered.sort(Comparator.comparing(Match::date));
        for (Match m : ordered) {
            history.computeIfAbsent(m.homeTeam(), k -> new ArrayList<>())
                    .add(new Entry(m.date(), m.awayTeam(), true, m.neutralVenue(), m.awayScore()));
            history.computeIfAbsent(m.awayTeam(), k -> new ArrayList<>())
                    .add(new Entry(m.date(), m.homeTeam(), false, m.neutralVenue(), m.homeScore()));
        }
    }

    /**
     * Mean opponent-adjusted defensive residual over the last {@link #WINDOW} matches strictly
     * before {@code date}, or {@code null} if fewer than {@link #WINDOW} exist. Positive means
     * the team has been conceding fewer goals than the fitted model expected of it.
     */
    private Double recentResidual(String team, LocalDate date, TeamStrength strength) {
        List<Entry> rows = history.get(team);
        if (rows == null) {
            return null;
        }
        int count = 0;
        double sum = 0.0;
        for (int i = rows.size() - 1; i >= 0 && count < WINDOW; i--) {
            Entry e = rows.get(i);
            if (e.date().isBefore(date)) {
                double expectedConceded = e.teamWasHome()
                        ? strength.lambdaAway(team, e.opponent(), e.neutral())
                        : strength.lambdaHome(e.opponent(), team, e.neutral());
                sum += expectedConceded - e.goalsConceded();
                count++;
            }
        }
        return count >= WINDOW ? sum / WINDOW : null;
    }

    /**
     * Probabilities nudged by recent opponent-adjusted defensive form. If either side lacks
     * {@link #WINDOW} prior matches, the input is returned unchanged. The {@code strength} must
     * be the same per-window fit used to produce {@code p}.
     */
    public DrawModel.Probabilities adjust(String home, String away, LocalDate date,
                                          TeamStrength strength, DrawModel.Probabilities p) {
        Double homeResid = recentResidual(home, date, strength);
        Double awayResid = recentResidual(away, date, strength);
        if (homeResid == null || awayResid == null) {
            return p;
        }
        double feature = homeResid - awayResid; // positive: home has the better recent defence
        double shift = lambda * feature;
        double h = p.homeWin() * Math.exp(shift / 2.0);
        double a = p.awayWin() * Math.exp(-shift / 2.0);
        double d = p.draw();
        double z = h + a + d;
        return new DrawModel.Probabilities(h / z, d / z, a / z);
    }
}
