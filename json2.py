import json


with open("back.txt", "r") as file:
    data = json.load(file)

with open("back.txt", "w") as file:
    json.dump(data, file, indent=4, sort_keys=True)
