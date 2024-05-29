import os
import subprocess
import requests
from sys import platform


class USBRedirectorAPI:

    _paths_win32 = (r"C:\Program Files\USB Redirector Client\usbrdrltsh.exe",
                    "./usbrdrltsh.exe")
    _paths_unix = ("/usr/local/bin/usbclnt", "./usbclnt")

    def __init__(self, server_ip, client_path=None, server_api_port=80,
                 server_port=45696):
        self.client_path = client_path
        self.server_ip = server_ip
        self.server_api_port = server_api_port
        self.server_port = server_port
        self._path_exists()

    def _path_exists(self):
        if platform == "win32":
            paths = self._paths_win32
        else:
            paths = self._paths_unix

        if self.client_path is None:
            for i in paths:
                self.client_path = i
                if os.path.exists(i):
                    break

    def _check_usb(self, port, serial):
        list_usb = self.list_usb()
        for usb in list_usb:
            if 'Port' in usb:
                if port == usb['Port']:
                    return True
            elif 'Serial' in usb:
                if serial == usb['Serial']:
                    return True
        return False

    def is_client_exists(self):
        return os.path.isfile(self.client_path)

    def connect_server(self):
        command = ["{}".format(self.client_path), "-addserver", "-server", 
                   "{}:{}".format(str(self.server_ip), str(self.server_port))]
        subprocess.Popen(command, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)

    def list_usb(self):
        response = requests.get(
            'http://{}:{}/api/devices'.format(str(self.server_ip), 
            str(self.server_api_port)), timeout=(5, 30))

        if response.status_code != 200:
            raise ConnectionError()

        return response.json()['Devices']

    def share_usb(self, port=None, serial=None):
        if self._check_usb(port=port, serial=serial) is False:
            raise ValueError()

        if port is not None:
            data = {'Port': str(port)}
        elif serial is not None:
            data = {'Serial': str(serial)}
        else:
            raise ValueError()

        response = requests.post(
            'http://{}:{}/api/device/share'.format(str(self.server_ip), 
            str(self.server_api_port)), data=data, timeout=(5, 30))

        if response.status_code != 200:
            raise ConnectionError()

    def connect_usb(self, port=None, serial=None, force=True):
        if self._check_usb(port=port, serial=serial) is False:
            raise ValueError()

        if force:
            self.connect_server()
            self.share_usb(port=port, serial=serial)

        command = ["{}".format(self.client_path), "-connect", "-server",
                   "{}:{}".format(str(self.server_ip), str(self.server_port))]

        if port is not None:
            command.extend(["-usbport", "{}".format(port)])
        elif serial is not None:
            command.extend(["-serial", "{}".format(serial)])
        else:
            raise ValueError()

        connect = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        result = connect.wait()
        if result != 0:
            raise ValueError('Connect usb failed')

        self.autoconnect_on(port=port, serial=serial)

    def autoconnect_on(self, port=None, serial=None):
        if self._check_usb(port=port, serial=serial) is False:
            raise ValueError()
        command = ["{}".format(self.client_path), "-autoconnect", "on", "-server",
                   "{}:{}".format(str(self.server_ip), str(self.server_port))]

        if port is not None:
            command.extend(["-usbport", "{}".format(port)])
        elif serial is not None:
            command.extend(["-serial", "{}".format(serial)])
        else:
            raise ValueError()

        connect = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        result = connect.wait()
        if result != 0:
            raise ValueError('Autoconnect_on failed')

    def autoconnect_off(self, port=None, serial=None):
        if self._check_usb(port=port, serial=serial) is False:
            raise ValueError()
        command = ["{}".format(self.client_path), "-autoconnect", "off", "-server",
                   "{}:{}".format(str(self.server_ip), str(self.server_port))]

        if port is not None:
            command.extend(["-usbport", "{}".format(port)])
        elif serial is not None:
            command.extend(["-serial", "{}".format(serial)])
        else:
            raise ValueError()

        connect = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        result = connect.wait()
        if result != 0:
            raise ValueError('Autoconnect_off failed')

    def disconnect_usb(self, port=None, serial=None, force=False):
        if self._check_usb(port=port, serial=serial) is False:
            raise ValueError()

        command = ["{}".format(self.client_path), "-disconnect", "-server",
                   "{}:{}".format(str(self.server_ip), str(self.server_port))]

        if port is not None:
            command.extend(["-usbport", "{}".format(port)])
        elif serial is not None:
            command.extend(["-serial", "{}".format(serial)])
        else:
            raise ValueError()

        connect = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        result = connect.wait()
        if result != 0:
            raise ValueError('Disconnect usb failed')

        if force:
            self.unshare_usb(port=port, serial=serial)
            self.disconnect_server()

    def unshare_usb(self, port=None, serial=None):
        if self._check_usb(port=port, serial=serial) is False:
            raise ValueError()
        if port is not None:
            data = {'Port': str(port)}
        elif serial is not None:
            data = {'Serial': str(serial)}
        else:
            raise ValueError()

        response = requests.post(
            'http://{}:{}/api/device/unshare'.format(str(self.server_ip), 
            str(self.server_api_port)), data=data, timeout=(5, 30))

        if response.status_code != 200:
            raise ConnectionError()

    def disconnect_server(self):
        command = ["{}".format(self.client_path), "-remserver", "-server",
                   "{}:{}".format(str(self.server_ip), str(self.server_port))]
        connect = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        result = connect.wait()

        if result != 0:
            raise ValueError('Disconnect server failed')
