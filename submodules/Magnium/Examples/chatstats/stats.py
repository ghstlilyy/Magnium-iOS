import collections
import datetime
import re

WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
STOP_WORDS = set("и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только ее мне было вот от меня еще нет о из ему теперь когда даже ну вдруг ли если уже или ни быть был него до вас нибудь опять уж вам ведь там потом себя ничего ей может они тут где есть надо ней для мы тебя их чем была сам чтоб без будто чего раз тоже себе под будет ж тогда кто этот того потому этого какой совсем ним здесь этом один почти мой тем чтобы нее сейчас были куда зачем всех никогда можно при наконец два об другой хоть после над больше тот через эти нас про всего них какая много разве три эту моя впрочем хорошо свою этой перед иногда лучше чуть том нельзя такой им более всегда конечно всю между это the a to of and is in it you i that".split())


def summarize(messages):
    if not messages:
        return None
    mine = [m for m in messages if m["outgoing"]]
    theirs = [m for m in messages if not m["outgoing"]]
    words = collections.Counter()
    hours = collections.Counter()
    weekdays = collections.Counter()
    for message in messages:
        moment = datetime.datetime.fromtimestamp(message["timestamp"])
        hours[moment.hour] += 1
        weekdays[moment.weekday()] += 1
        for word in re.findall(r"[a-zа-яё]{3,}", message["text"].lower()):
            if word not in STOP_WORDS:
                words[word] += 1
    first = datetime.datetime.fromtimestamp(min(m["timestamp"] for m in messages))
    lines = [
        "Сообщений: {} (с {})".format(len(messages), first.strftime("%d.%m.%Y")),
        "Ваших: {} · собеседника: {}".format(len(mine), len(theirs)),
        "Средняя длина: ваша {} · собеседника {} символов".format(
            round(sum(len(m["text"]) for m in mine) / max(1, len(mine))),
            round(sum(len(m["text"]) for m in theirs) / max(1, len(theirs)))),
        "Самый активный час: {}:00".format(hours.most_common(1)[0][0]),
        "Самый активный день: {}".format(WEEKDAYS[weekdays.most_common(1)[0][0]]),
    ]
    if words:
        lines.append("Любимые слова: " + ", ".join("{} ({})".format(word, count) for word, count in words.most_common(7)))
    deleted = sum(1 for m in messages if m.get("deleted"))
    if deleted:
        lines.append("Удалено собеседником: {}".format(deleted))
    return "\n".join(lines)
