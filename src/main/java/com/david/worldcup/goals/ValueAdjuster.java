package com.david.worldcup.goals;

import com.david.worldcup.value.EaRatingsTable;
import com.david.worldcup.value.MarketValueTable;

import java.time.LocalDate;
import java.util.HashMap;
import java.util.Map;
import java.util.OptionalDouble;
import java.util.Set;
import java.util.TreeSet;

/**
 * Folds squad market value into fitted {@link TeamStrength} attack/defence
 * ratings. A richer-than-average squad gets a higher attack prior and a lower
 * (better) defence prior; each team's fitted rating is shrunk toward that prior
 * by {@link ValueWeights}, with more pull for teams that have little match data.
 *
 * <p>This also lets the model rate a team with value data but <em>no</em> recent
 * matches (a debutant): such a team has no fitted rating, so it sits entirely at
 * its value-implied prior — exactly the blind spot value is meant to cover.
 */
public final class ValueAdjuster {

    private ValueAdjuster() {
    }

    public static TeamStrength adjust(TeamStrength fit, Map<String, Integer> matchCounts,
                                      MarketValueTable values, LocalDate asof, ValueWeights weights) {
        if (values.isEmpty()) {
            return fit;
        }

        // Standardise log market value across teams that have a valuation as of this date.
        Map<String, Double> logValue = new HashMap<>();
        double sum = 0.0;
        for (String team : values.teamsWithValueAsOf(asof)) {
            OptionalDouble v = values.valueAsOf(team, asof);
            if (v.isPresent() && v.getAsDouble() > 0) {
                double lv = Math.log(v.getAsDouble());
                logValue.put(team, lv);
                sum += lv;
            }
        }
        if (logValue.size() < 2) {
            return fit;
        }
        double mean = sum / logValue.size();
        double variance = 0.0;
        for (double lv : logValue.values()) {
            variance += (lv - mean) * (lv - mean);
        }
        double sd = Math.sqrt(variance / logValue.size());
        if (sd <= 0) {
            return fit;
        }

        Set<String> teams = new TreeSet<>(fit.attack().keySet());
        teams.addAll(fit.defence().keySet());
        teams.addAll(logValue.keySet());

        Map<String, Double> attack = new HashMap<>();
        Map<String, Double> defence = new HashMap<>();
        for (String team : teams) {
            double fittedAttack = fit.attackOf(team);
            double fittedDefence = fit.defenceOf(team);
            Double lv = logValue.get(team);
            if (lv == null) {
                attack.put(team, fittedAttack);
                defence.put(team, fittedDefence);
                continue;
            }
            double z = (lv - mean) / sd;
            double priorAttack = weights.valueScale() * z;
            double priorDefence = -weights.valueScale() * z;
            double w = weights.shrinkageFor(matchCounts.getOrDefault(team, 0));
            attack.put(team, (1 - w) * fittedAttack + w * priorAttack);
            defence.put(team, (1 - w) * fittedDefence + w * priorDefence);
        }
        recenter(attack);
        recenter(defence);
        return new TeamStrength(fit.baseline(), fit.homeAdvantage(), fit.rho(), attack, defence);
    }

