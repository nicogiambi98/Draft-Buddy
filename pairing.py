"""Pairings and standings logic.

This module implements Swiss-style standings and round pairings used by the app.
It queries the shared DB connection (db.DB) and never mutates UI state directly.
All algorithms are intentionally simple and predictable for small local events.

Note: Only documentation has been added; functionality remains unchanged.
"""
from typing import List, Tuple, Optional
import random
import time
from db import DB


def get_name_for_event_player(event_id: int, event_player_db_id: Optional[int]) -> str:
    """Return a displayable participant name for a given event_players.id.

    Parameters:
        event_id: The ID of the event.
        event_player_db_id: The primary key in event_players (as stored in matches).
    Returns:
        A best-effort string: guest_name, player nickname/full name, or placeholders.
    """
    # event_players stores player_id or guest_name, but matches store 'player1' as event_players.id
    if event_player_db_id is None:
        return "BYE"
    cur = DB.execute("SELECT player_id, guest_name FROM event_players WHERE id=?", (event_player_db_id,))
    row = cur.fetchone()
    if not row:
        return "Unknown"
    pid, guest = row
    if guest:
        return guest
    if pid:
        r = DB.execute("SELECT COALESCE(nickname, name) FROM players WHERE id=?", (pid,)).fetchone()
        return r[0] if r else "Unknown"
    return "Unknown"


def compute_standings(event_id: int):
    """
    Compute Swiss-style standings for the event.
    Returns a list of dicts per player with keys:
      - eid: event_players.id
      - name: display name
      - mp: match points (Win=3, Draw=1, Loss=0; BYE counts as Win)
      - wins, losses, draws: match record
      - mwp: match-win percentage (wins + 0.5*draws) / matches, BYE counts as a win; rounded to 4 decimals
      - omwp: opponents' match-win percentage (avg of opponents' mwp with 0.33 floor; excludes BYEs)
      - gwp: game-win percentage (game_wins / (game_wins + game_losses), BYE counts as 2-0); 0.33 floor
      - ogwp: opponents' game-win percentage (avg of opponents' gwp with 0.33 floor; excludes BYEs)
    Sorted by: mp DESC, omwp DESC, gwp DESC, ogwp DESC, name ASC
    """
    # Fetch players for the event
    players = DB.execute(
        "SELECT id, player_id, guest_name FROM event_players WHERE event_id=? ORDER BY seating_pos",
        (event_id,)
    ).fetchall()
    if not players:
        return []
    # Build name map
    def display_name(row):
        eid, pid, guest = row
        if guest:
            return guest
        if pid:
            # Fetch full name and nickname; choose nickname only if full name length >= 20
            r = DB.execute("SELECT name, nickname FROM players WHERE id=?", (pid,)).fetchone()
            if r:
                full_name = r[0] or ""
                nick = r[1]
                if len(full_name) >= 20 and nick:
                    return nick
                return full_name
            return "Unknown"
        return "Unknown"

    name_map = {eid: display_name((eid, pid, guest)) for eid, pid, guest in players}

    # Initialize stats
    stats = {
        eid: {
            'eid': eid,
            'name': name_map[eid],
            'mp': 0,
            'wins': 0,
            'losses': 0,
            'draws': 0,
            'matches': 0,
            'game_wins': 0,
            'game_losses': 0,
            'opponents': []  # list of opponent eids (exclude BYE)
        } for eid, _, _ in players
    }

    # Iterate matches
    cur = DB.execute("SELECT player1, player2, score_p1, score_p2, bye FROM matches WHERE event_id=?", (event_id,))
    for p1, p2, s1, s2, bye in cur.fetchall():
        s1 = int(s1 or 0)
        s2 = int(s2 or 0)
        if bye == 1 and p1 in stats:
            # BYE: counts as a 2-0 win
            st = stats[p1]
            st['wins'] += 1
            st['mp'] += 3
            st['matches'] += 1
            st['game_wins'] += 2
            st['game_losses'] += 0
            continue
        # Normal match must have both players
        if p1 in stats and p2 in stats:
            # add opponents
            stats[p1]['opponents'].append(p2)
            stats[p2]['opponents'].append(p1)
            # games
            stats[p1]['game_wins'] += s1
            stats[p1]['game_losses'] += s2
            stats[p2]['game_wins'] += s2
            stats[p2]['game_losses'] += s1
            # match outcome
            if s1 > s2:
                stats[p1]['wins'] += 1
                stats[p1]['mp'] += 3
                stats[p2]['losses'] += 1
            elif s2 > s1:
                stats[p2]['wins'] += 1
                stats[p2]['mp'] += 3
                stats[p1]['losses'] += 1
            else:
                # draw
                stats[p1]['draws'] += 1
                stats[p2]['draws'] += 1
                stats[p1]['mp'] += 1
                stats[p2]['mp'] += 1
            stats[p1]['matches'] += 1
            stats[p2]['matches'] += 1

    # Helper to compute percentages with floors
    def pct(n, d):
        return (n / d) if d > 0 else 0.0

    def floor_33(x):
        return max(x, 0.33)

    # Compute MW% and GW%
    for st in stats.values():
        mw = pct(st['wins'] + 0.5 * st['draws'], st['matches'])
        gw = pct(st['game_wins'], st['game_wins'] + st['game_losses'])
        st['mwp'] = round(mw, 4)
        st['gwp'] = round(floor_33(gw), 4)

    # Compute OMW% and OGW%
    for eid, st in stats.items():
        opps = st['opponents']
        if not opps:
            st['omwp'] = 0.0
            st['ogwp'] = 0.0
        else:
            omw_list = [floor_33(stats[opp]['mwp']) for opp in opps]
            ogw_list = [floor_33(stats[opp]['gwp']) for opp in opps]
            st['omwp'] = round(sum(omw_list) / len(omw_list), 4)
            st['ogwp'] = round(sum(ogw_list) / len(ogw_list), 4)

    # Build output list and sort
    out = list(stats.values())
    out.sort(key=lambda r: (-r['mp'], -r['omwp'], -r['gwp'], -r['ogwp'], r['name']))
    return out


