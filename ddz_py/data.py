from collections import Counter
from .card import card_rank


class DdzPlayer:
    def __init__(self, name: str):
        self.name = name
        self.player_type = 'spectator'
        self.cards: list[str] = []
        self.always_spectator = False

    def check_have_cards(self, cards: list[str]) -> bool:
        cnt_hand = Counter(self.cards)
        cnt_play = Counter(cards)
        for i in cnt_play:
            if cnt_hand[i] < cnt_play[i]:
                return False
        return True

    def sort_cards(self):
        self.cards.sort(key = lambda x: card_rank[x])

    def add_cards(self, cards: list[str]):
        for c in cards:
            self.cards.append(c)
        self.sort_cards()

    def remove_cards(self, cards: list[str]):
        for c in cards:
            self.cards.remove(c)

    def set_cards(self, cards: list[str]):
        self.cards = cards
        self.sort_cards()

    def player_status_abbr(self):
        if self.player_type == 'spectator':
            if self.always_spectator:
                return 'AS'
            return 'S'
        elif self.player_type.startswith('landlord'):
            return 'L'
        elif self.player_type.startswith('peasant'):
            return f'P{self.player_type[-1]}'
        else:
            return 'U'
