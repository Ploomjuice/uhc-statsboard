import numpy as np
from numba.cpython.rangeobj import state_types
from relational_ranking import RelRankPlayers
from db_ops import DBOPs
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
from collections import defaultdict
import pandas as pd
import pickle
from time import time
import ast
from pprint import pprint
import math


def clean_literals(s):
    s_clean = (s.replace("nan", "float('nan')").replace("inf", "float('inf')"))
    return eval(s_clean, {"__builtins__": None}, {"float": float})

interval_kills_q = """
                    SELECT killer_id, COUNT(killer_id)
                    FROM season_info s
                    LEFT JOIN season_killfeed k ON s.season_id = k.dupe_id
                    WHERE s.date >= ? AND s.date < ?
                    GROUP BY killer_id
                    """
interval_deaths_q = """
                         SELECT k.dead_id, COUNT(*)
                         FROM season_killfeed k
                         LEFT JOIN season_info s on k.dupe_id = s.season_id
                         WHERE ((pve_id NOT NULL AND pve_id != "Nothing") OR (killer_id NOT NULL))
                            AND (s.date >= ? AND s.date < ?)
                         GROUP BY dead_id
                         """
interval_pve_q ="""
                    SELECT dead_id, COUNT(*)
                     FROM season_killfeed k
                     LEFT JOIN season_info s on k.dupe_id = s.season_id
                     WHERE (pve_id NOT NULL AND pve_id != "Nothing")
                        AND (s.date >= ? AND s.date < ?)
                     GROUP BY dead_id

                    """
interval_rounds_q = """
                   SELECT dead_id, COUNT(s.season_id) 
                   FROM season_killfeed k
                   LEFT JOIN season_info s on k.dupe_id = s.season_id
                   WHERE s.date >= ? AND s.date < ?
                   GROUP BY dead_id

                   """
interval_h2h_q = """
    WITH victims AS (
        SELECT k.dead_id, CAST(COUNT(k.killer_id) AS FLOAT) as kills
        FROM season_killfeed k
       JOIN season_info i ON k.dupe_id = i.season_id
       WHERE k.killer_id = ?
            AND (i.date >= ? AND i.date < ?)
       GROUP BY k.dead_id
       ORDER BY COUNT(dead_id) DESC
    ),
    killers AS (
        SELECT k.killer_id, CAST(COUNT(k.killer_id) AS FLOAT) as kills
        FROM season_killfeed k
       JOIN season_info i ON k.dupe_id = i.season_id
       WHERE k.dead_id = ?
            AND (i.date >= ? AND i.date < ?)
       GROUP BY k.killer_id
       ORDER BY COUNT(killer_id) DESC
    ),
    victim_h2h AS (
        SELECT v.dead_id AS player_id, CAST(v.kills AS INT) AS wins, CAST(COALESCE(k.kills, 0) AS INT) AS losses
        FROM victims v
        LEFT JOIN killers k ON k.killer_id = v.dead_id
    ),
    killer_h2h AS (
        SELECT k.killer_id AS player_id, CAST(COALESCE(v.kills, 0) AS INT) AS wins, CAST(COALESCE(k.kills, 0) AS INT) AS losses
        FROM killers k
        LEFT JOIN victims v ON k.killer_id = v.dead_id
    ),
    all_h2h AS (
        SELECT * FROM victim_h2h
        UNION 
        SELECT * FROM killer_h2h
    )
    SELECT p.current_ign, a.wins, a.losses
    FROM all_h2h a
    JOIN players p ON a.player_id = p.player_id
    
    
    
"""

