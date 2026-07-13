package com.david.worldcup.sim;

import com.david.worldcup.elo.DrawModel;
import com.david.worldcup.elo.EloRatingSystem;
import com.david.worldcup.model.Fixture;
import com.david.worldcup.model.Match;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import java.util.TreeSet;

/**
 * Monte Carlo simulation of the remainder of the 2026 World Cup.
 *
 * <p>The simulator runs in one of two modes, chosen automatically from the
 * remaining fixtures:
 *
 * <ul>
 *   <li><b>Group stage</b> — when at least one team still has more than one
 *       remaining fixture. Each run replays the played group results, samples
 *       every remaining group fixture from the model's win/draw/loss
 *       probabilities, builds group standings, qualifies winners + runners-up +
 *       best thirds, then simulates a knockout bracket to a champion.</li>
 *   <li><b>Knockout stage</b> — when every team has at most one remaining
 *       fixture (single elimination). The remaining fixtures <em>are</em> the
 *       bracket, so groups are no longer inferred. Each run samples the bracket
 *       forward, round by round, to a champion.</li>
 * </ul>
 *
 * <p>Documented simplifications:
 * <ul>
 *   <li>Group composition (group-stage mode) is inferred from the fixture list
 *       (teams that play each other form a group) rather than hard-coded.</li>
 *   <li>Tie-breaks (group-stage mode) use points, then current Elo rating,
 *       instead of goal difference (outcomes are simulated, not scorelines).</li>
 *   <li>The knockout bracket tree is built by pairing the remaining fixtures and
 *       carried winners in schedule order (the dataset holds only the live
 *       frontier, not the full tree), which approximates FIFA's fixed bracket
 *       paths. A match already played carries its real winner forward. The
 *       frontier can straddle more than one bracket round, so it is flattened;
 *       when it is not a power of two it is reduced to one in a single play-in
 *       round so the field then passes cleanly through the semifinal (4) and
 *       final (2) stages.</li>
 *   <li>Knockout matches are treated as neutral-venue with no draws: the Elo
 *       expected score is used directly as the win probability, which folds
 *       extra time and penalties into a single number.</li>
 * </ul>
 */
public final class TournamentSimulator {

    private final EloRatingSystem elo;

    public record TeamOdds(String team, double titleShare, double finalShare, double semiShare) {}

    public TournamentSimulator(EloRatingSystem elo) {
        this.elo = elo;
    }

    /** Teams grouped by who plays whom in the group stage (connected components). */
    static List<Set<String>> inferGroups(List<Match> played, List<Fixture> remaining) {
        Map<String, Set<String>> adjacency = new HashMap<>();
        for (Match m : played) {
            adjacency.computeIfAbsent(m.homeTeam(), k -> new HashSet<>()).add(m.awayTeam());
            adjacency.computeIfAbsent(m.awayTeam(), k -> new HashSet<>()).add(m.homeTeam());
        }
        for (Fixture f : remaining) {
            adjacency.computeIfAbsent(f.homeTeam(), k -> new HashSet<>()).add(f.awayTeam());
            adjacency.computeIfAbsent(f.awayTeam(), k -> new HashSet<>()).add(f.homeTeam());
        }

        List<Set<String>> groups = new ArrayList<>();
        Set<String> visited = new HashSet<>();
        for (String team : new TreeSet<>(adjacency.keySet())) {
            if (visited.contains(team)) {
                continue;
            }
            Set<String> group = new TreeSet<>();
            List<String> stack = new ArrayList<>(List.of(team));
            while (!stack.isEmpty()) {
                String current = stack.remove(stack.size() - 1);
                if (!group.add(current)) {
                    continue;
                }
                stack.addAll(adjacency.getOrDefault(current, Set.of()));
            }
            visited.addAll(group);
            groups.add(group);
        }
        return groups;
    }

    /**
     * Knockout stage when every team appears in at most one remaining fixture
     * (single elimination). During the group stage teams have several remaining
     * fixtures, so this is false.
     */
    static boolean isKnockoutPhase(List<Fixture> remaining) {
        if (remaining.isEmpty()) {
            return false;
        }
        Map<String, Integer> appearances = new HashMap<>();
        for (Fixture f : remaining) {
            appearances.merge(f.homeTeam(), 1, Integer::sum);
            appearances.merge(f.awayTeam(), 1, Integer::sum);
        }
        return appearances.values().stream().allMatch(v -> v <= 1);
    }

