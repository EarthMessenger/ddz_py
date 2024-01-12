color_cards = '3456789XJQKA2'
king_cards = 'YZ'
suit_cards = color_cards * 4 + king_cards
card_rank = {
        '3': 0,
        '4': 1,
        '5': 2,
        '6': 3,
        '7': 4,
        '8': 5,
        '9': 6,
        'X': 7,
        'J': 8,
        'Q': 9,
        'K': 10,
        'A': 11,
        '2': 12,
        'Y': 13,
        'Z': 14,
        }

def is_bomb(cards: str):
    if len(cards) < 2:
        return False
    n = len(cards)
    if all((cards[i] == cards[i + 1] for i in range(n - 1))) and len(cards) >= 4:
        return True
    if all((c == 'Y' or c == 'Z' for c in cards)) and cards.find('Y') != -1 and cards.find('Z') != -1:
        return True;
    return False
