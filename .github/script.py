import json
import os

with open(f"{os.getcwd()}/config.json", "r") as f:
  jc = json.load(f)

jc["docker"] = True


with open(f"{os.getcwd()}/config.json", "w") as f:
  f.write(json.dumps(jc))