class FullAggregation:
    def __init__(self, interface=None, update=False, reinit=False):
        if interface:
            self.api = interface
        else:
            self.api = DBOPs("stats.db")

        with open("player_map.json", "r") as f:
            self.player_map = json.load(f)
        self.divs = [3, 6]
        if reinit:
            self.reinitialize()
        elif update:
            self.load_file()
            self.update_latest()
        else:
            self.load_file()
        self.api._save()
        self.api._reopen()


        # with open("aggs.json")

    def load_file(self):
        with open("all_agg_stats.pkl", "rb") as f:
            self.stats = pickle.load(f)
            self.kill_counter = self.stats['kills']
            self.kpy = self.stats['kpy']
            self.kpq = self.stats['kpq']
            self.kph = self.stats['kph']
            self.death_counter = self.stats['deaths']
            self.dpy = self.stats['dpy']
            self.dpq = self.stats['dpq']
            self.dph = self.stats['dph']
            self.round_counter = self.stats['rounds']
            self.first_deaths = self.stats['first_deaths']
            self.rpy = self.stats['rpy']
            self.rpq = self.stats['rpq']
            self.rph = self.stats['rph']
            self.first_bloods = self.stats['first_bloods']
            self.a_win_counter = self.stats['alive_wins']
            self.d_win_counter = self.stats['dead_wins']
            self.t_win_counter = self.stats['tied_wins']
            self.win_counter = self.stats['total_wins']
            self.kpr = self.stats['kpr']
            self.kpr_5 = self.stats['kpr_5']
            self.kdr = self.stats['kdr']
            self.kdr_5 = self.stats['kdr_5']
            self.wpr = self.stats['wpr']
            self.wpr_5 = self.stats['wpr_5']
            self.awpy = self.stats['awpy']
            self.dwpy = self.stats['dwpy']
            self.wpy = self.stats['wpy']
            self.kprpy = self.stats['kpr_py']
            self.kprpq = self.stats['kpr_pq']
            self.kprph = self.stats['kpr_ph']
            self.kdrpy = self.stats['kdr_py']
            self.kdrpq = self.stats['kdr_pq']
            self.kdrph = self.stats['kdr_ph']
            self.wprpy = self.stats['wpr_py']
            self.pve = self.stats['pve']
            self.pvepy = self.stats['pve_py']
            self.pvepq = self.stats['pve_pq']
            self.pveph = self.stats['pve_ph']
            # self.finals = self.stats['final_kills']
            self.krs = self.stats['kill_records']
            self.tks = self.stats['tks']
            self.suicides = self.stats['suicides']
            self.ironmans = self.stats['ironmans']
            self.fdams = self.stats['first_dmg']
            self.top_frags = self.stats['top_frags']
            # self.all_h2h = self.stats['all_h2h']
            self.yearly_ratings = self.stats['yearly_ratings']

    def reinitialize(self):
        # recalculate stats after inserting new data, recalculates all in case of deleting or changing rounds
        self.kill_counter = self.get_total_kills()
        self.kpy = self.get_interval_kills(m=12)
        self.kpq = self.get_interval_kills(m=3)
        self.kph = self.get_interval_kills(m=6)
        self.death_counter = self.get_total_deaths()
        self.dpy = self.get_interval_deaths(m=12)
        self.dpq = self.get_interval_deaths(m=3)
        self.dph = self.get_interval_deaths(m=6)
        self.round_counter = self.get_total_rounds()
        self.first_bloods = self.get_total_first_bloods()
        self.first_deaths = self.get_total_first_deaths()
        self.rpy = self.get_interval_rounds(m=12)
        self.rpq = self.get_interval_rounds(m=3)
        self.rph = self.get_interval_rounds(m=6)
        # self.srpy = 1 - self.dpy / self.rpy
        self.a_win_counter, self.d_win_counter, self.t_win_counter, self.win_counter = self.get_total_wins()
        self.kpr = self.kill_counter / self.round_counter

        self.kpr_5 = [p for p in self.kpr if self.round_counter[p][0] >= 5]
        self.kdr = self.kill_counter / self.death_counter
        self.kdr_5 = [p for p in self.kdr if self.round_counter[p][0] >= 5]
        self.wpr = self.win_counter / self.round_counter
        self.wpr_5 = [p for p in self.wpr if self.round_counter[p][0] >= 5]
        self.awpy, self.dwpy, self.wpy = self.get_yearly_wins()

        self.kprpy = self.kpy / self.rpy
        self.kprpq = self.kpq / self.rpq
        self.kprph = self.kph / self.rph

        self.kdrpy = self.kpy / self.dpy
        self.kdrpq = self.kpq / self.dpq
        self.kdrph = self.kph / self.dph

        self.wprpy = self.wpy / self.rpy

        # self.kpq = self.get_
        self.pve = self.get_total_pve_d()
        self.pvepy = self.get_interval_pve(m=12)
        self.pvepq = self.get_interval_pve(m=3)
        self.pveph = self.get_interval_pve(m=6)

        # self.finals = self.get_final_kills()
        self.krs = self.get_kill_records()
        self.tks = self.get_team_kills()
        self.suicides = self.get_suicides()
        self.ironmans = self.get_ironmans()
        self.fdams = self.get_fdams()
        self.top_frags = self.get_top_frags()
        # self.all_h2h = self.get_all_h2h()
        self.yearly_ratings = self.player_ratings_by_period()


        # save
        self.all_agg_stats = {
            'kills': self.kill_counter,
            'kpy': self.kpy,
            'kpq': self.kpq,
            'kph': self.kph,
            'deaths': self.death_counter,
            'dpy': self.dpy,
            'dpq': self.dpq,
            'dph': self.dph,
            'rounds': self.round_counter,
            'rpy': self.rpy,
            'rpq': self.rpq,
            'rph': self.rph,
            'first_deaths': self.first_deaths,
            'first_bloods': self.first_bloods,
            'alive_wins': self.a_win_counter,
            'dead_wins': self.d_win_counter,
            'tied_wins': self.t_win_counter,
            'total_wins': self.win_counter,
            'kpr': self.kpr,
            'kpr_5': self.kpr_5,
            'kdr': self.kdr,
            'kdr_5': self.kdr_5,
            'wpr': self.wpr,
            'wpr_5': self.wpr_5,
            'awpy': self.awpy,
            'dwpy': self.dwpy,
            'wpy': self.wpy,
            'kpr_py': self.kprpy,
            'kpr_pq': self.kprpq,
            'kpr_ph': self.kprph,
            'kdr_py': self.kdrpy,
            'kdr_pq': self.kdrpq,
            'kdr_ph': self.kdrph,
            'wpr_py': self.wprpy,
            'pve': self.pve,
            'pve_py': self.pvepy,
            'pve_pq': self.pvepq,
            'pve_ph': self.pveph,
            'kill_records': self.krs,
            # 'final_kills': self.finals,
            'tks': self.tks,
            'suicides': self.suicides,
            'ironmans': self.ironmans,
            'first_dmg': self.fdams,
            'top_frags': self.top_frags,
            # 'all_h2h': self.all_h2h,
            'yearly_ratings': self.yearly_ratings

        }
        with open("all_agg_stats.pkl", "wb") as f:
            pickle.dump(self.all_agg_stats, f)

        players = {ign.lower(): pid for pid, ign in self.api.cur.execute("""SELECT player_id, current_ign FROM players""").fetchall()}
        with open("player_map.json", "w") as f:
            json.dump(players, f)

        with open("pve_probs.json", "w") as f:
            json.dump(self.get_pve_msg_probs(), f)

        with open("pvp_probs.json", "w") as f:
            json.dump(self.get_pvp_msg_probs(), f)

    def update_latest(self):
        # year = datetime.today().year
        # month = datetime.today().month
        # start_month_q = math.ceil(month/3) * 3 - 2
        # end_month_q = start_month_q + 3 if start_month_q != 10 else 1
        # start_month_h = math.ceil(month/6)
        #

        start_q, end_q = FullAggregation.make_intervals(3)[-2:]
        start_h, end_h = FullAggregation.make_intervals(6)[-2:]
        start_y, end_y = FullAggregation.make_intervals(12)[-2:]
        print(start_q, end_q, start_h, end_h, start_y, end_y)

        self.init_new_players()

        # lazy so fully reloading the things that are easy to get
        # stats that aren't time separated (in df)
        self.kill_counter = self.get_total_kills()
        self.death_counter = self.get_total_deaths()
        self.round_counter = self.get_total_rounds()
        self.a_win_counter, self.d_win_counter, self.t_win_counter, self.win_counter = self.get_total_wins()

        self.tks = self.get_team_kills()
        self.suicides = self.get_suicides()
        self.ironmans = self.get_ironmans()
        self.fdams = self.get_fdams()
        self.top_frags = self.get_top_frags()

        # calculate from basic stats
        self.krs = self.get_kill_records()
        self.first_deaths = self.get_total_first_deaths()
        self.first_bloods = self.get_total_first_bloods()
        self.kpr = self.kill_counter / self.round_counter
        self.kdr = self.kill_counter / self.death_counter
        self.wpr = self.win_counter / self.round_counter

        # cheap time-partitioned stats (i'm just lazy)
        new_latest_kpy = self.get_stat_one_interval(interval_kills_q, start_y, end_y)
        new_latest_dpy = self.get_stat_one_interval(interval_deaths_q, start_y, end_y)
        new_latest_rpy = self.get_stat_one_interval(interval_rounds_q, start_y, end_y)

        new_latest_kpq = self.get_stat_one_interval(interval_kills_q, start_q, end_q)
        new_latest_dpq = self.get_stat_one_interval(interval_deaths_q, start_q, end_q)
        new_latest_rpq = self.get_stat_one_interval(interval_rounds_q, start_q, end_q)

        new_latest_kph = self.get_stat_one_interval(interval_kills_q, start_h, end_h)
        new_latest_dph = self.get_stat_one_interval(interval_deaths_q, start_h, end_h)
        new_latest_rph = self.get_stat_one_interval(interval_rounds_q, start_h, end_h)

        new_latest_pvepy = self.get_stat_one_interval(interval_pve_q, start_y, end_y)
        new_latest_pvepq = self.get_stat_one_interval(interval_pve_q, start_q, end_q)
        new_latest_pveph = self.get_stat_one_interval(interval_pve_q, start_h, end_h)

        self.kpy.iloc[-1] = new_latest_kpy
        self.kpq.iloc[-1] = new_latest_kpq
        self.kph.iloc[-1] = new_latest_kph

        self.dpy.iloc[-1] = new_latest_dpy
        self.dpq.iloc[-1] = new_latest_dpq
        self.dph.iloc[-1] = new_latest_dph

        self.rpy.iloc[-1] = new_latest_rpy
        self.rpq.iloc[-1] = new_latest_rpq
        self.rph.iloc[-1] = new_latest_rph

        self.pve = self.get_total_pve_d()
        self.pvepy.iloc[-1] = new_latest_pvepy
        self.pvepq.iloc[-1] = new_latest_pvepq
        self.pveph.iloc[-1] = new_latest_pveph

        self.kprpy = self.kpy / self.rpy
        self.kprpq = self.kpq / self.rpq
        self.kprph = self.kph / self.rph
        self.kdrpy = self.kpy / self.dpy
        self.kdrpq = self.kpq / self.dpq
        self.kdrph = self.kph / self.dph
        self.wprpy = self.wpy / self.rpy

        new_latest_ratings = self.player_ratings_one_year(self.kprpy.iloc[-1].to_dict(), self.wprpy.iloc[-1].to_dict(),
                                                          self.rpy.iloc[-1].to_dict(), start_y, end_y)

        for pid in self.player_map.values():
            self.yearly_ratings[pid][str(start_y)[:4]] = new_latest_ratings[pid] if pid in new_latest_ratings else np.nan

        self.all_agg_stats = {
            'kills': self.kill_counter,
            'kpy': self.kpy,
            'kpq': self.kpq,
            'kph': self.kph,
            'deaths': self.death_counter,
            'dpy': self.dpy,
            'dpq': self.dpq,
            'dph': self.dph,
            'rounds': self.round_counter,
            'rpy': self.rpy,
            'rpq': self.rpq,
            'rph': self.rph,
            'first_deaths': self.first_deaths,
            'first_bloods': self.first_bloods,
            'alive_wins': self.a_win_counter,
            'dead_wins': self.d_win_counter,
            'tied_wins': self.t_win_counter,
            'total_wins': self.win_counter,
            'kpr': self.kpr,
            'kpr_5': self.kpr_5,
            'kdr': self.kdr,
            'kdr_5': self.kdr_5,
            'wpr': self.wpr,
            'wpr_5': self.wpr_5,
            'awpy': self.awpy,
            'dwpy': self.dwpy,
            'wpy': self.wpy,
            'kpr_py': self.kprpy,
            'kpr_pq': self.kprpq,
            'kpr_ph': self.kprph,
            'kdr_py': self.kdrpy,
            'kdr_pq': self.kdrpq,
            'kdr_ph': self.kdrph,
            'wpr_py': self.wprpy,
            'pve': self.pve,
            'pve_py': self.pvepy,
            'pve_pq': self.pvepq,
            'pve_ph': self.pvepq,
            # 'final_kills': self.finals,
            'kill_records': self.krs,
            'tks': self.tks,
            'suicides': self.suicides,
            'ironmans': self.ironmans,
            'first_dmg': self.fdams,
            'top_frags': self.top_frags,
            # 'all_h2h': self.all_h2h,
            'yearly_ratings': self.yearly_ratings

        }
        with open("all_agg_stats.pkl", "wb") as f:
            pickle.dump(self.all_agg_stats, f)

        players = {ign.lower(): pid for pid, ign in
                   self.api.cur.execute("""SELECT player_id, current_ign FROM players""").fetchall()}
        with open("player_map.json", "w") as f:
            json.dump(players, f)

        with open("pve_probs.json", "w") as f:
            json.dump(self.get_pve_msg_probs(), f)

        with open("pvp_probs.json", "w") as f:
            json.dump(self.get_pvp_msg_probs(), f)

    def init_new_players(self):
        # # load updated player_map (delete later)
        # with open("player_map.json", "r") as f:
        #     self.player_map = json.load(f)
        year = datetime.today().year

        new_player_ids = [p for p in self.player_map.values() if p not in self.round_counter.columns]
        for pid in new_player_ids:
            for stat in self.stats:
                if isinstance(self.stats[stat], pd.DataFrame):
                    n_rows = self.stats[stat].shape[0]
                    self.stats[stat][pid] = np.zeros((n_rows, 1))
                elif isinstance(self.stats[stat], dict) and stat != 'yearly_ratings':
                    self.stats[stat][pid] = 0
                elif stat == 'yearly_ratings':
                    self.stats[stat][pid] = {str(y): np.nan for y in range(2012, year+1)}

    def get_interval_kills(self, m=12):

        return self.get_stat_by_interval(interval_kills_q, m)

    def get_interval_deaths(self, m=12):

        return self.get_stat_by_interval(interval_deaths_q, m)

    def get_interval_pve(self, m=12):

        return self.get_stat_by_interval(interval_pve_q, m)

    def get_interval_rounds(self, m=12):

        return self.get_stat_by_interval(interval_rounds_q, m)

    def get_total_kills(self):
        q = """
            WITH 
                        valid_seasons AS (
                            SELECT season_id
                            FROM season_killfeed
                            GROUP BY dupe_id
                        )
            SELECT killer_id, COUNT(killer_id)
                        FROM season_killfeed k
                        LEFT JOIN seasons s ON k.season_id = s.season_id
                        WHERE s.season_id IN valid_seasons
                        GROUP BY killer_id
            """
        return self.stat_to_df(q)

    def get_total_deaths(self):
        q = """
        WITH 
                    valid_seasons AS (
                        SELECT season_id
                        FROM season_killfeed
                        GROUP BY dupe_id
                    )
            SELECT dead_id, COUNT(*)
             FROM season_killfeed k
             WHERE (pve_id NOT NULL AND pve_id != "Nothing") OR (killer_id NOT NULL)
                AND k.season_id IN valid_seasons
             GROUP BY dead_id
               
            """
        return self.stat_to_df(q)

    def get_total_first_deaths(self):
        q ="""
           WITH first_deaths AS (
                SELECT dead_id, MIN(entry_id)
                FROM season_killfeed k
                GROUP BY dupe_id
            )
           SELECT dead_id, COUNT(*)
           FROM first_deaths
           GROUP BY dead_id

            """
        return self.stat_to_df(q)

    def get_total_first_bloods(self):
        q="""
                WITH first_bloods as (
                        SELECT DISTINCT dupe_id, FIRST_VALUE(killer_id) OVER (
                            
                            PARTITION BY dupe_id
                        ) as first_killer
                        FROM season_killfeed
                        WHERE killer_id NOT NULL

                )
                SELECT first_killer, COUNT(*)
                FROM first_bloods 
                GROUP BY first_killer
            """
        dk_q = """
        WITH 
        ranked AS (
            SELECT dupe_id, dead_id, killer_id,
            ROW_NUMBER() OVER (
                PARTITION BY dupe_id
            ) as rn
            FROM season_killfeed
            WHERE killer_id IS NOT NULL
            
        ),
        
        first_bloods as (
                SELECT DISTINCT dupe_id, FIRST_VALUE(dead_id) OVER (
                    PARTITION BY dupe_id
                ) as first_killed,
                
                FIRST_VALUE(killer_id) OVER (
                    
                    PARTITION BY dupe_id
                    
                ) as first_killer
                FROM season_killfeed
                WHERE killer_id IS NOT NULL
        )
        
        SELECT r.killer_id, COUNT(*)
        FROM ranked r
        JOIN first_bloods fb ON r.dupe_id = fb.dupe_id
        WHERE r.rn = 2
            AND r.killer_id IS NOT NULL
            AND fb.first_killer = r.dead_id
            AND r.killer_id = fb.first_killed
        GROUP BY r.killer_id
            """
        return self.stat_to_df(q) + self.stat_to_df(dk_q)

    def get_total_pve_d(self):
        q = """
                WITH 
                    valid_seasons AS (
                        SELECT season_id
                        FROM season_killfeed
                        GROUP BY dupe_id
                    )

                SELECT dead_id, COUNT(*)
                 FROM season_killfeed k
                 WHERE (pve_id NOT NULL AND pve_id != "Nothing")
                    AND season_id IN valid_seasons
                 GROUP BY dead_id

                    """
        return self.stat_to_df(q)

    def get_final_kills(self):
        q = """
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
                    
                    final_dead AS (
                        SELECT t.season_id, t.team, k.dead_id, k.killer_id, MAX(k.entry_id)
                        FROM season_killfeed k
                        JOIN season_teams t
                            ON k.season_id = t.season_id
                            AND k.dead_id = t.player_id
                        WHERE k.season_id IN (SELECT season_id FROM team_games)
                            AND k.killer_id IS NOT NULL
                        GROUP BY t.season_id, t.team
                    )
                    
            
                    SELECT killer_id, COUNT(*)
                    FROM final_dead
                    GROUP BY killer_id;

            """
        total_finals = {pid: finals for pid, finals in self.api.cur.execute(q).fetchall()if pid is not None}
        for id in list(self.player_map.values()):
            if id not in total_finals:
                total_finals[id] = 0
        return total_finals

    def get_kill_records(self):
        kr = """
            SELECT COUNT(killer_id)
            FROM season_killfeed
            WHERE killer_id = ?
            GROUP BY season_id
            ORDER BY COUNT(killer_id) DESC
            LIMIT 1
        """

        kill_record = {}
        for p in self.player_map.values():
            raw = self.api.cur.execute(kr, (p,)).fetchall()
            record = raw[0][0] if raw else 0
            kill_record[p] = record

        return kill_record
    def get_team_kills(self):
        q = """
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
                
                SELECT killer_id, COUNT(*)
                FROM tks
                GROUP BY killer_id
            """
        return self.stat_to_df(q)

    def get_total_rounds(self):
        q = """
             WITH 
                valid_seasons AS (
                        SELECT season_id
                        FROM season_killfeed
                        GROUP BY dupe_id
                    )
            SELECT k.dead_id, COUNT(s.season_id) 
               FROM season_killfeed k
               LEFT JOIN seasons s on k.season_id = s.season_id
               WHERE k.season_id IN valid_seasons
               GROUP BY k.dead_id
            """
        return self.stat_to_df(q)

    def get_total_wins(self):
        build = """
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
                )"""
        alive_q = """
                    SELECT dead_id, COUNT(*) as alive_wins
                    FROM alive_winners
                    GROUP BY dead_id
                    ORDER BY alive_wins DESC

                    """
        dead_q = """
                    winning_teams AS (
                        SELECT t.season_id, t.team
                        FROM season_teams t
                        JOIN alive_winners w ON t.season_id = w.dupe_id AND t.player_id = w.dead_id
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
                        WHERE w.dupe_id = t.season_id
                    )
                )

                    SELECT player_id, COUNT(*) AS dead_wins
                    FROM dead_winners
                    GROUP BY player_id
                    ORDER BY dead_wins DESC
                    """
        tied_build = """
                        WITH
                                    last_entries AS (
                                        SELECT MAX(entry_id) AS last_entry
                                        FROM season_killfeed
                                        GROUP BY dupe_id

                                    ),

                                    ending_death_seasons AS (
                                        SELECT s.season_id, k.dead_id, k.killer_id
                                        FROM seasons s
                                        JOIN season_killfeed k ON s.season_id = k.dupe_id
                                        JOIN last_entries le ON k.entry_id = le.last_entry
                                        WHERE k.killer_id NOT NULL
                                        GROUP BY k.dupe_id

                                    ),

                                    tied_winners AS (
                                    SELECT season_id, dead_id FROM ending_death_seasons
                                    UNION 
                                    SELECT season_id, killer_id FROM ending_death_seasons
                                    )
                """

        tied_alive_q = """

                                    SELECT dead_id, COUNT(*) as tied_wins
                                    FROM tied_winners
                                    GROUP BY dead_id
                                    ORDER BY tied_wins DESC
                        """
        tied_dead_q = """
                                    winning_teams AS (
                                        SELECT t.season_id, t.team
                                        FROM season_teams t
                                        JOIN tied_winners w ON t.season_id = w.season_id AND t.player_id = w.dead_id
                                    ),

                                    dead_winners AS (
                                        SELECT DISTINCT t.player_id, t.season_id
                                        FROM season_teams t
                                        JOIN winning_teams wt
                                            ON t.season_id = wt.season_id 
                                            AND t.team = wt.team
                                        WHERE t.player_id NOT IN (
                                            SELECT dead_id
                                            FROM tied_winners w
                                            WHERE w.season_id = t.season_id
                                        )
                                    )
                                    SELECT player_id, COUNT(*) AS dead_wins
                                    FROM dead_winners dw
                                    JOIN season_info i ON dw.season_id = i.season_id
                                    GROUP BY player_id
                                    ORDER BY dead_wins DESC
                """

        alive_wins = self.stat_to_df(build+alive_q)
        dead_wins = self.stat_to_df(build+','+dead_q) + self.stat_to_df(tied_build+','+tied_dead_q)
        tied_wins = self.stat_to_df(tied_build+tied_alive_q)
        print(alive_wins.shape, dead_wins.shape, tied_wins.shape)

        total_wins = pd.DataFrame({i: alive_wins[i]+dead_wins[i]+tied_wins[i] for i in alive_wins})

        return alive_wins, dead_wins, tied_wins, total_wins

    def get_suicides(self):
        q = """
                    WITH 
                        valid_seasons AS (
                            SELECT season_id
                            FROM season_killfeed
                            GROUP BY dupe_id
                        )
                    SELECT k.dead_id, COUNT(k.death_msg)
                                FROM season_killfeed as k
                                JOIN players p on k.dead_id = p.player_id
                                WHERE k.death_msg LIKE '%'||p.current_ign||'%'
                                    AND k.season_id IN valid_seasons
                                GROUP BY p.player_id
            """
        return self.stat_to_df(q)

    def get_ironmans(self):
        q = """
                WITH 
                    valid_seasons AS (
                        SELECT season_id
                        FROM season_killfeed
                        GROUP BY dupe_id
                    )
                SELECT 
                    p.player_id,
                    COUNT(*) AS season_count
                FROM players p
                JOIN season_info i
                    ON i.ironman = p.player_id
                    OR (
                        i.ironman LIKE '%[%' AND (
                            i.ironman LIKE '%'||p.player_id||', %' 
                            OR i.ironman LIKE '%, '|| p.player_id ||'%'
                        )
                    )
                WHERE season_id IN valid_seasons
                GROUP BY p.player_id
                ORDER BY season_count DESC;
                """
        total_ims = {pid: ims for pid, ims  in self.api.cur.execute(q).fetchall()if pid is not None}
        for id in list(self.player_map.values()):
            if id not in total_ims:
                total_ims[id] = 0
        return total_ims

    def get_fdams(self):
        q = """
           
                WITH 
                    valid_seasons AS (
                        SELECT season_id
                        FROM season_killfeed
                        GROUP BY dupe_id
                    )
            SELECT player_id, COUNT(first_dmg)
                FROM players p
                JOIN season_info i ON i.first_dmg = player_id
                WHERE i.season_id IN valid_seasons
                GROUP BY player_id
               
            """
        total_fdams = {pid: fd for pid, fd in self.api.cur.execute(q).fetchall()if pid is not None}
        for id in list(self.player_map.values()):
            if id not in total_fdams:
                total_fdams[id] = 0
        return total_fdams

    def get_top_frags(self):
        q = """

                SELECT
                    killer_id,
                    COUNT(*)
                FROM (
                    SELECT
                        dupe_id,
                        killer_id,
                        COUNT(*) AS kills,
                        RANK() OVER (
                            PARTITION BY dupe_id
                            ORDER BY COUNT(*) DESC
                        ) AS rank_in_game
                    FROM season_killfeed
                    WHERE killer_id NOT NULL
                    GROUP BY dupe_id, killer_id
                )
                WHERE rank_in_game = 1
                GROUP BY killer_id
              """
        total_tf = {pid: tf for pid, tf in self.api.cur.execute(q).fetchall()if pid is not None}
        for id in list(self.player_map.values()):
            if id not in total_tf:
                total_tf[id] = 0
        return total_tf

    def get_yearly_wins(self):
        build = """
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
                            WHERE k.killer_id IS NULL AND k.death_msg = ''
                        ),
                        alive_winners AS (
                            SELECT * FROM obj_winners
                            UNION
                            SELECT * FROM br_alive_winners
                        )"""
        alive_q = """
                            SELECT dead_id, COUNT(*) as alive_wins
                            FROM alive_winners aw
                            JOIN season_info i ON aw.season_id = i.season_id
                            WHERE i.date >= ? AND i.date < ? 
                            GROUP BY dead_id
                            ORDER BY alive_wins DESC

                            """
        dead_q = """
                            winning_teams AS (
                                SELECT t.season_id, t.team
                                FROM season_teams t
                                JOIN alive_winners w ON t.season_id = w.season_id AND t.player_id = w.dead_id
                            ),

                            dead_winners AS (
                                SELECT DISTINCT t.player_id, t.season_id
                                FROM season_teams t
                                JOIN winning_teams wt
                                    ON t.season_id = wt.season_id 
                                    AND t.team = wt.team
                                WHERE t.player_id NOT IN (
                                    SELECT dead_id
                                    FROM alive_winners w
                                    WHERE w.season_id = t.season_id
                                )
                            )
                            SELECT player_id, COUNT(*) AS dead_wins
                            FROM dead_winners dw
                            JOIN season_info i ON dw.season_id = i.season_id
                            WHERE i.date >= ? AND i.date < ?
                            GROUP BY player_id
                            ORDER BY dead_wins DESC
                            """
        tied_build = """
                WITH
                            last_entries AS (
                                SELECT MAX(entry_id) AS last_entry
                                FROM season_killfeed
                                GROUP BY season_id

                            ),

                            ending_death_seasons AS (
                                SELECT s.season_id, k.dead_id, k.killer_id
                                FROM seasons s
                                JOIN season_killfeed k ON s.season_id = k.season_id
                                JOIN last_entries le ON k.entry_id = le.last_entry
                                JOIN season_info i ON s.season_id = i.season_id
                                WHERE k.killer_id NOT NULL
                                    AND i.date >= ? AND i.date < ?

                            ),

                            tied_winners AS (
                            SELECT season_id, dead_id FROM ending_death_seasons
                            UNION 
                            SELECT season_id, killer_id FROM ending_death_seasons
                            )
        """


        tied_alive_q = """

                            SELECT dead_id, COUNT(*) as tied_wins
                            FROM tied_winners
                            GROUP BY dead_id
                            ORDER BY tied_wins DESC
                """
        tied_dead_q = """
                            winning_teams AS (
                                SELECT t.season_id, t.team
                                FROM season_teams t
                                JOIN tied_winners w ON t.season_id = w.season_id AND t.player_id = w.dead_id
                            ),

                            dead_winners AS (
                                SELECT DISTINCT t.player_id, t.season_id
                                FROM season_teams t
                                JOIN winning_teams wt
                                    ON t.season_id = wt.season_id 
                                    AND t.team = wt.team
                                WHERE t.player_id NOT IN (
                                    SELECT dead_id
                                    FROM tied_winners w
                                    WHERE w.season_id = t.season_id
                                )
                            )
                            SELECT player_id, COUNT(*) AS dead_wins
                            FROM dead_winners dw
                            JOIN season_info i ON dw.season_id = i.season_id
                            GROUP BY player_id
                            ORDER BY dead_wins DESC
        """

        yearly_alive_wins = self.get_stat_by_interval(build+alive_q)
        yearly_dead_wins = self.get_stat_by_interval(build+','+dead_q)+self.get_stat_by_interval(tied_build+','+tied_dead_q)
        yearly_tied_wins = self.get_stat_by_interval(tied_build+tied_alive_q)
        total_yearly_wins = yearly_dead_wins + yearly_alive_wins + yearly_tied_wins

        return yearly_alive_wins, yearly_dead_wins, total_yearly_wins

    def get_stat_by_interval(self, q, m=12):
        by_interval_stat = defaultdict(dict)

        intervals = FullAggregation.make_intervals(m)

        for idx in range(len(intervals)-1):
            interval_dict = self.get_stat_one_interval(q,intervals[idx], intervals[idx+1])
            by_interval_stat[intervals[idx]] = interval_dict


        return pd.DataFrame(by_interval_stat).T

    def get_stat_one_interval(self, q, start, stop):
        interval_stat = self.api.cur.execute(q, (start, stop)).fetchall()
        interval_dict = {pid: stat for pid, stat in interval_stat if pid is not None}

        # fill in missing keys with 0s
        for pid in list(self.player_map.values()):
            if pid not in interval_dict:
                interval_dict[pid] = 0

        return interval_dict

    def stat_to_df(self, q):
        total = {pid: [stat] for pid, stat in self.api.cur.execute(q).fetchall()if pid is not None}
        for id in list(self.player_map.values()):
            if id not in total:
                total[id] = [0]
        return pd.DataFrame(total)

       # return result_dict
    def player_profile(self, ign):
        """
        generates player-specific metrics
        or metrics unsuitable for observing on a leaderboard
        :param ign:
        :return:
        """
        self.api._reopen()
        start = time()
        print(ign)
        player_id = self.player_map[ign.lower()]
        stats = self.api.cur.execute(
            """
                SELECT *
                FROM player_stats
                WHERE player_id = ?
            """

        , (player_id, )).fetchall()[0]

        total_kills = stats[1]
        total_deaths = stats[2]
        total_rounds = stats[3]


        kdr = stats[4]
        kpr = stats[5]
        wpr = stats[6]
        kdr_percentile = stats[7]
        kpr_percentile = stats[8]
        wpr_percentile = stats[9]
        first_deaths = stats[10]


        rounds_by_period = ast.literal_eval(stats[11])
        kills_by_period = ast.literal_eval(stats[12])
        deaths_by_period = ast.literal_eval(stats[13])
        kpr_by_period = clean_literals(stats[14])
        kdr_by_period = clean_literals(stats[15])
        dpr_by_period = clean_literals(stats[16])
        pve_by_period = clean_literals(stats[17])

        ffa_kills = stats[18]
        team_game_kills = stats[19]
        total_wins = stats[20]
        yearly_wins = defaultdict(int, clean_literals(stats[21]))

        kill_record = stats[22]
        debut_date = stats[23]
        debut_rr = stats[24]
        lp_date = stats[25]
        last_rr = stats[26]
        tks = stats[27]
        suicides = stats[28]
        alive_wins = ast.literal_eval(stats[29])
        dead_wins = ast.literal_eval(stats[30])

        nemeses = clean_literals(stats[31])
        rivals = clean_literals(stats[32])
        dominating = clean_literals(stats[33])
        ironmans = stats[34]
        longest_ironman = stats[35]
        first_dmgs = stats[36]
        top_frags = stats[37]
        redacted = stats[38]

        # newer stats
        tied_wins = stats[39]
        if tied_wins:
           tied_wins = ast.literal_eval(tied_wins)
        rating = clean_literals(stats[40])
        first_bloods = stats[41]

        player_info = {
            'kills': total_kills, #
            'deaths': total_deaths, #
            'rounds': total_rounds, #
            'kdr': kdr, #
            'kpr': kpr, #
            'wpr': wpr, #
            'kdr_percentile': kdr_percentile, #
            'kpr_percentile': kpr_percentile, #
            'wpr_percentile': wpr_percentile, #
            'first_deaths': first_deaths, #
            'rounds_by_period': rounds_by_period,
            'kills_by_period': kills_by_period,
            'deaths_by_period': deaths_by_period,
            'kpr_by_period': kpr_by_period,
            'kdr_by_period': kdr_by_period,
            'dpr_by_period': dpr_by_period,
            'pve_by_period': pve_by_period,
            'ffa_kills': ffa_kills,
            'team_game_kills': team_game_kills,
            'total_wins': total_wins, #
            'alive_wins': alive_wins, #
            'dead_wins': dead_wins, #
            'yearly_wins': yearly_wins, #
            'kill_record': kill_record,
            'debut_date': debut_date, #
            'debut_rr': debut_rr, #
            'last_played': lp_date, #
            'last_rr': last_rr, #
            'tks': tks, #
            'suicides': suicides, #
            'nemeses': nemeses, #
            'rivals': rivals, #
            'dominating': dominating, #
            'ironmans': ironmans, #
            'longest_im': longest_ironman, #
            'first_dmgs': first_dmgs,
            'top_frags': top_frags,
            'redacted': redacted,
            'tied_wins': tied_wins, #
            'first_bloods': first_bloods,
            'rating': rating #

        }


        print(time()-start)
        return player_info



    # def combined_player_ratings(self):
    #
    #     ranker = RelRankPlayers(self.all_h2h, self.kpr.iloc[0, :].to_dict(), self.wpr.iloc[0, :].to_dict(),
    #                             self.round_counter.iloc[0, :].to_dict())
    #     rrpr = ranker.ratings
    #     return rrpr

    def player_ratings_by_period(self):

        intervals = self.make_intervals(12)
        #year_divided_ratings = defaultdict(dict[dict])

        player_year_rating = {p: {} for p in self.player_map.values()}
        for i in range(len(intervals)-1):
            year = intervals[i][:4]
            print(year)
            kpr = self.kprpy.iloc[i, :].to_dict()
            wpr = self.wprpy.iloc[i, :].to_dict()
            rounds = self.rpy.iloc[i, :].to_dict()
            if sum(list(rounds.values())) == 0:
                break

            ratings = self.player_ratings_one_year(kpr, wpr, rounds, intervals[i], intervals[i+1])

            for pid in self.player_map.values():
                player_year_rating[pid][year] = ratings[pid] if pid in ratings else np.nan


        return player_year_rating

    def player_ratings_one_year(self, kpr, wpr, rounds, start, stop):
        if sum(list(rounds.values())) == 0:
            return {}
        yearly_h2h = {}  # {player: {enemy: (w, l),...},...}
        for pid in self.player_map.values():
            h2h = self.api.cur.execute(interval_h2h_q,
                                       (pid, start, stop, pid, start, stop))
            yearly_h2h[pid] = {enemy: [w, l] for enemy, w, l in h2h} if h2h else {}
        pprint(yearly_h2h)
        yearly_h2h = self.remove_tks(yearly_h2h, start, stop)
        ranker = RelRankPlayers(yearly_h2h, kpr, wpr, rounds)
        ratings = ranker.ratings
        return ratings

    def remove_tks(self, node_dict, start, stop):
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
                                SELECT k.dead_id, k.killer_id
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
                                    AND (i.date >= ? AND i.date < ?)
                                    
                            )

                            SELECT *
                            FROM tks



            """
        team_kills = self.api.cur.execute(tk, (start, stop)).fetchall()
        for entry in team_kills:
            dead_id, killer_id = entry

            dead_ign = self.api.cur.execute("SELECT current_ign FROM players WHERE player_id = ?", (dead_id,)).fetchall()[0][0]
            killer_ign = self.api.cur.execute("SELECT current_ign FROM players WHERE player_id = ?", (killer_id,)).fetchall()[0][0]

            print(dead_ign, killer_ign)
            node_dict[killer_id][dead_ign][0] -= 1
            node_dict[dead_id][killer_ign][1] -= 1
        return node_dict

    def round_profile(self, rr):
        season_q_build = """
            WITH round_seasons AS (
                SELECT season_no, season_id
                FROM seasons
                WHERE round_name = ?
            )
        """
        seasons_q = """
            SELECT season_no
            FROM round_seasons s
        """


        seasons = [i[0] for i in self.api.cur.execute(season_q_build+seasons_q, (rr,)).fetchall()]
        n_seasons = self.api.cur.execute(season_q_build+"SELECT COUNT(*) FROM round_seasons", (rr,)).fetchall()[0][0]
        avg_eps_q = """
            SELECT AVG(eps) 
            FROM season_info i
            JOIN round_seasons s ON i.season_id = s.season_id
            
        """
        avg_eps = round(self.api.cur.execute(season_q_build+avg_eps_q, (rr,)).fetchall()[0][0], 2)

        roster_q = """
            SELECT DISTINCT(k.dead_id)
            FROM season_killfeed k
            JOIN round_seasons s ON k.season_id = s.season_id
        """
        roster = [i[0] for i in self.api.cur.execute(season_q_build+roster_q, (rr,)).fetchall()]
        roster_size = len(roster)

        szn_dates_q = """
            SELECT i.date
            FROM season_info i
            JOIN round_seasons s ON i.season_id = s.season_id
        """
        season_dates = [i[0] for i in self.api.cur.execute(season_q_build+szn_dates_q, (rr,)).fetchall()]
        first_year = int(season_dates[0][:4])
        season_datetimes = [datetime.strptime(d, '%Y-%m-%d') for d in season_dates]
        season_gaps = [season_datetimes[i+1]-season_datetimes[i] for i in range(len(season_datetimes)-1)]
        since_last_season = (datetime.today() - season_datetimes[-1]).days
        last_season_year = season_datetimes[-1].year
        season_gaps = [i.days for i in season_gaps]

        player_ratings_q = """
            ,
            roster AS (
                SELECT DISTINCT(dead_id)
                FROM season_killfeed k
                JOIN round_seasons s ON k.season_id = s.season_id
            )
            SELECT player_id, ratings
            FROM player_stats ps
            JOIN roster r ON ps.player_id = r.dead_id
            
        """
        players_ratings = self.api.cur.execute(season_q_build+player_ratings_q, (rr,)).fetchall()

        roster_ratings = {p: clean_literals(i) for p, i in players_ratings}
        rating_df = pd.DataFrame(roster_ratings.values())
        median_ratings = [np.median(rating_df[y].dropna()) for y in rating_df][first_year-2012:last_season_year+1]
        mean_ratings = [np.mean(rating_df[y]) for y in rating_df][first_year-2012:last_season_year+1]
        std_ratings = [np.std(rating_df[y]) for y in rating_df][first_year-2012:last_season_year+1]

        pve_deaths_q = """
            ,pve_deaths AS (
                SELECT COUNT(*) as pve
                FROM season_killfeed k
                JOIN round_seasons s on k.season_id = s.season_id
                WHERE k.pve_id IS NOT NULL AND killer_id IS NULL
                    AND k.pve_id IS NOT "Nothing"
            ),
            all_deaths AS (
                SELECT COUNT(*) as all_d
                FROM season_killfeed k
                JOIN round_seasons s on k.season_id = s.season_id
                WHERE k.killer_id != "Nothing"
            )
            SELECT CAST(p.pve AS float)/CAST(a.all_d AS float)
            FROM pve_deaths p
            JOIN all_deaths a
            
            
        """
        percent_pve = round(self.api.cur.execute(season_q_build+pve_deaths_q, (rr,)).fetchall()[0][0] *100, 1)

        players_per_season_q = """
            SELECT COUNT(DISTINCT(k.dead_id))
            FROM season_killfeed k
            JOIN round_seasons s ON k.season_id = s.season_id
            GROUP BY s.season_id
        """
        players_per_season = [i[0] for i in self.api.cur.execute(season_q_build+players_per_season_q, (rr,)).fetchall()]


        roster_id_one_season = """
            SELECT DISTINCT(dead_id)
            FROM season_killfeed
            WHERE season_id = ?
        """
        season_rosters = []
        for season_id in [s[0] for s in self.api.cur.execute(season_q_build+"SELECT season_id FROM round_seasons", (rr,)).fetchall()]:
            season_rosters.append([p[0] for p in self.api.cur.execute(roster_id_one_season, (season_id,)).fetchall()])

        # rep players


        round_dict = {
            'season_count': n_seasons,
            'avg_eps': avg_eps,
            'roster_size': roster_size,
            'season_dates': season_dates,
            'season_gaps': season_gaps,
            'since_last_season': since_last_season,
            'median_ratings': median_ratings,
            'mean_ratings': mean_ratings,
            'std_ratings': std_ratings,
            'percent_pve': percent_pve,
            'roster_ids': roster,
            'latest_year': last_season_year,
            'seasons': seasons,
            'players_by_season': players_per_season,
            'season_rosters': season_rosters,
            'player_ratings': roster_ratings,


        }

        return round_dict

    def season_profile(self, rr, season_no):
        q = """
            SELECT season_id
            FROM seasons
            WHERE round_name = ? AND season_no = ?
        """
        season_id = self.api.cur.execute(q, (rr, season_no)).fetchall()[0][0]
        kill_feed_q = """
            SELECT p2.current_ign, k.death_msg, p.current_ign, k.pve_id, k.killstealer
            FROM season_killfeed k
            LEFT JOIN players p ON k.killer_id = p.player_id
            LEFT JOIN players p2 ON k.dead_id = p2.player_id

            WHERE k.season_id = ?
        """
        kill_feed = self.api.cur.execute(kill_feed_q, (season_id,)).fetchall()


        season_info_q = """
            SELECT * FROM season_info
            WHERE season_id = ?
        """
        all_season_info = self.api.cur.execute(season_info_q, (season_id,)).fetchall()
        _, alias, nr, date, eps, team_size, team_type, version, im, im_time, fdam, fdam_time = all_season_info[0]

        if ']' in im:
            ironmans = ast.literal_eval(im)
            ironman = ', '.join([self.api.cur.execute("SELECT current_ign FROM players WHERE player_id = ?"
                                  , (i,)).fetchall()[0][0] for i in ironmans])

        else:
            ironman = self.api.cur.execute("SELECT current_ign FROM players WHERE player_id = ?", (im,)).fetchall()
            ironman = ironman[0][0]

        if fdam != 'N/A':
            first_damage = self.api.cur.execute("SELECT current_ign FROM players WHERE player_id = ?", (fdam,)).fetchall()[0][0]
        else:
            first_damage = 'N/A'



        gamemodes = [i[0] for i in
            self.api.cur.execute("SELECT gamemode FROM season_gms WHERE season_id = ?", (season_id,)).fetchall()]

        season_teams_q = """
            SELECT t.team, p.current_ign
            FROM season_teams t
            JOIN players p ON t.player_id = p.player_id
            WHERE t.season_id = ?

        """

        season_teams = self.api.cur.execute(season_teams_q, (season_id,)).fetchall()
        team_dict = defaultdict(list)
        for i in season_teams:
            team, player = i
            team_dict[team].append(player)

        team_kills_q = """

            SELECT t.team, COUNT(k.killer_id)
            FROM season_teams t
            LEFT JOIN season_killfeed k ON k.killer_id = t.player_id
                AND k.season_id = t.season_id
            WHERE t.season_id = ? 
            GROUP BY t.team
            
            
        """
        team_kills = {t:k for t, k in self.api.cur.execute(team_kills_q, (season_id,)).fetchall()}

        team_placement_q = """
            SELECT t.team, MAX(k.entry_id)
            FROM season_teams t
            LEFT JOIN season_killfeed k
                ON k.dead_id = t.player_id
                AND k.season_id = t.season_id
            WHERE t.season_id = ?
            GROUP BY t.team
            ORDER BY MAX(k.entry_id) DESC
        """

        team_placement = [t[0] for t in self.api.cur.execute(team_placement_q, (season_id,)).fetchall()]

        ffa_kills_q = """
            WITH selected_season AS (
                SELECT *
                FROM season_killfeed k
                WHERE season_id = ?
            ),
            roster AS (
                SELECT DISTINCT(dead_id)
                FROM season_killfeed
                WHERE season_id = ?
            )
            
            
            SELECT DISTINCT(p.current_ign), COALESCE(COUNT(s2.killer_id), 0)
            FROM roster r
            
            LEFT JOIN selected_season s2 ON s2.killer_id = r.dead_id
            LEFT JOIN players p ON p.player_id = r.dead_id
            GROUP BY p.player_id

            ORDER BY MAX(s2.entry_id) DESC

        """

        ffa_kills = {k:count for k, count in self.api.cur.execute(ffa_kills_q, (season_id,season_id)).fetchall()}

        newcomers_q = """
            SELECT p.current_ign
            FROM season_killfeed k
            JOIN players p ON k.dead_id = p.player_id
            WHERE k.season_id = ?  AND p.player_id NOT IN (
                SELECT k.dead_id 
                FROM season_killfeed k
                JOIN seasons s ON k.season_id = s.season_id
                WHERE s.season_id < ? AND s.round_name = ?)
        """

        newcomers = [p[0] for p in self.api.cur.execute(newcomers_q, (season_id, season_id, rr)).fetchall()]

        season_dict = {
            'kill_feed': kill_feed,
            'alias': alias,
            'nr': nr,
            'eps': eps,
            'team_size': team_size,
            'team_type': team_type,
            'version': version,
            'gamemodes': gamemodes,
            'ironman': ironman,
            'ironman_time': im_time,
            'first_damage': first_damage,
            'first_damage_time': fdam_time,
            'team_kills': team_kills,
            'teams': team_dict,
            'team_placement': team_placement,
            'ffa_kills': ffa_kills,
            'newcomers': newcomers,
            'date': date,


        }
        return season_dict

    def leaderboard_graph_stats(self):

        igns_raw = self.api.cur.execute("SELECT player_id, current_ign FROM players").fetchall()
        igns = {n: p for n, p in igns_raw}

        kills = {i:list(v.values())[0] for i, v in self.kill_counter.to_dict().items()}
        kpy = self.kpy.astype(int)
        deaths = {i:list(v.values())[0] for i, v in self.death_counter.to_dict().items()}
        dpy = self.dpy.astype(int)
        rounds = {i:list(v.values())[0] for i, v in self.round_counter.to_dict().items()}
        rpy = self.rpy.astype(int)
        wins = {i:list(v.values())[0] for i, v in self.win_counter.to_dict().items()}
        wpy = self.wpy.astype(int)
        alive_wins = {i:list(v.values())[0] for i, v in self.a_win_counter.to_dict().items()}
        awpy = self.awpy.astype(int)
        dead_wins = {i:list(v.values())[0] for i, v in self.d_win_counter.to_dict().items()}
        dwpy = self.dwpy.astype(int)
        tied_wins = {i:list(v.values())[0] for i, v in self.t_win_counter.to_dict().items()}
        pve = {i:list(v.values())[0] for i, v in self.pve.to_dict().items()}
        pvepy = self.pvepy.astype(int)
        top_frags = self.top_frags
        fdams = self.fdams
        fdeaths = {i:list(v.values())[0] for i, v in self.first_deaths.to_dict().items()}
        suicides = {i:list(v.values())[0] for i, v in self.suicides.to_dict().items()}
        ironmans = self.ironmans
        tks = {i:list(v.values())[0] for i, v in self.tks.to_dict().items()}

        kdr = {i: list(v.values())[0] for i, v in (self.kdr.round(2)).to_dict().items()}
        kdrpy = self.kdrpy.round(3)
        kpr = {i: list(v.values())[0] for i, v in (self.kpr.round(2)).to_dict().items()}
        kprpy = self.kprpy.round(3)
        wpr = {i: round(list(v.values())[0], 1) for i, v in (100*self.wpr.round(3)).to_dict().items()}
        wprpy = self.wprpy.round(3)


        top_frag_rate = {i:round(100*v/rounds[i], 1) for i, v in top_frags.items()}
        pve_rate = {i:round(100*v/deaths[i], 1) if deaths[i] != 0 else float('nan') for i, v in pve.items()} # % of deaths being pve
        suicide_rate = {i:round(100*v/deaths[i], 1) if deaths[i] != 0 else float('nan') for i, v in suicides.items()}
        fdam_rate = {i:round(100*v/rounds[i], 1) for i, v in fdams.items()}
        fdeath_rate = {i:round(100*v/rounds[i], 1) for i, v in fdeaths.items()}
        ironman_rate = {i:round(100*v/rounds[i], 1) for i, v in ironmans.items()}
        alive_win_rate = {i:round(100*v/rounds[i], 1) for i, v in alive_wins.items()}
        dead_win_rate = {i:round(100*v/rounds[i], 1) for i, v, in dead_wins.items()}
        tied_win_rate = {i:round(100*v/rounds[i], 1) for i, v, in tied_wins.items()}
        kr = self.krs


        longest_ims_q = """
            WITH valid_seasons AS (
                SELECT season_id
                FROM season_killfeed
                GROUP BY dupe_id
            )
            SELECT p.player_id, i.im_time, s.round_name, s.season_no, i.date
            FROM season_info i
            JOIN players p ON i.ironman = p.player_id
            JOIN seasons s ON i.season_id = s.season_id
            WHERE i.season_id IN valid_seasons
            ORDER BY i.im_time DESC

        """
        longest_ims = [(p, t, ' '.join([rr, s]), d) for p, t, rr, s, d in self.api.cur.execute(longest_ims_q).fetchall()]

        fdams_q = """
                    WITH valid_seasons AS (
                        SELECT season_id
                        FROM season_killfeed
                        GROUP BY dupe_id
                    )
                    SELECT p.player_id, i.fdam_time, s.round_name, s.season_no, i.date
                    FROM season_info i
                    JOIN players p ON i.first_dmg = p.player_id
                    JOIN seasons s ON i.season_id = s.season_id
                    WHERE i.season_id IN valid_seasons
                    ORDER BY i.fdam_time DESC
                    """
        latest_fdams = [(p, t, ' '.join([rr, s]), d) for p, t, rr, s, d in self.api.cur.execute(fdams_q).fetchall()]

        redacted = [i[0] for i in self.api.cur.execute("SELECT player_id FROM player_stats WHERE redacted IS NOT NULL").fetchall()]

        stats_dict = {
            'Kill Count': kills,
            'Death Count': deaths,
            'Rounds Played': rounds,
            'Win Count': wins,
            'Alive Win Count': alive_wins,
            'Alive Win Rate': alive_win_rate,
            'Dead Win Count': dead_wins,
            'Dead Win Rate': dead_win_rate,
            'Tied Win Count': tied_wins,
            'Tied Win Rate': tied_win_rate,
            'Win Rate': wpr,
            'KDR': kdr,
            'KPR': kpr,
            'PvE Death Count': pve,
            'PvE Death Rate': pve_rate,
            'Ironman Count': ironmans,
            'Ironman Rate': ironman_rate,
            'Top Frag Count': top_frags,
            'Top Frag Rate': top_frag_rate,
            'First Damage Count': fdams,
            'First Damage Rate': fdam_rate,
            'First Death Count': fdeaths,
            'First Death Rate': fdeath_rate,
            'Suicide Count': suicides,
            'Suicide Rate': suicide_rate,
            'Team Kill Count': tks,
            'Kill Record': kr,


            'Yearly Kill Count': kpy.T.to_dict(),
            'Yearly Death Count': dpy.T.to_dict(),
            'Yearly Rounds Played': rpy.T.to_dict(),
            'Yearly Win Count': wpy.T.to_dict(),
            'Yearly Alive Win Count': awpy.T.to_dict(),
            'Yearly Dead Win Count': dwpy.T.to_dict(),
            'Yearly Tied Win Count': (wpy-awpy-dwpy).T.to_dict(),
            'Yearly PvE Death Count': pvepy.T.to_dict(),
            'Yearly PvE Death Rate': (100*(pvepy/dpy)).round(2).T.to_dict(),
            'Yearly KDR': kdrpy.T.to_dict(),
            'Yearly KPR': kprpy.T.to_dict(),
            'Yearly Win Rate': (100*wprpy).round(2).T.to_dict(),
            'Yearly Alive Win Rate': (100*(awpy / wpy)).round(2).T.to_dict(),
            'Yearly Dead Win Rate': (100*(dwpy / wpy)).round(2).T.to_dict(),
            'Yearly Tied Win Rate': (100*((wpy-awpy-dwpy)/wpy)).round(2).T.to_dict(),
            'Yearly Ratings': self.yearly_ratings,
            'Longest Ironman': longest_ims,
            'Latest First Damages': latest_fdams,

            'igns': igns,
            'redacted': redacted

        }

        return stats_dict

    def get_deadliest(self, t_size=None, mode='kills'):
        if mode == 'kills':
            idx = 3
        else:
            idx = 4
        deadly_ffa = f"""
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
                        WHERE i.team_type = "FFA" AND i.season_id IN valid_seasons
                    )
                    SELECT p.current_ign, toX.round_name, toX.season_no, COUNT(k.killer_id) AS kills
                    FROM season_killfeed k
                    JOIN toX ON k.season_id = toX.season_id
                    JOIN players p ON k.killer_id = p.player_id
                    GROUP BY k.season_id, k.killer_id
                    ORDER BY {mode} DESC
                    
        """

        deadly_all = f"""
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
                        WHERE i.season_id IN valid_seasons
                    ),
                    ffa AS (
                        SELECT i.season_id, s.round_name, s.season_no
                        FROM season_info i 
                        JOIN seasons s ON i.season_id = s.season_id
                        WHERE i.team_type = "FFA" AND i.season_id IN valid_seasons
                    ),
                    ffa_kills AS (
                        SELECT k.season_id, p.current_ign as team_members, COUNT(k.killer_id) AS kills
                        FROM season_killfeed k
                        JOIN toX ON k.season_id = toX.season_id
                        JOIN players p ON k.killer_id = p.player_id
                        GROUP BY k.season_id, k.killer_id
                        ORDER BY kills DESC
                    
                    ),

                    team_kills AS (
                        SELECT DISTINCT t.season_id, GROUP_CONCAT(DISTINCT p.current_ign) AS team_members,
                         COUNT(k.killer_id) AS kills
                        FROM season_teams t
                        LEFT JOIN season_killfeed k ON k.killer_id = t.player_id
                            AND k.season_id = t.season_id
                        JOIN players p ON t.player_id = p.player_id
                        WHERE t.season_id IN (SELECT season_id FROM toX)
                        GROUP BY t.season_id, t.team
                        ORDER BY kills
                    ),
                    roster_size AS (
                        SELECT season_id, COUNT(DISTINCT k.dead_id) as size
                        FROM season_killfeed k
                        GROUP BY season_id
                    ),
                    roster AS (
                        SELECT season_id, COUNT(DISTINCT k.dead_id) as size
                        FROM season_killfeed k
                        GROUP BY season_id
                    ),
    
                    all_kills AS (
                        SELECT * FROM ffa_kills
                        UNION
                        SELECT * FROM team_kills
                        
                    )
                     SELECT ak.team_members, s.round_name, s.season_no, ak.kills, 
                            ROUND(100*CAST(ak.kills AS FLOAT)/CAST(r.size AS FLOAT), 1) AS pct_killed
                    FROM all_kills ak
                    JOIN roster_size r ON ak.season_id = r.season_id
                    JOIN seasons s ON ak.season_id = s.season_id
                    ORDER BY {mode} DESC
        """

        deadly_teams = f"""
                    
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
                    ORDER BY {mode} DESC
        """

        if not t_size or t_size == 0: # player kill records
            deadliest = self.api.cur.execute(deadly_all).fetchall()
        elif t_size == 1: # ffa kill records
            deadliest = self.api.cur.execute(deadly_ffa).fetchall()
        else: # team game combined kill records
            deadliest = self.api.cur.execute(deadly_teams, (t_size,)).fetchall()

        return sorted(deadliest, key=lambda x: x[idx], reverse=True)

    def simple_player_stats(self, player):
        # for simulator use

        q = """
            SELECT time_divided_pve, time_divided_rounds, lifetime_kpr, lifetime_wpr, ratings
            FROM player_stats
            WHERE player_id IN (SELECT player_id FROM players WHERE current_ign = ?)
        """
        raw_pve, raw_rounds, kpr, wpr, raw_ratings = self.api.cur.execute(q, (player,)).fetchall()[0]
        pve = clean_literals(raw_pve)
        clean_rounds = clean_literals(raw_rounds)
        rounds =  [i for i in clean_literals(raw_rounds)['12M'] if i != 0][-1]
        rating = list({i:v for i, v in clean_literals(raw_ratings).items() if not math.isnan(v)}.items())[-1]
        return round(100*sum(list(pve.values())[0])/sum(clean_rounds['12M']), 2), rounds, kpr, wpr, rating

    def get_pvp_msg_probs(self):
        msg_probs = {}

        pvp_q = """
            SELECT k.death_msg, COUNT(*)
            FROM season_killfeed k
            WHERE k.killer_id IS NOT NULL
            AND NOT EXISTS (
                            SELECT 1
                            FROM players p
                            WHERE k.death_msg LIKE '%' || p.current_ign || '%'
                        )
            GROUP BY k.death_msg
        """
        counts = self.api.cur.execute(pvp_q).fetchall()
        total = sum([i[1] for i in counts])
        for c in counts:
            msg, count = c
            msg_probs[msg] = count/total

        return msg_probs

    def get_pve_msg_probs(self):
        msg_probs = {}

        pve_q = """
                    SELECT k.death_msg, k.pve_id, COUNT(*)
                    FROM season_killfeed k
                    WHERE k.pve_id != "Nothing" 
                        AND k.pve_id IS NOT NULL 
                        AND k.killstealer IS NULL
                        AND k.death_msg != ''
                        AND NOT EXISTS (
                            SELECT 1
                            FROM players p
                            WHERE k.death_msg LIKE '%' || p.current_ign || '%'
                        )
                    GROUP BY death_msg, pve_id
                """
        counts = self.api.cur.execute(pve_q).fetchall()
        total = sum([i[2] for i in counts])
        for c in counts:
            death_msg, cause, count = c
            msg_probs[str([death_msg, cause])] = count/total

        return msg_probs

    @staticmethod
    def make_intervals(m=3):
        start = datetime.strptime('2012-01-01', '%Y-%m-%d')
        intervals = [datetime.strftime(start, '%Y-%m-%d')]
        current = start
        while current < datetime.today():
            current = current + relativedelta(months=m)
            intervals.append(datetime.strftime(current, "%Y-%m-%d"))
        return intervals





