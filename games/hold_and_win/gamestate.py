"""
gamestate.py - Logica dello stato del gioco Hold & Win
=======================================================
Questo e' il file piu' importante: definisce come il gioco
"ricorda" cosa sta succedendo durante ogni spin e durante il bonus.

CONCETTI CHIAVE:
- GameState: snapshot completo dello stato in un momento preciso
- Basegame: spin normale, cerca 6+ coin per triggerare il bonus
- Bonus (Hold & Win): fase con respins, coin bloccate, jackpot
"""

from dataclasses import dataclass, field
from typing import Optional
from src.gamestate.gamestate import GameState as BaseGameState
from game_config import GameConfig


@dataclass
class HoldAndWinBonusState:
    """
    Stato del bonus Hold & Win.

    Immagina la griglia 6x6 come una lista di 36 celle (6 colonne x 6 righe).
    Ogni cella puo' essere:
      - None: vuota (girera' nel prossimo respin)
      - un numero: valore in multipli della puntata (es. 5.0 = 5x)
      - una stringa: jackpot ("MINI", "MINOR", "MAJOR", "GRAND")

    Esempio griglia 6x6 appiattita (indici 0-35):
      Col0  Col1  Col2  Col3  Col4  Col5
      [0]   [6]   [12]  [18]  [24]  [30]   <- riga 0
      [1]   [7]   [13]  [19]  [25]  [31]   <- riga 1
      [2]   [8]   [14]  [20]  [26]  [32]   <- riga 2
      [3]   [9]   [15]  [21]  [27]  [33]   <- riga 3
      [4]   [10]  [16]  [22]  [28]  [34]   <- riga 4
      [5]   [11]  [17]  [23]  [29]  [35]   <- riga 5
    """

    # La griglia: lista di 36 celle. None = vuota, float/str = coin bloccata
    grid: list = field(default_factory=lambda: [None] * 36)

    # Respins rimanenti (parte a 3, si resetta a 3 quando arriva nuova coin)
    respins_remaining: int = 3

    # Respins totali eseguiti (per statistiche e debug)
    respins_total: int = 0

    # Bonus attivo o no
    is_active: bool = False

    # Valore totale accumulato dalle coin durante il bonus
    total_coin_value: float = 0.0

    # Jackpot trovati durante il bonus (es. ["MINI", "MAJOR"])
    jackpots_collected: list = field(default_factory=list)

    # Numero di coin bloccate in questo momento
    @property
    def locked_count(self) -> int:
        return sum(1 for cell in self.grid if cell is not None)

    # Numero di celle vuote (girano nel prossimo respin)
    @property
    def empty_count(self) -> int:
        return 36 - self.locked_count

    # Il bonus e' finito quando respins = 0
    @property
    def is_finished(self) -> bool:
        return self.respins_remaining <= 0

    def lock_coin(self, position: int, value) -> bool:
        """
        Blocca una coin in una posizione della griglia.

        Args:
            position: indice 0-35 nella griglia
            value: float (es. 10.0) o str (es. "MAJOR")

        Returns:
            True se e' una NUOVA coin (resetta i respins)
            False se la cella era gia' occupata
        """
        if self.grid[position] is None:
            self.grid[position] = value
            # Nuova coin! Resetta i respins a 3
            self.respins_remaining = 3

            # Accumula valore se e' una coin numerica
            if isinstance(value, (int, float)):
                self.total_coin_value += float(value)
            # Se e' un jackpot, registralo
            elif isinstance(value, str) and value in ("MINI", "MINOR", "MAJOR", "GRAND"):
                self.jackpots_collected.append(value)

            return True  # Nuova coin
        return False    # Cella gia' occupata

    def consume_respin(self) -> bool:
        """
        Consuma un respin. Chiamato alla fine di ogni respin senza nuove coin.

        Returns:
            True se ci sono ancora respins
            False se il bonus e' finito
        """
        self.respins_remaining -= 1
        self.respins_total += 1
        return self.respins_remaining > 0

    def calculate_total_win(self, config: 'GameConfig') -> float:
        """
        Calcola la vincita totale del bonus.

        Somma:
        1. Tutti i valori delle coin numeriche
        2. I valori dei jackpot raccolti (da config.jackpot_values)

        Returns:
            Vincita totale in multipli della puntata
        """
        total = self.total_coin_value

        # Aggiungi il valore di ogni jackpot raccolto
        for jackpot_name in self.jackpots_collected:
            total += config.jackpot_values.get(jackpot_name, 0.0)

        # Applica il wincap (non si puo' vincere piu' di 50,000x)
        return min(total, config.wincap)

    def reset(self):
        """Resetta il bonus per un nuovo ciclo."""
        self.grid = [None] * 36
        self.respins_remaining = 3
        self.respins_total = 0
        self.is_active = False
        self.total_coin_value = 0.0
        self.jackpots_collected = []


