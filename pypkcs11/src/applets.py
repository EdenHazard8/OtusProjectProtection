import abc
import time
import typing

from .constants import DICT_TEMPLATE
from pycryptoki.exceptions import LunaCallException
from pycryptoki.object_attr_lookup import c_find_objects_ex
from pycryptoki.session_management import (
    c_initialize_ex,
    c_finalize_ex,
    c_get_slot_list_ex,
    c_open_session_ex,
    login_ex,
    c_logout_ex,
    c_get_token_info_ex,
    c_init_pin_ex,
    c_set_pin_ex,
    c_get_slot_info_ex,
)
from pycryptoki.token_management import c_init_token_ex, jc_kt2_init_token_ex
from pycryptoki import defaults
from pycryptoki import defines
from pycryptoki.key_generator import c_generate_key_pair_ex


class FindSlotException(Exception):
    def __str__(self):
        return "Ошибка при поиске слота"


class LabelNameException(Exception):
    def __str__(self):
        return "Ошибка при установке метки"


class FindAppletException(Exception):
    def __str__(self):
        return "Ошибка при поиске апплета"


class ErrorAppletException(Exception):
    def __str__(self):
        return "Ошибка при работе с апплетом"


class GenKeyPairException(Exception):
    def __str__(self):
        return "Ошибка при генерации ключевой пары"


class Applet(abc.ABC):
    def __init__(
        self,
        path_to_pks11: str,
        serial_number: str,
        applet_model: str
    ):
        self._serial_number = serial_number
        self._applet_model = applet_model

        # Тут указывается p11-библиотека используемая pycryptoki
        defaults.CHRYSTOKI_DLL_FILE = (
            path_to_pks11
        )

    def __enter__(self):
        c_initialize_ex()

    def __exit__(self, exc_type, exc_val, exc_tb):
        c_finalize_ex()

    def _login(self, slot: int, pin: str, user_type: int = defines.CKU_USER) -> int:
        session = c_open_session_ex(slot)
        login_ex(session, slot, pin, user_type)

        return session

    def _logout(self, session: int) -> None:
        c_logout_ex(session)

    def _slot_definition(self) -> str:
        slots = c_get_slot_list_ex()
        for slot in slots:
            token = c_get_token_info_ex(slot)
            model = token["model"].decode("utf-8")
            serial_number = token["serialNumber"].decode("utf-8")

            if (
                model == self._applet_model and
                serial_number == self._serial_number
            ):
                return slot

    # Необходимо, если несколько апплетов.
    # После инициализации токен может "отвалиться"
    def _check_slot(func) -> typing.Callable:
        def wrapped(self, *args, **kwargs):
            timeout = 30
            current_time = 0
            start = time.time()
            while not self._slot_definition():
                time.sleep(1)
                current_time = time.time() - start
                if current_time > timeout:
                    raise FindSlotException
            func(self, *args, **kwargs)

        return wrapped

    def _change_pin(self, old_pin: str, user_pin: str) -> None:
        slot = self._slot_definition()
        if slot is None:
            raise FindSlotException
        session = c_open_session_ex(slot)
        c_set_pin_ex(session, old_pin, user_pin)

    def _get_objects(self, user_pin: str) -> typing.Dict[str, int]:
        slot = self._slot_definition()
        if slot is None:
            raise FindSlotException
        user_session = self._login(slot, user_pin)
        dict_objects = {}
        for key, value in DICT_TEMPLATE.items():
            keys = c_find_objects_ex(user_session, {defines.CKA_CLASS: value}, 10)
            dict_objects[key] = len(keys)

        self._logout(user_session)

        return dict_objects

    def _get_token_info(self):
        slot = self._slot_definition()
        return c_get_token_info_ex(slot)

    def _get_reader(self) -> str:
        slot_info = self._get_slot_info()
        slot_description = slot_info["slotDescription"].decode("utf-8")
        return slot_description

    def _get_slot_info(self):
        slot = self._slot_definition()
        if slot is None:
            raise FindSlotException
        try:
            return c_get_slot_info_ex(slot)
        except LunaCallException:
            raise ErrorAppletException

    def _generate_key_pair(
        self, mechanism, pub_template, priv_template, user_pin
    ):
        slot = self._slot_definition()
        if slot is None:
            raise FindSlotException
        user_session = self._login(slot, user_pin)

        try:
            handles = c_generate_key_pair_ex(
                user_session,
                mechanism,
                pub_template,
                priv_template,
            )
        except LunaCallException:
            raise GenKeyPairException

        return handles

    @classmethod
    def get_names(cls) -> typing.Tuple[str]:
        return cls._names

    @abc.abstractmethod
    def format(self) -> None:
        pass

    @abc.abstractmethod
    def change_pin(self) -> None:
        pass

    @abc.abstractmethod
    def get_objects(self) -> typing.Dict[str, int]:
        pass

    @abc.abstractmethod
    def get_reader(self) -> str:
        pass

    @abc.abstractmethod
    def login(self) -> None:
        pass

    @abc.abstractmethod
    def get_token_info(self):
        pass

    @abc.abstractmethod
    def get_slot_info(self):
        pass

    @abc.abstractmethod
    def get_slot(self):
        pass


