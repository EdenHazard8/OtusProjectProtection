import os
import time
import sys
import logging
import psutil

from common import ICommand, ExceptionHandler
from pathlib import Path
from enum import Enum
from subprocess import Popen, PIPE, STDOUT, TimeoutExpired


class FuncVipNet:
    def __init__(
            self,
            path_to_csp_invoke: str,
            container_name: str,
            user_pin: str,
            provtype: str,
            hash_alg: str,
            key_type: str,
            certificate_name: str,
            file_path: str
    ):
        self.csp_invoke = path_to_csp_invoke
        self.container_name = container_name
        self.user_pin = user_pin
        self.provtype = provtype
        self.hash_alg = hash_alg
        self.key_type = key_type
        self.certificate_name = certificate_name
        self.file_path = file_path
        self.csp_invoke_base_name = os.path.basename(self.csp_invoke)

    def _get_vip_net_process(self, key_name):
        functions_vipnet = {
            VipNetOperationsName.KEY_GENERATION: [self.csp_invoke, 'container', '--newkey', '--container',
                                                  self.container_name, '--provtype', self.provtype, '--keytype',
                                                  self.key_type, '--pin', self.user_pin],
            VipNetOperationsName.ENUM_CONTAINERS: [self.csp_invoke, 'container', '--enum', '--unique'],
            VipNetOperationsName.ENUM_CONTAINERS2: [self.csp_invoke, 'container', '--keyinfo', '--container',
                                                    self.container_name, '--pin', self.user_pin],
            VipNetOperationsName.SAVE_CONTAINER_PASSWORD: [self.csp_invoke, 'container', '--savepass', '--container',
                                                           self.container_name, '--pin', self.user_pin],
            VipNetOperationsName.CREATE_SELFSIGNED_CERT: [self.csp_invoke, 'mkcert', '--selfsigned', '--container',
                                                          self.container_name, '--cn',
                                                          f'CN={self.certificate_name}', '--out',
                                                          f'{self.certificate_name}.cer', '--provtype',
                                                          self.provtype, '--before', '01/01/2019', '--after',
                                                          '12/31/2049', '--pin', self.user_pin],
            VipNetOperationsName.SETUP_CERT_TO_CONTAINER: [self.csp_invoke, 'cert', '--cmd', 'copy', '--usecertin',
                                                           'file', '--certfile', f'{self.certificate_name}.cer',
                                                           '--rcontainer', self.container_name, '--userecipin',
                                                           'container', '--rpin', self.user_pin, '--rsilent',
                                                           '--rkeytype', 'signature'],
            VipNetOperationsName.CHECK_CERT_IN_CONTAINER: [self.csp_invoke, 'cert', '--cmd', 'info', '--usecertin',
                                                           'container', '--container', self.container_name],
            VipNetOperationsName.SETUP_CERT_TO_STORAGE: [self.csp_invoke, 'cert', '--cmd', 'install', '--usecertin',
                                                         'container', '--container', self.container_name, '--rstore',
                                                         'My'],
            VipNetOperationsName.SIGN_MESSAGE: [self.csp_invoke, 'cp', '--cmd', 'sign', '--hashalg', self.hash_alg,
                                                '--in', self.file_path, '--out', 'sign.sig', '--container',
                                                self.container_name, '--pin', self.user_pin],
            VipNetOperationsName.SIGN_MESSAGE2: [self.csp_invoke, 'cp', '--cmd', 'exppub', '--container',
                                                 self.container_name, '--out', 'key.pub'],
            VipNetOperationsName.CHECK_MESSAGE: [self.csp_invoke, 'cp', '--cmd', 'verify', '--hashalg', self.hash_alg,
                                                 '--in', self.file_path, '--public', 'key.pub', '--sigfile',
                                                 'sign.sig'],
            VipNetOperationsName.LOWLVL_CMS_SIGN_FROM_STORAGE: [self.csp_invoke, 'cms', '--cmd', 'lowsign', '--hashalg',
                                                                self.hash_alg, '--in', self.file_path, '--out',
                                                                'low.sig', '--include', '--dn', self.certificate_name,
                                                                '--pin', self.user_pin],
            VipNetOperationsName.LOWLVL_CMS_SIGN_FROM_STORAGE2: [self.csp_invoke, 'cms', '--cmd', 'lowverify',
                                                                 '--hashalg', self.hash_alg, '--in', 'low.sig', '--out',
                                                                 'low.sig.txt'],
            VipNetOperationsName.LOWLVL_CMS_SIGN_FROM_STORAGE3: [self.csp_invoke, 'cms', '--cmd', 'lowsign',
                                                                 '--hashalg', self.hash_alg, '--in', self.file_path,
                                                                 '--out', 'low_detached.sig', '--include',
                                                                 '--dn', self.certificate_name, '--detached', '--pin',
                                                                 self.user_pin],
            VipNetOperationsName.LOWLVL_CMS_SIGN_FROM_STORAGE4: [self.csp_invoke, 'cms', '--cmd', 'lowverify',
                                                                 '--hashalg', self.hash_alg, '--in', self.file_path,
                                                                 '--sigfile', 'low_detached.sig', '--out',
                                                                 'low_detached.sig.txt'],
            VipNetOperationsName.SIMPLE_CMS_SIGN_FROM_STORAGE: [self.csp_invoke, 'cms', '--cmd', 'sfsign', '--hashalg',
                                                                self.hash_alg, '--in', self.file_path, '--out',
                                                                'sf.sig', '--include', '--dn', self.certificate_name,
                                                                '--pin', self.user_pin],
            VipNetOperationsName.SIMPLE_CMS_SIGN_FROM_STORAGE2: [self.csp_invoke, 'cms', '--cmd', 'sfverify',
                                                                 '--hashalg', self.hash_alg, '--in', 'low.sig', '--out',
                                                                 'sf.sig.txt'],
            VipNetOperationsName.SIMPLE_CMS_SIGN_FROM_STORAGE3: [self.csp_invoke, 'cms', '--cmd', 'sfsign', '--hashalg',
                                                                 self.hash_alg, '--in', self.file_path, '--out',
                                                                 'sf_detached.sig', '--include', '--dn',
                                                                 self.certificate_name, '--detached', '--pin',
                                                                 self.user_pin],
            VipNetOperationsName.SIMPLE_CMS_SIGN_FROM_STORAGE4: [self.csp_invoke, 'cms', '--cmd', 'sfverify',
                                                                 '--hashalg', self.hash_alg, '--in', self.file_path,
                                                                 '--sigfile', 'sf_detached.sig', '--out',
                                                                 'sf_detached.sig.txt'],
            VipNetOperationsName.LOWLVL_CMS_ENCRYPT: [self.csp_invoke, 'cms', '--cmd', 'lowenc', '--in', self.file_path,
                                                      '--out', 'low.enc', '--rstore', 'My', '--rdn',
                                                      self.certificate_name],
            VipNetOperationsName.LOWLVL_CMS_ENCRYPT2: [self.csp_invoke, 'cms', '--cmd', 'lowdec', '--in', 'low.enc',
                                                       '--out', 'low.enc.txt', '--pin', self.user_pin, '--dn',
                                                       self.certificate_name],
            VipNetOperationsName.SIMPLE_CMS_ENCRYPT: [self.csp_invoke, 'cms', '--cmd', 'sfenc', '--in', self.file_path,
                                                      '--out', 'sf.enc', '--rstore', 'My', '--rdn',
                                                      self.certificate_name],
            VipNetOperationsName.SIMPLE_CMS_ENCRYPT2: [self.csp_invoke, 'cms', '--cmd', 'sfdec', '--in', 'sf.enc',
                                                       '--out', 'sf.enc.txt', '--pin', self.user_pin],
            VipNetOperationsName.DELETE_PASSWORD: [self.csp_invoke, 'container', '--delpass', '--container',
                                                   self.container_name, '--silent'],
            VipNetOperationsName.DELETE_CERT: [self.csp_invoke, 'cert', '--cmd', 'del', '--dn', self.certificate_name],
            VipNetOperationsName.DELETE_CONTAINER: [self.csp_invoke, 'container', '--delete', '--container',
                                                    self.container_name, '--pin', self.user_pin]
        }

        return ",".join(map(str, functions_vipnet[key_name])).split(",")

    def _wait_cspinvoke(func):
        def wrapper(self, *args, **kwargs):
            if sys.platform == "win32":
                for _ in range(40):
                    for proc in psutil.process_iter():
                        if proc.name() == self.csp_invoke_base_name:
                            time.sleep(1)
                    break
                else:
                    self._kill_cspinvoke()
                    logging.error('csp_invoke process name already exists')
                    raise TimeoutError('csp_invoke is already running, probably hung')
            return func(self, *args, **kwargs)

        return wrapper

    def _kill_cspinvoke(self):
        for proc in psutil.process_iter():
            if proc.name() == self.csp_invoke_base_name:
                proc.kill()

    @_wait_cspinvoke
    def _run_operation(self, process):
        if sys.platform == 'linux':
            process.insert(0, 'sudo')
        proc = Popen(process, stdout=PIPE, stderr=STDOUT)
        try:
            proc.wait(1080)
        except TimeoutExpired as e:
            self._kill_cspinvoke()
            logging.error('TimeoutError: csp_invoke failed after 360 seconds')
            return ExceptionHandler.handle(e, self)

        data = proc.communicate()

        return proc.returncode, data[0]

    def create_file(self):
        with Path(self.file_path).open('w') as fp:
            fp.write('IT IS A TEST FILE')

    def key_generation(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.KEY_GENERATION,
            )
        )
        assert return_code == 0, f"Ошибка при генерации ключа: {return_code}, {data}"

    def enum_containers_first(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.ENUM_CONTAINERS,
            )
        )
        assert return_code == 0, f"Ошибка при перечислении контейнеров на носителе: {return_code}, {data}"

    def enum_containers_second(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.ENUM_CONTAINERS2,
            )
        )
        assert return_code == 0, f"Ошибка при перечислении контейнеров на носителе: {return_code}, {data}"

    def save_container_password(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.SAVE_CONTAINER_PASSWORD
            )
        )
        assert return_code == 0, f"Ошибка при сохранении пароля от контейнера: {return_code}, {data}"

    def create_self_signed_cert(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.CREATE_SELFSIGNED_CERT
            )
        )
        assert return_code == 0, f"Ошибка при создании самоподписанного сертификата: {return_code}, {data}"

    def setup_cert_to_container(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.SETUP_CERT_TO_CONTAINER
            )
        )
        assert return_code == 0, f"Ошибка при установке сертификата в контейнер: {return_code}, {data}"

    def check_cert_in_container(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.CHECK_CERT_IN_CONTAINER
            )
        )
        assert return_code == 0, f"Ошибка при проверке присутствия сертификата в контейнере: {return_code}, {data}"

    def setup_cert_to_storage(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.SETUP_CERT_TO_STORAGE
            )
        )
        assert return_code == 0, f"Ошибка при установке сертификата из контейнера в хранилище MY: {return_code}, {data}"

    def sign_message_first(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.SIGN_MESSAGE
            )
        )
        assert return_code == 0, f"Ошибка при подписи сообщения / проверке подписи: {return_code}, {data}"

    def sign_message_second(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.SIGN_MESSAGE2
            )
        )
        assert return_code == 0, f"Ошибка при подписи сообщения / проверке подписи: {return_code}, {data}"

    def check_message(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.CHECK_MESSAGE
            )
        )
        assert return_code == 0, f"Ошибка при подписи сообщения / проверке подписи" \
                                 f" c несохраненным паролем: {return_code}, {data}"

    def lowlvl_cms_sign_from_storage_first(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.LOWLVL_CMS_SIGN_FROM_STORAGE
            )
        )
        assert return_code == 0, f"Ошибка при низкоуровневой подписи cms сообщения с использованием" \
                                 f" сертификата из хранилища MY: {return_code}, {data}"

    def lowlvl_cms_sign_from_storage_second(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.LOWLVL_CMS_SIGN_FROM_STORAGE2
            )
        )
        assert return_code == 0, f"Ошибка при низкоуровневой подписи cms сообщения с использованием" \
                                 f" сертификата из хранилища MY: {return_code}, {data}"

    def lowlvl_cms_sign_from_storage_third(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.LOWLVL_CMS_SIGN_FROM_STORAGE3
            )
        )
        assert return_code == 0, f"Ошибка при низкоуровневой подписи cms сообщения с использованием" \
                                 f" сертификата из хранилища MY: {return_code}, {data}"

    def lowlvl_cms_sign_from_storage_fourth(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.LOWLVL_CMS_SIGN_FROM_STORAGE4
            )
        )
        assert return_code == 0, f"Ошибка при низкоуровневой подписи cms сообщения с использованием" \
                                 f" сертификата из хранилища MY: {return_code}, {data}"

    def simple_cms_sign_from_storage_first(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.SIMPLE_CMS_SIGN_FROM_STORAGE
            )
        )
        assert return_code == 0, f"Ошибка при упрощенной подписи cms сообщения с использованием " \
                                 f"сертификата из хранилища MY: {return_code}, {data}"

    def simple_cms_sign_from_storage_second(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.SIMPLE_CMS_SIGN_FROM_STORAGE2
            )
        )
        assert return_code == 0, f"Ошибка при упрощенной подписи cms сообщения с использованием " \
                                 f"сертификата из хранилища MY: {return_code}, {data}"

    def simple_cms_sign_from_storage_third(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.SIMPLE_CMS_SIGN_FROM_STORAGE3
            )
        )
        assert return_code == 0, f"Ошибка при упрощенной подписи cms сообщения с использованием " \
                                 f"сертификата из хранилища MY: {return_code}, {data}"

    def simple_cms_sign_from_storage_fourth(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.SIMPLE_CMS_SIGN_FROM_STORAGE4
            )
        )
        assert return_code == 0, f"Ошибка при упрощенной подписи cms сообщения с использованием " \
                                 f"сертификата из хранилища MY: {return_code}, {data}"

    def lowlvl_cms_encrypt_first(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.LOWLVL_CMS_ENCRYPT
            )
        )
        assert return_code == 0, f"Ошибка при низкоуровневом шифровании cms сообщения / Расшифровании " \
                                 f"с использованием сертификата из хранилища MY: {return_code}, {data}"

    def lowlvl_cms_encrypt_second(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.LOWLVL_CMS_ENCRYPT2
            )
        )
        assert return_code == 0, f"Ошибка при низкоуровневом шифровании cms сообщения / Расшифровании " \
                                 f"с использованием сертификата из хранилища MY: {return_code}, {data}"

    def simple_cms_encrypt_first(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.SIMPLE_CMS_ENCRYPT
            )
        )
        assert return_code == 0, f"Ошибка при упрощенном шифрование cms сообщения / Расшифрование " \
                                 f"с использованием сертификата из хранилища MY: {return_code}, {data}"

    def simple_cms_encrypt_second(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.SIMPLE_CMS_ENCRYPT2
            )
        )
        assert return_code == 0, f"Ошибка при упрощенном шифрование cms сообщения / Расшифрование " \
                                 f"с использованием сертификата из хранилища MY: {return_code}, {data}"

    def delete_cert(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.DELETE_CERT
            )
        )
        assert return_code == 0, f"Ошибка при удалении сертификата из хранилища MY: {return_code}, {data}"

    def delete_password(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.DELETE_PASSWORD
            )
        )
        assert return_code == 0, f"Ошибка при удалении сохраненного пароля: {return_code}, {data}"

    def delete_container(self):
        return_code, data = self._run_operation(
            self._get_vip_net_process(
                VipNetOperationsName.DELETE_CONTAINER
            )
        )
        assert return_code == 0, f"Ошибка при удалении контейнера: {return_code}, {data}"


