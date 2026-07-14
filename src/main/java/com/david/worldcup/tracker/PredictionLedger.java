package com.david.worldcup.tracker;

import com.david.worldcup.data.MatchCsvParser;
import com.david.worldcup.elo.DrawModel;
import com.david.worldcup.model.Match;

import java.io.IOException;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Persistent record of predictions, stored as CSV and committed to git.
 *
 * <p>This file is the project's honesty mechanism: a prediction is appended
 * ("locked") before the match is played and never modified afterwards, so the
 * git history proves every prediction predates its result.
 *
 * <p>Each prediction stores an explicit win/draw/loss split and, when the
 * locking model is a goal model, the expected goals for each side (so the
 * predicted scoreline is locked too). The CSV is read backward-compatibly:
 * <ul>
 *   <li>6 columns — the original Elo schema (a single {@code p_home} expected
 *       score); expanded into a split via the deterministic {@link DrawModel}.</li>
 *   <li>8 columns — win/draw/loss with no expected goals.</li>
 *   <li>10 columns — win/draw/loss plus expected goals.</li>
 * </ul>
 * Missing expected goals are stored as blank and read back as {@code NaN}.
 */
public final class PredictionLedger {

    private static final String HEADER =
            "match_date,home_team,away_team,neutral,p_home,p_draw,p_away,xg_home,xg_away,locked_on";

    private static final int LEGACY_COLUMNS = 6;   // ...,p_home,locked_on
    private static final int THREE_WAY_COLUMNS = 8; // ...,p_home,p_draw,p_away,locked_on

    /**
     * @param matchDate    date of the predicted match
     * @param homeTeam     first-listed team
     * @param awayTeam     second-listed team
     * @param neutralVenue venue flag used for the prediction
     * @param pHome        locked probability of a home win
     * @param pDraw        locked probability of a draw
     * @param pAway        locked probability of an away win
     * @param xgHome       locked expected goals for the home side ({@code NaN} if not modelled)
     * @param xgAway       locked expected goals for the away side ({@code NaN} if not modelled)
     * @param lockedOn     date the prediction was locked
     */
    public record Prediction(
            LocalDate matchDate,
            String homeTeam,
            String awayTeam,
            boolean neutralVenue,
            double pHome,
            double pDraw,
            double pAway,
            double xgHome,
            double xgAway,
            LocalDate lockedOn) {

        /** Three-way constructor without expected goals. */
        public Prediction(LocalDate matchDate, String homeTeam, String awayTeam,
                          boolean neutralVenue, double pHome, double pDraw, double pAway,
                          LocalDate lockedOn) {
            this(matchDate, homeTeam, awayTeam, neutralVenue,
                    pHome, pDraw, pAway, Double.NaN, Double.NaN, lockedOn);
        }

        /**
         * Legacy binary constructor: expands a single locked win probability (the
         * Elo expected score {@code E = P(win) + P(draw)/2}) into a win/draw/loss
         * split via the deterministic {@link DrawModel}. The locked expected score
         * is preserved exactly ({@code pHome + pDraw/2}).
         */
        public Prediction(LocalDate matchDate, String homeTeam, String awayTeam,
                          boolean neutralVenue, double expectedScore, LocalDate lockedOn) {
            this(matchDate, homeTeam, awayTeam, neutralVenue, expand(expectedScore), lockedOn);
        }

        private Prediction(LocalDate matchDate, String homeTeam, String awayTeam,
                           boolean neutralVenue, DrawModel.Probabilities split, LocalDate lockedOn) {
            this(matchDate, homeTeam, awayTeam, neutralVenue,
                    split.homeWin(), split.draw(), split.awayWin(), Double.NaN, Double.NaN, lockedOn);
        }

        /** Whether a goal-model expected score was locked with this prediction. */
        public boolean hasExpectedGoals() {
            return !Double.isNaN(xgHome) && !Double.isNaN(xgAway);
        }

        /** The model's single most likely outcome. */
        public Match.Outcome predictedOutcome() {
            if (pDraw >= pHome && pDraw >= pAway) {
                return Match.Outcome.DRAW;
            }
            return pHome >= pAway ? Match.Outcome.HOME_WIN : Match.Outcome.AWAY_WIN;
        }

        /** Human-readable pick: a team name, or "Draw". */
        public String pick() {
            return switch (predictedOutcome()) {
                case HOME_WIN -> homeTeam;
                case AWAY_WIN -> awayTeam;
                case DRAW -> "Draw";
            };
        }

        /** Probability assigned to {@link #pick()} (the largest of the three). */
        public double pickProbability() {
            return Math.max(pHome, Math.max(pDraw, pAway));
        }

        private static DrawModel.Probabilities expand(double expectedScore) {
            double e = Math.max(1e-9, Math.min(1.0 - 1e-9, expectedScore));
            double effectiveGap = 400.0 * Math.log10(e / (1.0 - e));
            return DrawModel.split(e, effectiveGap);
        }
    }

