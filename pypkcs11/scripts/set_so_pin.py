import argparse
import os
import json
import sys

from pycryptoki.session_management import *
from pycryptoki.token_management import *
from pycryptoki import defaults


def finding_applets(list_slots):
    applets = {}
    support_applets = ["JaCarta Laser", "JaCarta DS", "PRO"]
    
    for x in range(len(list_slots)):
        slot = c_get_slot_list_ex()[x]
        applet = c_get_token_info_ex(slot)['model'].decode("utf-8")
        serial = c_get_token_info_ex(slot)['serialNumber'].decode("utf-8")

        if applet in support_applets:
            applets[f'find #{x}'] = {
              "applet" : applet,
              "serial" : serial,
              "slot" : slot
            }             
    return applets

def set_admin_pin(slot, current_so_pin, new_so_pin):
    session = c_open_session_ex(slot)
    login_ex(session, slot, current_so_pin, 0)
    c_set_pin_ex(session, current_so_pin, new_so_pin)

def main():
    parsarg = argparse.ArgumentParser()

    set_pin_admin_conf = parsarg.add_argument_group('set_pin_admin_conf')
    set_pin_admin = parsarg.add_argument_group('set_admin_pin')
    parsarg.add_argument('--PKCS11_library', help='path to .dll', required=True)
    set_pin_admin_conf.add_argument('--config_set_so_pin', help='path to config with passwords')
    set_pin_admin.add_argument('--current_so_pin', type=str, help='current admin password')
    set_pin_admin.add_argument('--new_so_pin', type=str, help='new admin password')
    set_pin_admin.add_argument('--applet', type=str, help='applet')

    args = parsarg.parse_args()
    
    if os.path.exists(args.PKCS11_library) is True:
        defaults.CHRYSTOKI_DLL_FILE = args.PKCS11_library
    else:
        raise Exception("PKCS11_library not found")
    
    c_initialize_ex()

    list_slots = c_get_slot_list_ex()
    
    if list_slots == []:
        raise Exception("no connected applets")
    else:
        found_applets = finding_applets(list_slots)
        if len(found_applets) == 0:
            raise Exception("no supported applets found")
        else:
            print(found_applets)

    if args.config_set_so_pin:
        args.config_set_so_pin = os.path.abspath(args.config_set_so_pin)
        with open(args.config_set_so_pin, "r") as config_passwords:
            data = json.loads(config_passwords.read())
        for x in found_applets:
            applet = found_applets[x]["applet"]
            slot = found_applets[x]["slot"]

            if applet in data:
                set_admin_pin(slot, data[applet]["current_so_pin"], data[applet]["new_so_pin"])   

    elif (args.current_so_pin and args.new_so_pin and args.applet):         
        for x in found_applets:
            if args.applet == found_applets[x]["applet"]:
                slot = found_applets[x]["slot"]
                set_admin_pin(slot, args.current_so_pin, args.new_so_pin)
    else:
        raise Exception("No related parameters found")
    
    c_finalize_ex()
    return 0

if __name__ == "__main__":
    sys.exit(main())