    /** Runs {@code runs} simulations and returns per-team odds, best title odds first. */
    public List<TeamOdds> simulate(List<Match> playedGroupMatches,
                                   List<Fixture> remainingGroupFixtures,
                                   int runs, long seed) {
        Map<String, int[]> tally = new LinkedHashMap<>(); // {titles, finals, semis}
        for (Match m : playedGroupMatches) {
            tally.putIfAbsent(m.homeTeam(), new int[3]);
            tally.putIfAbsent(m.awayTeam(), new int[3]);
        }
        for (Fixture f : remainingGroupFixtures) {
            tally.putIfAbsent(f.homeTeam(), new int[3]);
            tally.putIfAbsent(f.awayTeam(), new int[3]);
        }

        Random random = new Random(seed);
        if (isKnockoutPhase(remainingGroupFixtures)) {
            List<String[]> slots = buildKnockoutSlots(playedGroupMatches, remainingGroupFixtures);
            for (int i = 0; i < runs; i++) {
                runKnockoutOnce(slots, random, tally);
            }
        } else {
            List<Set<String>> groups = inferGroups(playedGroupMatches, remainingGroupFixtures);
            for (Set<String> g : groups) {
                for (String t : g) {
                    tally.putIfAbsent(t, new int[3]);
                }
            }
            for (int i = 0; i < runs; i++) {
                runOnce(groups, playedGroupMatches, remainingGroupFixtures, random, tally);
            }
        }

        List<TeamOdds> odds = new ArrayList<>();
        for (var e : tally.entrySet()) {
            odds.add(new TeamOdds(e.getKey(),
                    (double) e.getValue()[0] / runs,
                    (double) e.getValue()[1] / runs,
                    (double) e.getValue()[2] / runs));
        }
        odds.sort(Comparator.comparingDouble(TeamOdds::titleShare).reversed());
        return odds;
    }

    // ---- Knockout stage ------------------------------------------------------

    /**
     * Builds the current knockout round as an ordered list of "slots". Each slot
     * is either a fixture still to be played ({@code [home, away]}) or a team that
     * already won its current-round match and is awaiting the next round
     * ({@code [team]}). Slots are ordered by date so pairing them sequentially
     * approximates the fixed bracket tree.
     */
    static List<String[]> buildKnockoutSlots(List<Match> played, List<Fixture> remaining) {
        Set<String> inRemaining = new HashSet<>();
        for (Fixture f : remaining) {
            inRemaining.add(f.homeTeam());
            inRemaining.add(f.awayTeam());
        }

        Map<String, Integer> games = new HashMap<>();
        Map<String, Match> lastMatch = new HashMap<>();
        for (Match m : played) {
            for (String t : List.of(m.homeTeam(), m.awayTeam())) {
                games.merge(t, 1, Integer::sum);
                Match prev = lastMatch.get(t);
                if (prev == null || m.date().isAfter(prev.date())) {
                    lastMatch.put(t, m);
                }
            }
        }

        record Slot(LocalDate date, String[] teams) {}
        List<Slot> ordered = new ArrayList<>();

        // Carries: a team that has progressed past the group stage (>3 matches),
        // won its latest match, and has no scheduled fixture is a pending winner.
        for (Map.Entry<String, Integer> e : games.entrySet()) {
            String t = e.getKey();
            if (inRemaining.contains(t) || e.getValue() <= 3) {
                continue;
            }
            Match lm = lastMatch.get(t);
            boolean won = (lm.homeTeam().equals(t) && lm.outcome() == Match.Outcome.HOME_WIN)
                    || (lm.awayTeam().equals(t) && lm.outcome() == Match.Outcome.AWAY_WIN);
            if (won) {
                ordered.add(new Slot(lm.date(), new String[] {t}));
            }
        }
        for (Fixture f : remaining) {
            ordered.add(new Slot(f.date(), new String[] {f.homeTeam(), f.awayTeam()}));
        }
        ordered.sort(Comparator.comparing(Slot::date));

        List<String[]> slots = new ArrayList<>();
        for (Slot s : ordered) {
            slots.add(s.teams());
        }
        return slots;
    }

    private void runKnockoutOnce(List<String[]> slots, Random random, Map<String, int[]> tally) {
        // Every team in the starting frontier has, by definition, already reached
        // the round that frontier represents. The stage loop below only tallies
        // rounds reached AFTER this frontier is played out, so it misses the
        // frontier's own round: when the remaining fixtures already are the two
        // semifinals, playing them yields a field of two (the finalists) and the
        // "round.size() == 4" branch never fires, leaving every semiShare at zero.
        // Credit the frontier up front using the same field-size-to-stage mapping,
        // so the starting round is counted whichever round the simulation begins
        // from. Larger starting fields (round of 16, quarterfinals, ...) have no
        // dedicated stage slot, so they fall through and those runs are unchanged.
        Set<String> frontier = new HashSet<>();
        for (String[] s : slots) {
            for (String t : s) {
                frontier.add(t);
            }
        }
        if (frontier.size() == 4) {
            frontier.forEach(t -> tally.get(t)[2]++);
        } else if (frontier.size() == 2) {
            frontier.forEach(t -> tally.get(t)[1]++);
        }

        List<String> round = new ArrayList<>();
        for (String[] s : slots) {
            round.add(s.length == 1 ? s[0] : play(s[0], s[1], random));
        }
        if (round.isEmpty()) {
            return;
        }
        // If the field is not a power of two, resolve the surplus in a single
        // play-in round so it collapses to the nearest power of two at once.
        // Every later round then halves cleanly and passes through exactly four
        // (semifinalists) and two (finalists). Halving from an odd count with a
        // trailing bye — the previous behaviour — could step 11 -> 6 -> 3 -> 2 -> 1
        // and skip 4 entirely, which is why the semifinal tally stayed at zero.
        // Byes go to the trailing slots, and slots are in schedule order rather than
        // strength-seeded, so which teams sit out the play-in is arbitrary: a small,
        // documented approximation in the same spirit as the schedule-order bracket.
        int pow2 = Integer.highestOneBit(round.size());
        if (pow2 < round.size()) {
            int playIn = 2 * (round.size() - pow2); // leading teams contest the extra round
            List<String> next = new ArrayList<>();
            for (int i = 0; i + 1 < playIn; i += 2) {
                next.add(play(round.get(i), round.get(i + 1), random));
            }
            for (int i = playIn; i < round.size(); i++) {
                next.add(round.get(i)); // seeded bye into the clean bracket
            }
            round = next;
        }
        while (round.size() > 1) {
            if (round.size() == 4) {
                round.forEach(t -> tally.get(t)[2]++);
            }
            if (round.size() == 2) {
                round.forEach(t -> tally.get(t)[1]++);
            }
            List<String> next = new ArrayList<>();
            for (int i = 0; i + 1 < round.size(); i += 2) {
                next.add(play(round.get(i), round.get(i + 1), random));
            }
            round = next;
        }
        tally.get(round.get(0))[0]++;
    }

