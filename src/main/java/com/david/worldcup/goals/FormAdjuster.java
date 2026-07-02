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
 * Post-fit adjustment that nudges win/draw/loss probabilities by each side's
 * recent defensive form: the mean goals conceded over its last {@value #WINDOW}
 * matches before kickoff.
 *
 * <p>Held-out testing through the verification harness (research/verify.py)
 * showed that recent goals-against carries resolution the static attack/defence
 * ratings miss. A team conceding fewer than usual lately is sharper than its
 * long-run rating implies, and vice versa. Measured on the production model's
 * held-out predictions, this nudge cut the combined Brier by about 0.006 with
 * the gain landing in resolution (sharper separation), and a bootstrap CI clear
 * of zero.
 *
 * <p>The shift is applied on the home-vs-away log-odds axis; the draw
 * probability is left untouched and the three outcomes are renormalised. The
 * feature uses only matches strictly before the prediction date, so it is
 * leakage-safe. {@link #LAMBDA} is a deliberately conservative coefficient
 * (interior to the tested range, not the data-greedy edge). It was set by judgment
 * within that hand-checked range, not by a committed leave-one-tournament-out sweep,
 * so unlike the draw-transfer calibration it is measured but not gate-selected.
 */
public final class FormAdjuster {

    /** Number of recent matches averaged for the form figure. */
    public static final int WINDOW = 5;

    /** Nudge strength, in log-odds per goal of recent goals-against difference. */
    public static final double LAMBDA = 0.20;

    private record Entry(LocalDate date, int goalsAgainst) {}

    private final Map<String, List<Entry>> history = new HashMap<>();
    private final double lambda;

    public FormAdjuster(List<Match> matches) {
        this(matches, LAMBDA);
    }

    public FormAdjuster(List<Match> matches, double lambda) {
        this.lambda = lambda;
        List<Match> ordered = new ArrayList<>(matches);
        ordered.sort(Comparator.comparing(Match::date));
        for (Match m : ordered) {
            history.computeIfAbsent(m.homeTeam(), k -> new ArrayList<>())
                    .add(new Entry(m.date(), m.awayScore()));
            history.computeIfAbsent(m.awayTeam(), k -> new ArrayList<>())
                    .add(new Entry(m.date(), m.homeScore()));
        }
    }

    /**
     * Mean goals conceded over the last {@link #WINDOW} matches strictly before
     * {@code date}, or {@code null} if fewer than {@link #WINDOW} exist.
     */
    private Double recentGoalsAgainst(String team, LocalDate date) {
        List<Entry> rows = history.get(team);
        if (rows == null) {
            return null;
        }
        int count = 0;
        double sum = 0.0;
        for (int i = rows.size() - 1; i >= 0 && count < WINDOW; i--) {
            if (rows.get(i).date().isBefore(date)) {
                sum += rows.get(i).goalsAgainst();
                count++;
            }
        }
        return count >= WINDOW ? sum / WINDOW : null;
    }

    /**
     * Probabilities nudged by recent defensive form. If either side lacks
     * {@link #WINDOW} prior matches, the input is returned unchanged.
     */
    public DrawModel.Probabilities adjust(String home, String away, LocalDate date,
                                          DrawModel.Probabilities p) {
        Double homeGa = recentGoalsAgainst(home, date);
        Double awayGa = recentGoalsAgainst(away, date);
        if (homeGa == null || awayGa == null) {
            return p;
        }
        double feature = awayGa - homeGa; // positive: home has the better recent defence
        double shift = lambda * feature;
        double h = p.homeWin() * Math.exp(shift / 2.0);
        double a = p.awayWin() * Math.exp(-shift / 2.0);
        double d = p.draw();
        double z = h + a + d;
        return new DrawModel.Probabilities(h / z, d / z, a / z);
    }
}
