# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Что это за проект

pythondialog — Python-обёртка над UNIX-утилитой `dialog` (ncurses TUI). Вся библиотека
состоит из одного модуля `dialog.py` (~3770 строк), без сторонних зависимостей и без
пакета: `setup.py` объявляет `py_modules=["dialog"]`. Требуется Python 3 и установленный
исполняемый файл `dialog` (или совместимый `Xdialog`). Версия библиотеки задаётся
переменной `version_info` в начале `dialog.py` (сейчас 3.5.3).

Тестового фреймворка нет: `examples/demo.py` выполняет роль «дешёвого тест-сьюта»
(см. его `--test-suite`/`--fast`).

## Команды

```bash
# Простой пример (нужен TTY и бинарник dialog в PATH)
PYTHONPATH=. python3 examples/simple_example.py

# Демо / ручная проверка виджетов
PYTHONPATH=. python3 examples/demo.py
PYTHONPATH=. python3 examples/demo.py --help        # список опций
PYTHONPATH=. python3 examples/demo.py -t            # testsuite-режим (подразумевает -f)
PYTHONPATH=. python3 examples/demo.py -f            # fast-режим
PYTHONPATH=. python3 examples/demo.py --debug --debug-file=/tmp/debug.log

# Вариант с autowidgetsize
PYTHONPATH=. python3 examples/with-autowidgetsize/simple_example.py

# Проверка синтаксиса/импорта без запуска виджетов
python3 -c 'import dialog; print(dialog.__version__)'

# Установка
pip install .
pip install -e .
python3 setup.py sdist            # ChangeLog + sdist

# Документация (нужен Sphinx; вывод в doc/_build/html)
cd doc && make html
# либо: sphinx-build -b html . _build/html
```

Отладочные предупреждения об устаревших API: `PYTHONPATH=. python3 -Wd examples/demo.py 2>/tmp/warn.log`
(stderr нужно перенаправлять, иначе вывод dialog его затирает).

### Особенности setup.py

При наличии `.git` `setup.py` каждый раз перегенерирует `ChangeLog` из git-лога через
`gitlog-to-changelog` (должен быть в `PATH`) и `ChangeLog.init`. Без `.git` используется
существующий `ChangeLog`; если нет ни `.git`, ни `ChangeLog` — сборка прерывается.
`ChangeLog` не редактируется вручную; `ChangeLog.init` — рукописный префикс.

## Архитектура `dialog.py`

Порядок в файле отражает слои:

1. **Версии и исключения** — `VersionInfo`, `version_info`, иерархия `error`
   (`ExecutableNotFound`, `PythonDialogBug`, `BadPythonDialogUsage`,
   `PythonDialogSystemError` → `PythonDialogOSError`/`PythonDialogIOError`,
   `UnexpectedDialogOutput`, `DialogTerminatedBySignal`, `DialogError`,
   `UnableToRetrieveBackendVersion`/`UnableToParseBackendVersion`/
   `InadequateBackendVersion` и др.). Иерархия документирована в docstring модуля —
   при изменении обновлять его.
2. **Построение аргументов** — `_common_args_syntax` (dict: pythonic-имя →
   лямбда, формирующая флаги `dialog`), `_compute_common_args()`, `_dash_escape*`.
   Любой `**kwargs` виджета превращается в «общие опции» `dialog(1)`;
   подчёркивания соответствуют дефисам в именах опций, булевы опции передаются
   только при истинном значении.
3. **Версия бэкенда** — `BackendVersion`, `DialogBackendVersion` (сравнение по
   «dotted part» + «rest», например `1.2-20130902`). В `Dialog.__init__`
   вызывается `backend_version()` (`dialog --print-version`) и результат
   кэшируется в `cached_backend_version`; `_dialog_version_check()` бросает
   `InadequateBackendVersion` для виджетов, требующих свежий `dialog`
   (`buildlist`, `rangebox`, `treeview`, `programbox`).
4. **Декораторы** — `@widget` помечает методы, создающие виджеты (`func.is_widget`);
   `@retval_is_code` — что метод возвращает только высокоуровневый код
   (`func.retval_is_code`). Эти атрибуты публично значимы: `examples/demo.py`
   (`MyDialog.__getattr__`) и сторонний код строят на них обёртки. Не удалять и
   не менять семантику без необходимости.
