import pandas as pd
import json
from data_aggregation import FullAggregation, clean_literals
import numpy as np
from datetime import datetime
from collections import defaultdict
from db_ops import DBOPs
from pprint import pprint
import ast
# import
from urllib.error import HTTPError
import csv
sheet_id = "1cJnD5KPdTL1g_8CkWGiaibcpg00WKa2KgsGHzQnKnc8"
gid = "2101501032"
alive_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"

class Loader():
    def __init__(self):
        self.sheet_id = "1cJnD5KPdTL1g_8CkWGiaibcpg00WKa2KgsGHzQnKnc8"
        self.gid = "2101501032"
        self.alive_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
        self.alive_df = pd.read_csv(self.alive_url)
        #print(self.alive_df[(self.alive_df['Up to date?'] == 'Yes')])
        self.dead_df = self.alive_df[self.alive_df["Status"]=='Dead']
        self.alive_df = self.alive_df[(self.alive_df["Status"]=="Alive") & (self.alive_df["Up to date?"] == "Yes") | (self.alive_df['Round Name'] == "Impulse")]
        self.rounds = pd.read_csv("rounds.csv", header=None)
        self.update_dict = {rr: {} for rr in self.alive_df["Round Name"]}
        self.interface = DBOPs('stats.db')
        self.interface.conn.execute("PRAGMA journal_mode=WAL;")
        self.interface.conn.execute("PRAGMA synchronous=NORMAL;")
        self.players_to_be_updated = {}
        self.new_players = []
        with open("player_map.json", "r") as f:
            self.old_player_map = json.load(f)

    def add_round(self, round_name, round_gid):
        with open('rounds.csv', 'a') as f:
            f.write(f"\n{round_name},{round_gid}")


    def refresh(self):

        unknowns = []
        for round in self.update_dict:
            if round not in self.rounds.iloc[:, 0].to_list(): # round detected in alive rounds, not in csv
                msg = (f"New Round Detected: {round}, please use the upload tool to add the corresponding "
                       f"Google Sheet.")
                print(msg)
                unknowns.append(round)

        if unknowns:
            msg = "Update Stopped! Before retrying, please add the following rounds and their corresponding GID's:"
            for i in unknowns:
                msg += f'\n {i}'
            return unknowns, msg

        else: # load new seasons of known rounds
            for round in self.update_dict:
                gid = str(self.rounds[self.rounds[0]==round][1].iloc[0])
                print(gid)
                round_url = f"https://docs.google.com/spreadsheets/d/{self.sheet_id}/export?format=csv&gid={gid}"
                try:
                    round_df = pd.read_csv(round_url, header=None)
                except HTTPError:
                    with open('rounds.csv', 'r', newline='') as f:
                        reader = list(csv.reader(f))
                        # Keep all rows except the one we want to remove
                        rows = [row for row in reader if row[0] != round]
                    with open('rounds.csv', "w", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerows(rows)

                    return round, "Bad ID, please replace the links using the Round Insertion Tool."


                ls_q = """
                            SELECT season_no
                            FROM seasons
                            WHERE round_name = ?
                                AND season_id = (
                                    SELECT MAX(season_id)
                                    FROM seasons
                                    WHERE round_name = ?
                                )
                                   
                       """
                last_season = self.interface.cur.execute(ls_q, (round, round)).fetchall()
                if not last_season:
                    last_season = 0
                else:
                    last_season = last_season[0][0]


                newest_season = round_df.iloc[0, -3]
                print(round, newest_season, last_season)
                if newest_season != last_season:
                    selected = newest_season
                    i = 1
                    while selected != last_season:
                        if i == 1:
                            season_to_add = round_df.iloc[:, (-3*i):]
                        else:
                            season_to_add = round_df.iloc[:, (-3*i):(-3*(i-1))]
                        # if not any(char.isdigit() for char in season_to_add) :
                        #     del self.update_dict[round][selected]
                        #     print("Deleted", round, selected)
                        #     print(f"There seems to be an issue with the {round} sheet...\n"
                        #           f"Please contact the Global RR Community Stats sheet editors,"
                        #           f"or if it is formatted correctly and normally, please"
                        #           f"contact the developer.")
                        #     break

                        print(season_to_add)

                        _, k_start, t_start, imtime_start = Loader.load(round_df)
                        try:
                            Loader._load_info(round, season_to_add, t_start, imtime_start, self.update_dict)
                            Loader._load_teams(round, season_to_add, k_start, t_start, self.update_dict)
                            Loader._load_kills(round, season_to_add, k_start, self.update_dict)
                        except AttributeError: # if latest season is yet to be updated
                            del self.update_dict[round][selected]
                            print("Deleted", round, selected)
                            break
                        except Exception:
                            del self.update_dict[round][selected]
                            print("Deleted", round, selected)
                            break
                        # print(list(self.update_dict[round][selected].keys()))
                        # if "players_placement" not in list(self.update_dict[round][selected].keys()):
                        #     del self.update_dict[round][selected]
                        #     print("Deleted", round, selected)
                        #     break

                        i += 1
                        if 3*i < round_df.shape[1]:
                            selected = round_df.iloc[0, -3*i]
                        else:
                            break

        print(self.update_dict)

        # send update dict to db
        try:
            print("updating players")
            self.update_players() # player update
            try:
                print("updating seasons")
                self.update_seasons() # season_update
            except Exception as e:
                print('error:', repr(e))


            print("updating db")
            self.insert_player_stats()
        except Exception as e:
            with open("player_map.json", "w") as f:
                json.dump(self.old_player_map, f)
            print(repr(e))
            return 1, str(e)
        else:

            self.interface._save()
            self.interface._reopen()

        return [], "Data Transfer Success! Now Updating Stats..."


    def update_players(self):
        # add players
        ps = []
        invalid = []
        for rr in self.update_dict:
            for season in self.update_dict[rr]:
                print(rr, season)
                season_dict = self.update_dict[rr][season]


                # test for typos
                for player in season_dict['players_placement']:
                    if player in [p for team in season_dict['teams'].values() for p in team]:
                        pass
                    else:
                        invalid.append([rr, season])
                        break
                if [rr, season] not in invalid:
                    ps.extend(season_dict['players_placement'])

                print(ps)
        for game in invalid:
            rr, season = game
            del self.update_dict[rr][season]

        pprint(self.update_dict)

        players = set(ps)

        with open("player_map.json", "r") as f:
            player_map = json.load(f)
        print("check 1")
        # import alts
        gid_ = "1376186233"
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_}"
        df = pd.read_csv(url)
        current_igns = df["Player Name"]
        alts = df.drop(columns=["Player Name"])

        # if there are new players add them to players
        players_q = """ SELECT current_ign
                                FROM players
                                """
        existing_players = [p[0] for p in self.interface.cur.execute(players_q).fetchall()]
        print("check 2")
        # check to see if any existing players are using alts
        for i in range(len(current_igns)):
            # get alts
            old_names = [name for name in alts.iloc[i, :].to_list() if type(name) == str]

            # if there is a current ign (with an alt) not in player_map
            if current_igns[i] not in existing_players:

                # check if
                print(old_names)

                # look for the alt that IS in the player map
                try:
                    switched_name = [ign for ign in old_names if ign in existing_players][0]
                except IndexError: # player in alts, but not found in any round scraped
                    continue
                print("Old Name: ", switched_name)
                player_id = player_map[switched_name.lower()]
                print("New Name: ", current_igns[i])

                # set the player ign to new name
                q = """
                    UPDATE players
                    SET current_ign = ?
                    WHERE player_id = ?
                    """
                self.interface.cur.execute(q, (current_igns[i], player_id))


                # add old name to alts
                o_q = """
                        INSERT INTO alts (player_id, alt)
                        VALUES (?, ?)
                
                       """
                self.interface.cur.execute(o_q, (player_id, switched_name))

                print(self.interface.cur.execute("SELECT * FROM alts WHERE player_id = ?", (player_id,)).fetchall() )

        players_q = """ SELECT current_ign
                                        FROM players
                                        """
        updated_players = [p[0] for p in self.interface.cur.execute(players_q).fetchall()]
        print("check 3")

        for p in players:
            if p not in updated_players: # actual new player
                print(p)
                self.interface.add_player(p)
                self.new_players.append(p)

        lowered_players = [ign.lower() for ign in players]

        # update player_map
        player_map = {name.lower(): pid for pid, name in
                      self.interface.cur.execute("SELECT player_id, current_ign FROM players ORDER BY player_id")}

        # overwrite json
        with open("player_map.json", "w") as f:
            json.dump(player_map, f)

        # get players to be updated
        self.players_to_be_updated = {name:pid for name, pid in list(player_map.items()) if name in lowered_players}
        print(self.players_to_be_updated)


    def update_seasons(self):
        # get_id_q = """
        #             SELECT MAX(season_id)
        #             FROM seasons
        #             """
        # old_max_id = self.interface.cur.execute(get_id_q).fetchall()[0][0]
        with open("player_map.json", "r") as f:
            player_map = json.load(f)
        #
        # season_id = old_max_id + 1 # works if the thing isn't empty
        # print([[r, list(self.update_dict[r].keys())] for r in self.update_dict.keys() if self.update_dict[r] != {}])
        for rr in self.update_dict:
            rr_dict = dict(sorted(self.update_dict[rr].items(), key=lambda item: item[0]))
            for season in rr_dict:
                # init
                season_dict = rr_dict[season]
                print(rr, season)
                #pprint(season_dict)
                self.interface.add_season(rr, season)
                season_id = self.interface.cur.execute("""
                        SELECT season_id FROM seasons WHERE round_name = ? AND season_no = ?
                        """, (rr, season)).fetchall()[0][0]

                # info
                alias = season_dict['alias']
                nr = season_dict['NR']
                date = season_dict["date"]

                eps = season_dict['eps']
                team_size = season_dict['team_size']
                team_type = season_dict['team_type']
                version = season_dict['version']
                gamemodes = season_dict['gamemodes']
                ironman = season_dict['ironman']
                if "[" in ironman:
                    ironman = ast.literal_eval(ironman)
                    ironman = str([player_map[p.lower()] for p in ironman])
                else:
                    ironman = player_map[ironman.lower()]


                im_time = season_dict['im_time']
                fdamage = player_map[season_dict['fdamage'].lower()] if type(season_dict['fdamage']) == str else 'N/A'
                fdam_time = season_dict['fdam_time'] if season_dict['fdam_time'] != 'nan:nan:nan' else 'N/A'
                print(date, season_id)
                self.interface.add_season_info(season_id, alias, nr, date, eps, team_size,
                                          team_type, version, ironman, im_time,
                                          fdamage, fdam_time)
                self.interface._save()
                self.interface._reopen()


                # gamemode
                for gm in gamemodes:
                    self.interface.add_season_gm(season_id, gm)

                # teams
                teams = list(season_dict['teams'].keys())
                # players = list(season_dict['teams'].values())
                print(season_id)
                for i in range(len(teams)):
                    for player in season_dict['teams'][teams[i]]:
                        self.interface.add_season_teams(season_id, player_map[player.lower()], teams[i])

                self.interface._save()
                self.interface._reopen()

                # kills
                placement = season_dict["players_placement"]
                victims_id = [player_map[player.lower()] for player in placement]
                death_msgs = season_dict["death_msgs"]
                killers_id = [player_map[player.lower()] if player in placement else np.nan for player in
                              season_dict["killers"]]
                pve_id = [cause if cause not in placement else np.nan for cause in season_dict['killers']]
                ks = season_dict["killstealers"]
                print(season_id)
                for i in range(len(placement)):
                    self.interface.add_season_killfeed(season_id, victims_id[i], death_msgs[i], killers_id[i], pve_id[i],
                                                  ks[i], season_id)

                season_id += 1
                self.interface._save()
                self.interface._reopen()


    @staticmethod
    def load(df):
        # get boundaries
        labels = df[df[0].notnull()]
        kills_start = labels.index[-1]
        teams_start = labels.index[-4]
        imtime_start = labels.index[-7]
        print(kills_start, teams_start, imtime_start)
        return df, kills_start, teams_start, imtime_start

    @staticmethod
    def _load_info(rr_name, sheet_df, teams_start, imtime_start, store):
        # slice df from raw loaded sheet df
        info_df = sheet_df[:teams_start]

        for i in range(0, len(info_df.columns), 3):
            # get each season's info
            season_info_raw = info_df.iloc[:, i:(i+3)]
            season_no = season_info_raw.iloc[0, 0]
            store[rr_name][season_no] = {}
            store[rr_name][season_no]['alias'] = season_info_raw.iloc[0, 1]
            store[rr_name][season_no]['NR'] = season_info_raw.iloc[0, 2]

            # extract details + save into dict
            date = season_info_raw.iloc[1, 0]
            date_list = date.split('-')
            if len(date_list[0]) == 1:
                date = '0' + date
            try:
                store[rr_name][season_no]['date'] = datetime.strptime(date, "%d-%b-%Y").strftime("%Y-%m-%d")
            except ValueError:
                store[rr_name][season_no]['date'] = datetime.strptime(date, "%d-%B-%Y").strftime("%Y-%m-%d") # account for different format

            store[rr_name][season_no]['eps'] = season_info_raw.iloc[1, 1]
            if season_info_raw.iloc[1, 0] != 'X':
                store[rr_name][season_no]['team_size'] = season_info_raw.iloc[2, 0]
                store[rr_name][season_no]['team_type'] = season_info_raw.iloc[2, 1]
            else:
                store[rr_name][season_no]['team_size'] = 1
                store[rr_name][season_no]['team_type'] = 'FFA'

            store[rr_name][season_no]['version'] = season_info_raw.iloc[2, 2]
            store[rr_name][season_no]['gamemodes'] = season_info_raw.iloc[3, 0].split(',')
            # handle simul ironmans
            ironman_block = season_info_raw.iloc[4:imtime_start, :].to_numpy().flatten().tolist()
            ironman_block = [i for i in ironman_block if not pd.isna(i)]
            # preprocess for db insert later
            if len(ironman_block) == 1:
                ironman_block = ironman_block[0]
            else:
                ironman_block = str(ironman_block)

            store[rr_name][season_no]['ironman'] = ironman_block
            store[rr_name][season_no]['im_time'] = ':'.join(
                ['0' + i if len(str(i)) == 1 else str(i) for i in season_info_raw.iloc[imtime_start, 0:3].to_list()])
            store[rr_name][season_no]['fdamage'] = season_info_raw.iloc[imtime_start + 1, 0]
            store[rr_name][season_no]['fdam_time'] = ':'.join(['0' + i if len(str(i)) == 1 else str(i) for i in
                                                               season_info_raw.iloc[imtime_start + 2, 0:3].to_list()])

    @staticmethod
    def _load_teams(rr_name, sheet_df, kills_start, teams_start, store):
        # sheet_df = sheet_to_df(gid)
        # labels = sheet_df[sheet_df[0].notnull()]
        # kills_start = labels.index[-1]
        # teams_start = labels.index[-4]
        print(sheet_df)

        # get info from df
        if 0 in sheet_df.columns:
            teams_df = sheet_df[teams_start:kills_start].drop(columns=[0])
        else:
            teams_df = sheet_df[teams_start:kills_start]

        for i in range(0, len(teams_df.columns), 3):
            print(store[rr_name])
            season_no = sheet_df.iloc[0, 0]
            print(season_no)
            season_teams_raw = teams_df.iloc[:, [i, i + 2]].replace(' ', np.nan).dropna(how="all")
            teams = [team.split(',') for team in season_teams_raw.iloc[:, 0].to_list()]
            for team in teams:
                for i in range(len(team)):
                    team[i] = team[i].strip()

            colors = season_teams_raw.iloc[:, 1].to_list()

            # for secret/unmarked teams
            if colors == None:
                colors = [str(t) for t in np.arange(0, len(teams), 1)]

            # for uneven teams (moles, leftovers, etc.)
            elif len(colors) < len(teams):
                for i in range(len(teams) - len(colors)):
                    colors.extend("EX")
            print({f'{color} ({idx})': team for idx, (color, team) in
                                                  enumerate(zip(colors, teams))})
            # load into dict
            store[rr_name][season_no]['teams'] = {f'{color} ({idx})': team for idx, (color, team) in
                                                  enumerate(zip(colors, teams))}


            print(store)

    @staticmethod
    def _load_kills(rr_name, sheet_df, kills_start, store):
        if 0 in sheet_df.columns:
            kills_df = sheet_df[kills_start + 1:].drop(columns=[0])
        else:
            kills_df = sheet_df[kills_start + 1:]

        for i in range(0, len(kills_df.columns), 3):
            season_no = sheet_df.iloc[0, 0]
            season_info_raw = kills_df.iloc[:, i:i + 3]
            players = [p.strip() for p in season_info_raw.iloc[:, 0].dropna().to_list()]
            store[rr_name][season_no]['players_placement'] = [p.strip() for p in
                                                              season_info_raw.iloc[:, 0].dropna().to_list()]

            messages = season_info_raw.iloc[:len(players), 1].replace(np.nan, '').to_list()
            store[rr_name][season_no]['death_msgs'] = messages  # [_by_exception(msg) for msg in ]
            store[rr_name][season_no]['killstealers'] = [Loader._mob_ks(msg.strip()) for msg in
                                                         messages]  # also works for suicides

            # account for PvE deaths
            # last valid id
            killers = season_info_raw.iloc[:, 2].replace("Left", '')
            if killers.dropna().empty:
                print("Empty Season")
                raise Exception("Empty Season")
            else:
                feed_end = killers[killers.notna()].index[-1] - kills_start
                store[rr_name][season_no]['killers'] = [p.strip() for p in killers[:feed_end].replace(np.nan,'').to_list()]  # change to counter?

    def insert_player_stats(self):
        agg = FullAggregation(interface=self.interface, update=True)

        players_with_profiles = [i[0] for i in self.interface.cur.execute("SELECT player_id FROM player_stats").fetchall()]

        for ign in self.players_to_be_updated:
            player_id = self.players_to_be_updated[ign.lower()]
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
            tied_wins = str([f'{rr} {season}' for rr, season in agg.api.cur.execute(tied_q, (player_id,player_id)).fetchall()])

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




            if player_id not in players_with_profiles:
                print("New:", ign)
                self.interface.player_profile(str(player_id),

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
                                         str(ratings)

                                         )
            else:
                print("Existing: ", ign)
                self.interface.update_profile(

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
            self.interface._save()
            self.interface._reopen()
        self.interface.conn.commit()
        self.interface.conn.close()

    @staticmethod
    def _mob_ks(death_msg):
        split_msg = death_msg.split('by ')
        if len(split_msg) == 2:
            assist = split_msg[1]
            return assist
        elif len(split_msg) == 1:
            assist = split_msg[0].split('escape ')
        else:
            return ''


    def full_refresh(self):
        pass

if __name__ == "__main__":
    test = Loader()
    test.refresh()
    print(test.update_dict)
    print(test.players_to_be_updated)


