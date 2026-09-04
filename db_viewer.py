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
with open("data/player_map.json", "rb") as f:
    player_map = json.load(f)

pid = player_map["ticedup"]
# pid2 = player_map["ceije"]


q = """
    WITH 
            valid_seasons AS (
                SELECT season_id
                FROM season_killfeed
                GROUP BY dupe_id
            ),
            roster_sizes AS (
            SELECT DISTINCT season_id, 
                FIRST_VALUE(entry_id) OVER (
                PARTITION BY season_id
                ) AS first,
               LAST_VALUE(entry_id) OVER(
                    PARTITION BY season_id
                ) AS last,

                LAST_VALUE(entry_id) OVER(
                    PARTITION BY season_id
                )-FIRST_VALUE(entry_id) OVER (
                PARTITION BY season_id
                ) AS n_players
            FROM season_killfeed
            WHERE season_id IN valid_seasons
            )

            SELECT ROUND(CAST(r.n_players - (r.last - k.entry_id) AS FLOAT)/CAST(r.n_players AS FLOAT), 4) AS placement_pct
            FROM season_killfeed k
            JOIN roster_sizes r ON k.season_id = r.season_id

            WHERE k.pve_id IS NOT NULL AND k.pve_id != "Nothing"
"""
print(view.cur.execute(q).fetchall())

# print(view.cur.execute("SELECT round_name, season_no FROM seasons WHERE season_id = 95").fetchall())

# szn = view.cur.execute("SELECT season_id FROM seasons WHERE round_name = 'Jambo' AND season_no = 7").fetchall()[0][0]
# pprint(view.cur.execute(test, (szn,szn )).fetchall())
# pprint(view.cur.execute("SELECT * FROM season_killfeed WHERE season_id IN (SELECT season_id FROM seasons WHERE round_name = 'Jambo' AND season_no = 7)" ).fetchall())
gone = [
    'flameorb',
    'spacepod_',
    'abdalain',
    'crafters',
    'bofishkix',
    'energypulse',
    'pelycosaur',
    'hypcr',
    'oddishthoughts',
    'buildingbard300',
    'karasu994',
    'sithey',
    'derockproject',
    'awhivenguy',
    'mincrooft',
    'ri1eypaige',
]
cheated = [
    'zemnoz'
]
print(view.cur.execute("SELECT player_id, redacted FROM player_stats WHERE redacted IS NOT NULL").fetchall())
# for bye in gone:
#     p = player_map[bye]
#     view.cur.execute("UPDATE player_stats SET redacted = 'X' WHERE player_id = ?", (p,))
# for bye in cheated:
#     p = player_map[bye]
#     view.cur.execute("UPDATE player_stats SET redacted = 'C' WHERE player_id = ?", (p,))

# print(view.cur.execute("SELECT first_dmg FROM season_info").fetchall())

