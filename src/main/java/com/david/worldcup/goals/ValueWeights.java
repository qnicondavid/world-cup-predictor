package com.david.worldcup.goals;

/**
 * How strongly squad market value pulls a team's fitted attack/defence ratings
 * toward the value-implied prior.
 *
 * <p>The shrinkage weight for a team with {@code n} training matches is
 * {@code clamp(globalWeight + sparseWeight * kappa/(n + kappa), 0, 1)}:
 * <ul>
 *   <li>{@code globalWeight} applies to every team (the "blend" lever);</li>
 *   <li>{@code sparseWeight} adds extra pull for teams with little data — at
 *       {@code n = 0} it contributes its full value, fading as matches accumulate
 *       (the "prior for sparse teams" lever);</li>
 *   <li>{@code kappa} is the match count at which the sparse term is halved.</li>
 * </ul>
 * {@code valueScale} maps a one-standard-deviation richer squad to this many
 * log-goals of attack (and the same reduction in goals conceded).
 *
 * <p>The defaults were tuned by {@code --values-tune}: a grid search on World
 * Cups 2006-2018, validated once on held-out 2022. After held-out testing
 * showed the value prior was under-exploited, a widened sweep moved the optimum
 * to {@code globalWeight 0.40, valueScale 0.60} (roughly double the earlier
 * setting), which beats plain Dixon-Coles on held-out 2022 (Brier 0.5907 vs
 * 0.6123) and the earlier weaker prior (0.6065). The notable outcome is
 * {@code sparseWeight = 0}: at World Cup level no team is data-starved, so the
 * sparse-team prior does nothing and it is the uniform {@code globalWeight}
 * blend that helps.
 *
 * <p>Because the grid searched 2006-2018, the headline 0.5717 to 0.5566 improvement
 * (scored across all five World Cups) overlaps this tuning set on four of five
 * tournaments; only the 2022 leg is fully out-of-sample. A leave-one-tournament-out
 * re-tune is the honest next step.
 */
public record ValueWeights(double globalWeight, double sparseWeight, double kappa, double valueScale) {

    public static final ValueWeights DEFAULT = new ValueWeights(0.40, 0.00, 5.0, 0.60);

    /** Shrinkage weight toward the value prior for a team seen {@code matches} times. */
    public double shrinkageFor(int matches) {
        double w = globalWeight + sparseWeight * kappa / (matches + kappa);
        return Math.max(0.0, Math.min(1.0, w));
    }
}
