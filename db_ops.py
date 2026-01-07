"""
Contains a class of operations to use to interact with the database
"""
import sqlite3
from db_init import initialize

class DBOPs:
    def __init__(self, filename, uri=False):
        self.db_file = filename
        self.conn = sqlite3.connect(filename, uri=uri)
        self.cur = self.conn.cursor()

    def _save(self):
        self.conn.commit()
        self.conn.close()

    def _reopen(self):
        self.conn = sqlite3.connect(self.db_file)
        self.cur = self.conn.cursor()

    def _reset(self):
        """
        Resets/reinitializes database
        :return:
        """
        tables = []
        for i in tables:
            query = f"TRUNCATE TABLE {i}"

    def reload_data(self):
        """
        Fully (re)loads all round data from the most updated .json to the database
        Creates Backup of current version first


        """
        self.conn.commit()


    def update_profile(self,lifetime_kills,
                             lifetime_deaths,
                             lifetime_rounds,
                             lifetime_kdr,
                             lifetime_kpr,
                             lifetime_wpr,

                             kdr_percentile,
                             kpr_percentile,
                             wpr_percentile,

                             first_deaths,

                             time_divided_rounds,
                             time_divided_kills,
                             time_divided_deaths,
                             time_divided_kpr,
                             time_divided_kdr,
                             time_divided_dpr,
                             time_divided_pve,

                             lifetime_ffa_kills,
                             lifetime_teams_kills,

                             lifetime_wins,
                             year_divided_winrate,

                             kill_record,
                             debut,
                             debut_rr,
                             last_played,
                             last_rr,
                             team_kills,
                             suicides,
                             alive_wins,
                             dead_wins,

                             nemeses,
                             rivals,
                             dominating,
                             lifetime_ironmans,
                             longest_ironman,
                             lifetime_first_dmg,
                             top_frags,
                             tied_wins,
                             first_bloods,
                             ratings,
                             player_id):
        """
        (use after time cycle or on button interact)
        updates player profile

        """

        q = """
                 UPDATE player_stats
                 set

                    lifetime_kills = ?,
                    lifetime_deaths = ?,
                    lifetime_rounds = ?,
                    lifetime_kdr = ?,
                    lifetime_kpr = ?,
                    lifetime_wpr = ?,

                    kdr_percentile = ?,
                    kpr_percentile = ?,
                    wpr_percentile = ?,

                    first_deaths = ?,

                    time_divided_rounds = ?,
                    time_divided_kills = ?,
                    time_divided_deaths = ?,
                    time_divided_kpr = ?,
                    time_divided_kdr = ?,
                    time_divided_dpr = ?,
                    time_divided_pve = ?,

                    lifetime_ffa_kills = ?,
                    lifetime_teams_kills = ?,

                    lifetime_wins = ?,
                    yearly_wins = ?,

                    kill_record = ?,
                    debut = ?,
                    debut_rr = ?,
                    last_played = ?,
                    last_rr = ?,
                    team_kills = ?,
                    suicides = ?,
                    alive_wins = ?,
                    dead_wins = ?,

                    nemeses = ?,
                    rivals = ?,
                    dominating = ?,
                    lifetime_ironmans = ?,
                    longest_ironman = ?,
                    lifetime_first_dmg = ?,
                    top_frags = ?,
                    tied_wins = ?,
                    first_bloods = ?,
                    ratings = ?
                WHERE player_id = ?
                 """

        self.cur.execute(q, (
                             lifetime_kills,
                             lifetime_deaths,
                             lifetime_rounds,
                             lifetime_kdr,
                             lifetime_kpr,
                             lifetime_wpr,

                             kdr_percentile,
                             kpr_percentile,
                             wpr_percentile,

                             first_deaths,

                             time_divided_rounds,
                             time_divided_kills,
                             time_divided_deaths,
                             time_divided_kpr,
                             time_divided_kdr,
                             time_divided_dpr,
                             time_divided_pve,

                             lifetime_ffa_kills,
                             lifetime_teams_kills,

                             lifetime_wins,
                             year_divided_winrate,

                             kill_record,
                             debut,
                             debut_rr,
                             last_played,
                             last_rr,
                             team_kills,
                             suicides,
                             alive_wins,
                             dead_wins,

                             nemeses,
                             rivals,
                             dominating,
                             lifetime_ironmans,
                             longest_ironman,
                             lifetime_first_dmg,
                             top_frags,
                             tied_wins,
                             first_bloods,
                             ratings,
                             player_id
                             ))


    def get_players(self):
        q = """
            SELECT current_ign
            FROM players
            """
        self.cur.execute(q)
        players = [i[0] for i in self.cur.fetchall()]
        players.sort(key=lambda x: x.lower())

        return players

    def get_rounds(self):
        q = """
            SELECT DISTINCT round_name
            FROM seasons
            """
        self.cur.execute(q)
        rounds = [i[0] for i in self.cur.fetchall()]
        rounds.sort(key=lambda x: x.lower())

        return rounds

    def player_profile(self, player_id,
                       lifetime_kills,
                       lifetime_deaths,
                       lifetime_rounds,
                       lifetime_kdr,
                       lifetime_kpr,
                       lifetime_wpr,

                       kdr_percentile,
                       kpr_percentile,
                       wpr_percentile,

                       first_deaths,

                       time_divided_rounds,
                       time_divided_kills,
                       time_divided_deaths,
                       time_divided_kpr,
                       time_divided_kdr,
                       time_divided_dpr,
                       time_divided_pve,

                       lifetime_ffa_kills,
                       lifetime_teams_kills,

                       lifetime_wins,
                       year_divided_winrate,

                       kill_record,
                       debut,
                       debut_rr,
                       last_played,
                       last_rr,
                       team_kills,
                       suicides,
                       alive_wins,
                       dead_wins,

                       nemeses,
                       rivals,
                       dominating,
                       lifetime_ironmans,
                       longest_ironman,
                       lifetime_first_dmg,
                       top_frags,
                       tied_wins,
                       first_bloods,
                       ratings
                       ):
        """
        DATA TO PROFILE
        :param username: minecraft ign
        :return:
        """
        q = """
                 INSERT INTO player_stats (
                    player_id,
                        
                    lifetime_kills,
                    lifetime_deaths,
                    lifetime_rounds,
                    lifetime_kdr,
                    lifetime_kpr,
                    lifetime_wpr,
                    
                    kdr_percentile,
                    kpr_percentile,
                    wpr_percentile,
                    
                    first_deaths,

                    time_divided_rounds,
                    time_divided_kills,
                    time_divided_deaths,
                    time_divided_kpr,
                    time_divided_kdr,
                    time_divided_dpr,
                    time_divided_pve,
                    
                    lifetime_ffa_kills,
                    lifetime_teams_kills,
                    
                    lifetime_wins,
                    yearly_wins,
                    
                    kill_record,
                    debut,
                    debut_rr,
                    last_played,
                    last_rr,
                    team_kills,
                    suicides,
                    alive_wins,
                    dead_wins,
                                
                    nemeses,
                    rivals,
                    dominating,
                    lifetime_ironmans,
                    longest_ironman,
                    lifetime_first_dmg,
                    top_frags,
                    tied_wins,
                    first_bloods,
                    ratings)
                VALUES (?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,? ,?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,?, ?)
                 """

        self.cur.execute(q, (player_id,
                             lifetime_kills,
                             lifetime_deaths,
                             lifetime_rounds,
                             lifetime_kdr,
                             lifetime_kpr,
                             lifetime_wpr,

                             kdr_percentile,
                             kpr_percentile,
                             wpr_percentile,

                             first_deaths,

                             time_divided_rounds,
                             time_divided_kills,
                             time_divided_deaths,
                             time_divided_kpr,
                             time_divided_kdr,
                             time_divided_dpr,
                             time_divided_pve,

                             lifetime_ffa_kills,
                             lifetime_teams_kills,

                             lifetime_wins,
                             year_divided_winrate,

                             kill_record,
                             debut,
                             debut_rr,
                             last_played,
                             last_rr,
                             team_kills,
                             suicides,
                             alive_wins,
                             dead_wins,

                             nemeses,
                             rivals,
                             dominating,
                             lifetime_ironmans,
                             longest_ironman,
                             lifetime_first_dmg,
                             top_frags,
                             tied_wins,
                             first_bloods,
                             ratings
                             ))


        #return profile
    def redact_player(self, player, code):
        q = """
            UPDATE player_stats
            SET redacted = ?
            WHERE player_id IN (
                SELECT player_id
                FROM players
                WHERE current_ign = ?
            )
            """
        self.cur.execute(q, (code,player))

    def unredact_player(self, player):
        q = """
                    UPDATE player_stats
                    SET redacted = NULL
                    WHERE player_id IN (
                        SELECT player_id
                        FROM players
                        WHERE current_ign = ?
                    )
                    """
        self.cur.execute(q, (player,))

    def get_redacted(self):
        q = """
               SELECT p.current_ign
               FROM players p
               JOIN player_stats ps ON p.player_id = ps.player_id
               WHERE ps.redacted IS NOT NULL
               """
        return [p[0] for p in self.cur.execute(q).fetchall()]

    def add_round(self, name, gid):
        round_q = """
                  INSERT INTO rounds (round_gid, round_name)
                  VALUES (?, ?)
                  """

        self.cur.execute(round_q, (gid, name))

    def add_season(self, round_name, season_no):
        # extract season info from dict
        seasons_q = """
                    INSERT INTO seasons (round_name, season_no)
                    VALUES (?, ?)
                    """
        self.cur.execute(seasons_q, (round_name, season_no))

    def add_player(self, ign):
        # update players if there are new players
        players_q = """
                    INSERT INTO players (current_ign)
                    VALUES (?)
                    """
        self.cur.execute(players_q, (ign,))

    def add_alts(self, player_id, alt):
        alt_q = """
                INSERT INTO alts (player_id, alt)
                VALUES (?, ?)
                """
        self.cur.execute(alt_q, (player_id, alt))

    def add_season_info(self, sid, alias, nr, date, eps, team_size, team_type, ver, ironman, im_time, f_dmg, fdam_time):
        season_info_q = """
                         INSERT INTO season_info 
                         (season_id, alias, nr, date, eps, team_size, team_type, version, ironman, im_time, first_dmg, fdam_time)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                         """
        self.cur.execute(season_info_q, (sid, alias, nr, date, eps, team_size, team_type, ver, ironman, im_time, f_dmg, fdam_time))

    def add_season_gm(self, sid, gm):
        season_gm_q = """
                      INSERT INTO season_gms
                      (season_id, gamemode)
                      VALUES (?,?)
                      """
        self.cur.execute(season_gm_q, (sid, gm))

    def add_season_teams(self, sid, player, team):
        # update season teams
        season_teams_q = """
                          INSERT INTO season_teams
                          (season_id, player_id, team)
                          VALUES (?,?,?)
                          """

        self.cur.execute(season_teams_q, (sid, player, team))

    def add_season_killfeed(self, season_id, dead_id, death_msg, killer_id, pve_id, ks, dupe_id):
        season_killfeed_q = """
                            INSERT INTO season_killfeed
                            (season_id, dead_id, death_msg, killer_id, pve_id, killstealer, dupe_id)
                            VALUES (?,?,?,?,?,?, ?)
                            """
        self.cur.execute(season_killfeed_q, (season_id, dead_id, death_msg, killer_id, pve_id, ks, dupe_id))