tk = """
    WITH 
                            valid_seasons AS (
                                    SELECT season_id
                                    FROM season_killfeed
                                    GROUP BY dupe_id
                                ),
                            team_games AS (
                                SELECT season_id
                                FROM season_info
                                WHERE team_type != "FFA" AND season_id IN valid_seasons
                                GROUP BY season_id
                            ),

                            tks AS (
                                SELECT k.season_id, k.dead_id, k.killer_id
                                FROM season_killfeed k
                                JOIN season_teams kt
                                    ON k.season_id = kt.season_id
                                    AND k.killer_id = kt.player_id
                                JOIN season_teams vt
                                    ON k.season_id = vt.season_id
                                    AND k.dead_id = vt.player_id
                                JOIN season_info i ON k.season_id = i.season_id
                                WHERE k.season_id IN (SELECT season_id FROM team_games)
                                    AND kt.team = vt.team
                                    AND k.killer_id IS NOT NULL
                                    AND i.date >= ? AND i.date <= ?

                            )

                            SELECT *
                            FROM tks



"""
# print(view.cur.execute(tk, ('2013-01-01', '2014-01-01')).fetchall())
# print(view.cur.execute("SELECT round_name, season_no FROM seasons WHERE season_id = 1466").fetchall())
#
# h2h = """
#         WITH nemeses AS (
#            SELECT k.dead_id, p.player_id AS enemy_id, p.current_ign AS enemy_name, CAST(COUNT(k.killer_id) AS FLOAT) as kills
#            FROM season_killfeed k
#            JOIN players p ON k.killer_id = p.player_id
#            JOIN season_info i ON k.dupe_id = i.season_id
#            WHERE k.dead_id = ?
#                 AND (i.date >= ? AND i.date < ?)
#            GROUP BY killer_id
#            ORDER BY COUNT(killer_id) DESC
#            ),
#
#            revenges AS (
#            SELECT k.dead_id, k.killer_id, n.enemy_name, CAST(COUNT(*) AS FLOAT) as counters
#            FROM season_killfeed k
#            JOIN nemeses n ON k.dead_id = n.enemy_id
#            JOIN season_info i ON k.dupe_id = i.season_id
#            WHERE k.killer_id = n.dead_id
#                 AND (i.date >= ? AND i.date < ?)
#            GROUP BY k.dead_id
#            ORDER BY COUNT(*) DESC
#            )
#
#          SELECT n.enemy_name, CAST(COALESCE(r.counters, 0) AS INT), CAST(n.kills AS INT)
#            FROM nemeses n
#            LEFT JOIN revenges r ON n.enemy_id = r.dead_id
#            ORDER BY n.kills DESC, r.counters ASC"""
#
# all_h2h = """
#     WITH victims AS (
#         SELECT k.dead_id, CAST(COUNT(k.killer_id) AS FLOAT) as kills
#         FROM season_killfeed k
#        JOIN season_info i ON k.dupe_id = i.season_id
#        WHERE k.killer_id = ?
#             AND (i.date >= ? AND i.date < ?)
#        GROUP BY k.dead_id
#        ORDER BY COUNT(dead_id) DESC
#     ),
#     killers AS (
#         SELECT k.killer_id, CAST(COUNT(k.killer_id) AS FLOAT) as kills
#         FROM season_killfeed k
#        JOIN season_info i ON k.dupe_id = i.season_id
#        WHERE k.dead_id = ?
#             AND (i.date >= ? AND i.date < ?)
#        GROUP BY k.killer_id
#        ORDER BY COUNT(killer_id) DESC
#     ),
#     victim_h2h AS (
#         SELECT v.dead_id AS player_id, CAST(v.kills AS INT) AS wins, CAST(COALESCE(k.kills, 0) AS INT) AS losses
#         FROM victims v
#         LEFT JOIN killers k ON k.killer_id = v.dead_id
#     ),
#     killer_h2h AS (
#         SELECT k.killer_id AS player_id, CAST(COALESCE(v.kills, 0) AS INT) AS wins, CAST(COALESCE(k.kills, 0) AS INT) AS losses
#         FROM killers k
#         LEFT JOIN victims v ON k.killer_id = v.dead_id
#     ),
#     all_h2h AS (
#         SELECT * FROM victim_h2h
#         UNION
#         SELECT * FROM killer_h2h
#     )
#     SELECT p.current_ign, a.wins, a.losses
#     FROM all_h2h a
#     JOIN players p ON a.player_id = p.player_id
#
#
#
# """
#
# print(view.cur.execute(h2h, (1506, '2013-01-01', '2014-01-01', '2013-01-01', '2014-01-01')).fetchall())
# print(view.cur.execute(all_h2h, (1506, '2013-01-01', '2014-01-01', 1506, '2013-01-01', '2014-01-01')).fetchall())
# print(view.cur.execute(kr, (pid,)).fetchall())
#
# view.cur.execute("ALTER TABLE player_stats RENAME COLUMN final_kills TO kill_record")
# for p in player_map.values():
#     raw = view.cur.execute(kr, (p,)).fetchall()
#     record = raw[0][0] if raw else 0
#     view.cur.execute("UPDATE player_stats SET kill_record = ? WHERE player_id = ?",
#                      (record, p))

# pdata = FullAggregation(update=True)
print(view.cur.execute("SELECT redacted FROM player_stats WHERE player_id IN (SELECT player_id FROM players WHERE "
                       "current_ign = 'Nyxana')").fetchall())

# print(view.cur.execute("SELECT * FROM player_stats WHERE player_id = 3203").fetchall())

# view.cur.execute("DELETE FROM players WHERE player_id = 3202")

