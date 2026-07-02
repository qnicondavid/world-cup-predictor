package com.david.worldcup.elo;

/**
 * Splits the Elo expected score into explicit win / draw / loss probabilities.
 *
 * <p>The Elo expected score E conflates winning with drawing: E = P(win) + P(draw)/2.
 * To unpick it we need P(draw), estimated empirically by replaying the post-1980
 * internationals through this very Elo model: the draw rate falls from ~30% between
 * equal teams to ~2% at a 600-point effective rating gap. The table below holds that
 * curve per 50-point gap bin, rounded to three decimals and lightly smoothed in the
 * sparse high-gap bins, so it is not a bit-exact snapshot of the raw rates. Run
 * {@code --draw-curve} to reprint the observed rates from a fresh replay: it
 * reproduces this curve in shape to within ~0.015 (the gap is sampling noise in the
 * thin 500-600 bins) over the ~37,400 post-1980 internationals in the current
 * dataset (37,394 at the latest count; it grows as the dataset does). Lookups
 * interpolate linearly between bins.
 *
 * <p>Given P(draw), the split is: P(win) = E − P(draw)/2, P(loss) = 1 − P(win) − P(draw),
 * with clamping so nothing goes negative for extreme gaps.
 */
public final class DrawModel {

    /**
     * Observed draw rates at gap = 0, 50, 100, ... 600 (internationals since 1980).
     *
     * <p>DUPLICATED literal — must stay identical to {@code DRAW_RATE} in
     * {@code research/goal_models.py}. Regenerate/verify both from the dataset with the CLI
     * {@code mvn compile exec:java -Dexec.args="--draw-curve"} (see {@code Main.runDrawCurve}),
     * which reprints this curve from a fresh Elo replay so the two copies can't silently drift.
     */
    private static final double[] DRAW_RATE_BY_GAP = {
            0.299, 0.289, 0.270, 0.252, 0.243, 0.200, 0.181,
            0.150, 0.125, 0.102, 0.076, 0.041, 0.022
    };
    private static final double BIN_WIDTH = 50.0;

    public record Probabilities(double homeWin, double draw, double awayWin) {

        public Probabilities {
            double sum = homeWin + draw + awayWin;
            if (Math.abs(sum - 1.0) > 1e-9) {
                throw new IllegalArgumentException("probabilities sum to " + sum);
            }
        }
    }

    /** Empirical P(draw) for a given effective rating gap (sign is ignored). */
    public static double drawProbability(double ratingGap) {
        double gap = Math.abs(ratingGap);
        double maxGap = (DRAW_RATE_BY_GAP.length - 1) * BIN_WIDTH;
        if (gap >= maxGap) {
            return DRAW_RATE_BY_GAP[DRAW_RATE_BY_GAP.length - 1];
        }
        int bin = (int) (gap / BIN_WIDTH);
        double t = (gap - bin * BIN_WIDTH) / BIN_WIDTH;
        return DRAW_RATE_BY_GAP[bin] * (1 - t) + DRAW_RATE_BY_GAP[bin + 1] * t;
    }

    /**
     * Win/draw/loss probabilities for the home side, given the Elo expected
     * score and the effective rating gap it was computed from.
     */
    public static Probabilities split(double expectedScore, double ratingGap) {
        double pDraw = drawProbability(ratingGap);
        double pWin = expectedScore - pDraw / 2.0;
        pWin = Math.max(0.0, Math.min(1.0 - pDraw, pWin));
        return new Probabilities(pWin, pDraw, 1.0 - pDraw - pWin);
    }

    private DrawModel() {
    }
}
