import time
import sys
import pytest
import os
import glob
import yaml
import platform
import shutil
import logging
import re

from subprocess import Popen, PIPE, STDOUT
from USBRedirectorAPI.usbredirectorapi import USBRedirectorAPI
from pypkcs11.src.applets import (
    AppletSelector,
    FindAppletException,
    FindSlotException,
    ErrorAppletException,
)


def get_os_name():
    """
    Пока что не придумал более адекватный способ получать os name, тк есть проблемы с Windows Server 2019
    При попытке получить os name с вышеуказанной машины всегда возвращается 'windows 10' без пометки 'server'
    """
    os_platform = platform.platform(terse=True)
    if sys.platform == "win32":
        try:
            os_platform_win = Popen(
                [
                    "powershell.exe",
                    "-command",
                    "(Get-WmiObject Win32_OperatingSystem).Name.split('|')[0]"
                ], stdout=PIPE).communicate()[0]

            os_platform_win = str(os_platform_win).split('\\')

            count = len(os_platform_win[0])
            os_p = ''
            for os_plat in os_platform_win:
                if count < len(os_plat):
                    count = len(os_plat)
                    os_p = os_plat

            os_platform = ' '.join(map(str, os_p.split(' ')[1:])).rstrip().replace(' ', '_')
        except Exception:
            pass

    return os_platform


os_name_param = f'{get_os_name()}_{platform.architecture()[0]}'
tokens = None
ids_token_list = []
providers = {
    "provtype_77_hash_alg_2012_256": ['77', '2012-256'],
    "provtype_78_hash_alg_2012_512": ['78', '2012-512']
}
ids_provider_list = []


def pytest_addoption(parser):
    parser.addoption(
        "--path_to_JCPKCS11",
        type=str,
        default='C:\\WINDOWS\\System32\\jcPKCS11-2.dll' if sys.platform == "win32" else "/usr/lib/libjcPKCS11-2.so",
        help='Path to JCPKCS11'
    )
    parser.addoption(
        '--path',
        type=str,
        required=True,
        help='Path to csp_invoke'
    )
    parser.addoption(
        "--tokens",
        help="Path to file tokens.yml"
    )
    parser.addoption(
        '--local',
        action='store_true',
        help="Параметр для отладки на локальной машине"
    )
    parser.addoption(
        "--server",
        help="Параметр для подключения к серверу с токенами"
    )
    parser.addoption(
        "--vipnet_version",
        type=str,
        help="VipNet версия"
    )
    parser.addoption(
        "--path-to-log",
        type=str,
        default='C:\\VipNet\\logs\\JC_UL_LOG.log' if sys.platform == "win32" else "/home/admin-test/VipNet/Logs/JC_UL_LOG.log",
        help="Путь до JCPKCS11 log"
    )


@pytest.fixture(scope="session", autouse=True)
def get_default_values(request):
    pytest.path_to_jcpkcs11 = request.config.getoption("--path_to_JCPKCS11")
    if not os.path.isfile(pytest.path_to_jcpkcs11):
        raise Exception("JCPKCS11 path not valid")

    pytest.path_to_csp_invoke = request.config.getoption("--path")
    if not os.path.isfile(pytest.path_to_csp_invoke):
        raise Exception("csp_invoke path not valid")
    pytest.file_path = 'testfile.txt'
    pytest.certificate_name = 'testcertificate'
    pytest.path_to_log = request.config.getoption("--path-to-log")


@pytest.fixture(scope="class", autouse=True)
def get_container_name(token):
    pytest.container_name = f'1|2\\5|{token["family_id"]}\\17|{token["applet_serial"]}\\8|testcontainer'


@pytest.fixture(scope="function", autouse=True)
def clear_token(request):
    try:
        os.remove(pytest.path_to_log)
    except FileNotFoundError:
        pass
    yield
    files = [
        glob.glob('*.enc'),
        glob.glob('*.sig'),
        glob.glob('*.pub'),
        glob.glob('*.enc.txt'),
        glob.glob('*.sig.txt'),
        glob.glob(pytest.file_path),
        glob.glob(f"{pytest.certificate_name}.cer")
    ]
    for file in files:
        for f in file:
            os.remove(f)

    delpass = [pytest.path_to_csp_invoke, 'container', '--delpass', '--container', pytest.container_name, '--silent']
    delete_cert = [pytest.path_to_csp_invoke, 'cert', '--cmd', 'del', '--dn', 'testcertificate']

    for procces in delpass, delete_cert:
        if sys.platform == 'linux':
            procces.insert(0, 'sudo')
        process = Popen(procces, stdout=PIPE, stderr=STDOUT)
        process.wait(240)


@pytest.fixture(scope="function", autouse=True)
def check_configuration(token, provider):
    if provider[0] == "78" and token['family_id'] == "1500":
        pytest.skip('Unsupported configuration for token GOST with provtype 78 hash_alg 2012-512')


