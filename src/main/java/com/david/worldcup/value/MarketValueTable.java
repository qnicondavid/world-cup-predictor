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
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

/**
 * Squad market values per national team over time, read from a CSV with columns
 * {@code team,as_of,value_eur}. Multiple dated rows per team are allowed, so the
 * same file serves both a single current snapshot (for live 2026 predictions)
 * and historical snapshots (for backtesting): {@link #valueAsOf} always returns
 * the most recent value on or before the queried date — never a future one,
 * which would leak information into a backtest.
 *
 * <p>The source data (player-level valuations from Transfermarkt) is aggregated
 * into per-squad totals out of band; this class only consumes the result. If the
 * file is missing the table is simply empty and every lookup returns empty, so
 * the rest of the model degrades gracefully to its value-free behaviour.
 */
public final class MarketValueTable {

    private final Map<String, NavigableMap<LocalDate, Double>> byTeam;

    private MarketValueTable(Map<String, NavigableMap<LocalDate, Double>> byTeam) {
        this.byTeam = byTeam;
    }

    public static MarketValueTable load(Path file) throws IOException {
        Map<String, NavigableMap<LocalDate, Double>> byTeam = new HashMap<>();
        if (!Files.exists(file)) {
            return new MarketValueTable(byTeam);
        }
        List<String> lines = Files.readAllLines(file);
        for (String line : lines.subList(Math.min(1, lines.size()), lines.size())) {
            if (line.isBlank()) {
                continue;
            }
            List<String> f = MatchCsvParser.splitCsvLine(line);
            if (f.size() < 3) {
                continue;
            }
            try {
                String team = f.get(0).trim();
                LocalDate asOf = LocalDate.parse(f.get(1).trim());
                double value = Double.parseDouble(f.get(2).trim());
                byTeam.computeIfAbsent(team, k -> new TreeMap<>()).put(asOf, value);
            } catch (NumberFormatException | DateTimeParseException ignored) {
                // skip malformed rows
            }
        }
        return new MarketValueTable(byTeam);
    }

    public boolean isEmpty() {
        return byTeam.isEmpty();
    }

    /** Most recent squad value for {@code team} on or before {@code date}, if any. */
    public OptionalDouble valueAsOf(String team, LocalDate date) {
        NavigableMap<LocalDate, Double> history = byTeam.get(team);
        if (history == null) {
            return OptionalDouble.empty();
        }
        Map.Entry<LocalDate, Double> entry = history.floorEntry(date);
        return entry == null ? OptionalDouble.empty() : OptionalDouble.of(entry.getValue());
    }

    /** The most recent as-of date on record for {@code team}, or empty if the team is absent.
     *  Lets callers flag a team whose squad value has not been refreshed in a long time. */
    public java.util.Optional<LocalDate> latestAsOf(String team) {
        NavigableMap<LocalDate, Double> history = byTeam.get(team);
        return (history == null || history.isEmpty())
                ? java.util.Optional.empty() : java.util.Optional.of(history.lastKey());
    }

    /** Teams that have at least one valuation on or before {@code date}. */
    public Set<String> teamsWithValueAsOf(LocalDate date) {
        Set<String> teams = new TreeSet<>();
        for (Map.Entry<String, NavigableMap<LocalDate, Double>> e : byTeam.entrySet()) {
            if (e.getValue().floorEntry(date) != null) {
                teams.add(e.getKey());
            }
        }
        return teams;
    }
}
