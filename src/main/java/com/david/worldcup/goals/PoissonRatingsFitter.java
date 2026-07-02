package com.david.worldcup.goals;

import com.david.worldcup.model.Match;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;

/**
 * Fits per-team attack/defence ratings, a home-advantage term and the
 * Dixon-Coles low-score correction by weighted maximum likelihood.
 *
 * <p>The attack/defence/home/baseline parameters are found with an iterative
 * scaling (multiplicative fixed-point) scheme: each parameter is set to the
 * value that solves its own Poisson score equation given the others, and the
 * pass is repeated to convergence. This is the closed-form alternative to a
 * generic optimiser and needs no external library.
 *
 * <p>Two refinements matter for international football:
 * <ul>
 *   <li><b>Time decay</b> — each match is weighted by {@code exp(-xi * age)} with
 *       {@code xi} set from a half-life (default 2 years), so a friendly from a
 *       decade ago barely counts. Squads turn over.</li>
 *   <li><b>Shrinkage</b> — a small pseudo-count pulls rarely-seen teams toward
 *       the average, so a minnow with three caps does not get a wild rating.</li>
 * </ul>
 *
 * <p>{@code rho} is then chosen by a one-dimensional search that maximises the
 * Dixon-Coles-corrected likelihood with the goal rates held fixed.
 */
public final class PoissonRatingsFitter {

    private double halfLifeYears = 2.0;
    private int iterations = 200;
    private double shrinkage = 1.0; // pseudo-goals pulling each team toward average
    // Match-importance tier weights. Both default to 1.0, which makes tierWeight()
    // a pure no-op: the fit is byte-for-byte identical to a decay-only weighting.
    // Only an explicit opt-in path (e.g. --importance-export) sets non-default values.
    private double wFriendly = 1.0;
    private double wFinals = 1.0;
    private static final double RHO_MIN = -0.18;
    private static final double RHO_MAX = 0.18;

    public PoissonRatingsFitter halfLifeYears(double v) {
        this.halfLifeYears = v;
        return this;
    }

    public PoissonRatingsFitter iterations(int v) {
        this.iterations = v;
        return this;
    }

    public PoissonRatingsFitter shrinkage(double v) {
        this.shrinkage = v;
        return this;
    }

    /** Weight applied to friendlies (default 1.0 = no-op). Set &lt;1 to down-weight. */
    public PoissonRatingsFitter wFriendly(double v) {
        this.wFriendly = v;
        return this;
    }

    /** Weight applied to World Cup finals matches (default 1.0 = no-op). Set &gt;1 to up-weight. */
    public PoissonRatingsFitter wFinals(double v) {
        this.wFinals = v;
        return this;
    }

    /**
     * Match-importance multiplier by tournament tier, matching the project's
     * existing classification (see {@code research/goal_models.py} and
     * {@link Match#isWorldCupFinals()}): a friendly is any tournament whose name
     * (lowercased) contains "friendly"; the finals tier is exactly
     * "FIFA World Cup" (NOT "FIFA World Cup qualification" — qualifiers and every
     * other competition are the 1.0 competitive anchor). With the default
     * {@code wFriendly == wFinals == 1.0} this always returns 1.0.
     */
    private double tierWeight(String tournament) {
        if (tournament == null) {
            return 1.0;
        }
        if (tournament.toLowerCase(java.util.Locale.ROOT).contains("friendly")) {
            return wFriendly;
        }
        if (tournament.equalsIgnoreCase("FIFA World Cup")) {
            return wFinals;
        }
        return 1.0;
    }

