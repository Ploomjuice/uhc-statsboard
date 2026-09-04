from db_ops import DBOPs
from data_aggregation import clean_literals
import ast
import json
from collections import defaultdict
from pprint import pprint
import numpy as np


with open("data/player_map.json", "rb") as f:
    player_map = json.load(f)
view = DBOPs("data/stats.db")

def combine(old, new):
    old_stats = fetch_stats(old)
    new_stats = fetch_stats(new)
    pid = player_map[new.lower()]

    # ints and floats
    c_kills = old_stats['kills'] + new_stats['kills']
    c_deaths = old_stats['deaths'] + new_stats['deaths']
    c_rounds = old_stats['rounds'] + new_stats['rounds']

    c_fd = old_stats['first_deaths'] + new_stats['first_deaths']
    c_ffa_kills = old_stats['ffa_kills'] + new_stats['ffa_kills']
    c_tg_kills = old_stats['team_game_kills'] + new_stats['team_game_kills']
    c_total_wins = old_stats['total_wins'] + new_stats['total_wins']
    c_kr = np.max([old_stats['kill_record'], new_stats['kill_record']])
    c_tks = old_stats['tks'] + new_stats['tks']
    c_sc = old_stats['suicides'] + new_stats['suicides']
    c_im = old_stats['ironmans'] + new_stats['ironmans']
    c_fdam = old_stats['first_dmgs'] + new_stats['first_dmgs']
    c_tf = old_stats['top_frags'] + new_stats['top_frags']
    c_fb = old_stats['first_bloods'] + new_stats['first_bloods']




    # strs
    c_kpr_5 = 'nan' # tent
    c_kdr_5 = 'nan' # tent
    c_wpr_5 = 'nan' # tent
    c_kdr = c_kills/c_deaths
    c_kpr = c_kills/c_rounds
    c_wpr = c_total_wins/c_rounds
    c_debut = old_stats['debut_date']
    c_debut_rr = old_stats['debut_rr']
    c_lp = new_stats['last_played']
    c_last_rr = new_stats['last_rr']
    c_lim = 'N/A' # tent

    # lists
    c_aw = old_stats['alive_wins'] + new_stats['alive_wins']
    c_dw = old_stats['dead_wins'] + new_stats['dead_wins']
    c_tw = []
    #c_tw = old_stats['tied_wins'] + new_stats['tied_wins']


    # dicts
    c_rbp = combine_dicts(old_stats['rounds_by_period'], new_stats['rounds_by_period'])
    c_kbp = combine_dicts(old_stats['kills_by_period'], new_stats['kills_by_period'])
    c_dbp = combine_dicts(old_stats['kills_by_period'], new_stats['kills_by_period'])
    c_pvebp = combine_dicts(old_stats['pve_by_period'], new_stats['pve_by_period'])
    # c_yw = combine_dicts(old_stats['yearly_wins'], new_stats['yearly_wins'])
    c_yw = dict(new_stats['yearly_wins'])
    c_kprbp = {p: [i / j if j != 0 else 0 for i, j in zip(c_kbp[p], c_rbp[p])] for p in c_kbp}
    c_kdrbp = {p: [i / j if j != 0 else 0 for i, j in zip(c_kbp[p], c_dbp[p])] for p in c_kbp}
    c_dprbp = {p: [i / j if j != 0 else 0 for i, j in zip(c_dbp[p], c_rbp[p])] for p in c_dbp}
    c_nem = dict(old_stats['nemeses'], **new_stats['nemeses'])
    c_riv = dict(old_stats['rivals'], **new_stats['rivals'])
    c_dom = dict(old_stats['dominating'], **new_stats['dominating'])
    rating = {'2012': float('nan'),
               '2013': float('nan'),
               '2014': 19.744,
               '2015': float('nan'),
               '2016': float('nan'),
               '2017': float('nan'),
               '2018': float('nan'),
               '2019': float('nan'),
               '2020': float('nan'),
               '2021': float('nan'),
               '2022': float('nan'),
               '2023': float('nan'),
               '2024': float('nan'),
               '2025': 0,
               '2026': float('nan')} # hard coding lolmcgeeksftw


    view.update_profile(c_kills, c_deaths, c_rounds, c_kdr, c_kpr, c_wpr, c_kdr_5, c_kpr_5, c_wpr_5, c_fd, str(c_rbp), str(c_kbp), str(c_dbp),
                        str(c_kprbp), str(c_kdrbp), str(c_dprbp), str(c_pvebp), c_ffa_kills, c_tg_kills, c_total_wins, str(c_yw), c_kr, c_debut,
                        c_debut_rr, c_lp, c_last_rr, c_tks, c_sc, str(c_aw), str(c_dw), str(c_nem), str(c_riv), str(c_dom), c_im, c_lim, c_fdam, c_tf,
                        str(c_tw), c_fb, str(rating), pid)
    view.cur.execute("DELETE FROM players WHERE current_ign = ?", (old,))
    old_pid = player_map[old.lower()]
    view.cur.execute("DELETE FROM player_stats WHERE player_id = ?", (old_pid,))
    view._save()
    view._reopen()




def combine_dicts(old_dict, new_dict):
    combined = {p:[i+j for i, j in zip(old_dict[p], new_dict[p])] for p in old_dict}
    return combined


def fetch_stats(player):
    player_id = player_map[player.lower()]
    stats = view.cur.execute(
        """
            SELECT *
            FROM player_stats
            WHERE player_id = ?
        """

        , (player_id,)).fetchall()[0]

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
        'kills': total_kills,  #
        'deaths': total_deaths,  #
        'rounds': total_rounds,  #
        'kdr': kdr,  #
        'kpr': kpr,  #
        'wpr': wpr,  #
        'kdr_percentile': kdr_percentile,  #
        'kpr_percentile': kpr_percentile,  #
        'wpr_percentile': wpr_percentile,  #
        'first_deaths': first_deaths,  #
        'rounds_by_period': rounds_by_period,
        'kills_by_period': kills_by_period,
        'deaths_by_period': deaths_by_period,
        'kpr_by_period': kpr_by_period,
        'kdr_by_period': kdr_by_period,
        'dpr_by_period': dpr_by_period,
        'pve_by_period': pve_by_period,
        'ffa_kills': ffa_kills,
        'team_game_kills': team_game_kills,
        'total_wins': total_wins,  #
        'alive_wins': alive_wins,  #
        'dead_wins': dead_wins,  #
        'yearly_wins': yearly_wins,  #
        'kill_record': kill_record,
        'debut_date': debut_date,  #
        'debut_rr': debut_rr,  #
        'last_played': lp_date,  #
        'last_rr': last_rr,  #
        'tks': tks,  #
        'suicides': suicides,  #
        'nemeses': nemeses,  #
        'rivals': rivals,  #
        'dominating': dominating,  #
        'ironmans': ironmans,  #
        'longest_im': longest_ironman,  #
        'first_dmgs': first_dmgs,
        'top_frags': top_frags,
        'redacted': redacted,
        'tied_wins': tied_wins,  #
        'first_bloods': first_bloods,
        'rating': rating  #

    }
    for i in player_info:
        print(i, type(player_info[i]))
    return player_info

if __name__ == '__main__':

    combine("TheBestOtaku", "lolmcgeeksftw")
    pprint(fetch_stats("lolmcgeeksftw"))
    #print(view.cur.execute("SELECT * FROM player_stats WHERE player_id = 1851").fetchall())