def generate_round_one(event_id: int) -> None:
    """Generate and persist round 1 pairings based on seating.

    Rule:
      - Seat order is split in half; players are paired opposite at the table
        (i pairs with i + n/2 after removing a possible BYE).
      - If odd number of participants, select one BYE at random and award 2-0.
      - Starts the event by setting current_round=1 and round_start_ts.
    Side effects: Inserts into matches table and updates events.
    """
    # create round 1 pairings according to opposite-at-table rule
    cur = DB.cursor()
    rows = list(DB.execute("SELECT id, player_id, guest_name, seating_pos FROM event_players WHERE event_id=? ORDER BY seating_pos", (event_id,)).fetchall())
    if not rows:
        return
    # convert rows to list of (event_player_id, displayname)
    seating = [(r[0], r[2] if r[2] else (DB.execute("SELECT COALESCE(nickname, name) FROM players WHERE id=?", (r[1],)).fetchone()[0])) for r in rows]
    n = len(seating)
    # If odd, choose random bye - remove it from pairing list
    bye_id = None
    working = seating.copy()
    if n % 2 == 1:
        bye_choice = random.choice(working)
        bye_id = bye_choice[0]
        working = [x for x in working if x[0] != bye_id]
    # pair opposite: pair i with i + n/2 modulo
    pairs = []
    half = len(working) // 2
    for i in range(half):
        p1 = working[i][0]
        p2 = working[i + half][0]
        pairs.append((p1, p2, False))
    # insert pairs
    for p1, p2, _ in pairs:
        cur.execute("INSERT INTO matches (event_id, round, player1, player2, score_p1, score_p2, bye) VALUES (?, ?, ?, ?, 0, 0, 0)",
                    (event_id, 1, p1, p2))
    if bye_id:
        # award automatic win for BYE
        cur.execute("INSERT INTO matches (event_id, round, player1, player2, score_p1, score_p2, bye) VALUES (?, ?, ?, ?, 2, 0, 1)",
                    (event_id, 1, bye_id, None))
    # set current_round = 1 and start timer for round 1
    cur.execute("UPDATE events SET current_round=?, round_start_ts=? WHERE id=?", (1, int(time.time()), event_id))
    DB.commit()