    /** Samples a single knockout match (neutral venue, no draws) from the Elo gap. */
    private String play(String a, String b, Random random) {
        return random.nextDouble() < elo.winProbability(a, b, true) ? a : b;
    }

    // ---- Group stage ---------------------------------------------------------

    private void runOnce(List<Set<String>> groups, List<Match> played,
                         List<Fixture> remaining, Random random, Map<String, int[]> tally) {
        Map<String, Integer> points = new HashMap<>();

        for (Match m : played) {
            applyResult(points, m.homeTeam(), m.awayTeam(), switch (m.outcome()) {
                case HOME_WIN -> 0;
                case DRAW -> 1;
                case AWAY_WIN -> 2;
            });
        }
        for (Fixture f : remaining) {
            DrawModel.Probabilities p =
                    elo.outcomeProbabilities(f.homeTeam(), f.awayTeam(), f.neutralVenue());
            double roll = random.nextDouble();
            int outcome = roll < p.homeWin() ? 0 : (roll < p.homeWin() + p.draw() ? 1 : 2);
            applyResult(points, f.homeTeam(), f.awayTeam(), outcome);
        }

        // Rank each group: points, then current Elo (tie-break simplification).
        Comparator<String> byStrength = Comparator
                .comparingInt((String t) -> points.getOrDefault(t, 0)).reversed()
                .thenComparing(Comparator.comparingDouble(elo::ratingOf).reversed())
                .thenComparing(Comparator.naturalOrder());

        List<String> winners = new ArrayList<>();
        List<String> runners = new ArrayList<>();
        List<String> thirds = new ArrayList<>();
        for (Set<String> group : groups) {
            List<String> ranked = new ArrayList<>(group);
            ranked.sort(byStrength);
            winners.add(ranked.get(0));
            runners.add(ranked.get(1));
            if (ranked.size() > 2) {
                thirds.add(ranked.get(2));
            }
        }
        winners.sort(byStrength);
        runners.sort(byStrength);
        thirds.sort(byStrength);

        // Qualifiers: winners, runners-up, then best thirds until a power of two.
        List<String> seeds = new ArrayList<>(winners);
        seeds.addAll(runners);
        int target = Integer.highestOneBit(seeds.size()) == seeds.size()
                ? seeds.size()
                : Integer.highestOneBit(seeds.size()) * 2;
        for (String third : thirds) {
            if (seeds.size() >= target) {
                break;
            }
            seeds.add(third);
        }

        simulateKnockout(seeds, random, tally);
    }

    private void simulateKnockout(List<String> seeds, Random random, Map<String, int[]> tally) {
        List<String> alive = seeds;
        while (alive.size() > 1) {
            if (alive.size() == 4) {
                alive.forEach(t -> tally.get(t)[2]++);
            }
            if (alive.size() == 2) {
                alive.forEach(t -> tally.get(t)[1]++);
            }
            List<String> next = new ArrayList<>();
            for (int i = 0; i < alive.size() / 2; i++) {
                String a = alive.get(i);
                String b = alive.get(alive.size() - 1 - i);
                double pA = elo.winProbability(a, b, true);
                next.add(random.nextDouble() < pA ? a : b);
            }
            alive = next;
        }
        tally.get(alive.get(0))[0]++;
    }

    private static void applyResult(Map<String, Integer> points,
                                    String home, String away, int outcome) {
        points.merge(home, outcome == 0 ? 3 : (outcome == 1 ? 1 : 0), Integer::sum);
        points.merge(away, outcome == 2 ? 3 : (outcome == 1 ? 1 : 0), Integer::sum);
    }
}