@pytest.fixture(scope="class", autouse=True)
def connect_token(token, request):
    if request.config.getoption("--local"):
        yield token
        pkcs11_format_applet(token)
        return
    server = request.config.getoption("--server")
    usb_redirector_api = USBRedirectorAPI(server)
    usb_connect(usb_redirector_api, token)

    # После коннект токена ждем...
    os_name = platform.platform()
    os_time = 40
    time.sleep(os_time)

    yield token

    time.sleep(2)
    try:
        pkcs11_format_applet(token)
    except Exception as err:
        usb_disconnect(usb_redirector_api, token)
        raise Exception(err)
    usb_disconnect(usb_redirector_api, token)
    time.sleep(15)


@pytest.fixture(scope="function", autouse=True)
def init_token(token):
    time.sleep(10)
    pkcs11_format_applet(token)


def pkcs11_format_applet(token):
    try:
        applet = AppletSelector.get_applet(token['applet_model'])(
            pytest.path_to_jcpkcs11,
            token['applet_serial'].replace(' ', ''),
            token['applet_model'],
        )
    except FindAppletException:
        raise Exception("Ошибка при поиске апплета")

    with applet:
        try:
            applet.format(
                token['user_pin'],
                token['so_pin'],
                "VipNet tests"
            )
        except (FindSlotException, ErrorAppletException):
            raise Exception("Ошибка при работе со смарт-картой")


def usb_connect(server, token):
    if token['port'] is not None:
        server.connect_usb(token['port'])
    else:
        server.connect_usb(serial=token['serial'])


def usb_disconnect(server, token):
    if token['port'] is not None:
        server.disconnect_usb(token['port'])
    else:
        server.disconnect_usb(serial=token['serial'])


@pytest.fixture(scope="class")
def vip_net_attributes(token, provider):
    attributes = {
        "path_to_csp_invoke": pytest.path_to_csp_invoke,
        "container_name": pytest.container_name,
        "user_pin": token['user_pin'],
        "provtype": provider[0],
        "hash_alg": provider[1],
        "key_type": 'both',
        "certificate_name": pytest.certificate_name,
        "file_path": pytest.file_path
    }
    return attributes


@pytest.fixture(scope='session', autouse=True)
def parametrize_osname(os_name):
    pass


def get_tokens_list(tokens_group, vipnet_version):
    vipnet_version = '.'.join(vipnet_version.split('.')[:2])
    remove_list = []
    for token in tokens_group:
        if 'ALL' not in token['vipnet_versions'] and \
                vipnet_version not in token['vipnet_versions']:
            remove_list.append(token)
    for token in remove_list:
        tokens_group.remove(token)

    ids_tokens = []
    tokens_list = []
    for token in tokens_group:
        for applet in token['applets']:
            ids_tokens.append(
                f"token{len(token['name'])} {token['name']} "
                f"applet{len(applet['applet_model'])} {applet['applet_model']}"
            )

            token_item = token.copy()
            token_item.pop('applets', None)
            token_item.update(applet)

            tokens_list.append(token_item)

    return ids_tokens, tokens_list


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    def _set_logfile_name(count, log_file):
        if os.path.isfile(log_file):
            log_file = os.path.join(dir_for_logs, f'{file_name}_reruns_{count}.log')
            count += 1
            return _set_logfile_name(count, log_file)
        return log_file

    dir_for_logs = os.path.join(os.path.dirname(pytest.path_to_log), "failed_logs")
    outcome = yield
    result = outcome.get_result()
    if result.failed:
        if not os.path.exists(dir_for_logs):
            os.mkdir(dir_for_logs)
        test_name = re.search("[::]\w+[\[]", result.nodeid).group()[1:-1]
        params = re.search("(applet\d*\s)([^]]*)", result.nodeid).group(2).split('-provider')
        params_name = '_'.join([params[0].replace(' ', '_'), params[1].split(' ')[1].replace(' ', '_')])
        file_name = f"{test_name}_{params_name}"
        log_file = os.path.join(dir_for_logs, f'{file_name}.log')
        if os.path.exists(pytest.path_to_log):
            log_file = _set_logfile_name(1, log_file)
            shutil.copyfile(pytest.path_to_log, log_file)
        else:
            logging.error("Failed to copy logs. JCPKCS11 logs missing")


def pytest_generate_tests(metafunc):
    global os_name_param
    global tokens
    global ids_token_list
    global providers
    global ids_provider_list

    path_to_tokens = metafunc.config.getoption("--tokens")
    if not os.path.isfile(path_to_tokens):
        raise Exception("Tokens path not valid")

    if "os_name" in metafunc.fixturenames:
        metafunc.parametrize(
            "os_name",
            [os_name_param],
            scope="session",
            ids=[f'os{len(os_name_param)} {os_name_param}']
        )

    if "token" in metafunc.fixturenames:
        if tokens is None:
            with open(path_to_tokens) as f:
                tokens_yml = yaml.full_load(f)
            tokens_list = tokens_yml["tokens"]
            ids_token_list, tokens = get_tokens_list(tokens_list, metafunc.config.getoption("--vipnet_version"))

        metafunc.parametrize(
            "token",
            tokens,
            scope="class",
            ids=ids_token_list
        )

    if "provider" in metafunc.fixturenames:
        if not ids_provider_list:
            for provider in providers.keys():
                ids_provider_list.append(f"provider{len(provider)} {provider}")

        metafunc.parametrize(
            "provider",
            providers.values(),
            scope="class",
            ids=ids_provider_list
        )