    /**
     * Same as {@link #adjust}, extended with an additive EA Sports FC ratings prior. The value
     * logic above (standardise log market value, shrink each team's fitted rating toward the
     * value-implied prior) is reproduced exactly. On top of it, for every team that goes through
     * the value prior branch, a coverage-scaled combination of standardised EA squad-rating
     * aggregates (mean top-26 overall, attack-side overall, defence-side overall, best
     * goalkeeper overall, and the penetration composite atk_pen on the attack side) is added to
     * that team's prior attack and prior defence before the same shrinkage blend and recentre. Coverage is 0 for a squad with fewer than 5 rated players and
     * 1 at 15 or more, so a thin EA snapshot contributes little.
     *
     * <p>With {@code eaWeights} equal to {@link EaWeights#ZERO}, or {@code ea} null or empty,
     * every added term is multiplied by zero, so the result is exactly what {@link #adjust}
     * would produce. This method never changes {@link #adjust} itself.
     */
    public static TeamStrength adjustWithEa(TeamStrength fit, Map<String, Integer> matchCounts,
                                            MarketValueTable values, EaRatingsTable ea, LocalDate asof,
                                            ValueWeights weights, EaWeights eaWeights) {
        if (values.isEmpty()) {
            return fit;
        }

        // Standardise log market value across teams that have a valuation as of this date.
        Map<String, Double> logValue = new HashMap<>();
        double sum = 0.0;
        for (String team : values.teamsWithValueAsOf(asof)) {
            OptionalDouble v = values.valueAsOf(team, asof);
            if (v.isPresent() && v.getAsDouble() > 0) {
                double lv = Math.log(v.getAsDouble());
                logValue.put(team, lv);
                sum += lv;
            }
        }
        if (logValue.size() < 2) {
            return fit;
        }
        double mean = sum / logValue.size();
        double variance = 0.0;
        for (double lv : logValue.values()) {
            variance += (lv - mean) * (lv - mean);
        }
        double sd = Math.sqrt(variance / logValue.size());
        if (sd <= 0) {
            return fit;
        }

        // Standardise each EA aggregate across the teams that have it as of this date. An
        // aggregate with fewer than two present teams, or zero spread, contributes a z-score of
        // zero to every team, the same degrade-to-no-op rule the value standardisation follows.
        Map<String, Double> zOvrByTeam = standardiseEa(ea, asof, EaRatingsTable::ovrAsOf);
        Map<String, Double> zAtkByTeam = standardiseEa(ea, asof, EaRatingsTable::atkAsOf);
        Map<String, Double> zDefByTeam = standardiseEa(ea, asof, EaRatingsTable::defAsOf);
        Map<String, Double> zGkByTeam = standardiseEa(ea, asof, EaRatingsTable::gkAsOf);
        Map<String, Double> zAtkPenByTeam = standardiseEa(ea, asof, EaRatingsTable::atkPenAsOf);
        Map<String, Double> zSpThreatByTeam = standardiseEa(ea, asof, EaRatingsTable::spThreatAsOf);
        Map<String, Double> zSpVulnByTeam = standardiseEa(ea, asof, EaRatingsTable::spVulnAsOf);

        Set<String> teams = new TreeSet<>(fit.attack().keySet());
        teams.addAll(fit.defence().keySet());
        teams.addAll(logValue.keySet());

        Map<String, Double> attack = new HashMap<>();
        Map<String, Double> defence = new HashMap<>();
        for (String team : teams) {
            double fittedAttack = fit.attackOf(team);
            double fittedDefence = fit.defenceOf(team);
            Double lv = logValue.get(team);
            if (lv == null) {
                attack.put(team, fittedAttack);
                defence.put(team, fittedDefence);
                continue;
            }
            double z = (lv - mean) / sd;
            double priorAttack = weights.valueScale() * z;
            double priorDefence = -weights.valueScale() * z;

            double zOvr = zOvrByTeam.getOrDefault(team, 0.0);
            double zAtk = zAtkByTeam.getOrDefault(team, 0.0);
            double zDef = zDefByTeam.getOrDefault(team, 0.0);
            double zGk = zGkByTeam.getOrDefault(team, 0.0);
            double zAtkPen = zAtkPenByTeam.getOrDefault(team, 0.0);
            double zSpThreat = zSpThreatByTeam.getOrDefault(team, 0.0);
            double zSpVuln = zSpVulnByTeam.getOrDefault(team, 0.0);
            double cov = (ea == null || ea.isEmpty()) ? 0.0
                    : eaWeights.coverage(ea.nRatedAsOf(team, asof).orElse(0));
            priorAttack += cov * (eaWeights.wOverall() * zOvr + eaWeights.wAtk() * zAtk
                    + eaWeights.wAtkPen() * zAtkPen + eaWeights.wSp() * zSpThreat);
            priorDefence += -cov * (eaWeights.wOverall() * zOvr + eaWeights.wDef() * zDef
                    + eaWeights.wGk() * zGk + eaWeights.wSp() * zSpVuln);

            double w = weights.shrinkageFor(matchCounts.getOrDefault(team, 0));
            attack.put(team, (1 - w) * fittedAttack + w * priorAttack);
            defence.put(team, (1 - w) * fittedDefence + w * priorDefence);
        }
        recenter(attack);
        recenter(defence);
        return new TeamStrength(fit.baseline(), fit.homeAdvantage(), fit.rho(), attack, defence);
    }

    /**
     * Standardises one EA rating aggregate, read via {@code column}, across the teams that have
     * it on or before {@code asof}. Returns a team to z-score map covering only the teams with a
     * present value; a team missing from the map, or an empty {@code ea} table, should be read
     * as a z-score of zero by the caller. Mirrors the market value standardisation in
     * {@link #adjustWithEa}: fewer than two present teams, or zero spread, yields an empty map.
     */
    private static Map<String, Double> standardiseEa(EaRatingsTable ea, LocalDate asof, EaColumn column) {
        Map<String, Double> z = new HashMap<>();
        if (ea == null || ea.isEmpty()) {
            return z;
        }
        Map<String, Double> present = new HashMap<>();
        double sum = 0.0;
        for (String team : ea.teamsWithRatingAsOf(asof)) {
            OptionalDouble v = column.of(ea, team, asof);
            if (v.isPresent()) {
                present.put(team, v.getAsDouble());
                sum += v.getAsDouble();
            }
        }
        if (present.size() < 2) {
            return z;
        }
        double mean = sum / present.size();
        double variance = 0.0;
        for (double val : present.values()) {
            variance += (val - mean) * (val - mean);
        }
        double sd = Math.sqrt(variance / present.size());
        if (sd <= 0) {
            return z;
        }
        for (Map.Entry<String, Double> e : present.entrySet()) {
            z.put(e.getKey(), (e.getValue() - mean) / sd);
        }
        return z;
    }

    /** One EA rating column accessor, so {@link #standardiseEa} can be reused across all four. */
    @FunctionalInterface
    private interface EaColumn {
        OptionalDouble of(EaRatingsTable ea, String team, LocalDate date);
    }

    /** Re-centre to mean zero so attack/defence stay identifiable against the baseline. */
    private static void recenter(Map<String, Double> ratings) {
        double sum = 0.0;
        for (double v : ratings.values()) {
            sum += v;
        }
        double mean = sum / ratings.size();
        ratings.replaceAll((k, v) -> v - mean);
    }
}
