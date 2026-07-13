package com.david.worldcup.value;

import com.david.worldcup.data.MatchCsvParser;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.NavigableMap;
import java.util.OptionalDouble;
import java.util.OptionalInt;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

/**
 * Per-team EA Sports FC squad rating aggregates over time, read from a CSV with columns
 * {@code team,as_of,n_rated,ovr_top26,atk_top,def_top,gk_top,age_mean}. Mirrors
 * {@link MarketValueTable}: multiple dated rows per team are allowed, and every as-of lookup
 * returns the most recent row on or before the queried date, never a future one, so a backtest
 * cannot leak information.
 *
 * <p>Sub-aggregate cells ({@code atk_top}, {@code def_top}, {@code gk_top}, {@code age_mean})
 * can be empty strings when a squad snapshot lacks enough players in that group. Those cells are
 * stored as {@code Double.NaN} and every lookup treats NaN the same as absent. {@code age_mean}
 * is ignored; the five original aggregate columns plus the penetration composite
 * ({@code atk_pen}, the 14th field) are kept.
 *
 * <p>The source data (per-edition player ratings) is aggregated into per-squad totals out of
 * band; this class only consumes the result. If the file is missing the table is simply empty
 * and every lookup returns empty, so the rest of the model degrades gracefully to its EA-free
 * behaviour.
 */
public final class EaRatingsTable {

    private static final int IDX_N_RATED = 0;
    private static final int IDX_OVR = 1;
    private static final int IDX_ATK = 2;
    private static final int IDX_DEF = 3;
    private static final int IDX_GK = 4;
    private static final int IDX_ATK_PEN = 5;
    private static final int IDX_SP_THREAT = 6;
    private static final int IDX_SP_VULN = 7;

    private final Map<String, NavigableMap<LocalDate, double[]>> byTeam;

    private EaRatingsTable(Map<String, NavigableMap<LocalDate, double[]>> byTeam) {
        this.byTeam = byTeam;
    }

    public static EaRatingsTable load(Path file) throws IOException {
        Map<String, NavigableMap<LocalDate, double[]>> byTeam = new HashMap<>();
        if (!Files.exists(file)) {
            return new EaRatingsTable(byTeam);
        }
        List<String> lines = Files.readAllLines(file);
        for (String line : lines.subList(Math.min(1, lines.size()), lines.size())) {
            if (line.isBlank()) {
                continue;
            }
            List<String> f = MatchCsvParser.splitCsvLine(line);
            if (f.size() < 7) {
                continue;
            }
            try {
                String team = f.get(0).trim();
                LocalDate asOf = LocalDate.parse(f.get(1).trim());
                double[] row = new double[] {
                        parseCellOrNaN(f.get(2)),
                        parseCellOrNaN(f.get(3)),
                        parseCellOrNaN(f.get(4)),
                        parseCellOrNaN(f.get(5)),
                        parseCellOrNaN(f.get(6)),
                        f.size() > 13 ? parseCellOrNaN(f.get(13)) : Double.NaN,
                        f.size() > 9 ? parseCellOrNaN(f.get(9)) : Double.NaN,
                        f.size() > 10 ? parseCellOrNaN(f.get(10)) : Double.NaN,
                };
                byTeam.computeIfAbsent(team, k -> new TreeMap<>()).put(asOf, row);
            } catch (DateTimeParseException ignored) {
                // skip malformed rows
            }
        }
        return new EaRatingsTable(byTeam);
    }

    /** Parses a numeric CSV cell, treating a blank or unparsable cell as absent (NaN). */
    private static double parseCellOrNaN(String s) {
        String t = s == null ? "" : s.trim();
        if (t.isEmpty()) {
            return Double.NaN;
        }
        try {
            return Double.parseDouble(t);
        } catch (NumberFormatException e) {
            return Double.NaN;
        }
    }

    public boolean isEmpty() {
        return byTeam.isEmpty();
    }

    private OptionalDouble columnAsOf(String team, LocalDate date, int column) {
        NavigableMap<LocalDate, double[]> history = byTeam.get(team);
        if (history == null) {
            return OptionalDouble.empty();
        }
        Map.Entry<LocalDate, double[]> entry = history.floorEntry(date);
        if (entry == null) {
            return OptionalDouble.empty();
        }
        double value = entry.getValue()[column];
        return Double.isNaN(value) ? OptionalDouble.empty() : OptionalDouble.of(value);
    }

    /** Most recent mean top-26 overall (ovr_top26) for {@code team} on or before {@code date}, if any. */
    public OptionalDouble ovrAsOf(String team, LocalDate date) {
        return columnAsOf(team, date, IDX_OVR);
    }

    /** Most recent mean attack-side (forwards plus midfielders) overall, if any. */
    public OptionalDouble atkAsOf(String team, LocalDate date) {
        return columnAsOf(team, date, IDX_ATK);
    }

    /** Most recent mean defence-side (defenders plus goalkeepers) overall, if any. */
    public OptionalDouble defAsOf(String team, LocalDate date) {
        return columnAsOf(team, date, IDX_DEF);
    }

    /** Most recent best-goalkeeper overall, if any. */
    public OptionalDouble gkAsOf(String team, LocalDate date) {
        return columnAsOf(team, date, IDX_GK);
    }

    /** Most recent penetration composite (atk_pen, the 14th CSV field), if any. */
    public OptionalDouble atkPenAsOf(String team, LocalDate date) {
        return columnAsOf(team, date, IDX_ATK_PEN);
    }

    /** Most recent set-piece attacking threat composite (sp_threat, the 10th CSV field), if any. */
    public OptionalDouble spThreatAsOf(String team, LocalDate date) {
        return columnAsOf(team, date, IDX_SP_THREAT);
    }

    /** Most recent set-piece defensive vulnerability composite (sp_vuln, the 11th CSV field), if any. */
    public OptionalDouble spVulnAsOf(String team, LocalDate date) {
        return columnAsOf(team, date, IDX_SP_VULN);
    }

    /** Most recent rated-squad size for {@code team} on or before {@code date}, if any. */
    public OptionalInt nRatedAsOf(String team, LocalDate date) {
        OptionalDouble n = columnAsOf(team, date, IDX_N_RATED);
        return n.isPresent() ? OptionalInt.of((int) Math.round(n.getAsDouble())) : OptionalInt.empty();
    }

    /** Teams that have at least one EA rating snapshot on or before {@code date}. */
    public Set<String> teamsWithRatingAsOf(LocalDate date) {
        Set<String> teams = new TreeSet<>();
        for (Map.Entry<String, NavigableMap<LocalDate, double[]>> e : byTeam.entrySet()) {
            if (e.getValue().floorEntry(date) != null) {
                teams.add(e.getKey());
            }
        }
        return teams;
    }
}
