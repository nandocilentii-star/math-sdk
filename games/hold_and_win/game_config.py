"""
Hold & Win 6x6 - Game Configuration
=====================================
Gioco: Mike Perry Hold & Win
Griglia: 6 colonne x 6 righe = 36 posizioni totali
Meccanica: Hold & Win con respins (3 vite, reset su nuova coin)
RTP target: 96% | Hit Frequency: ~33% | Max Win: 50,000x
"""

import os
from src.config.config import Config
from src.config.distributions import Distribution
from src.config.betmode import BetMode


class GameConfig(Config):
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        super().__init__()

        # --- IDENTITA' DEL GIOCO ---
        self.game_id = "hold_and_win"
        self.provider_number = 0
        self.working_name = "Mike Perry Hold and Win"

        # --- PARAMETRI MATEMATICI CHIAVE ---
        # wincap: moltiplicatore massimo (50,000x la puntata)
        # win_type: "hold_and_win" = respins con coin bloccate
        # rtp: 0.96 = il gioco paga in media 96 cent per ogni euro
        self.wincap = 50000.0
        self.win_type = "hold_and_win"
        self.rtp = 0.96
        self.construct_paths()

        # --- DIMENSIONI GRIGLIA ---
        # 6 colonne x 6 righe = 36 posizioni totali
        self.num_reels = 6
        self.num_rows = [6] * self.num_reels

        # --- SIMBOLI SPECIALI ---
        self.special_symbols = {
            "wild": ["W"],
            "coin": ["COIN"],
            "jackpot": ["MINI", "MINOR", "MAJOR", "GRAND"],
        }

        # --- JACKPOT VALUES (multipli della puntata) ---
        self.jackpot_values = {
            "MINI":  50.0,
            "MINOR": 200.0,
            "MAJOR": 2000.0,
            "GRAND": 50000.0,
        }

        # --- VALORI COIN NEL BONUS ---
        # { valore_x: peso } - peso alto = esce piu' spesso
        self.coin_values = {
            1: 1000, 2: 600, 5: 300, 10: 150,
            25: 60, 50: 25, 100: 10, 500: 3,
        }

        # --- TRIGGER e RESPINS ---
        self.bonus_trigger_count = 6   # 6+ coin nel base game = bonus
        self.respin_count = 3          # 3 respins, reset su nuova coin

        # --- PAYTABLE BASE GAME (cluster pays, min 5 simboli) ---
        self.paytable = {
            (12,"W"):500,(10,"W"):200,(8,"W"):50,(6,"W"):20,(5,"W"):10,
            (12,"H1"):500,(10,"H1"):150,(8,"H1"):40,(6,"H1"):15,(5,"H1"):5,
            (12,"H2"):200,(10,"H2"):80,(8,"H2"):20,(6,"H2"):8,(5,"H2"):3,
            (12,"H3"):100,(10,"H3"):40,(8,"H3"):10,(6,"H3"):4,(5,"H3"):1.5,
            (12,"L1"):50,(10,"L1"):20,(8,"L1"):5,(6,"L1"):2,(5,"L1"):0.5,
            (12,"L2"):40,(10,"L2"):15,(8,"L2"):4,(6,"L2"):1.5,(5,"L2"):0.4,
            (12,"L3"):30,(10,"L3"):10,(8,"L3"):3,(6,"L3"):1,(5,"L3"):0.3,
            (12,"L4"):20,(10,"L4"):8,(8,"L4"):2,(6,"L4"):0.8,(5,"L4"):0.2,
        }
        self.cluster_size_min = 5

        # --- REEL STRIPS ---
        # BR0.csv = base game | BNS.csv = bonus (solo coin + jackpot)
        reels = {"BR0": "BR0.csv", "BNS": "BNS.csv"}
        self.reels = {}
        for r, f in reels.items():
            self.reels[r] = self.read_reels_csv(os.path.join(self.reels_path, f))
        self.padding_reels[self.basegame_type] = self.reels["BR0"]
        self.padding_reels[self.freegame_type] = self.reels["BNS"]

        # --- DISTRIBUZIONI ---
        # 40% spin -> zero win | 27% -> cluster win | 33% -> bonus | 0.05% -> wincap
        basegame_cond = {"reel_weights":{self.basegame_type:{"BR0":1}},"mult_values":{self.basegame_type:{1:1}},"force_wincap":False,"force_freegame":False}
        bonus_cond    = {"reel_weights":{self.basegame_type:{"BR0":1},self.freegame_type:{"BNS":1}},"force_wincap":False,"force_freegame":True}
        wincap_cond   = {"reel_weights":{self.basegame_type:{"BR0":1},self.freegame_type:{"BNS":1}},"force_wincap":True,"force_freegame":True}
        zerowin_cond  = {"reel_weights":{self.basegame_type:{"BR0":1}},"mult_values":{self.basegame_type:{1:1}},"force_wincap":False,"force_freegame":False}

        self.bet_modes = [
            BetMode(name="base", cost=1.0, rtp=self.rtp, max_win=50000.0,
                    auto_close_disabled=False, is_feature=True, is_buybonus=False,
                    distributions=[
                        Distribution(criteria="wincap",   quota=0.0005, win_criteria=50000.0, conditions=wincap_cond),
                        Distribution(criteria="freegame", quota=0.33,   conditions=bonus_cond),
                        Distribution(criteria="0",        quota=0.40,   win_criteria=0.0,     conditions=zerowin_cond),
                        Distribution(criteria="basegame", quota=0.27,   conditions=basegame_cond),
                    ]),
            BetMode(name="bonus_buy", cost=100.0, rtp=self.rtp, max_win=50000.0,
                    auto_close_disabled=False, is_feature=False, is_buybonus=True,
                    distributions=[
                        Distribution(criteria="wincap",   quota=0.001, win_criteria=50000.0, conditions=wincap_cond),
                        Distribution(criteria="freegame", quota=0.999, conditions=bonus_cond),
                    ]),
        ]
