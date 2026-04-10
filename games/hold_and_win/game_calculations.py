"""
game_calculations.py - Calcolo delle vincite
=============================================
Questo file si occupa di DUE tipi di calcolo:

1. BASE GAME: cerca cluster di simboli identici sulla griglia 6x6
   - Minimo 5 simboli adiacenti = vincita
   - I simboli COIN non fanno vincite nel base game (servono per il bonus)
   - Il Wild (W) si unisce a qualsiasi cluster

2. BONUS Hold & Win: calcola la vincita finale sommando
   - Tutti i valori delle coin bloccate
   - I valori dei jackpot raccolti
   - Applica il wincap di 50,000x

CONCETTO DI CLUSTER:
Un cluster e' un gruppo di simboli IDENTICI e ADIACENTI.
Adiacente = sopra, sotto, sinistra, destra (NON diagonale).

Esempio su griglia 6x6 (. = altro simbolo, H = H1):
  . . H . . .
  . H H H . .
  . . H . . .
Questo e' un cluster di 5x H1 -> vincita dal paytable (5, "H1")
"""

from src.calculations.calculations import Calculations
from game_config import GameConfig
from gamestate import GameState, HoldAndWinBonusState


class GameCalculations(Calculations):

    def calculate_win(self, game_state: GameState) -> float:
        """
        Punto di ingresso principale: calcola la vincita per il turno corrente.

        Se siamo nel base game -> cerca cluster wins
        Se siamo nel bonus    -> calcola il totale delle coin + jackpot
        """
        config = GameConfig()

        if game_state.game_mode == "bonus" and game_state.bonus_state:
            return self._calculate_bonus_win(game_state.bonus_state, config)
        else:
            return self._calculate_base_win(game_state, config)

    # ------------------------------------------------------------------ #
    #  BASE GAME: Cluster Pays                                             #
    # ------------------------------------------------------------------ #

    def _calculate_base_win(self, game_state: GameState, config: GameConfig) -> float:
        """
        Calcola le vincite cluster nel base game.

        Steps:
        1. Legge la griglia 6x6 (36 celle)
        2. Trova tutti i cluster di simboli identici >= 5
        3. Espande i cluster con i Wild
        4. Cerca il moltiplicatore nel paytable
        5. Somma tutte le vincite
        """
        grid = game_state.board  # griglia piatta [36] o [[6][6]] dipende dall'SDK

        # Normalizza a lista piatta di 36 elementi
        if isinstance(grid[0], list):
            flat_grid = [cell for col in grid for cell in col]
        else:
            flat_grid = list(grid)

        total_win = 0.0
        visited = [False] * 36  # tiene traccia delle celle gia' conteggiate

        for start_pos in range(36):
            symbol = flat_grid[start_pos]

            # Salta celle gia' visitate, celle vuote, COIN e spazi
            if visited[start_pos] or symbol in (None, "", "COIN", "EMPTY"):
                continue
            # Salta i Wild standalone (vengono contati solo nei cluster altrui)
            if symbol == "W":
                continue

            # Trova il cluster partendo da questa cella
            cluster = self._find_cluster(flat_grid, start_pos, symbol, visited)

            if len(cluster) >= config.cluster_size_min:
                # Segna le celle come visitate
                for pos in cluster:
                    visited[pos] = True

                # Cerca la vincita nel paytable
                win = self._lookup_paytable(len(cluster), symbol, config)
                total_win += win

        game_state.base_win = total_win
        return total_win

    def _find_cluster(self, grid: list, start: int, symbol: str, visited: list) -> list:
        """
        BFS (ricerca in ampiezza) per trovare tutti i simboli identici
        adiacenti partendo da 'start'.

        Considera anche i Wild (W) come parte del cluster.

        Griglia 6x6: colonna = start // 6, riga = start % 6
        Adiacenti: su(-1), giu(+1), sinistra(-6), destra(+6)
        """
        cluster = []
        queue = [start]
        seen = {start}

        while queue:
            pos = queue.pop(0)
            cell = grid[pos]

            # Aggiungi al cluster se e' il simbolo cercato o un Wild
            if cell == symbol or cell == "W":
                if not visited[pos]:
                    cluster.append(pos)

                    # Calcola i vicini (su, giu, sinistra, destra)
                    col = pos // 6
                    row = pos % 6
                    neighbors = []

                    if row > 0:          neighbors.append(pos - 1)  # su
                    if row < 5:          neighbors.append(pos + 1)  # giu
                    if col > 0:          neighbors.append(pos - 6)  # sinistra
                    if col < 5:          neighbors.append(pos + 6)  # destra

                    for nb in neighbors:
                        if nb not in seen:
                            seen.add(nb)
                            nb_cell = grid[nb]
                            if nb_cell == symbol or nb_cell == "W":
                                queue.append(nb)

        return cluster

    def _lookup_paytable(self, cluster_size: int, symbol: str, config: GameConfig) -> float:
        """
        Cerca la vincita nel paytable per (cluster_size, symbol).

        Se la dimensione esatta non esiste, usa la piu' grande disponibile
        che sia <= cluster_size.

        Esempio: cluster di 7 H1 -> cerca (7,"H1"), non trovato ->
                 usa (6,"H1") = 15x
        """
        # Raccogli tutte le dimensioni disponibili per questo simbolo
        available_sizes = [
            size for (size, sym) in config.paytable.keys()
            if sym == symbol and size <= cluster_size
        ]

        if not available_sizes:
            return 0.0

        # Usa la dimensione piu' grande <= cluster_size
        best_size = max(available_sizes)
        return config.paytable.get((best_size, symbol), 0.0)

    # ------------------------------------------------------------------ #
    #  BONUS: Hold & Win Win Calculation                                   #
    # ------------------------------------------------------------------ #

    def _calculate_bonus_win(
        self, bonus_state: HoldAndWinBonusState, config: GameConfig
    ) -> float:
        """
        Calcola la vincita finale del bonus Hold & Win.

        Somma:
        - Tutti i valori numerici delle coin bloccate nella griglia
        - I valori dei jackpot (da config.jackpot_values)
        - Applica il wincap di 50,000x

        Chiamato SOLO quando il bonus e' finito (respins = 0).
        """
        total = 0.0

        for cell in bonus_state.grid:
            if cell is None:
                continue  # cella vuota, ignora
            elif isinstance(cell, (int, float)):
                total += float(cell)  # coin con valore numerico
            elif isinstance(cell, str) and cell in config.jackpot_values:
                total += config.jackpot_values[cell]  # jackpot

        # Applica il wincap
        return min(total, config.wincap)

    # ------------------------------------------------------------------ #
    #  UTILITY: conteggio COIN per trigger                                 #
    # ------------------------------------------------------------------ #

    def count_coins(self, game_state: GameState) -> list:
        """
        Conta le COIN atterrate nel base game e restituisce le loro posizioni.

        Usato dal game_executables per decidere se triggerare il bonus.

        Returns:
            Lista di indici (0-35) dove si trovano le COIN
        """
        grid = game_state.board
        if isinstance(grid[0], list):
            flat_grid = [cell for col in grid for cell in col]
        else:
            flat_grid = list(grid)

        return [i for i, cell in enumerate(flat_grid) if cell == "COIN"]
