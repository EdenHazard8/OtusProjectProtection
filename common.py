from abc import ABC, abstractmethod
from errors import ERRORS


class ICommand(ABC):
    @abstractmethod
    def execute(self, command):
        pass


class Command:
    def __init__(self):
        self.store = []

    def add_command(self, command):
        self.store.append(command)

    def run_command(self):
        return self.store.pop(0).execute()

    def clear(self):
        self.store.clear()


class ExceptionHandler:
    errors = ERRORS

    @classmethod
    def handle(clt, e, c):
        command = c.__class__.__name__
        exception = e.__class__.__name__

        raise Exception(clt.errors[command][exception])
