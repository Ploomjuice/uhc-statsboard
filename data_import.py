import pandas as pd
import numpy as np
from collections import defaultdict, Counter
from time import time
from rapidfuzz import process
import json
from datetime import datetime

sheet_id = "1cJnD5KPdTL1g_8CkWGiaibcpg00WKa2KgsGHzQnKnc8"

rr_df = pd.read_csv("data/rounds.csv", header=None)
rounds = rr_df[0].to_list()
gids = rr_df[1].to_list()
master_dict = {rr: {} for rr in rounds}

kills = Counter() # total per player
pve_kills = Counter() # deaths by mob counter
deaths = Counter() # {player: #deaths}
death_msgs = Counter()
death_msgs_by_player = defaultdict(Counter) # {player: {deathmsg:count}}
player_killed = defaultdict(Counter)
died_to_pvp = defaultdict(Counter) #{player: {player:N,player:M,...}}
died_to_pve = defaultdict(Counter)

def divide_wins():
    return {'alive': [], 'dead': []}
wins = defaultdict(divide_wins)
# for totals


def update_death_msgs(player, death_msg):
    death_msgs_by_player[player][death_msg] += 1
    death_msgs[death_msg] += 1


def _load_kd_stats():
    """
    Updates dictionaries for kill-/death-related statistics
    - kills {player: count}
    - deaths {player: count}
    - pve_kills {mob/other: count}
    - player_killed {player: [victim, victim, ...]} (can have repeats, in this form for calculations later)
    - died_to_pvp {player: [killer, killer, ...]} -> aggregate to count
    - died_to_pve {player: [killer, killer, ...]}
    - death_msgs?
    -
    """
    for rr in master_dict:
        for season in master_dict[rr]:

            # for ease of access
            season_dict = master_dict[rr][season]
            placement = season_dict['players_placement']
            # all_players = [season_dict['teams'][t][p] for t in season_dict['teams'] for p in range(len(season_dict['teams'][t]))] # bc of typos
            # print(all_players)

            # test if there are discrepancies for team games (multiple entries of username)
            for i in range(len(placement)):
                killer = season_dict['killers'][i]
                player = placement[i]

                death_msg = season_dict['death_msgs'][i]

                # count deaths
                if killer in placement:  # pvp deaths
                    deaths[player] += 1
                    died_to_pvp[player][season_dict['killers'][i]] += 1
                    player_killed[season_dict['killers'][i]][player] += 1
                    update_death_msgs(player, death_msg)

                elif killer == '':  # pve deaths by env

                    if "lava" in death_msg:
                        died_to_pve[player]["Lava"] += 1
                    elif "burn" in death_msg:
                        died_to_pve[player]["Fire"] += 1
                    elif "fell" in death_msg or "impaled" in death_msg:
                        died_to_pve[player]["Fall"] += 1
                    elif "blew" in death_msg:
                        died_to_pve[player]["Explosion"] += 1
                    elif "drowned" in death_msg:
                        died_to_pve[player]["Drowning"] += 1
                    elif "stung" in death_msg:
                        died_to_pve[player]["Bees"] += 1
                    elif "confines" in death_msg:
                        died_to_pve[player]["Border"] += 1
                    elif "fell out of the world" in death_msg:
                        died_to_pve[player]["Void"] += 1
                    elif "pricked" in death_msg:
                        died_to_pve[player]["Cactus"] += 1
                    elif "poke" in death_msg:
                        died_to_pve[player]["Sweet Berry Bush"] += 1
                    elif "suffocated" in death_msg:
                        died_to_pve[player]["Suffocation"] += 1
                    elif "starved" in death_msg:
                        died_to_pve[player]["Starvation"] += 1
                    elif placement[i] in death_msg:
                        died_to_pve[player]["Suicide"] += 1
                    else:
                        died_to_pve[player]["Other"] += 1

                    update_death_msgs(player, death_msg)

                elif killer != "Nothing":  # pve deaths by mobs
                    died_to_pve[player][season_dict['killers'][i]] += 1  # improve to counters later?
                    update_death_msgs(player, death_msg)

                # wins
                else:
                    teams = master_dict[rr][season]['teams']
                    if "Winner" not in season_dict['death_msgs']:

                        # dead players on team
                        if master_dict[rr][season]['team_type'] != 'FFA':
                            winning_team = [teams[team] for team in teams if player in teams[team]]
                            if len(winning_team) == 1:
                                winning_team = winning_team[0]
                            for winner in winning_team:
                                # if winner not in all_players:
                                #  suggestion, score, _ = process.extractOne(player, all_players)
                                # if score > 90:
                                #     winner = suggestion
                                # else:
                                #  print(f"idk who {player} is")
                                if winner == "JewishHotpocket":  # hard coding to fix a typo remove later and find better solution
                                    winner = "JewishHotPocket"
                                if season_dict['killers'][placement.index(winner)] == 'Nothing':
                                    wins[winner]['alive'].append(f"{rr} {season}")
                                else:
                                    wins[winner]['dead'].append(f"{rr} {season}")
                            break

                        # ffa
                        else:
                            wins[player]['alive'].append(f"{rr} {season}")
                    elif death_msg == "Winner":  # objectives
                        if master_dict[rr][season]['team_type'] != 'FFA':
                            winning_team = [teams[team] for team in teams if player in teams[team]]
                            if len(winning_team) == 1:
                                winning_team = winning_team[0]
                            for winner in winning_team:

                                if season_dict['killers'][placement.index(winner)] == 'Nothing':
                                    wins[winner]['alive'].append(f"{rr} {season}")
                                else:
                                    wins[winner]['dead'].append(f"{rr} {season}")
                            break
                        else:
                            wins[player]['alive'].append(f"{rr} {season}")

            for killer in season_dict['killers']:
                if killer in placement:
                    kills[killer] += 1
                elif killer != "Nothing":
                    pve_kills[killer] += 1


