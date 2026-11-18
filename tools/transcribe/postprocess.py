#!/usr/bin/env python3
"""Постобработка результатов whisper-cli для transcribe.

  postprocess.py vad JSON LOG
      Пересчитать таймкоды токенов из шкалы «только речь» (VAD) в шкалу
      исходного файла и сохранить границы речи в поле "speech".

  postprocess.py render JSON TXT SRT --global ФАЙЛ --dir ПАПКА [--check]
      Применить списки замен к тексту сегментов и собрать из JSON файлы
      txt и srt (в том же формате, что пишет whisper-cli). Печатает число
      замен. С --check ничего не пишет; код выхода 1, если что-то изменится.
"""

import json
import os
import re
import sys

RULES_NAME = "замены.txt"


# --- VAD --------------------------------------------------------------------

def fix_vad(json_path, log_path):
    """Повторяет whisper_full_get_token_t0/t1 из whisper.cpp 1.9.5: whisper-cli
    пишет в JSON сырые времена токенов, не переводя их в шкалу файла."""
    pat = re.compile(r"vad_segment_info: orig_start: ([\d.]+), orig_end: ([\d.]+), "
                     r"vad_start: ([\d.]+), vad_end: ([\d.]+)")
    segs = []  # (orig_start, orig_end, vad_start, vad_end), сотые доли секунды
    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = pat.search(line)
            if m:
                segs.append(tuple(round(float(x) * 100) for x in m.groups()))

    with open(json_path, encoding="utf-8") as f:
        d = json.load(f)
    if d["transcription"] and not segs:
        sys.exit("в логе whisper нет границ VAD, таймкоды токенов не пересчитать")

    def to_orig(t):
        if t <= segs[0][2]:
            return segs[0][0]
        if t >= segs[-1][3]:
            return segs[-1][1]
        for i, (os_, oe, vs, ve) in enumerate(segs):
            if vs <= t <= ve:
                return os_ + (t - vs) * (oe - os_) // (ve - vs) if ve > vs else os_
            if i + 1 < len(segs) and ve < t < segs[i + 1][2]:
                return oe if t <= (ve + segs[i + 1][2]) // 2 else segs[i + 1][0]
        return t

    for seg in d["transcription"]:
        for tok in seg.get("tokens", []):
            if "offsets" not in tok:
                continue
            t0 = to_orig(tok["offsets"]["from"] // 10)
            t1 = max(to_orig(tok["offsets"]["to"] // 10), t0 + 1)
            tok["offsets"] = {"from": t0 * 10, "to": t1 * 10}
            tok["timestamps"] = {"from": stamp(t0 * 10), "to": stamp(t1 * 10)}

    d["speech"] = [{"offsets": {"from": s[0] * 10, "to": s[1] * 10}} for s in segs]
    write_json(json_path, d)


# --- замены -----------------------------------------------------------------

def rule_files(global_file, clip_dir):
    """Общий список, затем списки из папок от корня диска до папки клипа.
    Чем ближе к клипу, тем главнее: такое же слово дальше переопределяется."""
    found = []
    d = os.path.abspath(clip_dir)
    while True:
        p = os.path.join(d, RULES_NAME)
        if os.path.isfile(p):
            found.append(p)
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    found.reverse()
    if global_file and os.path.isfile(global_file) and global_file not in found:
        found.insert(0, global_file)
    return found


def load_rules(files):
    """Строка файла: «неверно -> верно» или «вариант | вариант -> верно».
    Пустые строки и строки с # игнорируются."""
    rules = {}
    for path in files:
        with open(path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "->" not in line:
                    print("%s:%d: нет «->», строка пропущена" % (path, n), file=sys.stderr)
                    continue
                left, right = line.rsplit("->", 1)
                right = right.strip()
                for variant in left.split("|"):
                    variant = variant.strip()
                    if not variant:
                        continue
                    rules[variant] = right
                    # Слово с маленькой буквы в начале предложения пишется с
                    # большой. Замена со строчной латинской буквы (ant-lab,
                    # git pull, main.c) — название или команда: регистр не трогаем.
                    if variant[0].islower():
                        keep = right[:1].isascii() and right[:1].islower()
                        rules.setdefault(variant[0].upper() + variant[1:],
                                         right if keep else right[:1].upper() + right[1:])
    return rules


# Метки разрезов субтитров: символы из частной области Unicode, по одному на
# разрез. Замена «видит» сквозь них (вариант «git, клон» найдётся и через
# разрез после запятой), а съеденная заменой метка склеивает два куска.
MARK0 = 0xE000
MARK_RX = re.compile("[\uE000-\uF8FF]")


def make_replacer(rules):
    """Одна регулярка на все варианты, длинные первыми: замены не цепляются
    друг за друга, и результат одной замены не попадает под другую."""
    if not rules:
        return lambda s: (s, 0)
    alts = sorted(rules, key=len, reverse=True)
    # re.escape экранирует пробел («\ »); перед пробелом может стоять метка.
    body = "|".join(re.escape(a).replace("\\ ", "[\uE000-\uF8FF]?\\ ") for a in alts)
    rx = re.compile(r"(?<!\w)(?:%s)(?!\w)" % body)

    def replace(s):
        return rx.subn(lambda m: rules[MARK_RX.sub("", m.group(0))], s)
    return replace


# --- нарезка субтитров ------------------------------------------------------

MAX_MS = 7000     # субтитр не длиннее 7 секунд
MAX_CHARS = 90    # и не больше ~двух строк по 42–45 знаков
MIN_CHARS = 20    # при разрезе по запятой или слову обе части не короче этого
WORD_MS = 1500    # токен перед паузой whisper растягивает на всю паузу;
                  # дольше полутора секунд слово не звучит
OVERLAP_MS = 200  # участок речи VAD «принадлежит» куску, если перекрытие не меньше
SENT_END = (".", "?", "!", "…")
CLAUSE_END = (",", ";", ":", "—", "–")


def cut_segment(seg, speech=()):
    """Куски сегмента whisper для srt/txt: [(from_ms, to_ms, сырой текст), ...].
    Короткий сегмент остаётся целым. Длинный режется по токенам: сначала по
    концам предложений (короткие соседние предложения склеиваются обратно),
    потом слишком длинные куски — по запятой ближе к середине, иначе по
    границе слова. Разрез — только перед токеном, начинающимся с пробела.
    speech — участки речи VAD [(from_ms, to_ms)]: края куска подрезаются по
    ним, чтобы пауза, приклеенная whisper к токену, не попала в субтитр."""
    raw = seg.get("text_raw", seg["text"])
    o = seg["offsets"]
    toks = [t for t in seg.get("tokens", [])
            if not (t["text"].startswith("[_") and t["text"].endswith("]"))]
    if (o["to"] - o["from"] <= MAX_MS and len(raw.strip()) <= MAX_CHARS) or \
            len(toks) < 2 or "".join(t["text"] for t in toks) != raw or \
            any("offsets" not in t for t in toks):
        return [(o["from"], o["to"], raw)]

    def t0(i): return toks[i]["offsets"]["from"]
    def t1(i): return min(toks[i]["offsets"]["to"], t0(i) + WORD_MS)
    def text(i, j): return "".join(t["text"] for t in toks[i:j])

    def span(i, j):
        """Время куска: по его токенам (в пределах сегмента), затем подрезка
        по участкам речи, которые кусок действительно перекрывает."""
        a, b = max(t0(i), o["from"]), min(t1(j - 1), o["to"])
        own = [(x, y) for x, y in speech if min(b, y) - max(a, x) >= OVERLAP_MS]
        if own:
            a, b = max(a, own[0][0]), min(b, own[-1][1])
        return a, b

    def long(i, j):
        a, b = span(i, j)
        return b - a > MAX_MS or len(text(i, j).strip()) > MAX_CHARS
    def cuts(i, j, ends):  # k: разрез перед токеном k
        return [k for k in range(i + 1, j) if toks[k]["text"].startswith(" ")
                and (ends is None or toks[k - 1]["text"].rstrip().endswith(ends))]

    def roomy(i, j, ks):  # без огрызков вроде «Мы видим,» на полсекунды
        return [k for k in ks if min(len(text(i, k).strip()), len(text(k, j).strip())) >= MIN_CHARS]

    def halve(i, j):
        if not long(i, j):
            return [(i, j)]
        c, w = cuts(i, j, CLAUSE_END), cuts(i, j, None)
        ks = roomy(i, j, c) or roomy(i, j, w) or c or w
        if not ks:
            return [(i, j)]
        mid = (t0(i) + t1(j - 1)) / 2
        k = min(ks, key=lambda k: abs(t0(k) - mid))
        return halve(i, k) + halve(k, j)

    bounds = [0] + cuts(0, len(toks), SENT_END) + [len(toks)]
    packed = []
    for i, j in zip(bounds, bounds[1:]):
        if packed and not long(packed[-1][0], j):
            packed[-1] = (packed[-1][0], j)
        else:
            packed.append((i, j))
    pieces = [r for i, j in packed for r in halve(i, j)]

    out = []
    for i, j in pieces:
        a, b = span(i, j)
        a = max(a, out[-1][1] if out else 0)
        out.append((a, max(b, a + 10), text(i, j)))
    return out


# --- вывод ------------------------------------------------------------------

def stamp(ms):
    return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


def write_json(path, d):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent="\t")


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def render(json_path, txt_path, srt_path, global_file, clip_dir, check):
    replace = make_replacer(load_rules(rule_files(global_file, clip_dir)))

    old_json = read(json_path)
    d = json.loads(old_json)
    total = 0
    txt, srt = [], []
    speech = [(r["offsets"]["from"], r["offsets"]["to"]) for r in d.get("speech", [])]
    for seg in d["transcription"]:
        # JSON: текст сегмента целиком, с заменами; исходный — в text_raw.
        raw = seg.get("text_raw", seg["text"])
        text, _ = replace(raw)
        seg["text"] = text
        if text != raw:
            seg["text_raw"] = raw
        else:
            seg.pop("text_raw", None)

        # srt/txt: куски сегмента. Замены — по всему сегменту сразу, с метками
        # на местах разрезов; метку, попавшую внутрь замены, замена съедает.
        pieces = cut_segment(seg, speech)
        marked = "".join(p[2] + (chr(MARK0 + k) if k < len(pieces) - 1 else "")
                         for k, p in enumerate(pieces))
        fixed, n = replace(marked)
        total += n
        parts, start, k_prev = [], 0, 0
        for m in MARK_RX.finditer(fixed):
            k = ord(m.group(0)) - MARK0
            parts.append((pieces[k_prev][0], pieces[k][1], fixed[start:m.start()]))
            start, k_prev = m.end(), k + 1
        parts.append((pieces[k_prev][0], pieces[-1][1], fixed[start:]))
        for a, b, t in parts:
            # Формат как у whisper-cli: txt без ведущих пробелов, srt как есть.
            txt.append(t.lstrip(" \t") + "\n")
            srt.append("%d\n%s --> %s\n%s\n\n" % (len(srt) + 1, stamp(a), stamp(b), t))

    new = {
        json_path: json.dumps(d, ensure_ascii=False, indent="\t"),
        txt_path: "".join(txt),
        srt_path: "".join(srt),
    }
    changed = [p for p, s in new.items() if read(p) != s]
    # JSON сравниваем по содержимому: старый мог быть записан whisper-cli.
    if json_path in changed and json.loads(old_json) == d:
        changed.remove(json_path)

    print(total)
    if check:
        return 1 if changed else 0
    for p in changed:
        with open(p, "w", encoding="utf-8") as f:
            f.write(new[p])
    return 0


def main(argv):
    if len(argv) >= 3 and argv[0] == "vad":
        fix_vad(argv[1], argv[2])
        return 0
    if len(argv) >= 4 and argv[0] == "render":
        args = argv[4:]
        opt = {"--global": None, "--dir": None}
        check = False
        i = 0
        while i < len(args):
            if args[i] == "--check":
                check = True
                i += 1
            elif args[i] in opt and i + 1 < len(args):
                opt[args[i]] = args[i + 1]
                i += 2
            else:
                sys.exit("неизвестный аргумент: " + args[i])
        clip_dir = opt["--dir"] or os.path.dirname(os.path.dirname(os.path.abspath(argv[1])))
        return render(argv[1], argv[2], argv[3], opt["--global"], clip_dir, check)
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