5. **Класс `Dialog`** — ядро API. Каждый виджет (`msgbox`, `yesno`, `checklist`,
   `menu`, `form`, `gauge_*`, `treeview`, …) — метод класса, который собирает
   список `cmd` и вызывает `_perform()`.

### Цепочка вызова

```
widget-метод
  → _default_size()          # autowidgetsize: None → 0 или старое значение
  → _perform(cmd, **kwargs)
      → _call_program()      # fork/exec, pipe для stderr (или stdout у Xdialog),
                             # DIALOG_* переменные окружения, опционально --file
      → _handle_program_exit()
      → _wait_for_program_termination()   # читает вывод, ждёт exit status
  → разбор вывода (_parse_help(), _split_shellstyle_arglist(), _to_onoff())
```

Важные детали `_call_program()`:
- общение с `dialog` идёт через pipe на **stderr** (у `compat="Xdialog"` —
  на stdout); `use_stdout` переключает это;
- в окружение дочернего процесса кладутся `DIALOG_OK`, `DIALOG_CANCEL`, …,
  чтобы контролировать коды завершения;
- `pass_args_via_file` (по умолчанию включён для `dialog >= 1.2-20150513`)
  пишет аргументы во временный файл и передаёт `--file`, скрывая их из
  списка процессов;
- `dash_escape` защищает пользовательские строки, начинающиеся с `--`.

### Два уровня кодов возврата

- Низкоуровневые целочисленные статусы `dialog`: `_DIALOG_OK` и т. п.,
  `_lowlevel_exit_codes`, `_dialog_exit_code_ll_to_hl`.
- Высокоуровневые строковые «Dialog exit codes»: `Dialog.OK`, `CANCEL`, `ESC`,
  `HELP`, `EXTRA`, `TIMEOUT`; публичный API должен использовать их.
  `DIALOG_*`-свойства оставлены для обратной совместимости и выдают
  `DeprecationWarning`.

Виджеты возвращают либо сам код, либо кортеж, первым элементом которого он
является. `--help`-вывод разбирается `_parse_help()` (учитывает
`--help-status`, `--item-help`, `--help-tags`).

### Потоковые виджеты

`gauge_start()`/`gauge_update()`/`gauge_stop()` и `progressbox`/`programbox`
передают данные в stdin дочернего процесса через `redir_child_stdin_from_fd`;
`gauge_iterate()` — генератор-обёртка. Не буферизуйте вывод: статус `dialog`
читается построчно через pipe.

### Размеры виджетов

`autowidgetsize=True` в конструкторе означает «вести себя как при
`height=0, width=0`»: параметры со значением по умолчанию `None` подменяются
на `0` в `_default_size()`. Явный `None` в размерах передавать нельзя.

## Документация

`doc/*.rst` + autodoc: Sphinx импортирует `dialog` (в `conf.py` добавлен `..`
в `sys.path`) и тянет docstrings прямо из `dialog.py`. Поэтому docstring'и —
основной источник правды; изменения API должны сопровождаться правкой
docstring'ов и, при необходимости, `doc/widgets.rst` /
`doc/Dialog_class_overview.rst`. В docstring'ах используются reST-директивы
`.. versionadded::`/`.. versionchanged::` — продолжайте эту практику.
`doc/index.rst` ссылается на `doc/intro/intro.rst`; скриншоты лежат в
`doc/screenshots/`.

## Соглашения и подводные камни

- Поддержка Python 3; никаких сторонних зависимостей в `dialog.py` —
  только стандартная библиотека.
- Обратная совместимость важна: устаревшее не удаляется, а помечается
  `DeprecationWarning` (например, `_obsolete_property`, старые имена опций
  вроде `cancel` → `cancel_label`).
- Форматирование исходников: кодировка UTF-8, ширина ~72–79 колонок,
  docstring'и в reST. В конце файлов — Emacs local variables, их не трогать.
- Все пользовательские строки, уходящие в `dialog`, должны проходить через
  dash-escaping; при добавлении нового виджета не забывайте про
  `--separate-output`, если вывод содержит теги/пробелы.
- `dialog` версии 1.3-20201126 (Debian) сломан; для проверок используйте
  другую сборку.
- В docstring'е `treeview` есть неэкранированный `\s` — на Python 3.12+
  `py_compile` выдаёт `SyntaxWarning` (не ошибка).
- Запуск примеров и любых виджетов требует настоящего TTY; в неинтерактивной
  среде проверяйте только импорт/синтаксис (`python3 -m py_compile dialog.py`).