    public static List<Prediction> load(Path file) throws IOException {
        List<Prediction> predictions = new ArrayList<>();
        if (!Files.exists(file)) {
            return predictions;
        }
        List<String> lines = Files.readAllLines(file);
        for (String line : lines.subList(Math.min(1, lines.size()), lines.size())) {
            if (line.isBlank()) {
                continue;
            }
            predictions.add(parse(MatchCsvParser.splitCsvLine(line)));
        }
        return predictions;
    }

    private static Prediction parse(List<String> f) {
        LocalDate date = LocalDate.parse(f.get(0));
        String home = f.get(1);
        String away = f.get(2);
        boolean neutral = Boolean.parseBoolean(f.get(3));
        if (f.size() <= LEGACY_COLUMNS) {
            return new Prediction(date, home, away, neutral,
                    Double.parseDouble(f.get(4)), LocalDate.parse(f.get(5)));
        }
        if (f.size() <= THREE_WAY_COLUMNS) {
            return new Prediction(date, home, away, neutral,
                    Double.parseDouble(f.get(4)), Double.parseDouble(f.get(5)),
                    Double.parseDouble(f.get(6)), LocalDate.parse(f.get(7)));
        }
        return new Prediction(date, home, away, neutral,
                Double.parseDouble(f.get(4)), Double.parseDouble(f.get(5)),
                Double.parseDouble(f.get(6)), parseGoals(f.get(7)), parseGoals(f.get(8)),
                LocalDate.parse(f.get(9)));
    }

    private static double parseGoals(String s) {
        return s.isBlank() ? Double.NaN : Double.parseDouble(s);
    }

    public static void save(Path file, List<Prediction> predictions) throws IOException {
        if (file.getParent() != null) {
            Files.createDirectories(file.getParent());
        }
        StringBuilder sb = new StringBuilder(HEADER).append('\n');
        for (Prediction p : predictions) {
            sb.append(String.join(",",
                    p.matchDate().toString(),
                    p.homeTeam(),
                    p.awayTeam(),
                    String.valueOf(p.neutralVenue()),
                    String.format(Locale.ROOT, "%.4f", p.pHome()),
                    String.format(Locale.ROOT, "%.4f", p.pDraw()),
                    String.format(Locale.ROOT, "%.4f", p.pAway()),
                    goals(p.xgHome()),
                    goals(p.xgAway()),
                    p.lockedOn().toString())).append('\n');
        }
        writeStringAtomic(file, sb.toString());
    }

    /**
     * Write {@code content} to {@code target} atomically: to a sibling temp file in the same
     * directory, then renamed over the target, so a reader (or a cloud sync client such as
     * OneDrive) never observes a half-written ledger. Falls back to a plain replace only if the
     * filesystem refuses an atomic move; even then the content is complete before the move, so no
     * truncated ledger is ever exposed. Mirrors {@code Main.writeStringAtomic}.
     */
    private static void writeStringAtomic(Path target, String content) throws IOException {
        Path dir = target.toAbsolutePath().getParent();
        Files.createDirectories(dir);
        Path tmp = Files.createTempFile(dir, target.getFileName().toString() + ".", ".tmp");
        try {
            Files.writeString(tmp, content);
            try {
                Files.move(tmp, target,
                        StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
            } catch (AtomicMoveNotSupportedException e) {
                Files.move(tmp, target, StandardCopyOption.REPLACE_EXISTING);
            }
        } finally {
            Files.deleteIfExists(tmp);
        }
    }

    private static String goals(double value) {
        return Double.isNaN(value) ? "" : String.format(Locale.ROOT, "%.4f", value);
    }

    private PredictionLedger() {
    }
}
