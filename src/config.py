import os

HOME_ADV = 3.0

DRAW_PROB = 0.26
FUZZY_CUTOFF = 0.8
ELO_DIVISOR = 18

MIN_EDGE = 0.05 #edge minimo para las apuestas ganadoras 
MIN_KELLY = 0.007

KELLY_FACTOR = 0.25
MAX_STAKE = 0.05
MIN_STAKE = 0.005

P_HOME = 0.40
P_MIN = 0.8 #para cuotas combinadas 
P_MIN_COMBO = 0.6 #prob minima para el combo
EDGE_MIN_COMBO = 0.01 # edge minimo para el combo

# When True, skip updating odds and ELOs in main pipeline
SKIP_UPDATES = False

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")
