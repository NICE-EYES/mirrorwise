"""Tiny message catalog (English / Russian). No dependencies."""

import os

_LANG = None

MESSAGES = {
    "en": {
        "eco_header": "{eco} - {title}",
        "col_id": "ID",
        "col_trust": "TRUST",
        "col_status": "STATUS",
        "col_latency": "LATENCY",
        "col_speed": "SPEED",
        "col_detail": "DETAIL",
        "col_region": "REGION",
        "col_name": "NAME",
        "col_confirmed": "CONFIRMED",
        "status_ok": "ok",
        "status_fail": "FAIL",
        "current": "current",
        "current_label": "currently configured",
        "verdict_ok": "OK: {what} works",
        "verdict_degraded": "DEGRADED: {what} is slow ({ms} ms); mirror {mirror} is faster",
        "verdict_down_fix": "DOWN: {what} is unreachable ({detail}). Healthy mirror: {mirror}. Run: mirrorwise apply {eco}",
        "verdict_down_nofix": "DOWN: {what} is unreachable ({detail}) and no allowed mirror answered",
        "verdict_down_community": "DOWN: {what} is unreachable. Only community mirrors answered ({mirror}). Add --allow-community if you trust them",
        "what_upstream": "the official registry",
        "what_current": "the configured source",
        "plan_title": "Plan for {eco}:",
        "plan_choice": "  chosen: {id} ({url}) - {reason}",
        "plan_file": "  config: {path}",
        "plan_nochange": "  nothing to change: {reason}",
        "reason_upstream_ok": "official registry is healthy",
        "reason_best_mirror": "official registry is down, fastest healthy allowed mirror",
        "reason_fastest": "fastest healthy source",
        "reason_degraded": "official registry is slow, mirror is clearly faster",
        "reason_explicit": "chosen explicitly",
        "reason_current_ok": "the configured source works",
        "reason_current_broken": "the configured source is broken, the official registry works",
        "warn_env_override": "warning: {source} is set and overrides the config file; unset it for the change to take effect",
        "reason_failback": "official registry is healthy again, restoring previous settings",
        "no_healthy": "  no healthy source for {eco}; nothing was changed",
        "confirm": "Apply these changes? [y/N] ",
        "aborted": "Aborted, nothing was changed.",
        "applied": "  done: {path} (backup saved)",
        "applied_go": "  done: ran `go env -w GOPROXY=...` (backup of {path} saved)",
        "dry_run": "  dry-run: nothing was written",
        "revert_hint": "  undo with: mirrorwise revert {eco}",
        "restart_docker": "  restart the Docker daemon to apply registry-mirrors",
        "reverted": "{eco}: restored {path}",
        "revert_nothing": "{eco}: nothing to revert",
        "revert_deleted": "{eco}: removed {path} (it did not exist before)",
        "status_header": "Current configuration",
        "status_unset": "default (not configured)",
        "status_managed": "managed by mirrorwise",
        "err_conflict": "{eco}: cannot edit automatically: {detail}",
        "err_permission": "{eco}: no permission to write {path}. Try sudo or --config-path",
        "err_go_missing": "go: the `go` command was not found in PATH",
        "err_unknown_mirror": "unknown mirror id '{id}' for {eco}. See: mirrorwise list {eco}",
        "err_insecure": "refusing non-HTTPS URL {url} (use --allow-insecure only for local tests)",
        "err_unhealthy_explicit": "{id} did not pass the probe ({detail}); use --force to apply anyway",
        "err_no_eco": "choose an ecosystem ({known}) or use --all",
        "err_unknown_eco": "unknown ecosystem '{eco}'. Known: {known}",
        "err_env_unsupported": "{eco}: environment variables are not supported for this ecosystem",
        "lint_ok": "mirrors data OK: {n} mirrors in {e} ecosystems",
        "lint_fail": "mirrors data has {n} problem(s):",
        "no_color": "",
        "tip_tls": "TLS handshake dropped: typical sign of filtering on the path to the host",
        "proxy_note": "note: a proxy from the environment is used; stage detection is approximate",
        "probing": "Probing {n} endpoint(s) from this machine...",
    },
    "ru": {
        "eco_header": "{eco} - {title}",
        "col_id": "ID",
        "col_trust": "ДОВЕРИЕ",
        "col_status": "СТАТУС",
        "col_latency": "ЗАДЕРЖКА",
        "col_speed": "СКОРОСТЬ",
        "col_detail": "ДЕТАЛИ",
        "col_region": "РЕГИОН",
        "col_name": "НАЗВАНИЕ",
        "col_confirmed": "ПОДТВЕРЖДЕНО",
        "status_ok": "ok",
        "status_fail": "СБОЙ",
        "current": "текущий",
        "current_label": "сейчас настроено",
        "verdict_ok": "ОК: {what} работает",
        "verdict_degraded": "МЕДЛЕННО: {what} отвечает долго ({ms} мс); зеркало {mirror} быстрее",
        "verdict_down_fix": "НЕДОСТУПНО: {what} ({detail}). Рабочее зеркало: {mirror}. Выполните: mirrorwise apply {eco}",
        "verdict_down_nofix": "НЕДОСТУПНО: {what} ({detail}), и ни одно разрешённое зеркало не ответило",
        "verdict_down_community": "НЕДОСТУПНО: {what}. Ответили только зеркала сообщества ({mirror}). Добавьте --allow-community, если доверяете им",
        "what_upstream": "официальный реестр",
        "what_current": "текущий источник",
        "plan_title": "План для {eco}:",
        "plan_choice": "  выбрано: {id} ({url}) - {reason}",
        "plan_file": "  конфиг: {path}",
        "plan_nochange": "  менять нечего: {reason}",
        "reason_upstream_ok": "официальный реестр работает",
        "reason_best_mirror": "официальный реестр недоступен, взято самое быстрое рабочее зеркало",
        "reason_fastest": "самый быстрый рабочий источник",
        "reason_degraded": "официальный реестр медленный, зеркало заметно быстрее",
        "reason_explicit": "выбрано явно",
        "reason_current_ok": "текущий источник работает",
        "reason_current_broken": "текущий источник не отвечает, официальный реестр работает",
        "warn_env_override": "предупреждение: задана {source}, она перекрывает конфиг-файл; снимите её, чтобы изменение сработало",
        "reason_failback": "официальный реестр снова работает, возвращаю прежние настройки",
        "no_healthy": "  для {eco} нет рабочего источника; ничего не изменено",
        "confirm": "Применить изменения? [y/N] ",
        "aborted": "Отменено, ничего не изменено.",
        "applied": "  готово: {path} (резервная копия сохранена)",
        "applied_go": "  готово: выполнено `go env -w GOPROXY=...` (копия {path} сохранена)",
        "dry_run": "  dry-run: ничего не записано",
        "revert_hint": "  откат: mirrorwise revert {eco}",
        "restart_docker": "  перезапустите демон Docker, чтобы применить registry-mirrors",
        "reverted": "{eco}: восстановлен {path}",
        "revert_nothing": "{eco}: откатывать нечего",
        "revert_deleted": "{eco}: удалён {path} (раньше его не было)",
        "status_header": "Текущая конфигурация",
        "status_unset": "по умолчанию (не настроено)",
        "status_managed": "под управлением mirrorwise",
        "err_conflict": "{eco}: автоматическая правка невозможна: {detail}",
        "err_permission": "{eco}: нет прав на запись в {path}. Попробуйте sudo или --config-path",
        "err_go_missing": "go: команда `go` не найдена в PATH",
        "err_unknown_mirror": "неизвестный id зеркала '{id}' для {eco}. Смотрите: mirrorwise list {eco}",
        "err_insecure": "отказываюсь от URL без HTTPS: {url} (--allow-insecure только для локальных тестов)",
        "err_unhealthy_explicit": "{id} не прошёл проверку ({detail}); добавьте --force, чтобы применить всё равно",
        "err_no_eco": "укажите экосистему ({known}) или --all",
        "err_unknown_eco": "неизвестная экосистема '{eco}'. Доступны: {known}",
        "err_env_unsupported": "{eco}: для этой экосистемы переменные окружения не поддерживаются",
        "lint_ok": "данные зеркал в порядке: {n} зеркал в {e} экосистемах",
        "lint_fail": "в данных зеркал проблем: {n}",
        "no_color": "",
        "tip_tls": "TLS-рукопожатие оборвано: типичный признак фильтрации на пути к хосту",
        "proxy_note": "примечание: используется прокси из окружения, определение стадии приблизительное",
        "probing": "Проверяю {n} адрес(ов) с этой машины...",
    },
}


def detect_lang():
    explicit = os.environ.get("MIRRORWISE_LANG", "").strip().lower()
    if explicit in MESSAGES:
        return explicit
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        val = os.environ.get(var, "").lower()
        if val.startswith("ru"):
            return "ru"
        if val:
            break
    return "en"


def set_lang(lang):
    global _LANG
    _LANG = lang if lang in MESSAGES else "en"


def get_lang():
    return _LANG or detect_lang()


def t(key, **kwargs):
    table = MESSAGES.get(get_lang(), MESSAGES["en"])
    text = table.get(key)
    if text is None:
        text = MESSAGES["en"].get(key, key)
    return text.format(**kwargs) if kwargs else text
