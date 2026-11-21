"""Backend import alias for the installed/native shared protected storage."""
import sys

import authority_private

sys.modules[__name__] = authority_private
