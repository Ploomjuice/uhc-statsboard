import pandas as pd
import json
from db_ops import DBOPs
from pprint import pprint

old_new = pd.read_csv("alt_csvs/to_change.csv", header=None)
print(old_new)
api = DBOPs("data/stats.db")
for _, (old, new) in old_new.iterrows():

    pid = api.cur.execute("SELECT player_id FROM players WHERE current_ign = ?", (old,)).fetchall()
    if not pid:
        continue
    else:
        pid = pid[0][0]

    # update name
    replace_name = """UPDATE players SET current_ign = ? WHERE current_ign = ?"""

    api.cur.execute(replace_name, (new, old))

    # update alts
    api.add_alts(pid, old)



api._save()
api._reopen()

# update player_map
player_map = {name.lower(): pid for pid, name in
              api.cur.execute("SELECT player_id, current_ign FROM players ORDER BY player_id")}

# overwrite json
with open("data/player_map.json", "w") as f:
    json.dump(player_map, f)

pprint(player_map)