def _mob_ks(death_msg):
    split_msg = death_msg.split('by ')
    if len(split_msg) == 2:
        assist = split_msg[1]
        return assist
    elif len(split_msg) == 1:
        assist = split_msg[0].split('escape ')
    else:
        return ''


def check_typo(name, team):
    suggestion, score, _ = process.extractOne(name, team)
    if score > 90:
        return suggestion
    else:
        return name


# {round: {season: {config:, duration:, ironman:, etc.}}}
# {round: {season: {team: players}}}
# {round: {season: {killfeed}}}

def _sheet_to_df(gid):
    # get df
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    df = pd.read_csv(url, header=None)

    # get boundaries
    labels = df[df[0].notnull()]
    kills_start = labels.index[-1]
    teams_start = labels.index[-4]
    imtime_start = labels.index[-7]
    return df, kills_start, teams_start, imtime_start


def _load_info(rr_name, sheet_df, teams_start, imtime_start, store):
    # slice df from raw loaded sheet df
    info_df = sheet_df[:teams_start]

    for i in range(1, info_df.columns[-1], 3):
        # get each season's info
        season_info_raw = info_df.iloc[:, i:i + 3]
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
            store[rr_name][season_no]['date'] = datetime.strptime(date, "%d-%B-%Y").strftime("%Y-%m-%d")
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
        store[rr_name][season_no]['im_time'] = ':'.join(['0' + i if len(str(i)) == 1 else str(i) for i in season_info_raw.iloc[imtime_start, 0:3].to_list()])
        store[rr_name][season_no]['fdamage'] = season_info_raw.iloc[imtime_start+1, 0]
        store[rr_name][season_no]['fdam_time'] = ':'.join(['0' + i if len(str(i)) == 1 else str(i) for i in season_info_raw.iloc[imtime_start+2, 0:3].to_list()])


def _load_teams(rr_name, sheet_df, kills_start, teams_start, store):
    # sheet_df = sheet_to_df(gid)
    # labels = sheet_df[sheet_df[0].notnull()]
    # kills_start = labels.index[-1]
    # teams_start = labels.index[-4]

    # get info from df
    teams_df = sheet_df[teams_start:kills_start].drop(columns=[0])
    for i in range(0, teams_df.columns[-1], 3):
        season_no = list(store[rr_name].keys())[int(i / 3)]
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
        # load into dict
        store[rr_name][season_no]['teams'] = {f'{color} ({idx})': team for idx, (color, team) in
                                                    enumerate(zip(colors, teams))}


def _load_kills(rr_name, sheet_df, kills_start, store):
    kills_df = sheet_df[kills_start + 1:].drop(columns=[0])

    for i in range(0, kills_df.columns[-1], 3):
        season_no = list(store[rr_name].keys())[int(i / 3)]
        season_info_raw = kills_df.iloc[:, i:i + 3]
        players = [p.strip() for p in season_info_raw.iloc[:, 0].dropna().to_list()]
        store[rr_name][season_no]['players_placement'] = [p.strip() for p in
                                                                season_info_raw.iloc[:, 0].dropna().to_list()]

        messages = season_info_raw.iloc[:len(players), 1].replace(np.nan, '').to_list()
        store[rr_name][season_no]['death_msgs'] = messages  # [_by_exception(msg) for msg in ]
        store[rr_name][season_no]['killstealers'] = [_mob_ks(msg.strip()) for msg in
                                                           messages]  # also works for suicides

        # account for PvE deaths
        # last valid id
        killers = season_info_raw.iloc[:, 2].replace("Left", '')
        if killers.dropna().empty:
            print("Empty Season")
            store[rr_name][season_no]['killers'] = []
        else:
            feed_end = killers[killers.notna()].index[-1] - kills_start
            store[rr_name][season_no]['killers'] = [p.strip() for p in killers[:feed_end].replace(np.nan,
                                                                                                    '').to_list()]  # change to counter?


def _load_everything(rr_name, gid, store):
    print(f"Loading {rr_name} Data...")
    # df
    df, k_start, t_start, imt_start = _sheet_to_df(gid)
    # info
    _load_info(rr_name, df, t_start, imt_start, store)
    # teams
    _load_teams(rr_name, df, k_start, t_start, store)
    # kills
    _load_kills(rr_name, df, k_start, store)



def full_load(round_filename):
    start = time()
    with open(round_filename, 'r') as f:
        for row in f:
            rr, gid = row.split(',')
            _load_everything(rr, gid, master_dict)
    _load_kd_stats()
    print(time() - start)

# save
if __name__ == '__main__':
    full_load('data/rounds.csv')
    with open('master_dict.json', 'w') as f:
        json.dump(master_dict, f, indent=4)

    kd_stats = {"kills": kills,
                "pve_kills": pve_kills,
                "deaths": deaths,
                "death_msgs_all": death_msgs,
                "death_msgs_by_player": death_msgs_by_player,
                "player_killed": player_killed,
                "died_to_pvp": died_to_pvp,
                "died_to_pve": died_to_pve,
                "wins": wins}
    with open("kd_stats.json", 'w') as f:
        json.dump(kd_stats, f, indent=4)


