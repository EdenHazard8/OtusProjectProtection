"""
Exception-s and exception handling code.
"""
import inspect
import logging
from functools import wraps

from six import integer_types

from .defines import CKR_OK
from .lookup_dicts import ret_vals_dictionary, ATTR_NAME_LOOKUP

LOG = logging.getLogger(__name__)


def make_error_handle_function(luna_function):
    """This function is a helper function that creates a new function which checks the
    result code returned from a function in luna. It is called by calling::

        c_generate_key_pair_ex = make_error_handle_function(c_generate_key_pair)

    This code will create a c_generate_key_pair_ex which will call c_generate_key_pair and check the
    first argument. The first argument is the return code of c_generate_key_pair. If the return
    code != CKR_OK then c_generate_key_pair_ex will raise a LunaCallException. You can call
    c_generate_key_pair_ex as if it is c_generate_key_pair::

        c_generate_key_pair_ex(h_session, CKM_RSA_PKCS_KEY_PAIR_GEN,
                               CKM_RSA_PKCS_KEY_PAIR_GEN_PUBTEMP,
                               CKM_RSA_PKCS_KEY_PAIR_GEN_PRIVTEMP)

    The return values of c_generate_pair are (ret, public_key_handle, private_key_handle)

    The return values of c_generate_pair_ex are (public_key_handle, private_key_handle)

    This lets you create two versions of a function. One version is for setup and
    the other version is for testing the result.

    Directly testing the result::

        ret = c_initialize()
        assert ret == CKR_SOME_ERROR_CODE, "This test case will fail if this condition is not met"

    Expecting the call to go through without error. The test case should have an error (not a
    failure)::

        c_initialize_ex()

    This should therefore make for shorter test cases

    :param luna_function: Function object to wrap.
    """

    @wraps(luna_function)
    def luna_function_exception_handle(*args, **kwargs):
        """

        :param *args:
        :param **kwargs:

        """
        return_tuple = luna_function(*args, **kwargs)
        if isinstance(return_tuple, tuple):
            if len(return_tuple) > 2:
                return_data = return_tuple[1:]
                ret = return_tuple[0]
            elif len(return_tuple) == 2:
                return_data = return_tuple[1]
                ret = return_tuple[0]
            else:
                return_data = return_tuple[0]
                ret = return_tuple[0]
        elif isinstance(return_tuple, integer_types):
            ret = return_tuple
            return_data = return_tuple
        else:
            raise Exception(
                "Functions wrapped by the exception handler should return a tuple or just the "
                "long representing Luna's return code.")

        check_luna_exception(ret, luna_function, args, kwargs)
        return return_data

    luna_function_exception_handle.__doc__ = """Executes :py:func:`{}`, and checks the
retcode; raising an exception if the return code is not CKR_OK.

    .. note:: By default, this will not return the return code if the function returns additional
        data.

        Example::

            retcode, key_handle = c_generate_key(...)
            #vs
            key_handle = c_generate_key_ex(...)

        If the function *only* returns the retcode, then that will still be returned::

            retcode = c_seed_random(...)
            retcode = c_seed_random_ex(...)


    """.format(luna_function.__name__)
    return luna_function_exception_handle


def check_luna_exception(ret, luna_function, args, kwargs):
    """
    Check the return code from cryptoki.dll, and if it's non-zero raise an
    exception with the error code looked up.

    :param ret: Return code from the C call
    :param luna_function: pycryptoki function that was called
    :param args: Arguments passed to the pycryptoki function.
    """
    log_list = []
    all_args = inspect.getcallargs(luna_function, *args, **kwargs)
    for key, value in all_args.items():
        if "template" in key and isinstance(value, dict):
            # Means it's a template, so let's perform a lookup on all of the objects within
            # this.
            log_list.append("\t\t%s: " % key)
            for template_key, template_value in all_args[key].items():
                log_list.append("\t\t\t%s: %s" % (ATTR_NAME_LOOKUP.get(template_key, template_key),
                                                  template_value))
        elif "password" in key:
            log_list.append("\t\t%s: *" % key)
        else:
            if len(str(value)) > 20:
                msg = "\t\t%s: %s[...]%s" % (key, str(value)[:10], str(value)[-10:])
            else:
                msg = "\t\t%s: %s" % (key, value)
            log_list.append(msg)

    arg_string = "({})".format("\n".join(log_list))
    LOG.debug("Call to %s returned %s (%s)", luna_function.__name__,
              ret_vals_dictionary.get(ret, "Unknown retcode"), str(hex(ret)))
    if ret != CKR_OK:
        raise LunaCallException(ret, luna_function.__name__, arg_string)


class LunaException(Exception):
    """
    Base exception class for every custom exception raised by pycryptoki.
    """
    pass


class LunaCallException(LunaException):
    """Exceptions raised from the result of a PKCS11 call that returned a non-zero
    return code. This will attempt to look up the error code defines for human-readable output.
    """

    def __init__(self, error_code, function_name, arguments):
        """
        :param error_code: The error code of the error
        :param function_name: The name of the function
        :param arguments: The arguments passed into the function
        """
        self.error_code = error_code
        self.function_name = function_name
        self.arguments = arguments

        if self.error_code in ret_vals_dictionary:
            self.error_string = ret_vals_dictionary[self.error_code]
        else:
            self.error_string = "Unknown Code=" + str(hex(self.error_code))

    def __str__(self):
        data = ("\n\tFunction: {func_name}"
                "\n\tError: {err_string}"
                "\n\tError Code: {err_code}"
                "\n\tArguments:\n{args}").format(func_name=self.function_name,
                                                 err_string=self.error_string,
                                                 err_code=hex(self.error_code),
                                                 args=self.arguments)

        return data
