import numpy as np
from collections import defaultdict, Counter
import itertools
import math
from trueskill import Rating, quality_1vs1, setup, global_env
from data_aggregation import FullAggregation
from db_ops import DBOPs
import json
from scipy.stats import gaussian_kde
from sklearn.preprocessing import MinMaxScaler
import ast
class Simulator:
    def __init__(self, table_dict, region_size=3.5):
        self.table_dict = table_dict
        self.players = []
        self.teams = defaultdict(list)


        # store team spawns, locations
        self.locations = defaultdict()
        self.adjacent = defaultdict()
        self.region_size = region_size

        # put data into more convenient data structures
        self.dict_to_lists(table_dict)
        self.stats = defaultdict()
        for team_dict in table_dict.values():
            for p, stats in team_dict.items():
                self.stats[p] = stats

        self.players_copy = self.players.copy()
        self.teams_copy = self.teams.copy()

        self.api = DBOPs("data/stats.db")
        self.fetch = FullAggregation()
        self.scaler = MinMaxScaler()
        #self.base_clean_chance = 0.2
        print("i got here")
        # likelihoods
        self.pve_chances = self.overall_pve_likelihood()
        print("i got here")
        self.pvp_chances = self.overall_pvp_likelihood()
        print("i got here")
        self.pve, self.rounds = self.pve_death_rates()
        print("i got here")
        self.player_pve_death_rates = {p:(i/j).iat[0] for (p, i), j in zip(self.pve.items(), self.rounds.values())}
        print("after the sql stuff")

        self.player_pve_chances = {p: self.generate_pve_probabilities(p) for p in self.players}
        self.player_pvp_chances = {p: self.generate_pvp_probabilities(p) for p in self.players}

        setup()

        self.fatigue = {p:0 for p in self.players}


        # kill feed
        self.kill_board = []

        self.all_simulations = []

        with open("data/pve_probs.json", 'r') as f:
            self.pve_msg_chances = json.load(f)
        with open("data/pvp_probs.json", 'r') as f:
            self.pvp_msg_chances = json.load(f)

    def reinit(self):
        # put data into more convenient data structures
        self.players = []
        self.teams = defaultdict(list)
        self.dict_to_lists(self.table_dict)
        self.stats = defaultdict()
        for team_dict in self.table_dict.values():
            for p, stats in team_dict.items():
                self.stats[p] = stats
        self.kill_board = []


    def dict_to_lists(self, table_dict, spawn_together=True):
        """

        populate team lists, player lists
        :param table_dict:
        :param spawn_together: spawn teammates together
        :return:
        """
        for team in table_dict:

            if team != "%%%":

                for player in table_dict[team]:
                    self.teams[team].append(player)
                    self.players.append(player)

            else:
                for solo in table_dict[team]:
                    self.teams[solo] = [solo]
                    self.players.append(solo)

        self.n_players = len(self.players)
        self.regions = math.ceil(self.region_size * self.n_players)

        # point = 0
        # jump = math.floor(self.region_size)
        # spawns
        forbidden_spawns = []

        if spawn_together:
            for team in self.teams:
                #spawn = np.random.randint(0, self.regions -1)
                spawn = np.random.choice([i for i in range(self.regions) if i not in forbidden_spawns], 1)[0]

                for player in self.teams[team]:
                    self.locations[player] = spawn
                    self.adjacent[player] = [r for r in (spawn - 1, spawn, spawn + 1) if self.regions - 1 >= r >= 0]
                    forbidden_spawns += self.adjacent[player]
                # point += jump
        else:
            for player in self.players:
                spawn = np.random.choice([i for i in range(self.regions) if i not in forbidden_spawns], 1)[0]
                self.locations[player] = spawn
                self.adjacent[player] = [r for r in (spawn - 1, spawn, spawn + 1) if self.regions - 1 >= r >= 0]
                forbidden_spawns += self.adjacent[player]

        print(self.players)


    def get_random_simulation(self):
        idx = np.random.randint(0, len(self.all_simulations))
        return self.all_simulations[idx]



    def simulate(self, iter=1):
        """
        Simulates a game
        notes:
        - dying to pve is more common in the beginning than the end
            - take pve death rate + padding and decrease it based off number of deaths elapsed
        - randomize death messages from what exists in the database
        - 1v1: use ratings and h2h scores when two individuals are chosen
            - take ratings as probability scores (/combined rating, team combined for team games)
            - use h2h scores to offset probabilities (w/l benefitting the winner)
        - include suicides and mob kill-steal chances (don't do mob kill-steal if it's inconvenient)

        :param iter: n simulations

        :return:
        """
        # tentative game transition points
        early_end = math.floor(len(self.players) * 0.7) - 1
        mid_end = 2 * early_end
        late_end = 3 * early_end


        # get team ratings

        # early game
        tick = 0 # one player dead per tick maximum
        # deaths = len(self.kill_board)
        print(tick)
        print("early end", early_end)
        print('middle end', mid_end)
        print("late end", late_end)

        print("alive", (len(self.players)/self.n_players))

        for i in range(iter):
            tick = 0
            if i != 0:
                self.reinit()

            while tick < early_end and (len(self.players)/self.n_players) > 0.5:

                # order: move -> events -> move -> events ->...
                self.change_player_positions(0)

                self.pve_event()
                self.pvp_event(0)
                #
                self.fatigue_decay(state=0)
                tick += 1
                # if len(self.kill_board) > deaths:
                #
                #     deaths += 1

            # shrink lightly
            self.regions = math.floor(self.regions*2/3)

            for player in self.locations:
                self.locations[player] = math.floor(self.locations[player] * 2 / 3)
                new = self.locations[player]
                self.adjacent[player] = [r for r in (new - 1, new, new + 1) if self.regions - 1 >= r >= 0]



            while tick < mid_end and (len(self.players)/self.n_players) > 0.2:

                # order: move -> events -> move -> events ->...
                self.change_player_positions(1)

                self.pve_event()
                self.pvp_event(1)
                #
                self.fatigue_decay(state=1)
                tick += 1

            self.regions = math.floor(self.regions / 2)

            for player in self.locations:
                self.locations[player] = math.floor(self.locations[player] / 2)
                new = self.locations[player]
                self.adjacent[player] = [r for r in (new - 1, new, new + 1) if self.regions - 1 >= r >= 0]


            while tick < late_end and len(self.teams) > 1:

                # order: move -> events -> move -> events ->...
                self.change_player_positions(2)

                self.pve_event()
                self.pvp_event(2)
                #
                self.fatigue_decay(state=2)
                tick += 1

            scale = self.regions / len(self.players)
            self.regions = len(self.players)

            for player in self.locations:
                self.locations[player] = math.floor(self.locations[player] / scale)
                new = self.locations[player]
                self.adjacent[player] = [r for r in (new - 1, new, new + 1) if self.regions - 1 >= r >= 0]

            while len(self.teams) > 1:

                # order: move -> events -> move -> events ->...
                self.change_player_positions(3)

                self.pve_event()
                self.pvp_event(3)
                #
                self.fatigue_decay(state=3)
                tick += 1

            for p in self.players:
                self.kill_board.append((p, '', "Nothing"))

            self.all_simulations.append(self.kill_board)


        # while len(self.teams) > 1:
        #     pass

    def kill_player(self, player):


        self.players.remove(player)

        self.teams[self.stats[player][0]].remove(player)

        if len(self.teams[self.stats[player][0]]) == 0:
            del self.teams[self.stats[player][0]]
        del self.locations[player]

        del self.adjacent[player]



    def pve_event(self):
        """
        single pve death event, access per tick
        :return: nothing
        """
        print("pve time")

        place = len(self.kill_board) - 1
        # will an event happen?
        chance = self.pve_chances[place]
        occurrence = np.random.rand() <= chance

        if occurrence: # event will happen
            print("Event")

            # select a player
            probabilities_at_tick = {player:chances[place]*self.stats[player][4] if isinstance(chances[place], float) else
                                     chances[place].item()*self.stats[player][4] for player, chances in self.player_pve_chances.items()
                                     if player in self.players}
            #print(probabilities_at_tick)
            players = list(probabilities_at_tick.keys())
            print(players)

            # get chances of pve death
            weights = self.scaler.fit_transform(np.array(list(probabilities_at_tick.values())).reshape(-1, 1))
            print(weights)
            if np.sum(weights) > 0:
                normalized_weights = weights/np.sum(weights)
            else:
                normalized_weights = np.ones((1, len(weights))) / len(weights)


            # will they die

            selected_player = np.random.choice(players, size=1, p=normalized_weights.ravel())[0]
            print(selected_player)

            die = np.random.rand() <= self.player_pve_death_rates[selected_player]

            if die:

                causes = list(self.pve_msg_chances.keys())
                probs = list(self.pve_msg_chances.values())
                choice = np.random.choice(causes, p=probs)
                msg, pve = ast.literal_eval(choice)

                self.kill_player(selected_player)

                self.kill_board.append((selected_player, msg, pve))


        else:
            print("No Event")



    def pvp_event(self, state):
        """
        one encounter, the number of players present for a fight per team is dependent on the game stage
        note: while the basics and fundamentals were drafted out by myself,
        chatgpt aided in helping me decide normalization functions for certain stats
        0: early game (ep 1-4)
        1: mid-game (ep 5)
        2: end-game (ep 6)
        3: finish up
        :return:
        """
        print("pvp time")
        place = len(self.kill_board)
        # check if an event *can* happen: which players are adjacent to each other?
        can_fight = defaultdict()
        for player in self.locations:
            possible_opps = [opp for opp in self.locations if self.locations[opp] in self.adjacent[player]
                                 and opp not in self.teams[self.stats[player][0]] and opp != player]
            if possible_opps:
                can_fight[player] = possible_opps

        # select from players who are close
        if len(can_fight) != 0:
            player_a = np.random.choice(list(can_fight.keys()))
            player_b = np.random.choice(can_fight[player_a])
            print(player_a, player_b)
        else:
            print('nobody is close')
            return





        # will an event happen? artificially space out kills based on estimated willingness + location to take fights
        if state == 0: # teams are more likely to be separate here
            chance = 0.8
            fatigue_multiplier = 1.0
        elif state == 1: # teams are starting to come together
            chance = 0.95
            fatigue_multiplier = 1.25
        elif state == 2: # teams may have lost members at this point
            chance = 0.7
            fatigue_multiplier = 1.75
        else:
            chance = 1
            fatigue_multiplier = 2.5

        occurrence = np.random.rand() <= chance

        if occurrence: # if pvp event with a death occurs

            # adjacent teammates
            a_all = [teammate for teammate in self.teams[self.stats[player_a][0]]
                     if self.locations[teammate] in self.adjacent[player_a]]
            print(a_all)
            b_all = [teammate for teammate in self.teams[self.stats[player_b][0]]
                     if self.locations[teammate] in self.adjacent[player_b]]
            print(b_all)

            # get winning chances
            a_ratings_total = sum([self.stats[p][1] * (1-self.fatigue[p]) for p in a_all]) * len(a_all)**0.8 # adjust for fighting party size
            b_ratings_total = sum([self.stats[p][1] * (1-self.fatigue[p]) for p in b_all]) * len(b_all)**0.8

            a_ratings = [Rating(self.stats[p][1]) for p in a_all]  # adjust for fighting party size
            b_ratings = [Rating(self.stats[p][1]) for p in b_all]

            a_win_chance = self.win_probability(a_ratings, b_ratings)
            max_messiness = quality_1vs1(Rating(a_ratings_total), Rating(b_ratings_total)) # use to demerit einner and surviving loser
            a_lose_chance = 1 - a_win_chance

            roll = np.random.choice([1,-1], size=1, p=[a_win_chance, a_lose_chance])[0]

            # for tomorrow, get kill probabilities, decide who dies
            # for each loser, get death chance
            if roll == 1: # one person dies from losing party
                dead, killer = self.get_kill_data(place, a_all, b_all)

            else:
                dead, killer = self.get_kill_data(place, b_all, a_all)

            causes = list(self.pvp_msg_chances.keys())
            probs = list(self.pvp_msg_chances.values())
            choice = np.random.choice(causes, size=1, p=probs)[0]

            self.kill_board.append((dead, choice, killer))
            self.kill_player(dead)
            # apply rating-based fatigue addition
            diff = self.stats[killer][1] - self.stats[dead][1]
            rb_adjust = 1.03 ** ((diff / 10) * len(b_all) ** 0.8)



            for player in a_all + b_all:
                messiness = np.random.uniform(0, max_messiness)


                fatigue = messiness * fatigue_multiplier if messiness < (1 / fatigue_multiplier) else 1
                self.fatigue[player] += fatigue * rb_adjust
                # if self.fatigue[player] > 0.9:





            print('win', a_win_chance)
            print(self.kill_board)
            print(self.fatigue)

        else:
            print("No Event")

    def fatigue_decay(self, state):
        decays = [0.05, 0.03, 0.01, 0]
        for player in self.fatigue:
            self.fatigue[player] -= decays[state]
            if self.fatigue[player] < 0:
                self.fatigue[player] = 0

    def get_kill_data(self, tick, winners, losers):

        winner_norm_ratings = sum([self.stats[winner][1] for winner in winners]) ** 0.6
        pvp_prob = [self.player_pvp_chances[winner][tick] for winner in winners]
        print(pvp_prob)
        normalized_probs = [i / sum(pvp_prob) for i in pvp_prob]
        print(normalized_probs)

        death_probs = defaultdict()

        for teammate in losers:  # losing party

            loser_norm_rating = (self.stats[teammate][1] - 22.5) / 22.5
            h2h_against_winners = [(i[1], i[2]) for i in self.get_all_h2h(teammate) if i[0] in winners]
            adj_h2h = sum([np.tanh((h[0] - h[1]) / (h[0] + h[1])) for h in h2h_against_winners]) ** 0.8
            adj_h2h = adj_h2h if not math.isnan(adj_h2h) else 0
            death_score = -0.2 + 0.8 * winner_norm_ratings - 0.7 * loser_norm_rating - 0.6 * adj_h2h
            death_prob = 1 / (1 + math.exp(-death_score))
            death_probs[teammate] = death_prob
        print(death_probs)
        normalized_death_probs = [i / sum(list(death_probs.values())) for i in death_probs.values()]
        killer = np.random.choice(winners, size=1, p=normalized_probs)[0]
        dead = np.random.choice(losers, size=1, p=normalized_death_probs)[0]
        return dead, killer

    def win_probability(self, team1, team2): # from TrueSkill Documentation
        delta_mu = sum(r.mu for r in team1) - sum(r.mu for r in team2)
        sum_sigma = sum(r.sigma ** 2 for r in itertools.chain(team1, team2))
        size = len(team1) + len(team2)
        denom = math.sqrt(size * 100 + sum_sigma)
        ts = global_env()
        return ts.cdf(delta_mu / denom)

    def change_player_positions(self, state):
        if state == 0:
            for player in self.adjacent:
                for i in range(2):
                    choices = self.adjacent[player]
                    new = np.random.choice(choices, 1)[0]
                    self.locations[player] = new
                    self.adjacent[player] = [r for r in (new - 1, new, new + 1) if self.regions - 1 >= r >= 0]
        elif state > 0: # adjust for late stages where they move as a team
            for team in self.teams:
                locations = [v for i, v in self.locations.items() if i in self.teams[team]]
                if not locations:
                    continue

                average = math.floor(np.mean(locations))

                for player in self.teams[team]:
                    if self.locations[player] < (average - 1):
                        self.locations[player] += 1
                    elif self.locations[player] > (average + 1):
                        self.locations[player] -= 1
                    else:
                        choices = self.adjacent[player]
                        print(self.regions, player, choices)
                        new = np.random.choice(choices, 1)[0]
                        self.locations[player] = new
                    new_loc = self.locations[player]
                    self.adjacent[player] = [r for r in (new_loc - 1, new_loc, new_loc + 1) if self.regions - 1 >= r >= 0]
        # elif state > 1:
        #
        #     pass



    def fetch_stats(self, player):
        """
        fetches relevant stats:
        - rating
        - pve death rate
        - win rate

        :return:
        """
        q = """
            SELECT 
                time_divided_rounds,
                yearly_wins,
                lifetime_wpr,
                first_deaths,
                time_divided_pve,
                team_kills,
                suicides,
                CAST(first_bloods AS INT)/CAST(lifetime_rounds AS INT) AS fb_rate,
                CAST(top_frags AS INT)/CAST(lifetime_rounds AS INT) AS tf_rate,
                top_frags,
                
                nemeses,
                rivals,
                dominating,
                
                ratings,
                
                
                
        """

    def generate_pvp_probabilities(self, ign):
        n_players = self.n_players
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

            SELECT
                ROUND(CAST(r.n_players - (r.last - k.entry_id) AS FLOAT)/CAST(r.n_players AS FLOAT), 4) AS placement_pct
            FROM season_killfeed k
            JOIN roster_sizes r ON k.season_id = r.season_id

            WHERE k.killer_id IN (SELECT player_id FROM players WHERE current_ign = ?)
        """
        raw = [i[0] for i in self.api.cur.execute(q, (ign,)).fetchall()]
        if len(raw) == 0:
            chances = self.pvp_chances
            modifier = 0.5 / (self.rounds[ign].iat[0] + 10)

            return chances * modifier

        elif len(raw) == 1:

            chances = self.pvp_chances
            modifier = (raw[0] + 0.5) / (self.rounds[ign].iat[0] + 10)

            return chances * modifier

        elif len(set(raw)) == 1 and raw[0] == 0.0:
            chances = self.pvp_chances
            modifier = (raw[0] + 0.5) / (self.rounds[ign].iat[0] + 10)
            early = math.floor(len(self.players) * 0.5) - 1
            adjusted_chances = (chances * modifier).tolist()
            return np.array([i if adjusted_chances.index(i) < early else i * 0.01 for i in adjusted_chances])

        else:
            kde = gaussian_kde(raw)
            x = np.arange(0, 1, 1 / n_players)
            pdf = kde(x)

            return pdf / sum(pdf)

    def generate_pve_probabilities(self, ign):
        n_players = self.n_players
        print(ign)
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

            SELECT
                ROUND(CAST(r.n_players - (r.last - k.entry_id) AS FLOAT)/CAST(r.n_players AS FLOAT), 4) AS placement_pct
            FROM season_killfeed k
            JOIN roster_sizes r ON k.season_id = r.season_id

            WHERE k.dead_id IN (SELECT player_id FROM players WHERE current_ign = ?) AND k.pve_id IS NOT NULL AND k.pve_id != 'Nothing'
        
        """
        raw = [i[0] for i in self.api.cur.execute(q, (ign,)).fetchall()]
        #print(raw)
        if len(raw) == 0:
            chances = self.pve_chances
            modifier = 0.5 / (self.rounds[ign].iat[0] + 10)
            #print(chances * modifier)
            dist = chances * modifier


        elif len(raw) == 1:

            chances = self.pve_chances
            modifier = (raw[0] + 0.5) / (self.rounds[ign].iat[0] + 10)
            dist = chances * modifier

        elif len(set(raw)) == 1 and raw[0] == 0.0:
            chances = self.pve_chances
            modifier = (raw[0] + 0.5) / (self.rounds[ign].iat[0] + 10)
            early = math.floor(len(self.players) * 0.5) - 1
            adjusted_chances = (chances * modifier).tolist()
            dist = np.array([i if adjusted_chances.index(i) < early else i * 0.01 for i in adjusted_chances])

        else:
            kde = gaussian_kde(raw)
            x = np.arange(0, 1, 1 / n_players)
            pdf = kde(x)

            dist = pdf/sum(pdf) * self.player_pve_death_rates[ign]

        print(dist)

        return [i if i else 0.0001 for i in dist]

    def overall_pve_likelihood(self):

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
        placements = [i[0] for i in self.api.cur.execute(q).fetchall() if i[0]]
        kde = gaussian_kde(placements)
        x = np.arange(0, 1, 1 / self.n_players)
        pdf = kde(x)
        return pdf/sum(pdf)

    def overall_pvp_likelihood(self):
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

            SELECT
                ROUND(CAST(r.n_players - (r.last - k.entry_id) AS FLOAT)/CAST(r.n_players AS FLOAT), 4) AS placement_pct
            FROM season_killfeed k
            JOIN roster_sizes r ON k.season_id = r.season_id

        """
        placements = [i[0] for i in self.api.cur.execute(q).fetchall() if i[0]]
        kde = gaussian_kde(placements)
        x = np.arange(0, 1, 1 / self.n_players)
        pdf = kde(x)
        return pdf / sum(pdf)

    def pve_death_rates(self):
        q = """
            SELECT player_id
            FROM players
            WHERE current_ign = ?
        """
        pids = [self.api.cur.execute(q, (p,)).fetchall()[0][0] for p in self.players]
        pve = {p: np.sum(self.fetch.pve[pid]) for p, pid in zip(self.players, pids)}
        rounds = {p: self.fetch.round_counter[pid] for p, pid in zip(self.players, pids)}
        return pve, rounds

    def fetch_h2h(self, player_lose, player_win):
        q = """
            SELECT 
                nemeses, rivals, dominating
            FROM player_stats
            WHERE player_id IN (SELECT player_id FROM players WHERE current_ign = ?)
            """
        loser_h2h = [ast.literal_eval(i) for i in self.api.cur.execute(q, (player_lose,)).fetchall()[0]]

        record = 0
        for i in loser_h2h:
            if player_win in i:
                record = i[player_win][0] - i[player_win][1]
                return record
        return record

    def get_all_h2h(self, ign):
        q = """
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
                       WHERE k.dead_id IN (SELECT player_id FROM players WHERE current_ign = ?)
                       GROUP BY killer_id
                       ORDER BY COUNT(killer_id) DESC
                       ),
                       revenges AS (
                       SELECT k.dead_id, n.player_id, n.current_ign, CAST(COUNT(*) AS FLOAT) as counters
                       FROM season_killfeed k
                       JOIN nemeses n ON k.dead_id = n.player_id
                       WHERE k.killer_id = n.dead_id
                       GROUP BY k.dead_id
                       ORDER BY COUNT(*) DESC
                       )

                     SELECT n.current_ign, CAST(COALESCE(r.counters, 0) AS INT), CAST(n.kills AS INT)
                       FROM nemeses n
                       LEFT JOIN revenges r ON n.player_id = r.dead_id
                       ORDER BY n.kills DESC, r.counters ASC"""

        h2h = self.api.cur.execute(q, (ign,)).fetchall()
        return h2h

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
            msg_probs[(death_msg, cause)] = count/total

        return msg_probs



    def aggregate_sims(self):
        # get average n kills, team placement, indiv placement, win count, win%
        placements = [[i[0] for i in feed][::-1] for feed in self.all_simulations]
        total = len(placements)
        team_placements = []
        for entry in placements:
            single_sim_placements = []
            for player in entry:
                team = self.stats[player][0]
                if team in single_sim_placements:
                    pass
                else:
                    single_sim_placements.append(team)
            team_placements.append(single_sim_placements)
        kills = [Counter([i[2] for i in feed]) for feed in self.all_simulations]
        print(kills)
        print(placements)
        print(team_placements)

        player_data = {}

        for player in self.players_copy:
            print(player)
            team = self.stats[player][0]
            avg_kills = round(np.mean([l[player] for l in kills]), 2)
            print(avg_kills)
            avg_i_placement = round(np.mean([l.index(player)+1 for l in placements]), 2)
            avg_t_placement = round(np.mean([l.index(team)+1 for l in team_placements]), 2)
            print(avg_t_placement)
            win_count = len([game for game in team_placements if game[0] == team])
            win_pct = round(100*win_count/total, 2)
            player_data[player] = {'team': team,
                                   'avg_kills': avg_kills,
                                   'avg_i_placement': avg_i_placement,
                                   'avg_t_placement': avg_t_placement,
                                   'win_count': win_count,
                                   'win_pct': win_pct}
        print(player_data)
        return player_data


# if __name__ == '__main__':
#     test = TeamBuilder({'poo': {"ColdBac": (3,2,1)}})
#


