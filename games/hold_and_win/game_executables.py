"""
game_executables.py - Il Direttore d'Orchestra
===============================================
Questo e' il file che fa GIRARE il gioco.
Collega tutti gli altri file e definisce il flusso completo
di ogni singolo spin, dall'inizio alla fine.

FLUSSO COMPLETO DI UN GIRO:
  execute_base_game()
      |
      +--> Gira BR0.csv, legge la griglia 6x6
      +--> Conta le COIN atterrate
      |
      +--> SE coin >= 6:
      |       start_bonus() -> blocca le coin trigger
      |       execute_bonus_loop()
      |           |
      |           +--> respin 1: gira BNS.csv nelle celle vuote
      |           |    nuove coin? -> lock -> reset respins a 3
      |           |    nessuna? -> consume_respin() -> respins - 1
      |           +--> respin 2: stesso
      |           +--> respins = 0 -> bonus finito
      |           +--> calculate_total_win() -> restituisce vincita
      |
      +--> SE coin < 6:
              calcola cluster wins nel base game
              restituisce vincita (puo' essere 0)
"""

from src.executables.executables import Executables
from game_config import GameConfig
from gamestate import GameState
from game_calculations import GameCalculations


class GameExecutables(Executables):

    def execute(self, game_state: GameState) -> float:
        """
        Esegue UN giro completo del gioco.
        Chiamato dal Math SDK per ogni spin simulato.

        Returns:
            Vincita totale in multipli della puntata (es. 5.0 = 5x)
        """
        config = GameConfig()
        calc = GameCalculations()

        # --- STEP 1: Gira le reel del base game ---
        # Il motore del Math SDK popola game_state.board con la griglia
        # usando il reel strip BR0.csv. Noi la leggiamo qui.
        self._spin_base_reels(game_state, config)

        # --- STEP 2: Conta le COIN atterrate ---
        coin_positions = calc.count_coins(game_state)
        game_state.coins_landed = len(coin_positions)

        # --- STEP 3: Decide il percorso ---
        if game_state.coins_landed >= config.bonus_trigger_count:
            # === PERCORSO BONUS ===
            return self._execute_bonus(game_state, config, calc, coin_positions)
        else:
            # === PERCORSO BASE GAME ===
            return self._execute_base(game_state, config, calc)

    # ------------------------------------------------------------------ #
    #  BASE GAME                                                           #
    # ------------------------------------------------------------------ #

    def _execute_base(
        self, game_state: GameState, config: GameConfig, calc: GameCalculations
    ) -> float:
        """
        Esegue il base game: calcola i cluster wins e restituisce la vincita.
        Non c'e' molto da fare qui: il Math SDK ha gia' girato le reel,
        noi calcoliamo solo cosa e' atterrato.
        """
        game_state.game_mode = "base"
        win = calc._calculate_base_win(game_state, config)
        return win

    # ------------------------------------------------------------------ #
    #  BONUS: Hold & Win                                                   #
    # ------------------------------------------------------------------ #

    def _execute_bonus(
        self,
        game_state: GameState,
        config: GameConfig,
        calc: GameCalculations,
        trigger_positions: list,
    ) -> float:
        """
        Esegue il bonus Hold & Win completo.

        FLUSSO DETTAGLIATO:
        1. Attiva il bonus con le coin gia' atterrate nel trigger
        2. Loop di respins:
           a. Gira BNS.csv nelle celle vuote
           b. Blocca le nuove coin -> se nuova -> reset respins a 3
           c. Se nessuna nuova coin -> respins -= 1
           d. Ripeti finche' respins = 0
        3. Calcola e restituisce la vincita totale
        """
        # Attiva il bonus e blocca le coin trigger
        game_state.start_bonus(trigger_positions)
        bonus = game_state.bonus_state

        # --- LOOP RESPINS ---
        while not bonus.is_finished:

            # Gira le celle vuote con il BNS reel
            new_spin_grid = self._spin_bonus_reels(game_state, config)

            # Controlla se sono arrivate nuove coin nelle celle VUOTE
            new_coin_found = False
            for pos in range(36):
                if bonus.grid[pos] is None:  # cella era vuota
                    new_symbol = new_spin_grid[pos]

                    if new_symbol == "COIN":
                        # Assegna un valore alla nuova coin
                        coin_val = self._assign_coin_value(config)
                        was_new = bonus.lock_coin(pos, coin_val)
                        if was_new:
                            new_coin_found = True

                    elif new_symbol in config.jackpot_values:
                        # E' un jackpot! Bloccalo direttamente
                        was_new = bonus.lock_coin(pos, new_symbol)
                        if was_new:
                            new_coin_found = True

            # Se non e' arrivata nessuna nuova coin, consuma un respin
            if not new_coin_found:
                bonus.consume_respin()
            # Se e' arrivata una nuova coin, i respins sono gia' stati
            # resettati a 3 dentro lock_coin() -> il loop continua

        # --- BONUS FINITO ---
        total_win = game_state.end_bonus()
        return total_win

    # ------------------------------------------------------------------ #
    #  UTILITY: spin delle reel                                            #
    # ------------------------------------------------------------------ #

    def _spin_base_reels(self, game_state: GameState, config: GameConfig):
        """
        Popola game_state.board girando il reel BR0.
        In produzione questo e' gestito dal motore del Math SDK.
        Qui definiamo solo l'interfaccia.
        """
        # Il Math SDK chiama questa funzione internamente.
        # La griglia viene popolata automaticamente dal sistema RNG.
        pass

    def _spin_bonus_reels(self, game_state: GameState, config: GameConfig) -> list:
        """
        Gira il BNS reel per le celle vuote durante il bonus.
        Restituisce una griglia piatta [36] con i nuovi simboli.
        Le celle gia' occupate (locked) vengono ignorate dal chiamante.
        """
        # In produzione: il Math SDK usa il reel BNS e il suo RNG
        # per determinare cosa appare nelle celle vuote.
        # Restituiamo una lista piatta che il loop respins usera'.
        return self._get_bonus_spin_result(game_state, config)

    def _get_bonus_spin_result(self, game_state: GameState, config: GameConfig) -> list:
        """
        Simula un singolo respin usando il BNS reel strip.
        Questo metodo viene sostituito dal motore reale in produzione.
        """
        import random
        bonus_reel = config.reels.get("BNS", [])
        result = []
        for col_idx in range(config.num_reels):
            col_reel = [row[col_idx] for row in bonus_reel if col_idx < len(row)]
            for _ in range(config.num_rows[col_idx]):
                pos = random.randint(0, len(col_reel) - 1)
                result.append(col_reel[pos])
        return result

    def _assign_coin_value(self, config: GameConfig):
        """
        Assegna un valore casuale a una coin basandosi sui pesi
        definiti in config.coin_values.

        Esempio:
          coin_values = {1: 1000, 2: 600, 5: 300, 10: 150, ...}
          -> il valore 1 esce 1000/(1000+600+...) % del tempo
        """
        import random
        values = list(config.coin_values.keys())
        weights = list(config.coin_values.values())
        return float(random.choices(values, weights=weights, k=1)[0])