class KeyGeneration(ICommand):
    def __init__(self, executor):
        self.__executor = executor

    def execute(self):
        self.__executor.key_generation()


class VipNetOperationsName(Enum):
    KEY_GENERATION = "key_generation"
    ENUM_CONTAINERS = "enum_containers"
    ENUM_CONTAINERS2 = "enum_containers2"
    SAVE_CONTAINER_PASSWORD = "save_container_password"
    CREATE_SELFSIGNED_CERT = "create_selfsigned_cert"
    SETUP_CERT_TO_CONTAINER = "setup_cert_to_container"
    CHECK_CERT_IN_CONTAINER = "check_cert_in_container"
    SETUP_CERT_TO_STORAGE = "setup_cert_to_storage"
    SIGN_MESSAGE = "sign_message"
    SIGN_MESSAGE2 = "sign_message2"
    CHECK_MESSAGE = "check_message"
    LOWLVL_CMS_SIGN_FROM_STORAGE = "lowlvl_cms_sign_from_storage"
    LOWLVL_CMS_SIGN_FROM_STORAGE2 = "lowlvl_cms_sign_from_storage2"
    LOWLVL_CMS_SIGN_FROM_STORAGE3 = "lowlvl_cms_sign_from_storage3"
    LOWLVL_CMS_SIGN_FROM_STORAGE4 = "lowlvl_cms_sign_from_storage4"
    SIMPLE_CMS_SIGN_FROM_STORAGE = "simple_cms_sign_from_storage"
    SIMPLE_CMS_SIGN_FROM_STORAGE2 = "simple_cms_sign_from_storage2"
    SIMPLE_CMS_SIGN_FROM_STORAGE3 = "simple_cms_sign_from_storage3"
    SIMPLE_CMS_SIGN_FROM_STORAGE4 = "simple_cms_sign_from_storage4"
    LOWLVL_CMS_ENCRYPT = "lowlvl_cms_encrypt"
    LOWLVL_CMS_ENCRYPT2 = "lowlvl_cms_encrypt2"
    SIMPLE_CMS_ENCRYPT = "simple_cms_encrypt"
    SIMPLE_CMS_ENCRYPT2 = "simple_cms_encrypt2"
    DELETE_PASSWORD = "delete_password"
    DELETE_CERT = "delete_cert"
    DELETE_CONTAINER = "delete_container"
