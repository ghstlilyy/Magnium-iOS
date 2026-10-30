EN = "`qwertyuiop[]asdfghjkl;'zxcvbnm,./~QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>?"
RU = "ёйцукенгшщзхъфывапролджэячсмитьбю.ЁЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,"
TO_RU = dict(zip(EN, RU))
TO_EN = dict(zip(RU, EN))


def to_russian(text):
    return "".join(TO_RU.get(character, character) for character in text)


def to_english(text):
    return "".join(TO_EN.get(character, character) for character in text)


def fix(text):
    """Guesses the direction: mostly Latin letters become Russian, mostly Cyrillic become English."""
    latin = sum(1 for character in text if "a" <= character.lower() <= "z")
    cyrillic = sum(1 for character in text if "а" <= character.lower() <= "я" or character.lower() == "ё")
    return to_russian(text) if latin >= cyrillic else to_english(text)