# view.cur.execute("DELETE FROM players WHERE player_id >= 3199")
# print(view.cur.execute("SELECT * FROM players").fetchall())
# print(view.cur.execute("DELETE FROM players WHERE player_id = 1851").fetchall())
# pprint(view.cur.execute("SELECT yearly_wins FROM player_stats WHERE player_id = 1").fetchall())
# pprint(view.cur.execute("SELECT * FROM player_stats WHERE player_id = 1851").fetchall())
# pprint(view.cur.execute("SELECT * FROM season_killfeed k JOIN seasons s ON s.season_id = k.season_id AND s.round_name = 'Cinema'").fetchall())
# pprint(view.cur.execute("SELECT * FROM players WHERE player_id = 1851").fetchall())
# pprint(view.cur.execute("SELECT lifetime_rounds FROM player_stats WHERE player_id = 954").fetchall())
# pprint(view.cur.execute("SELECT * FROM players WHERE player_id = 954").fetchall())
# print(a.kpy.isna().any().to_dict())
# print(a.kpy)
# print(a.stats['kpr_5'])
test = f"""

                   WITH 
                    valid_seasons AS (
                        SELECT season_id
                        FROM season_killfeed
                        GROUP BY dupe_id
                    ),
                    toX AS (
                        SELECT i.season_id, s.round_name, s.season_no
                        FROM season_info i 
                        JOIN seasons s ON i.season_id = s.season_id
                        WHERE i.team_size = ? AND i.season_id IN valid_seasons
                    ),
                    team_kills AS (
                        SELECT k.season_id,
                            GROUP_CONCAT(DISTINCT p.current_ign) AS team_members,
                            COUNT(k2.killer_id) as kills
                        FROM season_teams t
                        JOIN players p ON t.player_id = p.player_id
                        LEFT JOIN season_killfeed k ON k.dead_id = t.player_id
                            AND k.season_id = t.season_id
                        LEFT JOIN season_killfeed k2 ON k2.killer_id = t.player_id
                            AND k2.season_id = t.season_id
                        WHERE t.season_id in (SELECT season_id FROM toX)
                        GROUP BY k.season_id, t.team
                        ORDER BY kills DESC
                    ),
                    roster AS (
                        SELECT season_id, COUNT(DISTINCT k.dead_id) as size
                        FROM season_killfeed k
                        GROUP BY season_id
                    )
                    SELECT tk.team_members, s.round_name, s.season_no, tk.kills, 
                            ROUND(100*CAST(tk.kills AS FLOAT)/CAST(r.size AS FLOAT), 1) AS pct_killed
                    FROM team_kills tk
                    JOIN roster r ON tk.season_id = r.season_id
                    JOIN seasons s ON tk.season_id = s.season_id
                    ORDER BY kills DESC
                    LIMIT 5
        """
pprint(view.cur.execute(test, (2,)).fetchall())
cinema = """
    SELECT * FROM season_killfeed WHERE season_id IN (
        SELECT season_id FROM seasons
        WHERE season_no = 16 AND round_name = 'Cinema'
    )
"""
# delete1 = """
#      DELETE FROM season_teams WHERE (season_id <= 2026 AND season_id >= 2021) OR season_id = 458
# """
# delete2 = """
#      DELETE FROM season_killfeed WHERE (season_id <= 2026 AND season_id >= 2021) OR season_id = 458
# """
# delete3 = """
#      DELETE FROM seasons WHERE (season_id <= 2026 AND season_id >= 2021) OR season_id = 458
# """
# delete1 = """
#       DELETE FROM season_teams WHERE entry_id >= 48563 AND entry_id <= 48592
# """
# view.cur.execute(delete1)
# pprint(view.cur.execute(cinema).fetchall())
pprint(view.cur.execute("SELECT * FROM seasons s WHERE (s.round_name = 'Cinema' AND s.season_no = '16b') OR (s.round_name = 'Phobia' AND s.season_no = '28')").fetchall())

view.cur.execute("UPDATE season_killfeed SET dupe_id = 2072 WHERE dupe_id = 2028")


# view.cur.execute(delete2)
# view.cur.execute(delete3)
view._save()
view._reopen()

# pprint(view.cur.execute("SELECT * FROM season_killfeed WHERE entry_id >= 50000 AND season_id < 1800"))
# print(view.cur.execute("SELECT * FROM players WHERE current_ign = 'Kubaslov'").fetchall())
# print(view.cur.execute("SELECT * FROM players WHERE current_ign = 'Nikikula'").fetchall())
#