@dataclass
class GameState(BaseGameState):
    """
    Stato completo del gioco Hold & Win.

    Estende il GameState base del Math SDK aggiungendo
    lo stato specifico del bonus Hold & Win.

    FLUSSO DI UN GIOCO COMPLETO:
    1. Spin normale (base game):
       - Il motore gira il BR0.csv
       - Conta i simboli COIN atterrati
       - Se >= 6 coin: game_mode passa a "bonus"
       - Se < 6 coin: calcola cluster wins normali
    2. Bonus Hold & Win:
       - bonus_state.is_active = True
       - I COIN atterrati nel trigger vengono bloccati nella griglia
       - Parte con respins_remaining = 3
       - Ogni respin: le celle vuote girano con BNS.csv
       - Nuova coin -> lock_coin() -> respins reset a 3
       - Nessuna nuova coin -> consume_respin() -> respins -1
       - respins = 0 -> bonus finito -> paga calculate_total_win()
    """

    # Stato del bonus H&W (None se non in bonus)
    bonus_state: Optional[HoldAndWinBonusState] = None

    # Fase attuale: "base" o "bonus"
    game_mode: str = "base"

    # Quante COIN sono atterrate nell'ultimo spin del base game
    coins_landed: int = 0

    # Vincita del base game (cluster wins)
    base_win: float = 0.0

    def start_bonus(self, trigger_positions: list):
        """
        Attiva il bonus Hold & Win.

        Args:
            trigger_positions: lista di indici (0-35) dove sono atterrate
                               le coin nel base game che hanno triggerato il bonus
        """
        self.bonus_state = HoldAndWinBonusState()
        self.bonus_state.is_active = True
        self.game_mode = "bonus"

        # Blocca immediatamente le coin che hanno triggerato il bonus
        config = GameConfig()
        for pos in trigger_positions:
            # Assegna un valore casuale alla coin trigger
            # (il valore viene scelto dal motore in base a coin_values)
            coin_val = self._pick_coin_value(config)
            self.bonus_state.lock_coin(pos, coin_val)

        # Le coin trigger NON resettano i respins (partono gia' a 3)
        self.bonus_state.respins_remaining = 3

    def _pick_coin_value(self, config: 'GameConfig'):
        """
        Sceglie un valore casuale per una coin basandosi sui pesi.
        In produzione questo viene gestito dal motore RNG del Math SDK.
        """
        import random
        values = list(config.coin_values.keys())
        weights = list(config.coin_values.values())
        return random.choices(values, weights=weights, k=1)[0]

    def end_bonus(self) -> float:
        """
        Termina il bonus e restituisce la vincita totale.

        Returns:
            Vincita totale in multipli della puntata
        """
        if self.bonus_state is None:
            return 0.0

        config = GameConfig()
        win = self.bonus_state.calculate_total_win(config)

        # Resetta lo stato per il prossimo giro
        self.game_mode = "base"
        self.bonus_state = None

        return win
