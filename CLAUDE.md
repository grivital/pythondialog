# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Что это за проект

pythondialog — Python-обёртка над UNIX-утилитой `dialog` (ncurses TUI).
Основной код — один модуль `dialog.py` (~3800 строк) без сторонних зависимостей.
Это поддерживаемый форк: https://github.com/grivital/pythondialog (версия 3.6.0,
Python >= 3.10). Упаковка — PEP 517/621 (`pyproject.toml`, setuptools).

## Команды

```bash
# Тесты (не нужен TTY; используется tests/fake_dialog.py)
python3 -m unittest discover -s tests -v
make test

# Линт/проверка синтаксиса
make check
ruff check --select F,E9 dialog.py tests
python3 -m py_compile dialog.py

# Сборка sdist (без python-build)
make sdist
# или: python3 -c "import setuptools.build_meta as b; print(b.build_sdist('dist'))"

# Документация (нужен Sphinx; вывод в doc/_build/html)
make docs
cd doc && make html

# Установка
pip install .
pip install -e .

# Ручная проверка виджетов (нужен TTY и бинарник dialog)
PYTHONPATH=. python3 examples/simple_example.py
PYTHONPATH=. python3 examples/demo.py
PYTHONPATH=. python3 examples/demo.py -t      # testsuite-режим
PYTHONPATH=. python3 examples/demo.py --debug --debug-file=/tmp/debug.log
```

Тестового фреймворка нет специально: стандартный `unittest`, имитатор
`tests/fake_dialog.py` понимает `--file`, `--print-version`, основные виджеты,
`--help`, `--gauge` и позволяет проверять fork/exec, pipe и парсинг без TTY.

### Gentoo

Самодостаточный overlay лежит в `gentoo/`:

```bash
make sdist
cd gentoo/dev-python/pythondialog
DISTDIR="$OLDPWD/dist" ebuild pythondialog-3.6.0.ebuild manifest
sudo emaint sync -r pythondialog-overlay   # после настройки repos.conf
sudo emerge -av dev-python/pythondialog
```

Ebuild: EAPI 8, `distutils-r1`, `DISTUTILS_USE_PEP517=setuptools`,
`PYTHON_COMPAT=( python3_{11..14} pypy3 )`, `RDEPEND="dev-util/dialog"`.
Исходники скачиваются из GitHub Release `v3.6.0`; после изменения кода
нужно пересобрать sdist, выпустить релиз и обновить `Manifest`.

## Архитектура `dialog.py`

Порядок в файле отражает слои:

1. **Версии и исключения** — `VersionInfo`, `version_info`, иерархия `error`
   (`ExecutableNotFound`, `PythonDialogBug`, `BadPythonDialogUsage`,
   `PythonDialogSystemError` → `PythonDialogOSError`, `UnexpectedDialogOutput`,
   `DialogTerminatedBySignal`, `DialogError`, исключения версий бэкенда).
   `PythonDialogIOError` сохранён для обратной совместимости, но больше не
   выбрасывается (в Python 3 `IOError` — алиас `OSError`).
2. **Построение аргументов** — `_common_args_syntax` (dict: pythonic-имя →
   лямбда, формирующая флаги `dialog`), `_compute_common_args()`,
   `_dash_escape*`. Неизвестная опция даёт `BadPythonDialogUsage`.
   Подчёркивания соответствуют дефисам, булевы опции передаются только при
   истинном значении. Часть опций, влияющих на формат вывода
   (`--output-separator`, `--quoted`, `--single-quoted`, `--no-items`,
   `--last-key`, `--and-widget`), намеренно не добавлена — см. `TODO`.
3. **Версия бэкенда** — `BackendVersion` (ABC), `DialogBackendVersion`
   (сравнение по dotted part + rest). В `Dialog.__init__` вызывается
   `backend_version()` (`dialog --print-version`), результат кэшируется в
   `cached_backend_version`; `_dialog_version_check()` бросает
   `InadequateBackendVersion` для `buildlist`, `rangebox`, `treeview`,
   `prgbox`, `programbox`.
4. **Декораторы** — `@widget` (`func.is_widget`) и `@retval_is_code`
   (`func.retval_is_code`). Эти атрибуты публично значимы: `examples/demo.py`
   (`MyDialog.__getattr__`) и сторонний код строят на них обёртки.
5. **Класс `Dialog`** — каждый виджет собирает список `cmd` и вызывает
   `_perform()`.

