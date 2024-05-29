"""
Created on Aug 24, 2012

@author: mhughes
"""
import logging
from ctypes import byref

# Cryptoki Constants
from six import b

from .attributes import to_char_array
from .cryptoki import (CK_ULONG,
                       CK_BBOOL,
                       CK_SLOT_ID,
                       CK_MECHANISM_TYPE,
                       CK_MECHANISM_INFO)
from .defaults import ADMIN_PARTITION_LABEL, ADMIN_SLOT
from .defines import CKR_OK

# Cryptoki functions.
from .cryptoki import (C_InitToken,
                       C_GetSlotList,
                       C_GetMechanismList,
                       C_GetMechanismInfo,
                       CA_GetTokenPolicies,
                       JC_PKI_WipeCard,
                       JC_SetLabel,
                       JC_KT2_InitToken)
from .session_management import c_get_token_info
from .exceptions import make_error_handle_function
from .common_utils import AutoCArray
from .common_utils import refresh_c_arrays

LOG = logging.getLogger(__name__)


def c_init_token(slot_num, password, token_label='Main Token'):
    """Initializes at token at a given slot with the proper password and label

    :param slot_num: The index of the slot to c_initialize a token in
    :param password: The password to c_initialize the slot with
    :param token_label: The label to c_initialize the slot with (Default value = 'Main Token')
    :returns: The result code

    """
    LOG.info("C_InitToken: Initializing token (slot=%s, label='%s', password='%s')",
             slot_num, token_label, password)

    if password == b'':
        password = None
    password = AutoCArray(data=password)
    slot_id = CK_ULONG(slot_num)
    label = AutoCArray(data=token_label)

    return C_InitToken(slot_id,
                       password.array, password.size.contents,
                       label.array)


c_init_token_ex = make_error_handle_function(c_init_token)


def jc_pki_wipe_card(slot):
    """Wipes laser's content. Needs to be autentificated as admin

    :param slot: The index of the slot to wipe content a token in
    :returns: The result code

    """
    LOG.info("JC_PKI_WipeCard: Wiping content. slot=%s", slot)
    slot_id = CK_ULONG(slot)
    ret = JC_PKI_WipeCard(slot_id)
    return ret


jc_pki_wipe_card_ex = make_error_handle_function(jc_pki_wipe_card)


def jc_kt2_init_token(slot, user_pin, label):
    """Init token
    All sessions must be closed

    :param slot: The index of the slot
    :param userpin: Current PIN user
    :param label: Token name to change
    :returns: The result code

    """
    LOG.info("C_InitToken: Initializing token (slot=%s, label='%s', password='%s')",
             slot, label, user_pin)
    user_pin = AutoCArray(data=user_pin)
    label = AutoCArray(data=label)

    ret = JC_KT2_InitToken(CK_SLOT_ID(slot), user_pin.array, user_pin.size.contents, label.array)

    return ret


jc_kt2_init_token_ex = make_error_handle_function(jc_kt2_init_token)


def jc_set_label(slot, label):
    """Changes applet's label

    :param slot: The index of the slot to change label in
    :param label: Applet's name to change. Must be string or list of string
    :returns: The result code

    """
    LOG.info("JC_SetLabel: Changing label to %s in slot=%s", label, slot)
    slot_id = CK_ULONG(slot)
    c_label = AutoCArray(data=label)
    ret = JC_SetLabel(slot_id, c_label.array, c_label.size.contents)

    return ret


jc_set_label_ex = make_error_handle_function(jc_set_label)


def get_token_by_label(label):
    """Iterates through all the tokens and returns the first token that
    has a label that is identical to the one that is passed in

    :param label: The label of the token to search for
    :returns: The result code, The slot of the token

    """

    if label == ADMIN_PARTITION_LABEL:
        # XXX the admin partition's label changes depending on
        # the boards state
        #        ret, slot_info = get_slot_info("Viper")
        #        return ret, slot_info.keys()[1]
        return CKR_OK, ADMIN_SLOT

    slot_list = AutoCArray()

    @refresh_c_arrays(1)
    def _get_slot_list():
        """Closure
        """
        return C_GetSlotList(CK_BBOOL(1), slot_list.array, slot_list.size)

    ret = _get_slot_list()
    if ret != CKR_OK:
        return ret, None

    for slot in slot_list:
        ret, token_info = c_get_token_info(slot)
        if token_info['label'] == label:
            return ret, slot

    raise Exception("Slot with label " + str(label) + " not found.")


get_token_by_label_ex = make_error_handle_function(get_token_by_label)


def c_get_mechanism_list(slot):
    """Gets the list of mechanisms from the HSM

    :param slot: The slot number to get the mechanism list on
    :returns: The result code, A python dictionary representing the mechanism list

    """
    slot_id = CK_ULONG(slot)
    mech = AutoCArray(ctype=CK_MECHANISM_TYPE)

    @refresh_c_arrays(1)
    def _c_get_mech_list():
        """Closure for retry to work w/ properties.
        """
        return C_GetMechanismList(slot_id, mech.array, mech.size)

    ret = _c_get_mech_list()
    return ret, [x for x in mech]


c_get_mechanism_list_ex = make_error_handle_function(c_get_mechanism_list)


def c_get_mechanism_info(slot, mechanism_type):
    """Gets a mechanism's info

    :param slot: The slot to query
    :param mechanism_type: The type of the mechanism to get the information for
    :returns: The result code, The mechanism info

    """
    mech_info = CK_MECHANISM_INFO()
    ret = C_GetMechanismInfo(CK_ULONG(slot), CK_MECHANISM_TYPE(mechanism_type), byref(mech_info))
    return ret, mech_info


c_get_mechanism_info_ex = make_error_handle_function(c_get_mechanism_info)


def ca_get_token_policies(slot):
    """
    Get the policies of the given slot.

    :param int slot: Target slot number
    :return: retcode, {id: val} dict of policies (None if command failed)
    """
    slot_id = CK_ULONG(slot)
    pol_ids = AutoCArray()
    pol_vals = AutoCArray()

    @refresh_c_arrays(1)
    def _get_token_policies():
        """Closure for retries to work w/ properties.
        """
        return CA_GetTokenPolicies(slot_id, pol_ids.array, pol_ids.size,
                                   pol_vals.array, pol_vals.size)

    ret = _get_token_policies()

    return ret, dict(list(zip(pol_ids, pol_vals)))


ca_get_token_policies_ex = make_error_handle_function(ca_get_token_policies)
