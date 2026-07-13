package com.david.worldcup.data;

import com.david.worldcup.model.Fixture;
import com.david.worldcup.model.Match;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * Parses the international results CSV from
 * https://github.com/martj42/international_results
 *
 * <p>Expected columns:
 * {@code date,home_team,away_team,home_score,away_score,tournament,city,country,neutral}
 *
 * <p>Rows with numeric scores are completed matches ({@link Match}); rows with
 * {@code NA} scores are scheduled fixtures ({@link Fixture}).
 */
public final class MatchCsvParser {

    private static final int EXPECTED_COLUMNS = 9;

    /** All completed matches; unplayed fixtures and malformed rows are skipped. */
    public List<Match> parse(Path csvFile) throws IOException {
        List<Match> matches = new ArrayList<>();
        try (BufferedReader reader = Files.newBufferedReader(csvFile)) {
            String header = reader.readLine(); // skip header row
            if (header == null) {
                return matches;
            }
            String line;
            while ((line = reader.readLine()) != null) {
                parseLine(line).ifPresent(matches::add);
            }
        }
        return matches;
    }

    /** All scheduled-but-unplayed fixtures (rows with non-numeric scores). */
    public List<Fixture> parseFixtures(Path csvFile) throws IOException {
        List<Fixture> fixtures = new ArrayList<>();
        try (BufferedReader reader = Files.newBufferedReader(csvFile)) {
            String header = reader.readLine();
            if (header == null) {
                return fixtures;
            }
            String line;
            while ((line = reader.readLine()) != null) {
                parseFixtureLine(line).ifPresent(fixtures::add);
            }
        }
        return fixtures;
    }

    /**
     * Parses one CSV row into a {@link Match}, or {@link Optional#empty()} if the
     * row is malformed or represents an unplayed fixture.
     */
    static Optional<Match> parseLine(String line) {
        List<String> fields = splitCsvLine(line);
        if (fields.size() < EXPECTED_COLUMNS) {
            return Optional.empty();
        }
        try {
            return Optional.of(new Match(
                    LocalDate.parse(fields.get(0)),
                    fields.get(1),
                    fields.get(2),
                    Integer.parseInt(fields.get(3)),
                    Integer.parseInt(fields.get(4)),
                    fields.get(5),
                    Boolean.parseBoolean(fields.get(8))));
        } catch (NumberFormatException | DateTimeParseException e) {
            // "NA" scores = future fixture; bad date = malformed row. Skip both.
            return Optional.empty();
        }
    }

    /** Parses one CSV row into a {@link Fixture} if it is a valid unplayed match. */
    static Optional<Fixture> parseFixtureLine(String line) {
        List<String> fields = splitCsvLine(line);
        if (fields.size() < EXPECTED_COLUMNS) {
            return Optional.empty();
        }
        try {
            LocalDate date = LocalDate.parse(fields.get(0));
            if (isInteger(fields.get(3)) && isInteger(fields.get(4))) {
                return Optional.empty(); // has a score, so it's a result not a fixture
            }
            String home = fields.get(1);
            String away = fields.get(2);
            if (isPlaceholderTeam(home) || isPlaceholderTeam(away)) {
                // Undecided knockout fixtures (the final and third-place playoff) are
                // seeded "NA" until the semifinals are played. Skip them: the model
                // cannot rate a team that does not exist yet.
                return Optional.empty();
            }
            return Optional.of(new Fixture(
                    date, home, away, fields.get(5),
                    Boolean.parseBoolean(fields.get(8))));
        } catch (DateTimeParseException e) {
            return Optional.empty();
        }
    }

    private static boolean isInteger(String s) {
        try {
            Integer.parseInt(s);
            return true;
        } catch (NumberFormatException e) {
            return false;
        }
    }

    /** martj42 seeds not-yet-decided fixtures (final, third place) with "NA" team names. */
    private static boolean isPlaceholderTeam(String team) {
        return team == null || team.isBlank() || team.equalsIgnoreCase("NA");
    }

    /**
     * Minimal quote-aware CSV field splitter. Handles fields like
     * {@code "Washington, D.C."} that contain commas inside double quotes.
     */
    public static List<String> splitCsvLine(String line) {
        List<String> fields = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        boolean inQuotes = false;
        for (int i = 0; i < line.length(); i++) {
            char c = line.charAt(i);
            if (c == '"') {
                inQuotes = !inQuotes;
            } else if (c == ',' && !inQuotes) {
                fields.add(current.toString());
                current.setLength(0);
            } else {
                current.append(c);
            }
        }
        fields.add(current.toString());
        return fields;
    }
}
