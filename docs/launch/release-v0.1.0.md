# mirrorwise 0.1.0 (pre-release)

Probe your package registries from your own network, pick a working mirror, switch to it safely, and switch back when the official registry recovers. Python 3.9+, no dependencies.

**What it does**

- `mirrorwise doctor`: checks the official registry and the mirrors for pip, npm, Go, Cargo and Docker from *your* machine, and tells you at which stage a request fails (DNS, connect, TLS, HTTP, wrong content, timeout, proxy). Exit code `0` / `1` / `2`, so it works in CI.
- `mirrorwise apply <eco>`: switches to the best healthy source. Backup first, `--dry-run` to preview, atomic writes. When the official registry is healthy again, running `apply` puts your original config back.
- `mirrorwise revert <eco>`: restores the exact original bytes of the config.
- `mirrorwise env`: variables for CI (`sh`, `powershell`, `github`, `json`) without touching files.
- Trust levels: community-run mirrors are off unless you pass `--allow-community`. https only.
- English and Russian messages.

**Install**: download `mirrorwise.pyz` below and run `python3 mirrorwise.pyz doctor` (useful when `pip install` is the broken part), or `pipx install git+https://github.com/NICE-EYES/mirrorwise`. Verify the download against `mirrorwise.pyz.sha256`.

**Please read before relying on it**

- This is an alpha. The bundled mirror list (16 mirrors) comes from public articles and vendor documentation, and every entry is marked `confirmed: false`: the author could not test them from an affected network. The probe on your machine decides, not the list. Help confirm entries with the *Mirror request* issue template.
- A mirror is a third party. Keep hash-pinned lockfiles.
- Tested on Linux with Python 3.11-3.13 (107 offline tests); Windows and macOS are covered by CI but have had little real use. Bug reports welcome.
- It does not touch git or GitHub access, and it is not a VPN or proxy.

Full list of changes: [CHANGELOG.md](https://github.com/NICE-EYES/mirrorwise/blob/main/CHANGELOG.md).

---

# mirrorwise 0.1.0 (пре-релиз)

Проверяет реестры пакетов из вашей сети, выбирает рабочее зеркало, безопасно переключает на него и возвращает всё назад, когда официальный реестр снова работает. Python 3.9+, без зависимостей.

**Что умеет**

- `mirrorwise doctor`: проверяет официальный реестр и зеркала для pip, npm, Go, Cargo и Docker с вашей машины и показывает, на каком этапе ломается запрос (DNS, соединение, TLS, HTTP, неверное содержимое, таймаут, прокси). Коды выхода `0` / `1` / `2` — подходит для CI.
- `mirrorwise apply <eco>`: переключается на лучший рабочий источник. Сначала резервная копия, `--dry-run` для просмотра, атомарная запись. Когда официальный реестр снова здоров, `apply` возвращает исходный конфиг.
- `mirrorwise revert <eco>`: возвращает конфиг байт в байт.
- `mirrorwise env`: переменные для CI (`sh`, `powershell`, `github`, `json`), не трогая файлы.
- Уровни доверия: зеркала от частных лиц выключены без `--allow-community`. Только https.
- Сообщения на русском и английском.

**Установка**: скачайте `mirrorwise.pyz` ниже и запустите `python3 mirrorwise.pyz doctor` (удобно, когда сломан сам `pip install`) или `pipx install git+https://github.com/NICE-EYES/mirrorwise`. Сверьте файл с `mirrorwise.pyz.sha256`.

**Прочитайте перед использованием**

- Это альфа. Встроенный список зеркал (16 штук) собран из публичных статей и документации вендоров, все записи помечены `confirmed: false`: автор не мог проверить их из затронутой сети. Решает проба на вашей машине, а не список. Помогите подтвердить записи через шаблон issue *Mirror request*.
- Зеркало — третья сторона. Держите lock-файлы с хешами.
- Проверено на Linux с Python 3.11–3.13 (107 тестов без сети); Windows и macOS покрыты CI, но в реальной работе почти не проверялись. Сообщения об ошибках приветствуются.
- Инструмент не касается доступа к git и GitHub и не является VPN или прокси.
