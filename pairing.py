# pairing.py
from typing import List, Tuple, Optional
import random
import time
from db import DB


def get_name_for_event_player(event_id: int, event_player_db_id: Optional[int]) -> str:
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
        r = DB.execute("SELECT name FROM players WHERE id=?", (pid,)).fetchone()
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
            r = DB.execute("SELECT name FROM players WHERE id=?", (pid,)).fetchone()
            return r[0] if r else "Unknown"
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
    # create round 1 pairings according to opposite-at-table rule
    cur = DB.cursor()
    rows = list(DB.execute("SELECT id, player_id, guest_name, seating_pos FROM event_players WHERE event_id=? ORDER BY seating_pos", (event_id,)).fetchall())
    if not rows:
        return
    # convert rows to list of (event_player_id, displayname)
    seating = [(r[0], r[2] if r[2] else (DB.execute("SELECT name FROM players WHERE id=?", (r[1],)).fetchone()[0])) for r in rows]
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
    Compute pairings for the next round (Swiss-ish):
    - If odd number of players, assign a single BYE to the lowest-scoring player who hasn't had one yet.
    - Pair remaining players by similar score while avoiding rematches if possible.
    - Returns list of tuples (p1, p2 or None, is_bye)
    """
    # fetch all event_players ids
    players = [r[0] for r in DB.execute("SELECT id FROM event_players WHERE event_id=? ORDER BY seating_pos", (event_id,)).fetchall()]
    if not players:
        return []

    # compute cumulative match points so far (Win=3, Draw=1, BYE=3)
    mp_map = {pid: 0 for pid in players}
    # also build set of previous pairings (frozenset of two ids)
    previous_pairs = set()
    cur = DB.execute("SELECT player1, player2, score_p1, score_p2, bye FROM matches WHERE event_id=?", (event_id,))
    for p1, p2, s1, s2, bye in cur.fetchall():
        p1 = p1
        p2 = p2
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

    # Determine BYE only if odd number of players
    bye_candidate = None
    if len(players) % 2 == 1:
        had_byes = set(r[0] for r in DB.execute("SELECT player1 FROM matches WHERE event_id=? AND bye=1", (event_id,)).fetchall())
        # lowest MP who hasn't had a bye; tie-break randomly
        sorted_by_mp = sorted(players, key=lambda pid: (mp_map.get(pid, 0), random.random()))
        for pid in sorted_by_mp:
            if pid not in had_byes:
                bye_candidate = pid
                break
        if bye_candidate is None:
            bye_candidate = sorted_by_mp[0]

    # players to pair
    to_pair = [p for p in players if p != bye_candidate]
    # sort by MP desc
    to_pair.sort(key=lambda p: (-mp_map.get(p, 0), random.random()))

    pairs = []

    # Backtracking pairing to avoid rematches when possible
    used = set()

    def backtrack(result):
        if len(used) == len(to_pair):
            return result
        # pick next unpaired player
        p = next(pid for pid in to_pair if pid not in used)
        used.add(p)
        # candidates: remaining players, try closest MP first, no rematch
        candidates = [q for q in to_pair if q not in used]
        # sort by score proximity, then random for variety
        candidates.sort(key=lambda q: (abs(mp_map.get(q, 0) - mp_map.get(p, 0)), random.random()))
        # 1) try without rematches
        for q in candidates:
            if frozenset((p, q)) in previous_pairs:
                continue
            used.add(q)
            res = backtrack(result + [(p, q, False)])
            if res is not None:
                return res
            used.remove(q)
        # 2) if no solution, allow rematch
        for q in candidates:
            used.add(q)
            res = backtrack(result + [(p, q, False)])
            if res is not None:
                return res
            used.remove(q)
        used.remove(p)
        return None

    res = backtrack([])
    if res is None:
        # fallback greedy
        remaining = [p for p in to_pair]
        while remaining:
            p = remaining.pop(0)
            # best candidate by proximity avoiding rematch if possible
            candidates = sorted(remaining, key=lambda q: (frozenset((p, q)) in previous_pairs, abs(mp_map.get(q, 0) - mp_map.get(p, 0)), random.random()))
            q = candidates[0]
            remaining.remove(q)
            pairs.append((p, q, False))
    else:
        pairs = res

    # add bye match if needed
    if bye_candidate is not None:
        pairs.append((bye_candidate, None, True))

    return pairs
