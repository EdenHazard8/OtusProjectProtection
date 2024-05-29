## Pycryptoki
[![Doc Status](https://readthedocs.org/projects/pycryptoki/badge/?version=latest)](http://pycryptoki.readthedocs.io/en/latest/)

Pycryptoki is a python wrapper around the PKCS11 library.

## Внесенные изменения

##### Добавлен параметр определяющий конвертирование вывода в attributes.to_byte_array [коммит](http://gitlab.aladdin.ru/TestDep/pycryptoki/commit/3ba767fdb2235a88b7f30b13a7de7b8bec92a23f)

##### Добавлен механизм CKM_GOSTR3410_KEY_PAIR_GEN [коммит](http://gitlab.aladdin.ru/TestDep/pycryptoki/commit/1b62d4763109c6d180dcc356ed046b9204d961ff)

##### Добавлена поддержка JC_PKI_WipeCard [коммит](http://gitlab.aladdin.ru/TestDep/pycryptoki/commit/3af2b0efa2046b1f211c2ec4456371e55a8850f5)

##### Добавлена поддержка JC_PKI_UnlockUserPIN [коммит](http://gitlab.aladdin.ru/TestDep/pycryptoki/commit/e9178799958334e640cb1ef5feef7fef7d4fcc71)

##### Добавлена поддержка JC_SetLabel [коммит](http://gitlab.aladdin.ru/TestDep/pycryptoki/commit/b53fc1e753dc738d241905f443e0377372749ff9)

##### Добавлена поддержка JC_CreateCertificateRequest [коммит](http://gitlab.aladdin.ru/TestDep/pycryptoki/commit/8e01284d689fd823ff312513714b575bba4d9723)

##### Добавлена поддержка freeBuffer [коммит](http://gitlab.aladdin.ru/TestDep/pycryptoki/commit/1f1f7437139b79051f730d7a51d1c63f9fdb2f85)


## Documentation

Latest API documentation can be found on [readthedocs](http://pycryptoki.readthedocs.io/en/latest/index.html).


## Installation

pip install git+https://github.com/gemalto/pycryptoki

## Key Generation Example

```py
from pycryptoki.default_templates import *
from pycryptoki.defines import *
from pycryptoki.key_generator import *
from pycryptoki.session_management import *
from pycryptoki.encryption import *


c_initialize_ex()
auth_session = c_open_session_ex(0)   # HSM slot # in this example is 0
login_ex(auth_session, 0, 'userpin')  # 0 is still the slot number, ‘userpin’ should be replaced by your password (None if PED or no challenge)

# Get some default templates
# They are simple python dictionaries, and can be modified to suit needs.
pub_template, priv_template = get_default_key_pair_template(CKM_RSA_PKCS_KEY_PAIR_GEN)

# Modifying template would look like:
pub_template[CKA_LABEL] = "RSA PKCS Pub Key"
pub_template[CKA_MODULUS_BITS] = 2048   # 2048 key size

pubkey, privkey = c_generate_key_pair_ex(auth_session, CKM_RSA_PKCS_KEY_PAIR_GEN, pub_template, priv_template)
print("Generated Private key at %s and Public key at %s" % (privkey, pubkey))

c_logout_ex(auth_session)
c_close_session_ex(auth_session)
c_finalize_ex()
```
## Verbose logging

If you want to see what calls to the C library are being performed, set pycryptoki logging to `DEBUG`:

```py
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Tests

Test requirements can be installed via `pip install -r test_requirements.txt`.

Unittests can be run on any environment via:
```
py.test tests/unittests
```

Functional tests require an HSM to test against, and will actively test the integration
 with the libCryptoki library. This *will* create and destroy objects on the HSM, so don't run
  on a production HSM!

```
py.test tests/functional --slot=<slot_num> [--reset] [--password=<pwd>] [--copassword=<pwd>] [--user=<user>] [--loglevel=<level>]
```
