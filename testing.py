import ORB_STR_MT5 as orb
import MetaTrader5 as mt5

# Demo Account
LOGIN = 62867314
PASSWORD = "2nNh1%)w"
SERVER = "OANDATMS-MT5"

# orb.get_current_price("BTCUSD")
def initialize_trading():
    # Initialize MT5 connection
    if not mt5.initialize():
        error_msg = f"initialize() failed, error code = {mt5.last_error()}"
        # logging.error(error_msg)
        print(error_msg)
        return False
    # Connect to the account
    authorized = mt5.login(LOGIN, password=PASSWORD, server=SERVER)
    if not authorized:
        error_msg = f"Failed to connect to account {LOGIN}, error code: {mt5.last_error()}"
        # logging.error(error_msg)
        print(error_msg)
        mt5.shutdown()
        return False
    return True

initialize_trading()

# var = mt5.symbol_info("BTCUSD")

# print(var)