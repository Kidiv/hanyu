# -*- coding: utf-8 -*-
"""Собирает веб-тренажёр из файлов папки с материалами.

Запуск:
    python build_web.py [--src ПАПКА] [--rotation 0,1,2,3,4]

Кладёт рядом с материалами два файла:
    Ханьюй-тренажёр.html  автономный (charset + viewport + каркас), для пересылки
    hanyu_artifact.html   без каркаса, для публикации артефактом (Artifact сам добавит head)

Данные берутся из файлов папки:
    Урок_NN_слова.txt        иероглифы TAB пиньинь TAB перевод TAB разбор частей
    Урок_NN_предложения.txt  слова через пробел TAB перевод
    Тексты_уроки_*.md        конспекты диалогов (## Урок N. ...)
"""
import os, re, io, glob, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "hanyu_template.html")
CJK = re.compile("[\u4e00-\u9fff]")
CYR = re.compile("[А-Яа-яЁё]")


def lesson_num(path):
    m = re.search(r"Урок_(\d+)_", os.path.basename(path))
    return int(m.group(1)) if m else None


def load_words(src):
    words = []
    for path in sorted(glob.glob(os.path.join(src, "Урок_*_слова.txt"))):
        n = lesson_num(path)
        if n is None:
            continue
        for line in io.open(path, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            p = (line.split("\t") + ["", "", ""])[:4]
            words.append({"h": p[0], "p": p[1], "r": p[2], "c": p[3], "l": n})
    return words


def load_sents(src):
    sents = []
    for path in sorted(glob.glob(os.path.join(src, "Урок_*_предложения.txt"))):
        n = lesson_num(path)
        if n is None:
            continue
        for line in io.open(path, encoding="utf-8"):
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2 and parts[0].strip():
                toks = [t for t in parts[0].split() if t]
                if len(toks) >= 2:
                    sents.append({"t": toks, "r": parts[1], "l": n})
    return sents


def load_texts(src):
    texts = []
    for path in sorted(glob.glob(os.path.join(src, "Тексты_уроки_*.md"))):
        cur = None
        for line in io.open(path, encoding="utf-8"):
            line = line.rstrip("\n")
            m = re.match(r"##\s+Урок\s+(\d+)", line)
            if m:
                cur = {"l": int(m.group(1)), "title": line.lstrip("# "), "rows": []}
                texts.append(cur)
                continue
            if cur is None or line.startswith("# "):
                continue
            if line.startswith("**"):
                cur["rows"].append({"t": "b", "x": line.strip("*")})
            elif CJK.search(line):
                cur["rows"].append({"t": "zh", "x": line})
            elif line.strip():
                mm = CYR.search(line)
                if mm and mm.start() > 3:      # строка «пиньинь + перевод»
                    cur["rows"].append({"t": "pr", "p": line[:mm.start()].strip(),
                                        "r": line[mm.start():].strip()})
                else:
                    cur["rows"].append({"t": "r", "x": line})
            else:
                cur["rows"].append({"t": "sp", "x": ""})
    return texts


def build(src, rotation=None, version="v4"):
    words, sents, texts = load_words(src), load_sents(src), load_texts(src)
    lessons = sorted({w["l"] for w in words})
    if rotation is None:
        rotation = lessons
    data = {"words": words, "sents": sents, "texts": texts,
            "lessons": lessons, "rotation": rotation}
    tpl = io.open(TEMPLATE, encoding="utf-8").read()
    html = tpl.replace("__DATA__", json.dumps(data, ensure_ascii=False))

    artifact = os.path.join(src, "hanyu_artifact.html")
    io.open(artifact, "w", encoding="utf-8").write(html)

    head, rest = html.split("</title>", 1)
    rest = rest.replace("Ханьюй-тренажёр</h1>",
                        'Ханьюй-тренажёр <span id="vtag" style="font-size:11px;color:#98a1aa">'
                        + version + "</span></h1>", 1)
    guard = (
        '<noscript><div style="padding:14px;background:#b23a26;color:#fff;font-family:sans-serif">'
        'Этот просмотрщик отключил JavaScript, приложение не сможет работать. '
        'Откройте файл в браузере.</div></noscript>'
        '<script>window.onerror=function(m,s,l,c){var d=document.createElement("div");'
        'd.style.cssText="padding:10px;background:#b23a26;color:#fff;font:13px sans-serif;white-space:pre-wrap";'
        'd.textContent="Ошибка: "+m+" ("+l+":"+c+")";document.body.insertBefore(d,document.body.firstChild);};'
        'document.addEventListener("DOMContentLoaded",function(){var v=document.getElementById("vtag");'
        'if(v)v.textContent="' + version + '·js";});</script>')
    standalone = ('<!doctype html><html lang="ru"><head><meta charset="utf-8">'
                  '<meta name="viewport" content="width=device-width, initial-scale=1">'
                  + head + "</title></head><body>" + guard + rest + "</body></html>")
    offline = os.path.join(src, "Ханьюй-тренажёр.html")
    io.open(offline, "w", encoding="utf-8").write(standalone)
    io.open(os.path.join(src, "index.html"), "w", encoding="utf-8").write(standalone)
    return {"words": len(words), "sents": len(sents), "texts": len(texts),
            "lessons": lessons, "rotation": rotation,
            "offline": offline, "artifact": artifact}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=r"C:\Users\Mechrevo\Documents\Китайский_экзамен")
    ap.add_argument("--rotation", default=None,
                    help="уроки в ротации карточек, через запятую; по умолчанию все")
    ap.add_argument("--version", default="v4")
    a = ap.parse_args()
    rot = [int(x) for x in a.rotation.split(",")] if a.rotation else None
    info = build(a.src, rot, a.version)
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("слов {words}, фраз {sents}, блоков текста {texts}".format(**info))
    print("уроки:", info["lessons"], "ротация:", info["rotation"])
    print("автономный:", info["offline"])
    print("для артефакта:", info["artifact"])
