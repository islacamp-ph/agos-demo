import sys
from smoke_test import bapi, token_for

# Prints a Clerk sign-in ticket for UI testing: python mk_ticket.py <email>
_, uid = token_for(sys.argv[1])
print(bapi("/sign_in_tokens", {"user_id": uid, "expires_in_seconds": 900})["token"])