    public TeamStrength fit(List<Match> matches, LocalDate asof) {
        TreeSet<String> teamSet = new TreeSet<>();
        for (Match m : matches) {
            teamSet.add(m.homeTeam());
            teamSet.add(m.awayTeam());
        }
        List<String> teams = new ArrayList<>(teamSet);
        int n = teams.size();
        Map<String, Integer> idx = new HashMap<>();
        for (int i = 0; i < n; i++) {
            idx.put(teams.get(i), i);
        }

        int m = matches.size();
        int[] hi = new int[m];
        int[] ai = new int[m];
        double[] hg = new double[m];
        double[] ag = new double[m];
        double[] w = new double[m];
        boolean[] neutral = new boolean[m];
        double xi = Math.log(2.0) / (halfLifeYears * 365.25);
        for (int k = 0; k < m; k++) {
            Match mt = matches.get(k);
            hi[k] = idx.get(mt.homeTeam());
            ai[k] = idx.get(mt.awayTeam());
            hg[k] = mt.homeScore();
            ag[k] = mt.awayScore();
            neutral[k] = mt.neutralVenue();
            long age = Math.max(0, ChronoUnit.DAYS.between(mt.date(), asof));
            w[k] = Math.exp(-xi * age) * tierWeight(mt.tournament());
        }

        // Multiplicative parameters: A=exp(attack), D=exp(defence), B=exp(baseline), H=exp(home).
        double[] att = new double[n];
        double[] def = new double[n];
        java.util.Arrays.fill(att, 1.0);
        java.util.Arrays.fill(def, 1.0);
        double base = 1.3;
        double home = 1.3;

        for (int iter = 0; iter < iterations; iter++) {
            // --- baseline B ---
            double numB = 0, denB = 0;
            for (int k = 0; k < m; k++) {
                double hf = neutral[k] ? 1.0 : home;
                numB += w[k] * (hg[k] + ag[k]);
                denB += w[k] * (att[hi[k]] * def[ai[k]] * hf + att[ai[k]] * def[hi[k]]);
            }
            base = numB / denB;

            // --- home advantage H (non-neutral matches only) ---
            double numH = 0, denH = 0;
            for (int k = 0; k < m; k++) {
                if (neutral[k]) {
                    continue;
                }
                numH += w[k] * hg[k];
                denH += w[k] * base * att[hi[k]] * def[ai[k]];
            }
            if (denH > 0) {
                home = numH / denH;
            }

            // --- attack A ---
            double[] numA = new double[n];
            double[] denA = new double[n];
            for (int k = 0; k < m; k++) {
                double hf = neutral[k] ? 1.0 : home;
                numA[hi[k]] += w[k] * hg[k];
                numA[ai[k]] += w[k] * ag[k];
                denA[hi[k]] += w[k] * base * def[ai[k]] * hf;
                denA[ai[k]] += w[k] * base * def[hi[k]];
            }
            for (int i = 0; i < n; i++) {
                att[i] = (numA[i] + shrinkage) / (denA[i] + shrinkage);
            }

            // --- defence D (goals conceded) ---
            double[] numD = new double[n];
            double[] denD = new double[n];
            for (int k = 0; k < m; k++) {
                double hf = neutral[k] ? 1.0 : home;
                numD[hi[k]] += w[k] * ag[k];
                numD[ai[k]] += w[k] * hg[k];
                denD[hi[k]] += w[k] * base * att[ai[k]];
                denD[ai[k]] += w[k] * base * att[hi[k]] * hf;
            }
            for (int i = 0; i < n; i++) {
                def[i] = (numD[i] + shrinkage) / (denD[i] + shrinkage);
            }

            // --- re-centre so attack and defence have geometric mean 1 ---
            double gA = geometricMean(att);
            double gD = geometricMean(def);
            for (int i = 0; i < n; i++) {
                att[i] /= gA;
                def[i] /= gD;
            }
            base *= gA * gD;
        }

        Map<String, Double> attackMap = new HashMap<>();
        Map<String, Double> defenceMap = new HashMap<>();
        for (int i = 0; i < n; i++) {
            attackMap.put(teams.get(i), Math.log(att[i]));
            defenceMap.put(teams.get(i), Math.log(def[i]));
        }
        double baseline = Math.log(base);
        double homeAdv = Math.log(home);
        double rho = fitRho(matches, w, baseline, homeAdv, attackMap, defenceMap);
        return new TeamStrength(baseline, homeAdv, rho, attackMap, defenceMap);
    }

    /** Grid search for the rho that maximises the Dixon-Coles corrected log-likelihood. */
    private double fitRho(List<Match> matches, double[] w, double baseline, double homeAdv,
                          Map<String, Double> attack, Map<String, Double> defence) {
        TeamStrength s = new TeamStrength(baseline, homeAdv, 0.0, attack, defence);
        double best = 0.0;
        double bestLl = Double.NEGATIVE_INFINITY;
        for (int step = 0; step <= 72; step++) {
            double rho = RHO_MIN + (RHO_MAX - RHO_MIN) * step / 72.0;
            double ll = 0.0;
            boolean valid = true;
            for (int k = 0; k < matches.size() && valid; k++) {
                Match mt = matches.get(k);
                int x = mt.homeScore();
                int y = mt.awayScore();
                if (x > 1 || y > 1) {
                    continue; // tau == 1, no contribution
                }
                double lh = s.lambdaHome(mt.homeTeam(), mt.awayTeam(), mt.neutralVenue());
                double la = s.lambdaAway(mt.homeTeam(), mt.awayTeam(), mt.neutralVenue());
                double tau = dcTau(x, y, lh, la, rho);
                if (tau <= 0) {
                    valid = false;
                } else {
                    ll += w[k] * Math.log(tau);
                }
            }
            if (valid && ll > bestLl) {
                bestLl = ll;
                best = rho;
            }
        }
        return best;
    }

    static double dcTau(int x, int y, double lh, double la, double rho) {
        if (x == 0 && y == 0) {
            return 1 - lh * la * rho;
        }
        if (x == 0 && y == 1) {
            return 1 + lh * rho;
        }
        if (x == 1 && y == 0) {
            return 1 + la * rho;
        }
        if (x == 1 && y == 1) {
            return 1 - rho;
        }
        return 1.0;
    }

    private static double geometricMean(double[] v) {
        double s = 0.0;
        for (double x : v) {
            s += Math.log(x);
        }
        return Math.exp(s / v.length);
    }
}
