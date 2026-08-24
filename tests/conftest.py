import os
import tempfile

import pytest


@pytest.fixture(scope="session", autouse=True)
def nandatown_home():
    """Keep keystores and attestation identities out of the real home
    directory for the whole test session."""
    with tempfile.TemporaryDirectory() as home:
        os.environ["NANDATOWN_HOME"] = home
        yield home
