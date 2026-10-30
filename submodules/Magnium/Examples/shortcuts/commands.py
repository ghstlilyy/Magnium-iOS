"""The commands. Each takes the text after the command and returns what to send, or None."""

import datetime
import random

EMOTICONS = {
    ":shrug:": "¯\\_(ツ)_/¯",
    ":tableflip:": "(╯°□°)╯︵ ┻━┻",
    ":unflip:": "┬─┬ ノ( ゜-゜ノ)",
    ":lenny:": "( ͡° ͜ʖ ͡°)",
    ":disapprove:": "ಠ_ಠ",
    ":hug:": "(づ｡◕‿‿◕｡)づ",
    ":cool:": "(⌐■_■)",
    ":cry:": "(ಥ﹏ಥ)",
    ":bear:": "ʕ•ᴥ•ʔ",
    ":cat:": "(=^･ω･^=)",
    ":magic:": "(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧",
    ":dance:": "└(^o^)┐┌(^o^)┘",
}

EIGHT_BALL = [
    "Бесспорно", "Предрешено", "Никаких сомнений", "Определённо да", "Можешь быть уверен в этом",
    "Мне кажется — да", "Вероятнее всего", "Хорошие перспективы", "Знаки говорят — да", "Да",
    "Пока не ясно, попробуй снова", "Спроси позже", "Лучше не рассказывать", "Сейчас нельзя предсказать",
    "Сконцентрируйся и спроси опять", "Даже не думай", "Мой ответ — нет", "По моим данным — нет",
    "Перспективы не очень хорошие", "Весьма сомнительно",
]

ZALGO_MARKS = [chr(code) for code in range(0x0300, 0x036F)]


def mock(text):
    result, upper = [], False
    for character in text:
        if character.isalpha():
            result.append(character.upper() if upper else character.lower())
            upper = not upper
        else:
            result.append(character)
    return "".join(result)


def zalgo(text):
    return "".join(character + "".join(random.choice(ZALGO_MARKS) for _ in range(random.randint(1, 4))) if character.strip() else character for character in text)


def spaced(text):
    return " ".join(text.upper())


def bubble(text):
    table = {}
    for index, letter in enumerate("abcdefghijklmnopqrstuvwxyz"):
        table[letter] = chr(0x24D0 + index)
        table[letter.upper()] = chr(0x24B6 + index)
    return "".join(table.get(character, character) for character in text)


def roll(argument):
    try:
        top = max(2, int(argument)) if argument else 100
    except ValueError:
        top = 100
    return "🎲 {} (из {})".format(random.randint(1, top), top)


def choose(argument):
    options = [option.strip() for option in argument.replace(" или ", ",").split(",") if option.strip()]
    if len(options) < 2:
        return None
    return "🤔 Выбираю: {}".format(random.choice(options))


# command -> (function of the rest of the text, needs text after it)
COMMANDS = {
    "/time": (lambda _: "🕒 " + datetime.datetime.now().strftime("%H:%M"), False),
    "/date": (lambda _: "📅 " + datetime.datetime.now().strftime("%d.%m.%Y"), False),
    "/roll": (roll, False),
    "/coin": (lambda _: random.choice(["🪙 Орёл", "🪙 Решка"]), False),
    "/8ball": (lambda question: "🎱 " + random.choice(EIGHT_BALL), False),
    "/choose": (choose, True),
    "!mock": (mock, True),
    "!up": (lambda text: text.upper(), True),
    "!low": (lambda text: text.lower(), True),
    "!rev": (lambda text: text[::-1], True),
    "!zalgo": (zalgo, True),
    "!space": (spaced, True),
    "!bubble": (bubble, True),
    "!clap": (lambda text: " 👏 ".join(text.split()) + " 👏", True),
}


def transform(text, use_emoticons=True, use_commands=True):
    """Returns the replacement for an outgoing text, or None to send it as is."""
    if use_commands:
        head, _, rest = text.partition(" ")
        command = COMMANDS.get(head.lower())
        if command is not None:
            function, needs_text = command
            if needs_text and not rest.strip():
                return None
            return function(rest.strip())
    if use_emoticons and ":" in text:
        replaced = text
        for code, emoticon in EMOTICONS.items():
            replaced = replaced.replace(code, emoticon)
        if replaced != text:
            return replaced
    return None