### Цепочка вызова

```
widget-метод
  → _default_size()          # autowidgetsize: None → 0 или старое значение
  → _perform(cmd, **kwargs)
      → _call_program()      # fork/exec, pipe для stderr (stdout у Xdialog),
                             # DIALOG_* в окружении, опционально --file
      → _handle_program_exit()
      → _wait_for_program_termination()
  → разбор вывода (_parse_help, _split_shellstyle_arglist, _to_onoff)
```

`_call_program()`:
- общение с `dialog` идёт через pipe на **stderr** (`compat="Xdialog"` —
  stdout); `use_stdout` переключает это;
- в окружение дочернего процесса кладутся `DIALOG_OK`, `DIALOG_CANCEL`, …;
- `pass_args_via_file` (по умолчанию включён для `dialog >= 1.2-20150513`)
  пишет аргументы во временный файл и передаёт `--file`;
- `dash_escape` защищает строки, начинающиеся с `--`;
- ошибки до `fork()`/`exec()` очищают pipe и временный файл; в дочернем
  процессе `father_stderr` инициализируется до `dup(2)`, чтобы не потерять
  traceback.

### Два уровня кодов возврата

- Низкоуровневые целочисленные статусы `dialog`: `_DIALOG_OK` и т.п.,
  `_lowlevel_exit_codes`, `_dialog_exit_code_ll_to_hl`.
- Высокоуровневые строковые «Dialog exit codes»: `Dialog.OK`, `CANCEL`, `ESC`,
  `HELP`, `EXTRA`, `TIMEOUT`. Публичный API должен использовать их.
  `DIALOG_*`-свойства оставлены с `DeprecationWarning`.

Виджеты возвращают либо сам код, либо кортеж, первым элементом которого он
является. `--help`-вывод разбирается `_parse_help()` (учитывает
`--help-status`, `--item-help`, `--help-tags`); пустой вывод при включённом
`--help-status` — это `PythonDialogBug`.

### Потоковые виджеты

`gauge_start()`/`gauge_update()`/`gauge_stop()` и `progressbox`/`programbox`
передают данные в stdin дочернего процесса через `redir_child_stdin_from_fd`;
`gauge_iterate()` — устаревшая обёртка над `gauge_update()`. Не буферизуйте
вывод: статус `dialog` читается через pipe.

### Размеры виджетов

`autowidgetsize=True` означает «вести себя как при `height=0, width=0`»:
параметры со значением по умолчанию `None` подменяются на `0` в
`_default_size()`. Явный `None` в размерах передавать нельзя.

## Документация

`doc/*.rst` + autodoc: Sphinx импортирует `dialog` (в `conf.py` добавлен `..`
в `sys.path`) и тянет docstrings из `dialog.py`. Docstring'и — основной
источник правды; изменения API должны сопровождаться правкой docstring'ов и,
при необходимости, `doc/widgets.rst` / `doc/Dialog_class_overview.rst`.
Используются reST-директивы `.. versionadded::`/`.. versionchanged::`.
`doc/index.rst` ссылается на `doc/intro/intro.rst`; скриншоты — в
`doc/screenshots/`. `intersphinx_mapping` пуст, чтобы сборка не ходила в сеть.

## Соглашения и подводные камни

- Только стандартная библиотека в `dialog.py`; сторонние зависимости не
  добавлять. Минимум — Python 3.10.
- Обратная совместимость: устаревшее не удаляется, а помечается
  `DeprecationWarning` (`_obsolete_property`, `setBackgroundTitle`, `clear`,
  `gauge_iterate`, `_perform_no_options`).
- Форматирование: UTF-8, ~72–79 колонок, reST-docstring'и. Emacs local
  variables в конце файлов не трогать.
- Пользовательские строки, уходящие в `dialog`, проходят dash-escaping.
- `ChangeLog` больше не генерируется из git автоматически; новые записи
  добавляются вручную в том же формате.
- Запуск примеров и виджетов требует настоящего TTY; в неинтерактивной среде
  используйте `tests/fake_dialog.py` и `python3 -m py_compile`.
- `dialog` 1.3-20201126 (Debian) сломан; для проверок используйте другую сборку
  (в текущем окружении — 1.3-20250817).
- Репозиторий: https://github.com/grivital/pythondialog. Коммиты и push —
  только по запросу пользователя.
