# Announcement drafts

Rules for all posts: say what it is in the first sentence, say what does **not** work, do not invent numbers, do not ask for upvotes or stars, link the README rather than the research file, and answer comments. Check each platform's current self-promotion rules right before posting; the author did not verify them and they change.

Placeholders: `YOUR_LOGIN` for the repository owner.

The drafts are written in the first person as if by you. Edit anything that is not true for you (for example, what you tested and where) before posting; every factual claim about incidents is sourced in [docs/research.md](../research.md).

---

## Hacker News (Show HN)

**Title** (limit 80 characters):

```
Show HN: Mirrorwise - probe package registries, switch mirrors, switch back
```

**URL:** https://github.com/YOUR_LOGIN/mirrorwise

**First comment** (post it right after submitting):

```
Hi HN. I wrote this after reading how many people hit "pip install fails
on TLS but the website opens fine" (as reported) during the June 2026 PyPI
incident in Russia, then hand-edit mirror URLs from blog posts into four config
formats and forget to undo them.

mirrorwise is a small stdlib-only Python CLI. `doctor` probes the official
registry and some mirrors from your own network and says at which stage
each fails (DNS/connect/TLS/HTTP/wrong content); `apply` switches pip, npm,
Go, Cargo or Docker config with a backup; running it again restores your
original config when upstream is healthy. There is also `env` for CI and a
single-file `.pyz` build for when pip itself is the broken part.

What it does not do: it is not a VPN, it does not cover git/GitHub access,
and the bundled mirror list is unverified (every entry is confirmed:false, I
could not test from an affected network). A mirror is also a third party,
so keep hash-pinned lockfiles. Tested on Linux with Python 3.11-3.13;
Windows/macOS are only covered by CI so far.

The part I most want feedback on: the policy (keep upstream while healthy,
no flapping between mirrors, drop our mirror once upstream is back) and
the safety model for editing config files. Prior art I know of: chsrc
(much broader, C) and nrm (npm only).
```

---

## Reddit (r/Python, and r/devops or r/selfhosted if their rules allow project posts)

**Title:**

```
I built a zero-dependency CLI that probes PyPI/npm/Go/Cargo/Docker from your network, switches to a working mirror, and switches back
```

**Body:**

```
After the PyPI connection drops reported from Russian networks in June 2026
(TLS handshake cut; some people reported the website still opened in a browser), I noticed the
usual fix is a mirror URL copied from a blog post, edited by hand into
pip.conf/.npmrc/daemon.json/cargo config, and then never removed.

mirrorwise tries to make that boring:

- `mirrorwise doctor` probes upstream + candidate mirrors from YOUR machine
  and reports the failing stage (dns / connect / tls / http / content /
  timeout / proxy). A captive portal answering 200 with HTML counts as a
  failure.
- `mirrorwise apply pip --dry-run` shows the diff; `apply` makes a backup and
  writes atomically; running `apply` after upstream recovers restores your
  original config. `revert` restores exact bytes.
- `mirrorwise env --format github` for CI.
- stdlib only, Python 3.9+, and a single `mirrorwise.pyz` so you can use it
  when `pip install` is the thing that is broken.

Limits, honestly: alpha; the bundled mirror list comes from public articles
and is all `confirmed: false` (I couldn't test from an affected network); a
mirror is a third party, so use hash-pinned lockfiles; Linux tested, Windows
and macOS only via CI so far; it does not touch git/GitHub.

Repo: https://github.com/YOUR_LOGIN/mirrorwise
I'd love corrections to the mirror data (there is an issue template that
asks for your `mirrorwise probe` output) and ideas for the next backends
(uv.toml, Maven, Composer... see good first issues).
```

---

## Habr (draft in Russian)

**Заголовок:**

```
Когда pip install падает на TLS: утилита, которая проверяет зеркала из вашей сети и аккуратно возвращает всё назад
```

**Хабы (проверьте актуальные):** Python, Open source, DevOps, Разработка.

**Текст:**

```
1–2 июня 2026 многие разработчики из России сообщали, что `pip install`
обрывается при установке защищённого соединения (по отдельным сообщениям,
сайт pypi.org при этом открывался в браузере). Источники расходятся и в датах, и в причинах (РКН блокировку
отрицает, часть данных мониторинга показывала доступность), поэтому
я не буду гадать о причине. Меня зацепило другое: типичное решение —
вставить в pip.conf адрес зеркала из статьи, а потом про него забыть.
В Docker в 2024-м было то же самое: блокировку сняли, а зеркала остались
в daemon.json (владельцы публичного зеркала сами просят их убрать).

Я написал mirrorwise — маленькую утилиту без зависимостей (Python 3.9+),
которая делает четыре вещи:

1. Проверяет официальный реестр и кандидатов-зеркала С ВАШЕЙ машины
   и говорит, на каком этапе сбой: DNS, соединение, TLS, HTTP, неверное
   содержимое (captive-портал с кодом 200), таймаут, прокси.
2. Выбирает источник по понятной политике: пока официальный реестр здоров,
   ничего не трогаем; если он недоступен — самое быстрое здоровое зеркало
   из разрешённых; зеркала частных лиц выключены по умолчанию.
3. Меняет конфиг pip, npm, Go, Cargo или Docker с резервной копией,
   атомарной записью и предварительным `--dry-run`.
4. Возвращает всё назад: повторный `apply`, когда официальный реестр снова
   работает, восстанавливает исходный конфиг байт в байт.

Для CI есть `mirrorwise env --format github`. Если сломан сам pip, можно
скачать единственный файл `mirrorwise.pyz` и запустить его без установки.

Чего нет: это не VPN и не обход блокировок — помогает только когда
легитимное зеркало доступно из вашей сети. GitHub и git не затрагиваются.
Встроенный список зеркал собран из публичных статей и документации, все
записи помечены `confirmed: false`, потому что я не мог проверить их
из затронутой сети; решает проба у вас на машине. Зеркало — третья сторона,
поэтому держите lock-файлы с хешами. Проверялось на Linux (Python 3.11–3.13),
Windows и macOS пока покрыты только CI.

Похожие инструменты: chsrc (шире по числу целей, на C, GPL-3.0) и nrm
(только npm). Моя ставка — диагностика этапа сбоя, политика
«официальный реестр в приоритете» и откат.

Исследование (источники, оценки, что я не смог проверить) лежит
в docs/research.md. Репозиторий: https://github.com/YOUR_LOGIN/mirrorwise.
Буду рад поправкам к данным о зеркалах и идеям для следующих бэкендов.
```

---

## Telegram (short, Russian)

```
mirrorwise 0.1.0 — маленькая утилита без зависимостей для тех, у кого pip/npm/Go/Cargo/Docker иногда не достаёт до официального реестра.

doctor из вашей сети показывает, на каком этапе сбой (TLS, DNS, HTTP...), apply переключает конфиг на рабочее зеркало с бэкапом, а когда реестр оживает — возвращает всё назад. Есть режим для CI и один файл .pyz на случай, когда сломан сам pip.

Альфа: список зеркал не подтверждён (confirmed: false), Windows/macOS почти не проверены, к GitHub отношения не имеет. Нужны поправки по зеркалам и идеи.

https://github.com/YOUR_LOGIN/mirrorwise
```

---

## Notes on timing

- Post when you can answer for the next several hours.
- Do not post all four on the same day: fix what the first thread finds, then continue.
- If someone points out a wrong claim, correct the post and the README, and say so in the thread.
