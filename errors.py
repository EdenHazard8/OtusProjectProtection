class CspInvokeException(Exception):
    def __str__(self):
        return "Ошибка при работе с csp_invoke"


ERRORS = {
    "FuncVipNet":
        {
            "TimeoutExpired": CspInvokeException()
        },
}
