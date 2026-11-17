# Contributing to mirrorwise

Thanks for helping. This project is small on purpose: standard library only, no runtime dependencies, and every change that touches a user's config file has to be reversible.

[Русская версия ниже](#вклад-в-проект)

## Ground rules

1. **No runtime dependencies.** The tool must work as a single `.pyz` on a machine where `pip` is broken.
2. **Never weaken the safety model**: https only, backup before write, atomic writes, revert restores exact bytes. See "Safety model" in the README.
3. **Tests for everything that changes behavior.** Tests must run offline; use the fixture servers in `tests/helpers.py` instead of real registries.
4. **No third-party code or text copied in.** If you are inspired by another tool, say so in the PR and write the code yourself. Check the license of anything you reference.
5. **No personal data.** Do not paste usernames, IP addresses of other people, or private URLs from forums, chats or logs into issues, data files or docs. Public URLs of official pages and vendor documentation are fine.
6. Python 3.9 compatible syntax (no `match`, no `X | Y` type unions at runtime).

## Setup

```bash
git clone https://github.com/NICE-EYES/mirrorwise && cd mirrorwise
PYTHONPATH=src python3 -m pytest tests -q        # pytest, or:
PYTHONPATH=src python3 -m unittest discover -s tests -t .
PYTHONPATH=src python3 -m mirrorwise --help
```

Useful scripts:

```bash
python3 scripts/build_zipapp.py                  # dist/mirrorwise.pyz
python3 scripts/demo.py en > docs/demo.txt       # regenerate the demo transcript
PYTHONPATH=src python3 -m mirrorwise lint-data   # validate bundled mirror data
```

## Project layout

```
src/mirrorwise/
  cli.py          commands, planning (_plan_for), output
  probe.py        probes and failure-stage diagnosis
  selection.py    which source to pick (pure function, easy to test)
  registry.py     mirror catalog, validation, overlay files
  fsutil.py       atomic writes, backups, manifest, revert
  i18n.py         EN/RU messages
  backends/       one file per ecosystem: read current, render new config
  data/mirrors.json
tests/            offline tests with local fixture servers
scripts/          zipapp builder, demo generator
docs/             research report, good first issues, launch material
```

## Adding a mirror to the bundled catalog

Use the **Mirror request** issue first, or open a PR that:

1. Adds the entry to `src/mirrorwise/data/mirrors.json` with an `evidence` URL (official documentation of the operator is best; a blog post is acceptable but weaker).
2. Sets `trust` honestly: `vendor` is for companies, universities and cloud providers; individuals or unknown operators are `community`.
3. Leaves `"confirmed": false` unless you ran `mirrorwise probe` **from a network that can reach it** and pasted the output in the PR. Do not set `confirmed: true` from guesses.
4. Passes `mirrorwise lint-data`.

Please do not add mirrors whose operator asks users not to use them, or services that require accounts or payment.

## Adding an ecosystem backend

1. Add `src/mirrorwise/backends/<name>.py` with a subclass of `Backend` (see `npm.py` for the smallest one): `default_path`, `read_current`, `render`.
2. Register it in `backends/__init__.py` and add an ecosystem section (probe path, expected content, upstream) to the data file.
3. Add tests to `tests/test_backends.py`: render, idempotency (applying twice changes nothing), revert returns the original bytes, a foreign config is never silently overwritten.
4. Add messages to both languages in `i18n.py` if you need new ones.

## Pull requests

- Keep them focused. One backend or one fix per PR.
- Describe what you ran. For anything that touches real config files, show the `--dry-run` output.
- Run the whole test suite before pushing.
- Be kind in review. Maintainers are volunteers.

By contributing you agree that your contribution is licensed under the MIT License.

---

# Вклад в проект

Спасибо за помощь. Проект маленький намеренно: только стандартная библиотека, без зависимостей, а любое изменение пользовательского конфига должно быть обратимым.

## Правила

1. **Никаких зависимостей времени выполнения.** Инструмент должен работать одним `.pyz` на машине, где сломан `pip`.
2. **Не ослаблять модель безопасности**: только https, копия перед записью, атомарная запись, `revert` возвращает исходные байты.
3. **Тесты на любое изменение поведения.** Тесты работают офлайн; используйте фикстурные серверы из `tests/helpers.py`, а не настоящие реестры.
4. **Не копировать чужой код и тексты.** Если вас вдохновил другой инструмент, укажите это в PR и напишите код сами. Проверяйте лицензию всего, на что ссылаетесь.
5. **Никаких персональных данных.** Не вставляйте в issue, файлы данных и документы ники, чужие IP-адреса и приватные ссылки из форумов, чатов и логов. Публичные страницы официальных ресурсов и документации вендоров — можно.
6. Синтаксис, совместимый с Python 3.9.

## Как добавить зеркало в каталог

1. Откройте issue **Mirror request** или сделайте PR с записью в `src/mirrorwise/data/mirrors.json` и ссылкой-доказательством (лучше всего — официальная документация оператора).
2. Честно укажите `trust`: `vendor` — компании, университеты, облака; частные и неизвестные операторы — `community`.
3. Оставьте `"confirmed": false`, если не запускали `mirrorwise probe` **из сети, где зеркало доступно**, и не приложили вывод к PR.
4. Убедитесь, что `mirrorwise lint-data` проходит.

## Как добавить бэкенд экосистемы

См. раздел выше (Adding an ecosystem backend): подкласс `Backend`, регистрация, данные, тесты (идемпотентность, откат, чужой конфиг не перезаписывается), сообщения на двух языках.

Вклад распространяется на условиях лицензии MIT.
