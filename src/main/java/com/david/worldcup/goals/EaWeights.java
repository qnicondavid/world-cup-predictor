package com.david.worldcup.goals;

/**
 * How strongly each EA Sports FC squad rating aggregate pulls a team's attack and defence
 * ratings, on top of the market value prior in {@link ValueAdjuster#adjustWithEa}. Mirrors the
 * role {@link ValueWeights#valueScale} plays for market value: each weight maps a one standard
 * deviation gap in the standardised aggregate to that many log goals of effect.
 *
 * <p>All six weights default to zero via {@link #ZERO}, so the EA prior is opt-in and additive
 * only. It never changes {@link ValueAdjuster#adjust}.
 *
 * @param wOverall weight on the standardised top-26 mean overall (ovr_top26)
 * @param wAtk     weight on the standardised attack-side mean overall (atk_top)
 * @param wDef     weight on the standardised defence-side mean overall (def_top)
 * @param wGk      weight on the standardised best-goalkeeper overall (gk_top)
 * @param wAtkPen  weight on the standardised penetration composite (atk_pen), attack side only
 * @param wSp      shared weight on the set-piece pair: z(sp_threat) on attack, z(sp_vuln) on defence
 */
public record EaWeights(double wOverall, double wAtk, double wDef, double wGk, double wAtkPen,
                        double wSp) {

    /** No EA pull at all: every added term in {@link ValueAdjuster#adjustWithEa} is zero. */
    public static final EaWeights ZERO = new EaWeights(0, 0, 0, 0, 0, 0);

    /** Rated-squad size at or below which coverage is 0 (the aggregate builder's own floor). */
    private static final double COV_ZERO = 5;

    /** Rated-squad size at or above which coverage is 1 (a full, trustworthy snapshot). */
    private static final double COV_FULL = 15;

    /**
     * How much an EA snapshot with {@code nRated} rated squad players is trusted: 0 at or below
     * {@link #COV_ZERO} players, rising linearly to 1 at {@link #COV_FULL} players, clamped to
     * the range [0, 1] outside that band.
     */
    public double coverage(int nRated) {
        return Math.max(0.0, Math.min(1.0, (nRated - COV_ZERO) / (COV_FULL - COV_ZERO)));
    }
}