class AppletSelector:
    _applets = []

    @staticmethod
    def register_applet(applet):
        AppletSelector._applets.append(applet)
        return applet

    @staticmethod
    def get_applet(applet_model: str):
        for applet in AppletSelector._applets:
            if applet_model in applet.get_names():
                return applet

        raise FindAppletException


@AppletSelector.register_applet
class Laser(Applet):
    _names = ("JaCarta Laser", "PRO", "eToken")

    @Applet._check_slot
    def format(self, user_pin: str, so_pin: str, label_name="jc test") -> None:
        slot = self._slot_definition()
        if slot is None:
            raise FindSlotException
        if len(label_name) > 32:
            raise LabelNameException

        label_name += + (32 - len(label_name)) * " "
        try:
            # Есть какое-то правило на 32 символа
            c_init_token_ex(
                slot,
                so_pin,
                label_name,
            )
            so_session = self._login(slot, so_pin, 0)
            c_init_pin_ex(so_session, user_pin)
            self._logout(so_session)
        except LunaCallException:
            raise ErrorAppletException

    def change_pin(self, old_pin: str, user_pin: str) -> None:
        self._change_pin(old_pin, user_pin)

    def get_token_info(self):
        return self._get_token_info()

    def get_slot_info(self):
        return self._get_slot_info()

    def get_slot(self):
        return self._slot_definition()

    def get_objects(self, pin: str) -> typing.Dict[str, int]:
        return self._get_objects(pin)

    def get_reader(self) -> str:
        return self._get_reader()

    def login(self, pin: str) -> None:
        slot = self._slot_definition()
        if slot is None:
            raise FindSlotException
        session = self._login(slot, pin)
        self._logout(session)

    def generate_rsa_key_pair(
        self, user_pin: str, key_size=1024, container_name="test"
    ) -> typing.Tuple[int, int]:
        mechanism = defines.CKM_RSA_PKCS_KEY_PAIR_GEN
        pub_template = {
            defines.CKA_ID: container_name,
            defines.CKA_LABEL: container_name,
            defines.CKA_TOKEN: defines.CK_TRUE,
            defines.CKA_ENCRYPT: defines.CK_TRUE,
            defines.CKA_VERIFY: defines.CK_TRUE,
            defines.CKA_WRAP: defines.CK_TRUE,
            defines.CKA_MODULUS_BITS: key_size,
            defines.CKA_PUBLIC_EXPONENT: [0x01, 0x00, 0x01],
        }
        priv_template = {
            defines.CKA_ID: container_name,
            defines.CKA_LABEL: container_name,
            defines.CKA_TOKEN: defines.CK_TRUE,
            defines.CKA_PRIVATE: defines.CK_TRUE,
            defines.CKA_SENSITIVE: defines.CK_TRUE,
            defines.CKA_DECRYPT: defines.CK_TRUE,
            defines.CKA_SIGN: defines.CK_TRUE,
            defines.CKA_UNWRAP: defines.CK_TRUE,
        }

        return self._generate_key_pair(
            mechanism, pub_template, priv_template, user_pin)


