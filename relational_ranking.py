import numpy as np
from pprint import pprint
from collections import defaultdict
import networkx as nx
import json
from sklearn.preprocessing import MinMaxScaler
import math

class RelRankPlayers:
    def __init__(self, nodes: dict[dict[tuple]], kpr:dict, wpr:dict, r: dict):
        """

        :param nodes: dict of players' nemeses, rivals, and dominating players
        :param kpr:
        :param wpr:
        """
        self.node_dict = nodes # {player: {player: (win, loss), ...}}

        self.edges = []
        self.rounds_played = r



        # setting up

        self.G = nx.DiGraph()
        with open("data/player_map.json", "rb") as f:
            self.player_map = json.load(f)
        for pid in self.player_map.values():
            self.G.add_node(pid)
            if pid not in self.node_dict:
                self.node_dict[pid] = {}
        self.node_graph()
        self.ranked_G = self.page_rank()
        self.normal_ranked_G = {pid: score/(self.rounds_played[pid] ** 0.5) for pid, score in self.ranked_G.items()
                                if self.rounds_played[pid] != 0}

        # scaling
        scaler = MinMaxScaler()
        pr_score = scaler.fit_transform(np.array(list(self.normal_ranked_G.values())).reshape(-1, 1))
        self.scaled_normal_ranked_G = {pid: score[0] for pid, score in zip(list(self.normal_ranked_G.keys()), pr_score)}

        # stats for computing score

        self.kpr = self.normalize_dict_values(kpr)

        # self.wpr = self.normalize_dict_values(wpr)

        self.h2h = {player: [w - l for w, l in [self.node_dict[player][i] for i in self.node_dict[player]]] for player
                    in self.node_dict}

        # self.significant_record = {player: sum(record) for player, record in self.h2h.items()}
        self.vol = self.normalize_dict_values({player: np.std(record) if record else 0 for player, record in self.h2h.items()})
        self.avg = self.normalize_dict_values({player: np.mean(record) if record else -self.rounds_played[player] for player, record in self.h2h.items()})
        self.perf_score = self.normalize_dict_values({player: self.avg[player]/(1+self.vol[player])
                                                      for player in self.h2h.keys()})

        pprint(self.perf_score)
        self.ratings = self.agg_rating_score()
        #pprint(self.ratings)



    def normalize_dict_values(self, stat_dict):

        scaler = MinMaxScaler()

        scaled_values = scaler.fit_transform(np.array(list(stat_dict.values())).reshape(-1, 1))
        return {pid: score[0] for pid, score in zip(stat_dict.keys(), scaled_values)}

    def node_graph(self):
        for node in self.node_dict:
            for neighbor in self.node_dict[node]:
                w, l = self.node_dict[node][neighbor]
                self.G.add_edge(self.player_map[neighbor.lower()], node, weight=w)
                self.G.add_edge(node, self.player_map[neighbor.lower()], weight=l)

        # isolates = list(nx.isolates(self.G))
        # print(isolates)
        # self.G.remove_nodes_from(isolates)

    def page_rank(self):
        return nx.pagerank(self.G, max_iter=1000, alpha=0.67, tol=1e-06)

    def agg_rating_score(self):
        ratings = {}
        for pid in self.scaled_normal_ranked_G.keys():
            # page rank
            adj_pr = self.scaled_normal_ranked_G[pid]

            # per-round stats
            # wpr = self.wpr[pid]
            kpr = self.kpr[pid]

            # head-to-head metadata
            perf_cons_score = self.perf_score[pid]

            print(adj_pr)



            rating = round(100 * (adj_pr * 0.5 + kpr * 0.25 + perf_cons_score * 0.25), 3)
            #rating = round(100 * adj_pr, 3)
            if math.isnan(rating):
                ratings[pid] = 0
            else:
                ratings[pid] = rating.item()
        pprint(ratings)
        return ratings








    