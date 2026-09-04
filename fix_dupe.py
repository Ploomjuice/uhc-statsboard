from db_ops import DBOPs
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
from data_aggregation import FullAggregation
from pprint import pprint
import pandas as pd
import numpy as np
import pickle
import ast
from collections import defaultdict
import math
import time

view = DBOPs("data/stats.db")
# pprint(view.cur.execute("SELECT * FROM seasons s WHERE (s.round_name = 'Cinema' AND s.season_no = '16b') OR (s.round_name = 'Phobia' AND s.season_no = '28')").fetchall())
#
# view.cur.execute("UPDATE season_killfeed SET dupe_id = 2072 WHERE dupe_id = 2028")
players_to_be_updated = {i[0] for i in view.cur.execute("SELECT dead_id FROM season_killfeed k JOIN seasons s ON s.season_id = k.season_id WHERE s.season_no = 28 AND s.round_name = 'Phobia'").fetchall()}

print(players_to_be_updated)
agg = FullAggregation(interface=view, reinit=True)


players_with_profiles = [i[0] for i in view.cur.execute("SELECT player_id FROM player_stats").fetchall()]

for player_id in players_to_be_updated:
    print(player_id)

    total_kills = agg.kill_counter[player_id][0]
    total_deaths = agg.death_counter[player_id][0]
    total_rounds = agg.round_counter[player_id][0]
    total_wins = agg.win_counter[player_id][0]
    wpr = agg.wpr[player_id][0]
    kdr = agg.kdr[player_id][0]
    kpr = agg.kpr[player_id][0]
    first_deaths = agg.first_deaths[player_id].iat[0]
    first_bloods = agg.first_bloods[player_id].iat[0]

    # progressive stats (other than 12 months)
    kills_by_period = defaultdict(list)
    deaths_by_period = defaultdict(list)
    rounds_by_period = defaultdict(list)
    kpr_by_period = defaultdict(list)
    dpr_by_period = defaultdict(list)

    kdr_by_period = defaultdict(list)

    # load 12 months (no need to requery)
    kills_by_period["12M"] = agg.kpy[player_id].to_list()
    deaths_by_period["12M"] = agg.dpy[player_id].to_list()
    rounds_by_period["12M"] = agg.rpy[player_id].to_list()
    kpr_by_period["12M"] = (agg.kpy[player_id] / agg.rpy[player_id]).to_list()
    dpr_by_period['12M'] = (agg.dpy[player_id] / agg.rpy[player_id]).to_list()
    kdr_by_period['12M'] = (agg.kpy[player_id] / agg.dpy[player_id]).to_list()
    kills_by_period["6M"] = agg.kph[player_id].to_list()
    deaths_by_period["6M"] = agg.dph[player_id].to_list()
    rounds_by_period["6M"] = agg.rph[player_id].to_list()
    kpr_by_period["6M"] = (agg.kph[player_id] / agg.rph[player_id]).to_list()
    dpr_by_period['6M'] = (agg.dph[player_id] / agg.rph[player_id]).to_list()
    kdr_by_period['6M'] = (agg.kph[player_id] / agg.dph[player_id]).to_list()
    kills_by_period["3M"] = agg.kpq[player_id].to_list()
    deaths_by_period["3M"] = agg.dpq[player_id].to_list()
    rounds_by_period["3M"] = agg.rpq[player_id].to_list()
    kpr_by_period["3M"] = (agg.kpq[player_id] / agg.rpq[player_id]).to_list()
    dpr_by_period['3M'] = (agg.dpq[player_id] / agg.rpq[player_id]).to_list()
    kdr_by_period['3M'] = (agg.kpq[player_id] / agg.dpq[player_id]).to_list()
    yearly_wins = agg.wpy[player_id].T.to_dict()
    pve_by_period = {'3M': agg.pvepq[player_id].to_list(),
                     '6M': agg.pveph[player_id].to_list(),
                     '12M': agg.pvepy[player_id].to_list()}

    # kdr, kpr, wpr %ile for people who've played at least 5 games
    if total_rounds >= 5:
        kdr_percentile = 100 * len([p for p in agg.kdr_5 if agg.kdr[p].iloc[0] < kdr]) / len(agg.kdr_5)
        kpr_percentile = 100 * len([p for p in agg.kpr_5 if agg.kpr[p].iloc[0] < kpr]) / len(agg.kpr_5)
        wpr_percentile = 100 * len([p for p in agg.wpr_5 if agg.wpr[p].iloc[0] < wpr]) / len(agg.wpr_5)
    else:
        kdr_percentile = np.nan
        kpr_percentile = np.nan
        wpr_percentile = np.nan

    kills_by_period = str(dict(kills_by_period))
    deaths_by_period = str(dict(deaths_by_period))
    rounds_by_period = str(dict(rounds_by_period))
    kpr_by_period = str(dict(kpr_by_period))
    dpr_by_period = str(dict(dpr_by_period))
    pve_by_period = str(dict(pve_by_period))
    kdr_by_period = str(dict(kdr_by_period))

    # ffa kills / team kills
    ffa_q = """
                                    WITH
                                        valid_seasons AS (
                                            SELECT season_id
                                            FROM season_killfeed
                                            GROUP BY dupe_id
                                        )

                                        SELECT COUNT(killer_id)
                                            FROM season_info s
                                            LEFT JOIN season_killfeed k ON s.season_id = k.season_id
                                            WHERE s.team_type = 'FFA' AND killer_id = ?
                                                AND s.season_id IN valid_seasons
                                    """
    ffa_kills = agg.api.cur.execute(ffa_q, (player_id,)).fetchall()[0][0]
    team_game_kills = total_kills - ffa_kills

    # --- SPECIAL KILL STATS  ---

    # final kill (eliminated a team)

    # final_kills = agg.finals[player_id]
    # kill record
    kr = """
                SELECT COUNT(killer_id)
                FROM season_killfeed
                WHERE killer_id = ?
                GROUP BY season_id
                ORDER BY COUNT(killer_id) DESC
                LIMIT 1
            """
    raw = agg.api.cur.execute(kr, (player_id,)).fetchall()
    kill_record = raw[0][0] if raw else 0

    # team kills
    tk_q = """
                            WITH
                            valid_seasons AS (
                                SELECT season_id
                                FROM season_killfeed
                                GROUP BY dupe_id
                            ),

                            team_games AS (
                                SELECT season_id
                                FROM season_info
                                WHERE team_type != "FFA"
                                    AND season_id IN valid_seasons
                            ),

                            tks AS (
                                SELECT k.dead_id, k.killer_id
                                FROM season_killfeed k
                                JOIN season_teams kt
                                    ON k.season_id = kt.season_id
                                    AND k.killer_id = kt.player_id
                                JOIN season_teams vt
                                    ON k.season_id = vt.season_id
                                    AND k.dead_id = vt.player_id
                                WHERE k.season_id IN (SELECT season_id FROM team_games)
                                    AND kt.team = vt.team
                                    AND k.killer_id IS NOT NULL
                            )

                            SELECT COUNT(*)
                            FROM tks
                            WHERE killer_id = ?
                            GROUP BY killer_id
                        """
    n_tks_raw = agg.api.cur.execute(tk_q, (player_id,)).fetchall()
    n_tks = n_tks_raw[0][0] if n_tks_raw else 0

    # suicides
    suicides = agg.suicides[player_id][0]

    # most recent round played
    recent_q = """
                                WITH
                                valid_seasons AS (
                                    SELECT season_id
                                    FROM season_killfeed
                                    GROUP BY dupe_id
                                ),
                                seasons_played AS (
                                    SELECT season_id
                                    FROM season_killfeed
                                    WHERE dead_id = ?
                                )

                                SELECT MAX(i.date), s.round_name, s.season_no
                                FROM seasons_played p
                                JOIN season_info i ON p.season_id = i.season_id
                                JOIN seasons s ON i.season_id = s.season_id
                                """

    lp_date, lp_round, lp_season = agg.api.cur.execute(recent_q, (player_id,)).fetchall()[0]
    lp_rr = f"{lp_round} {lp_season}"

    debut_q = """
                                        WITH
                                        valid_seasons AS (
                                    SELECT season_id
                                    FROM season_killfeed
                                    GROUP BY dupe_id
                                ),
                                        seasons_played AS (
                                            SELECT season_id
                                            FROM season_killfeed
                                            WHERE dead_id = ?
                                        )

                                        SELECT MIN(i.date), s.round_name, s.season_no
                                        FROM seasons_played p
                                        JOIN season_info i ON p.season_id = i.season_id
                                        JOIN seasons s ON i.season_id = s.season_id
                                        """
    fp_date, fp_round, fp_season = agg.api.cur.execute(debut_q, (player_id,)).fetchall()[0]
    fp_rr = f"{fp_round} {fp_season}"

    # win list
    alive_q = """
                               WITH
                                    obj_winners AS (
                                        SELECT DISTINCT dupe_id, dead_id
                                        from season_killfeed
                                        WHERE death_msg = "Winner"
                                    ),

                                    br_games AS (
                                        SELECT DISTINCT dupe_id
                                        FROM season_killfeed
                                        WHERE dupe_id NOT IN (SELECT dupe_id FROM obj_winners)
                                    ),

                                    br_alive_winners AS (
                                        SELECT k.dupe_id, k.dead_id
                                        FROM season_killfeed k
                                        JOIN br_games b on k.season_id = b.dupe_id
                                        WHERE k.pve_id = "Nothing"
                                    ),
                                    alive_winners AS (
                                        SELECT * FROM obj_winners
                                        UNION
                                        SELECT * FROM br_alive_winners
                                    )
                                SELECT s.round_name, season_no
                                FROM alive_winners w
                                JOIN seasons s on w.dupe_id = s.season_id
                                WHERE w.dead_id = ?

                                """
    dead_q = """
                            WITH
                            valid_seasons AS (
                                    SELECT season_id
                                    FROM season_killfeed
                                    GROUP BY dupe_id
                                ),
                            obj_winners AS (
                                SELECT season_id, dead_id
                                from season_killfeed
                                WHERE death_msg = "Winner"
                                    AND season_id IN valid_seasons
                            ),

                            br_games AS (
                                SELECT DISTINCT season_id
                                FROM season_killfeed
                                WHERE season_id NOT IN (SELECT season_id FROM obj_winners)
                                    AND season_id IN valid_seasons
                            ),

                            br_alive_winners AS (
                                SELECT k.season_id, k.dead_id
                                FROM season_killfeed k
                                JOIN br_games b on k.season_id = b.season_id
                                WHERE pve_id = 'Nothing'
                            ),

                            alive_winners AS (
                                SELECT * FROM obj_winners
                                UNION
                                SELECT * FROM br_alive_winners
                            ),

                            winning_teams AS (
                                SELECT t.season_id, t.team
                                FROM season_teams t
                                JOIN alive_winners w ON t.season_id = w.season_id AND t.player_id = w.dead_id
                            ),

                        dead_winners AS (
                            SELECT DISTINCT t.player_id, t.season_id, s.round_name, s.season_no
                            FROM season_teams t
                            JOIN winning_teams wt
                                ON t.season_id = wt.season_id
                                AND t.team = wt.team
                            JOIN seasons s
                                ON t.season_id = s.season_id
                            WHERE t.player_id NOT IN (
                                SELECT dead_id
                                FROM alive_winners w
                                WHERE w.season_id = t.season_id
                            )
                        )
                            SELECT round_name, season_no
                            FROM dead_winners
                            WHERE player_id = ?

                            """
    tied_q = """
                        WITH

                        last_entries AS (
                            SELECT MAX(entry_id) AS last_entry
                            FROM season_killfeed
                            GROUP BY season_id

                        ),

                        ending_death_seasons AS (
                            SELECT s.round_name, s.season_no, k.dead_id, k.killer_id
                            FROM seasons s
                            JOIN season_killfeed k ON s.season_id = k.dupe_id
                            JOIN last_entries le ON k.entry_id = le.last_entry
                            WHERE k.killer_id NOT NULL AND (k.killer_id = ? OR k.dead_id = ?)
                            GROUP BY k.dupe_id

                        )
                        SELECT round_name, season_no
                        FROM ending_death_seasons
                    """

    alive_wins = str([f'{rr} {season}' for rr, season in agg.api.cur.execute(alive_q, (player_id,)).fetchall()])
    dead_wins = str([f'{rr} {season}' for rr, season in agg.api.cur.execute(dead_q, (player_id,)).fetchall()])
    tied_wins = str([f'{rr} {season}' for rr, season in agg.api.cur.execute(tied_q, (player_id, player_id)).fetchall()])

    # nemeses (killed by the most) / rivals (closest in match-up)
    build = """
                            WITH
                            valid_seasons AS (
                                SELECT season_id
                                FROM season_killfeed
                                GROUP BY dupe_id
                            ),
                            nemeses AS (
                           SELECT k.dead_id, p.player_id, p.current_ign, CAST(COUNT(k.killer_id) AS FLOAT) as kills
                           FROM season_killfeed k
                           JOIN players p on k.killer_id = p.player_id
                           WHERE k.dead_id = ? AND k.season_id IN valid_seasons
                           GROUP BY killer_id
                           ORDER BY COUNT(killer_id) DESC
                           ),
                           revenges AS (
                           SELECT k.dead_id, n.player_id, n.current_ign, CAST(COUNT(*) AS FLOAT) as counters
                           FROM season_killfeed k
                           JOIN nemeses n ON k.dead_id = n.player_id
                           WHERE k.killer_id = n.dead_id AND k.season_id IN valid_seasons
                           GROUP BY k.dead_id
                           ORDER BY COUNT(*) DESC
                           )"""
    nemeses_q = """

                       SELECT n.current_ign, CAST(COALESCE(r.counters, 0) AS INT), CAST(n.kills AS INT)
                       FROM nemeses n
                       LEFT JOIN revenges r ON n.player_id = r.dead_id
                       WHERE (r.counters IS NOT NULL AND n.kills > r.counters AND ABS(n.kills - r.counters)/(r.counters) > 1.2)
                        OR (r.counters IS NULL AND n.kills >= 3)
                       ORDER BY n.kills DESC, r.counters ASC
                       """
    nemeses = str(
        {ign: (w, l) for ign, w, l in agg.api.cur.execute(build + nemeses_q, (player_id,)).fetchall()})
    rivals_q = """
                       SELECT n.current_ign, CAST(r.counters AS INT), CAST(n.kills AS INT)
                           FROM nemeses n
                           JOIN revenges r ON n.player_id = r.dead_id
                           WHERE (n.kills BETWEEN r.counters -2 AND r.counters + 2)
                            AND n.kills IS NOT NULL AND n.kills >= 2
                            AND r.counters IS NOT NULL AND r.counters >= 2
                            AND ((n.kills <= r.counters AND ABS(n.kills - r.counters)/(n.kills) <= 1.2) OR
                                (n.kills > r.counters AND ABS(n.kills - r.counters)/(r.counters) <= 1.2))
                           GROUP BY n.player_id
                           ORDER BY r.counters DESC, n.kills DESC
                       """
    rivals = str({ign: (w, l) for ign, w, l in agg.api.cur.execute(build + rivals_q, (player_id,)).fetchall()})
    dominating_q = """
                        WITH
                        valid_seasons AS (
                            SELECT season_id
                            FROM season_killfeed
                            GROUP BY dupe_id
                        ),
                       killed AS (
                        SELECT k.dead_id, k.killer_id, p.current_ign, CAST(COUNT(k.dead_id) AS FLOAT) as kills
                        FROM season_killfeed k
                        JOIN players p on k.dead_id = p.player_id
                        WHERE k.killer_id = ? AND k.season_id IN valid_seasons
                        GROUP BY k.dead_id
                        ORDER BY COUNT(killer_id) DESC
                       ),

                       revenges AS (
                        SELECT k.dead_id, k.killer_id, ki.current_ign, CAST(COUNT(*) AS FLOAT) as counters
                        FROM season_killfeed k
                        JOIN killed ki ON k.killer_id = ki.dead_id
                        WHERE k.dead_id = ki.killer_id AND k.season_id IN valid_seasons
                        GROUP BY k.killer_id
                        ORDER BY COUNT(*) DESC
                       )

                       SELECT k.current_ign, CAST(k.kills AS INT), CAST(COALESCE(r.counters, 0) AS INT)
                       FROM killed k
                       LEFT JOIN revenges r ON k.dead_id = r.killer_id
                       WHERE (r.counters IS NOT NULL AND ABS(k.kills - r.counters)/r.counters > 1.2) OR
                        (r.counters IS NULL AND k.kills >= 3)

                       """
    dominating = {ign: (w, l) for ign, w, l in agg.api.cur.execute(dominating_q, (player_id,)).fetchall()}

    ironmans = agg.ironmans[player_id]

    longest_im_q = """
                                WITH
                            valid_seasons AS (
                                SELECT season_id
                                FROM season_killfeed
                                GROUP BY dupe_id
                            )

                                    SELECT s.round_name, s.season_no, i.im_time
                                    FROM season_info i
                                    JOIN seasons s ON i.season_id = s.season_id
                                    WHERE ((i.ironman = ?) OR
                                        (i.ironman LIKE '%[%' AND
                                        (i.ironman LIKE '%'||?||', %' OR i.ironman LIKE '%, '||?||'%'))
                                        AND s.season_id IN valid_seasons)
                                    GROUP BY s.season_id
                                    ORDER BY i.im_time DESC
                                    LIMIT 1

                                """
    longest_im = agg.api.cur.execute(longest_im_q, (player_id, player_id, player_id)).fetchall()
    if longest_im:
        longest_im = ' '.join(longest_im[0])
    else:
        longest_im = 'N/A'
    f_dmg = agg.fdams[player_id]
    top_frags = agg.top_frags[player_id]
    ratings = agg.yearly_ratings[player_id]

    view.update_profile(

        str(total_kills),
        str(total_deaths),
        str(total_rounds),
        str(kdr),  # %ile
        str(kpr),  # %ile
        str(wpr),  # %ile

        str(kdr_percentile),
        str(kpr_percentile),
        str(wpr_percentile),

        str(first_deaths),

        str(rounds_by_period),
        str(kills_by_period),
        str(deaths_by_period),
        str(kpr_by_period),
        str(kdr_by_period),
        str(dpr_by_period),
        str(pve_by_period),

        str(ffa_kills),
        str(team_game_kills),

        str(total_wins),
        str(yearly_wins),

        str(kill_record),
        str(fp_date),
        str(fp_rr),
        str(lp_date),
        str(lp_rr),
        str(n_tks),
        str(suicides),
        str(alive_wins),
        str(dead_wins),

        str(nemeses),
        str(rivals),
        str(dominating),
        str(ironmans),
        str(longest_im),
        str(f_dmg),
        str(top_frags),
        str(tied_wins),
        str(first_bloods),
        str(ratings),

        str(player_id)

    )
    view._save()
    view._reopen()