def compute_next_round_pairings(event_id: int):
    """
    Compute pairings for the next round following a strict top-down rule:
    - Determine standings (ranked by MP, OMW%, GW%, OGW%, name) and pair from
      highest ranked to lowest.
    - For each highest remaining player, pick the first available opponent in
      rank order among remaining players that is not a rematch.
    - If a later conflict makes it impossible to complete the round without
      rematches, backtrack to the last couple and try the next available
      opponent for that top player, still proceeding top-down.
    - Only if no perfect (no-rematch) pairing exists will rematches be allowed,
      and then the algorithm minimizes the number of rematches while preserving
      the same top-down order.
    - If odd number of players, assign a BYE to the lowest ranked player who
      has not already received one (deterministic; no randomness).
    - Returns list of tuples (p1, p2 or None, is_bye)
    """
    # Get all event players
    players = [r[0] for r in DB.execute("SELECT id FROM event_players WHERE event_id=? ORDER BY seating_pos", (event_id,)).fetchall()]
    if not players:
        return []

    # compute cumulative match points so far (Win=3, Draw=1, BYE=3)
    mp_map = {pid: 0 for pid in players}
    # also build set of previous pairings (frozenset of two ids)
    previous_pairs = set()
    cur = DB.execute("SELECT player1, player2, score_p1, score_p2, bye FROM matches WHERE event_id=?", (event_id,))
    for p1, p2, s1, s2, bye in cur.fetchall():
        if bye == 1:
            if p1 in mp_map:
                mp_map[p1] += 3
            continue
        if p1 in mp_map and p2 in mp_map:
            if s1 > s2:
                mp_map[p1] += 3
            elif s2 > s1:
                mp_map[p2] += 3
            else:
                mp_map[p1] += 1
                mp_map[p2] += 1
            previous_pairs.add(frozenset((p1, p2)))

    # Determine standings order (top-down) for deterministic pairing
    standings = compute_standings(event_id)
    ranked = [row['eid'] for row in standings if row['eid'] in mp_map]

    # Determine BYE only if odd number of players (lowest ranked without prior BYE)
    bye_candidate = None
    if len(players) % 2 == 1:
        had_byes = set(r[0] for r in DB.execute("SELECT player1 FROM matches WHERE event_id=? AND bye=1", (event_id,)).fetchall())
        for pid in reversed(ranked):  # lowest ranked first
            if pid not in had_byes:
                bye_candidate = pid
                break
        if bye_candidate is None and ranked:
            bye_candidate = ranked[-1]

    # players to pair: standings order, top-down, excluding BYE
    to_pair = [p for p in ranked if p != bye_candidate]

    pairs = []

    # Strict top-down backtracking without rematches
    used = set()

    def backtrack_strict(result):
        if len(used) == len(to_pair):
            return result
        # Always pick the highest-ranked remaining player next
        p = next(pid for pid in to_pair if pid not in used)
        used.add(p)
        # Candidates in rank order among remaining
        for q in to_pair:
            if q in used or q == p:
                continue
            if frozenset((p, q)) in previous_pairs:
                continue  # skip rematches in strict phase
            used.add(q)
            res = backtrack_strict(result + [(p, q, False)])
            if res is not None:
                return res
            used.remove(q)
        used.remove(p)
        return None

    res = backtrack_strict([])

    if res is None:
        # Allow rematches but minimize their number, still pairing top-down
        used = set()
        best_result = None
        best_repeats = 10**9

        def backtrack_min(result, repeats_so_far):
            nonlocal best_result, best_repeats
            if repeats_so_far > best_repeats:
                return
            if len(used) == len(to_pair):
                best_result = list(result)
                best_repeats = repeats_so_far
                return
            p = next(pid for pid in to_pair if pid not in used)
            used.add(p)
            for q in to_pair:
                if q in used or q == p:
                    continue
                is_repeat = frozenset((p, q)) in previous_pairs
                used.add(q)
                backtrack_min(result + [(p, q, False)], repeats_so_far + (1 if is_repeat else 0))
                used.remove(q)
            used.remove(p)

        backtrack_min([], 0)
        pairs = best_result or []
    else:
        pairs = res

    # add bye match if needed
    if bye_candidate is not None:
        pairs.append((bye_candidate, None, True))

    return pairs