@AppletSelector.register_applet
class DataStore(Applet):
    _names = ("JaCarta DS")

    @Applet._check_slot
    def format(self, user_pin: str, so_pin: str, label_name="jc test") -> None:
        slot = self._slot_definition()
        if slot is None:
            raise FindSlotException
        if len(label_name) > 32:
            raise LabelNameException

        label_name += (32 - len(label_name)) * " "
        try:
            # Есть какое-то правило на 32 символа
            c_init_token_ex(
                slot,
                so_pin,
                label_name,
            )
            user_session = self._login(slot, so_pin, 1)
            c_set_pin_ex(user_session, so_pin, user_pin)
            self._logout(user_session)
        except LunaCallException:
            raise ErrorAppletException

    def change_pin(self, old_pin: str, user_pin: str) -> None:
        self._change_pin(old_pin, user_pin)

    def get_objects(self, pin: str) -> typing.Dict[str, int]:
        return self._get_objects(pin)

    def get_reader(self) -> str:
        return self._get_reader()

    def get_token_info(self):
        return self._get_token_info()

    def get_slot_info(self):
        return self._get_slot_info()

    def get_slot(self):
        return self._slot_definition()

    def login(self, pin: str) -> None:
        slot = self._slot_definition()
        if slot is None:
            raise FindSlotException
        session = self._login(slot, pin)
        self._logout(session)


@AppletSelector.register_applet
class Cryptotoken2(Applet):
    _names = ("JaCarta GOST 2.0")

    @Applet._check_slot
    def format(self, user_pin: str, so_pin: str, label_name="jc test") -> None:
        slot = self._slot_definition()
        if slot is None:
            raise FindSlotException
        if len(label_name) > 32:
            raise LabelNameException

        label_name += (32 - len(label_name)) * " "
        try:
            # Есть какое-то правило на 32 символа
            jc_kt2_init_token_ex(
                slot,
                user_pin,
                label_name,
            )
        except LunaCallException:
            raise ErrorAppletException

    def change_pin(self, old_pin: str, user_pin: str) -> None:
        self._change_pin(old_pin, user_pin)

    def get_objects(self, pin: str) -> typing.Dict[str, int]:
        return self._get_objects(pin)

    def get_reader(self) -> str:
        return self._get_reader()

    def get_token_info(self):
        return self._get_token_info()

    def get_slot_info(self):
        return self._get_slot_info()

    def get_slot(self):
        return self._slot_definition()

    def login(self, pin: str) -> None:
        slot = self._slot_definition()
        if slot is None:
            raise FindSlotException
        session = self._login(slot, pin)
        self._logout(session)

    def generate_gost_256_key_pair(self, user_pin, container_name="test"):
        mechanism = defines.CKM_GOSTR3410_KEY_PAIR_GEN
        public_key_template = {
            defines.CKA_CLASS: defines.CKO_PUBLIC_KEY,
            defines.CKA_ID: container_name,
            defines.CKA_LABEL: container_name,
            defines.CKA_KEY_TYPE: defines.CKK_GOSTR3410,
            defines.CKA_TOKEN: defines.CK_TRUE,
            defines.CKA_PRIVATE: defines.CK_FALSE,
            defines.CKA_GOSTR3410_PARAMS: defines.STR_CRYPTO_PRO_GOST3410_2012,
            defines.CKA_GOSTR3411_PARAMS: defines.STR_CRYPTO_PRO_GOST3411_2012,
        }
        private_key_template = {
            defines.CKA_CLASS: defines.CKO_PRIVATE_KEY,
            defines.CKA_ID: container_name,
            defines.CKA_LABEL: container_name,
            defines.CKA_KEY_TYPE: defines.CKK_GOSTR3410,
            defines.CKA_TOKEN: defines.CK_TRUE,
            defines.CKA_PRIVATE: defines.CK_TRUE,
            defines.CKA_DERIVE: defines.CK_TRUE,
            defines.CKA_GOSTR3410_PARAMS: defines.STR_CRYPTO_PRO_GOST3410_2012,
            defines.CKA_GOSTR3411_PARAMS: defines.STR_CRYPTO_PRO_GOST3411_2012,
        }

        return self._generate_key_pair(
            mechanism, public_key_template, private_key_template, user_pin)
