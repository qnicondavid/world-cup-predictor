package com.david.worldcup.goals;

import com.david.worldcup.elo.DrawModel;
import com.david.worldcup.model.Match;

import java.time.LocalDate;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Cross-confederation strength correction, ported from research/confederation.py.
 *
 * <p>The idea: over a training window, inter-confederation matchups (home team in
 * confederation ca, away team in confederation cb, ca != cb) carry a systematic
 * residual between the actual goal difference and the Dixon-Coles expected goal
 * difference. That residual, decay-weighted, becomes a directional offset per
 * ordered confederation pair. At prediction time the offset is split symmetrically
 * in log-rate space and applied only to inter-confederation matchups.
 *
 * <p>Leakage-safe: offsets are estimated only from the training matches passed in,
 * then applied to the test matchups by the caller.
 */
public final class Confederations {

    private Confederations() {
    }

    // ------------------------------------------------------------------
    // 1. Confederation map from continental tournaments
    // ------------------------------------------------------------------

    /**
     * Maps a tournament name to a confederation string, or null when ambiguous.
     * Faithful port of confed_of_tournament.
     */
    public static String confedOfTournament(String tournament) {
        if (tournament == null) {
            return null;
        }
        String s = tournament.toLowerCase(Locale.ROOT);
        // UEFA
        if (s.startsWith("uefa euro") || s.equals("uefa nations league")
                || s.equals("british home championship") || s.equals("nordic championship")
                || s.equals("baltic cup") || s.equals("central european international cup")
                || s.equals("balkan cup") || s.equals("cyprus international tournament")
                || s.equals("muratti vase") || s.equals("island games")) {
            return "UEFA";
        }
        // CONMEBOL
        if (s.contains("copa américa") || s.contains("copa america")
                || s.equals("south american championship")) {
            return "CONMEBOL";
        }
        // CONCACAF
        if (s.contains("concacaf") || s.equals("gold cup") || s.equals("cccf championship")
                || s.equals("uncaf cup") || s.equals("cfu caribbean cup")
                || s.equals("windward islands tournament") || s.equals("caribbean cup")) {
            return "CONCACAF";
        }
        // AFC (Asia)
        if (s.contains("afc ") || s.equals("afc asian cup") || s.equals("asian games")
                || s.equals("gulf cup") || s.equals("arab cup") || s.equals("aff championship")
                || s.equals("saff cup") || s.equals("eaff championship") || s.equals("king's cup")
                || s.equals("korea cup") || s.equals("kirin cup") || s.equals("merdeka tournament")
                || s.equals("waff championship") || s.equals("southeast asian games")
                || s.equals("southeast asian peninsular games") || s.equals("south asian games")
                || s.equals("nehru cup") || s.equals("indonesia tournament")
                || s.contains("asian cup")) {
            return "AFC";
        }
        // CAF (Africa)
        if (s.contains("african cup of nations") || s.equals("cecafa cup") || s.equals("cosafa cup")
                || s.equals("amílcar cabral cup") || s.equals("all-african games")
                || s.equals("udeac cup") || s.equals("indian ocean island games")
                || s.contains("african")) {
            return "CAF";
        }
        // OFC (Oceania)
        if (s.equals("oceania nations cup") || s.equals("south pacific games")
                || s.equals("pacific games")) {
            return "OFC";
        }
        return null;
    }

    /**
     * Builds a per-team confederation by plurality vote across continental matches.
     * Faithful port of build_confed_map. Ties are broken by first-seen confederation
     * (matching Python Counter.most_common insertion-order tie-break).
     */
    public static Map<String, String> buildConfedMap(List<Match> all) {
        // Preserve insertion order of confederations per team so ties resolve to the
        // first confederation seen for that team, as Python's Counter does.
        Map<String, LinkedHashMap<String, Integer>> votes = new HashMap<>();
        for (Match m : all) {
            String c = confedOfTournament(m.tournament());
            if (c == null) {
                continue;
            }
            votes.computeIfAbsent(m.homeTeam(), k -> new LinkedHashMap<>()).merge(c, 1, Integer::sum);
            votes.computeIfAbsent(m.awayTeam(), k -> new LinkedHashMap<>()).merge(c, 1, Integer::sum);
        }
        Map<String, String> cmap = new HashMap<>();
        for (Map.Entry<String, LinkedHashMap<String, Integer>> e : votes.entrySet()) {
            String best = null;
            int bestCount = -1;
            for (Map.Entry<String, Integer> v : e.getValue().entrySet()) {
                if (v.getValue() > bestCount) {
                    bestCount = v.getValue();
                    best = v.getKey();
                }
            }
            cmap.put(e.getKey(), best);
        }
        return cmap;
    }

