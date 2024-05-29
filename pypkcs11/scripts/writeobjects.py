import time
import os
import argparse
import time
import string
import random
from pycryptoki import defaults
from pycryptoki.session_management import (c_initialize_ex, c_finalize_ex, c_open_session_ex, login_ex, c_logout_ex,
    c_close_session_ex, c_get_slot_list_ex, c_get_token_info_ex)
from pycryptoki.misc import (c_create_object_ex)
from pycryptoki.object_attr_lookup import (c_find_objects_ex, c_get_attribute_value_ex)
from pycryptoki.key_generator import (c_destroy_object_ex)
from pycryptoki.defines import (CKU_USER, CKA_CLASS, CKO_DATA, CKA_TOKEN, CKA_LABEL, CKA_VALUE)
import itertools
import datetime
from shutil import copyfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', default="jcPKCS11-2.dll", help='jcPKCS11 library path')
    parser.add_argument('--slot', type=int, help='Applet slot')
    parser.add_argument('--show_slots', action="store_true", help='Show slots')
    parser.add_argument('--pin', help='token user pin')
    parser.add_argument('--start_size', type=int, default=512, help='Start data size')
    parser.add_argument('--stop_size', type=int, default=20480, help='Stop data size')
    parser.add_argument('--step_size', type=int, default=512, help='Increase data step size')
    parser.add_argument('--cycles', type=int, default=1, help='How many times execute operations. If set "0" testing '\
        'will runs forever with --start_size object')
    parser.add_argument('--random_size', action='store_true', help='If --cycles "0", size of write data will be '\
        'from --start_size to --stop_size')
    parser.add_argument('--no_delete', action='store_true', help='Do not delete created objects')
    parser.add_argument('--one_session', action='store_true', help='Open only one session while testing')
    parser.add_argument('--one_login', action='store_true', help='Login only one time while testing')
    parser.add_argument('--log_file', help='Path to log file')
    parser.add_argument('--do_backup', action='store_true', help='Do backup files')
    parser.add_argument('--backup_lines', type=int, default=10000, help='Number of backup lines')
    args = parser.parse_args()

    defaults.CHRYSTOKI_DLL_FILE = args.library
    c_initialize_ex()

    if args.show_slots:
        slots = c_get_slot_list_ex()

        print("Slots:")

        if len(slots):
            for slot in slots:
                token_info = c_get_token_info_ex(slot)

                print(f"{slot}: {token_info['serialNumber'].decode('utf-8')} {token_info['model'].decode('utf-8')}")
        else:
            print("No slots found")

        return 0

    template = {CKA_CLASS: CKO_DATA, CKA_TOKEN: True, CKA_LABEL: None, CKA_VALUE: None}

    args.slot = int(args.slot)

    start_size = args.start_size
    stop_size = args.stop_size
    step_size = args.step_size
    current_size = start_size

    need_to_session = True
    need_to_login = True

    while current_size <= stop_size:
        for i in range(args.cycles) if args.cycles > 0 else itertools.count():
            if need_to_session:
                session = c_open_session_ex(args.slot)

                need_to_session = False if args.one_session else True

            if need_to_login:
                login_ex(session, args.slot, args.pin, CKU_USER)

                need_to_login = False if args.one_login else True

            template[CKA_LABEL] = "".join(random.choice(string.ascii_letters + string.digits) for _ in range(6))

            if args.random_size and args.cycles <= 0:
                current_size = random.randint(args.start_size, args.stop_size)

            template[CKA_VALUE] = os.urandom(current_size)

            temp_time = time.time()
            obj_handle = c_create_object_ex(session, template)
            write_time = time.time() - temp_time
            if obj_handle == 0:
                print("Error while writing data. Size: {}".format(current_size))
                return 1

            temp_time = time.time()
            obj_handle = c_find_objects_ex(session, template, 1)
            find_time = time.time() - temp_time
            if not len(obj_handle) or obj_handle[0] == 0:
                print("Error while finding data. Size: {}".format(current_size))
                return 1

            obj_handle = obj_handle[0]

            temp_time = time.time()
            read_template = {CKA_VALUE: None}
            obj_data = c_get_attribute_value_ex(session, obj_handle, read_template, to_hex=False)
            read_time = time.time() - temp_time
            if obj_data is None or CKA_VALUE not in obj_data:
                print("Error while reading data. Size: {}".format(current_size))
                return 1

            obj_data = obj_data[CKA_VALUE]

            if obj_data != template[CKA_VALUE]:
                print("DATA ERROR! Size: {}".format(current_size))
                return 1
            
            temp_time = time.time()
            if not args.no_delete:
                c_destroy_object_ex(session, obj_handle)
            delete_time = time.time() - temp_time

            log_string = "{}:\t\t{}\t\tWRITE: {:.7f}\t\tFIND: {:.7f}\t\tREAD: {:.7f}\t\tDELETE: {:.7f}".format(i + 1,
                current_size, write_time, find_time, read_time, delete_time if not args.no_delete else 0)

            print(log_string)

            if need_to_login:
                c_logout_ex(session)

            if need_to_session:
                c_close_session_ex(session)

            if args.log_file is not None and len(args.log_file):
                with open(args.log_file, "a") as log_file:
                    log_file.write(f"{datetime.datetime.now()}\t{log_string}\n")

            if args.do_backup is not None:
                if not ((i + 1) % args.backup_lines):
                    copyfile(args.log_file, f"{args.log_file}.{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}")
                    os.remove(args.log_file)

        current_size += step_size

    c_finalize_ex()

if __name__ == "__main__":
    main()