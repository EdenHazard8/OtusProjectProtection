import sys
import ctypes
import argparse
import os
from pyjcpkcs11 import pyjcpkcs11


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', default="jcPKCS11-2.dll", help='jcPKCS11 library path')
    args = parser.parse_args()

    library_path = os.path.abspath(args.library)

    lib = ctypes.CDLL(library_path)
    
    status = lib.C_Initialize(0)
    if status:
        print("C_Initialize failed with {}".format(status))
        return 1

    slots_count = ctypes.c_long(0)
    status = lib.C_GetSlotList(ctypes.c_long(1), ctypes.c_long(0), ctypes.byref(slots_count))
    if status:
        print("C_GetSlotList failed with {}".format(status))
        return 1

    if not slots_count.value:
        print("No slots")
        return 1

    slot_list = [0] * slots_count.value
    slot_list = (ctypes.c_long * slots_count.value)(*slot_list)
    status = lib.C_GetSlotList(ctypes.c_long(1), ctypes.byref(slot_list), ctypes.byref(slots_count))
    if status:
        print("C_GetSlotList failed with {}".format(status))
        return 1

    token_info = pyjcpkcs11.CK_TOKEN_INFO()
    for slot in slot_list:
        status = lib.C_GetTokenInfo(ctypes.c_long(slot), ctypes.byref(token_info))
        if status:
            print("C_GetTokenInfo failed with {}".format(status))
            continue

        print("Slot: {}; Model: {}; SerialNumber: {};".format(slot, token_info.model.decode("utf-8").strip(), 
                                                              token_info.serialNumber.decode("utf-8").strip()))
    
if __name__ == "__main__":
    sys.exit(main())