    // ------------------------------------------------------------------
    // 2. Estimate inter-confederation offsets from TRAINING data only
    // ------------------------------------------------------------------

    /**
     * Integer date encoding used by goal_models and confederation.py:
     * enc(d) = year*372 + month*31 + day.
     */
    private static long enc(LocalDate d) {
        return (long) d.getYear() * 372L + (long) d.getMonthValue() * 31L + d.getDayOfMonth();
    }

    /**
     * Estimates directional inter-confederation offsets from the training matches.
     *
     * <p>offset["ca|cb"] is the decay-weighted mean of (actualGD - expectedGD) over
     * training matches where the home team is in confederation ca, the away team is
     * in cb, and ca != cb, with both teams known to the fitted model. expectedGD is
     * lambdaHome - lambdaAway under the supplied strength; actualGD is
     * homeScore - awayScore. The weight is exp(-ln(2)/(halfLifeYears*372) * (encAsof - encDate)).
     * A pair is emitted only when its raw match count is at least minN.
     *
     * <p>Leakage-safe: only the training list passed in is consulted.
     */
    public static Map<String, Double> estimateOffsets(TeamStrength strength, List<Match> train,
                                                      Map<String, String> cmap, LocalDate asof,
                                                      double halfLifeYears, int minN) {
        double xi = Math.log(2.0) / (halfLifeYears * 372.0);
        long encAsof = enc(asof);
        Map<String, Double> num = new HashMap<>();
        Map<String, Double> den = new HashMap<>();
        Map<String, Integer> cnt = new HashMap<>();
        for (Match m : train) {
            String ca = cmap.get(m.homeTeam());
            String cb = cmap.get(m.awayTeam());
            if (ca == null || cb == null || ca.equals(cb)) {
                continue;
            }
            if (!strength.attack().containsKey(m.homeTeam())
                    || !strength.attack().containsKey(m.awayTeam())) {
                continue;
            }
            double lh = strength.lambdaHome(m.homeTeam(), m.awayTeam(), m.neutralVenue());
            double la = strength.lambdaAway(m.homeTeam(), m.awayTeam(), m.neutralVenue());
            double expGd = lh - la;
            double actGd = m.homeScore() - m.awayScore();
            double resid = actGd - expGd;
            double w = Math.exp(-xi * (encAsof - enc(m.date())));
            String key = ca + "|" + cb;
            num.merge(key, w * resid, Double::sum);
            den.merge(key, w, Double::sum);
            cnt.merge(key, 1, Integer::sum);
        }
        Map<String, Double> offsets = new HashMap<>();
        for (Map.Entry<String, Integer> e : cnt.entrySet()) {
            if (e.getValue() >= minN) {
                offsets.put(e.getKey(), num.get(e.getKey()) / den.get(e.getKey()));
            }
        }
        return offsets;
    }

    // ------------------------------------------------------------------
    // 3. Apply the offset to the log-lambdas for inter-confed matchups
    // ------------------------------------------------------------------

    /**
     * Computes win/draw/loss probabilities with the confederation offset applied
     * (inter-confederation matchups only). The goal-difference offset o is clamped
     * to [-cap, cap], split symmetrically in log-rate space as adj = scale*o/2, and
     * applied by multiplying the home rate by exp(adj) and the away rate by exp(-adj).
     *
     * <p>When there is no offset for the pair, the pair is intra-confederation, or
     * scale is 0, the rates are left untouched (scale 0 gives adj 0 and exp(0) == 1.0
     * exactly), so the result matches the unmodified model bit for bit.
     */
    public static DrawModel.Probabilities applyOffset(TeamStrength strength, String home, String away,
                                                      boolean neutral, Map<String, String> cmap,
                                                      Map<String, Double> offsets, double scale, double cap) {
        double lh = strength.lambdaHome(home, away, neutral);
        double la = strength.lambdaAway(home, away, neutral);
        String ca = cmap.get(home);
        String cb = cmap.get(away);
        double o = 0.0;
        if (ca != null && cb != null && !ca.equals(cb)) {
            Double got = offsets.get(ca + "|" + cb);
            if (got != null) {
                o = got;
            }
        }
        if (o != 0.0) {
            o = Math.max(-cap, Math.min(cap, o));
            double adj = scale * o / 2.0;
            lh = lh * Math.exp(adj);
            la = la * Math.exp(-adj);
        }
        return ScoreGrid.dixonColes(lh, la, strength.rho());
    }
}
