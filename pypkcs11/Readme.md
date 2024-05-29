# Структура проекта:
- папка scripts - утилиты для работы с p11 библиотекой
- папка src - модуль взаимодействия с токеном. Необходим для форматирования апплетов
- папка deploy - пустая

# папка scripts - утилиты для работы с p11 библиотекой

## Утилита writeobjects.py (writeobjects.exe)

Утилита тестирования записи бинарных объектов на токен

``` bash
$ python writeobjects.py --help
usage: writeobjects.py [-h] [--library LIBRARY] [--slot SLOT] [--show_slots]
                       [--pin PIN] [--start_size START_SIZE]
                       [--stop_size STOP_SIZE] [--step_size STEP_SIZE]
                       [--cycles CYCLES] [--random_size] [--no_delete]
                       [--one_session] [--one_login] [--log_file LOG_FILE]
                       [--do_backup] [--backup_lines BACKUP_LINES]

optional arguments:
  -h, --help            show this help message and exit
  --library LIBRARY     jcPKCS11 library path
  --slot SLOT           Applet slot
  --show_slots          Show slots
  --pin PIN             token user pin
  --start_size START_SIZE
                        Start data size
  --stop_size STOP_SIZE
                        Stop data size
  --step_size STEP_SIZE
                        Increase data step size
  --cycles CYCLES       How many times execute operations. If set "0" testing
                        will runs forever with --start_size object
  --random_size         If --cycles "0", size of write data will be from
                        --start_size to --stop_size
  --no_delete           Do not delete created objects
  --one_session         Open only one session while testing
  --one_login           Login only one time while testing
  --log_file LOG_FILE   Path to log file
  --do_backup           Do backup files
  --backup_lines BACKUP_LINES
                        Number of backup lines
```

Сценарии запуска:

Получить все доступные слоты апплетов

```
writeobjects.exe --show_slots
```

Используя слот 131071 и пароль пользователя 1234567890 выполнить бесконечную запись бинарных объектов длинны 
от 512 байт до 1024 байт построив одну сессию и предъявив для неё пароль. Дополнительно сохранять логи в файл log.txt
и делать резервную копию файла каждые 1000 строк

``` bash
writeobjects.exe --slot 131071 --pin 1234567890 --cycles 0 --start_size 512 --stop_size 1024 --random_size --one_session --one_login --log_file log.txt --do_backup --backup_lines 10000
```

Используя слот 131071 и пароль пользователя 1234567890 выполнить запись бинарных объектов из 6 циклов на каждый шаг длинны начиная с 512 байт 
заканчивая 2048 байт с шагом в 128 байт построив одну сессию и предъявив для неё пароль. Дополнительно сохранять логи в файл log.txt
и делать резервную копию файла каждые 1000 строк

``` bash
writeobjects.exe --slot 131071 --pin 1234567890 --cycles 5 --start_size 512 --stop_size 2048 --step_size 128 --one_session --one_login --log_file log.txt --do_backup --backup_lines 10000
```

Получить все доступные слоты апплетов, через библиотеку p11, которая располагается по ./new_lib/lib.dll

```
writeobjects.exe --show_slots --library "./new_lib/lib.dll"
```
## Утилита set_so_pin.py ##

**Утилита смены ПИН админа**
(Поддерживаемые апплеты: "JaCarta Laser", "JaCarta DS", "PRO")

``` bash
$ python set_so_pin.py --help
usage: set_so_pin.py [-h] --PKCS11_library PKCS11_LIBRARY
                     [--config_set_so_pin CONFIG_SET_SO_PIN]
                     [--current_so_pin CURRENT_SO_PIN]
                     [--new_so_pin NEW_SO_PIN] 
                     [--applet APPLET]
optional arguments:
  -h, --help            show this help message and exit
  --PKCS11_library PKCS11_LIBRARY - path to .dll
set_pin_admin_conf:
  --config_set_so_pin CONFIG_SET_SO_PIN - path to config with passwords
set_admin_pin:
--current_so_pin CURRENT_SO_PIN - current admin password
--new_so_pin NEW_SO_PIN - new admin password
--applet APPLET       applet  
```
**Запуск:**
- Через конфиг:
  Пример:
  ```bash
  $ python set_so_pin.py --PKCS11_library "C:\WINDOWS\System32\jcPKCS11-2.dll" --config_set_so_pin "C:\dev\conf.json"
  ```
  Пример JSON:
  ```
  {"JaCarta Laser":{"current_so_pin": "00000000", "new_so_pin": "11111111"}}
  ```
- Через указание текущего и нового ПИН:
  Пример:
  ```bash
  $ python set_so_pin.py --PKCS11_library "C:\WINDOWS\System32\jcPKCS11-2.dll" --applet "JaCarta Laser" --current_so_pin "00000000" --new_so_pin "11111111"
  ```