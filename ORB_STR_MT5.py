import MetaTrader5 as mt5
from datetime import datetime, timedelta
from threading import Timer
import time
import logging
import json
import os

# Set up logging
log_filename = "trading_log.log"
logging.basicConfig(filename=log_filename, level=logging.DEBUG,
                    format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

logging.info("Starting the trading script.")
print("Started")
# =================== CONFIGURABLE PARAMETERS ===================
# LOGIN = 62429978
# PASSWORD = "=gK8CQ!X"

# Demo Account
LOGIN = 62867314
PASSWORD = "2nNh1%)w"
# SERVER = "OANDATMS-MT5"
SERVER = "OANDA-Demo-1"

# Define your configurable parameters here
TRADING_HOURS = [9, 10, 11, 12, 13, 14, 15, 16, 17,
                 18, 19, 20, 21, 22, 23]  # Trading hours in UTC
OPENING_RANGE_MINUTES = 4  # The first x minutes of the total range
TOTAL_RANGE_MINUTES = 15  # Total range period
LOT_SIZE = 0.01  # Lot size for orders
deviation = 20
symbol = "US100.pro"
# =================== Management A Parameters ===================
TP1_enabled = True
TP1_RR = 2  # TP1 Risk-Reward ratio
TP1_percentage = 35  # TP1 percentage

TP2_enabled = True
TP2_RR = 3  # TP2 Risk-Reward ratio
TP2_percentage = 35  # TP2 percentage

TP3_enabled = True
TP3_RR = 4  # TP3 Risk-Reward ratio
TP3_percentage = 30  # TP3 percentage

BE_enabled = True
BE_RR = 1  # Break Even Risk-Reward ratio

# ========================= Order Placement =======================
# Toggle states for each order type
SELL_LIMIT_ENABLED = True
BUY_STOP_ENABLED = True
BUY_LIMIT_ENABLED = True
SELL_STOP_ENABLED = True


def initialize_trading():
    # Initialize MT5 connection
    if not mt5.initialize():
        error_msg = f"initialize() failed, error code = {mt5.last_error()}"
        logging.error(error_msg)
        print(error_msg)
        return False
    # Connect to the account
    authorized = mt5.login(LOGIN, password=PASSWORD, server=SERVER)
    if not authorized:
        error_msg = f"Failed to connect to account {LOGIN}, error code: {mt5.last_error()}"
        logging.error(error_msg)
        print(error_msg)
        mt5.shutdown()
        return False
    return True


def shutdown_trading():
    mt5.shutdown()


# File to store data
DATA_FILE = "order_data.json"
FLAGS_FILE = "order_flags.json"  # Separate file for flags

# Function to save data to file
def save_data(order_data):
    with open(DATA_FILE, "a") as file:  # Open the file in append mode
        json.dump(order_data, file)
        file.write('\n')  # Add a new line to separate different orders


# Function to save order flags to file
def save_flags(order_flags):
    with open(FLAGS_FILE, "w") as file:
        json.dump(order_flags, file)
        # file.write('\n')  # Add a new line to separate different orders

# Function to load data from file


def load_data(filename):
    if os.path.exists(filename):
        with open(filename, "r") as file:
            data = json.load(file)
        # Return an empty dictionary if "order_data" key doesn't exist
        return data
    else:
        return {}  # Return an empty dictionary if the file doesn't exist

# Function to load order flags from file


def load_flags():
    if os.path.exists(FLAGS_FILE):
        with open(FLAGS_FILE, "r") as file:
            return json.load(file)
    else:
        return {}


# Function to update data file after removing closed orders
def update_data_file(order_data):
    save_data(order_data)

# Function to remove closed orders from data file


def remove_closed_orders(order_data, closed_order_tickets):
    for ticket in closed_order_tickets:
        if ticket in order_data:
            del order_data[ticket]  # Remove the order data entry
    update_data_file(order_data)


def actualtime():
    # datetime object containing current date and time
    now = datetime.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    # print("date and time =", dt_string)
    return str(dt_string)


def sync_60sec(op):
    info_time_new = datetime.strptime(str(actualtime()), '%d/%m/%Y %H:%M:%S')
    waiting_time = 60 - info_time_new.second

    t = Timer(waiting_time, op)
    t.start()

    print(actualtime(), f'waiting till next minute and 00 sec...')


def check_request_limit():
    global REQUEST_COUNTER
    REQUEST_COUNTER += 1
    if REQUEST_COUNTER >= REQUEST_LIMIT:
        logging.warning("Daily request limit reached. Exiting...")
        print("Warning: Daily request limit reached.")
        exit(1)


def get_current_price(symbol):
    # check_request_limit()
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info:
        # Ensure bid and ask prices are scalar
        logging.debug(
            f"Type of symbol_info.bid: {type(symbol_info.bid)}, value: {symbol_info.bid}")
        logging.debug(
            f"Type of symbol_info.ask: {type(symbol_info.ask)}, value: {symbol_info.ask}")
        return symbol_info.bid, symbol_info.ask
    else:
        logging.error(f"Error fetching symbol info for {symbol}.")
        return None, None


def calculate_TP(price, RR_ratio, opening_std_dev):
    return price + RR_ratio * opening_std_dev


def calculate_RR(price, RR_ratio, opening_std_dev):
    return price + RR_ratio * opening_std_dev


def expiration_time(**delta_kwargs):
    import datetime as dt
    expire = dt.datetime.now() + dt.timedelta(**delta_kwargs)
    timestamp = int(expire.timestamp())
    return timestamp


def print_trade_executed(request):
    print(
        f"Trade executed - Symbol: {request['symbol']} Price: {request['price']} - SL: {request['sl']} - Lots: {request['volume']}")
    logging.info(
        f"Trade executed - Symbol: {request['symbol']} Price: {request['price']} - SL: {request['sl']} - Lots: {request['volume']}")


def get_symbol_point(symbol):
    # Get symbol info
    symbol_info = mt5.symbol_info(symbol)

    # Check if symbol info is available
    if symbol_info is None:
        print(symbol, "not found, cannot call order_check()")
        mt5.shutdown()
        quit()

    # If the symbol is unavailable in MarketWatch, add it
    if not symbol_info.visible:
        print(symbol, "is not visible, trying to switch on")
        if not mt5.symbol_select(symbol, True):
            print("symbol_select({}}) failed, exit", symbol)
            mt5.shutdown()
            quit()

    # Return the point value of the symbol
    return symbol_info.point


def normalize_price(symbol, price):
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is not None:
        decimals = symbol_info.digits
        return round(price, decimals)
    else:
        logging.error(f"Failed to get symbol info for {symbol}.")
        return price  # Return the original price if symbol info is not available


def adjust_entry_price(symbol, entry_price, order_type):
    logging.info(
        f"Adjusting entry price for {symbol}: {entry_price}, Order type: {order_type}")
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Failed to retrieve symbol information for {symbol}")
        return None

    if order_type == mt5.ORDER_TYPE_SELL_LIMIT:
        # Adjust entry price to ensure it's above the current bid price
        adjusted_entry_price = max(entry_price, symbol_info.bid)
    elif order_type == mt5.ORDER_TYPE_BUY_STOP:
        # Adjust entry price to ensure it's above the current ask price
        adjusted_entry_price = max(entry_price, symbol_info.ask)
    elif order_type == mt5.ORDER_TYPE_BUY_LIMIT:
        # Adjust entry price to ensure it's below the current ask price
        adjusted_entry_price = min(entry_price, symbol_info.ask)
    elif order_type == mt5.ORDER_TYPE_SELL_STOP:
        # Adjust entry price to ensure it's below the current bid price
        adjusted_entry_price = min(entry_price, symbol_info.bid)
    else:
        logging.error("Invalid order type.")
        return None

    logging.info(
        f'Price {entry_price} adjusted based on order type to adjusted price {adjusted_entry_price}.')
    return adjusted_entry_price


def is_valid_price(symbol, price, order_type):
    # Get symbol information (assuming you have a function to retrieve this)
    symbol_info = mt5.symbol_info(symbol)

    # Check if the price is within the valid price range for the symbol
    if symbol_info is not None:
        if order_type in [mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_BUY_STOP]:
            if symbol_info.ask <= price:
                logging.info(
                    f"Price {price} is within the valid price range for {order_type}.")
                return True
            else:
                logging.info(
                    f"Price {price} is outside the valid price range for {order_type}.")
                return False
        elif order_type in [mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_STOP]:
            if symbol_info.bid >= price:
                logging.info(
                    f"Price {price} is within the valid price range for {order_type}.")
                return True
            else:
                logging.info(
                    f"Price {price} is outside the valid price range for {order_type}.")
                return False
        else:
            logging.error("Invalid order type.")
            return False
    else:
        logging.error("Failed to retrieve symbol information.")
        return False


def find_filling_mode(symbol, order_type, entry_price, stoploss):
    global LOT_SIZE
    for i in range(3):
        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": LOT_SIZE,
            "type": order_type,
            "price": entry_price,
            "sl": stoploss,
            "type_filling": i,
            "type_time": mt5.ORDER_TIME_GTC}

        result = mt5.order_check(request)
        # logging.debug(result)

        if result.comment == "Done":
            logging.debug(f"Order Check Request: Done: {result}")
            logging.debug(result.comment)
            break
        else:
            logging.debug(f"Order Check Request Failed: {request.comment}")
        #     logging.info(result.comment)
    return i


# Configure logging
logging.basicConfig(level=logging.DEBUG)


def place_order(symbol, order_type, qty, entry_price, stop_loss = None):
    # global LOT_SIZE
    # # Determine the order type string for the comment
    # order_type_str = "buy" if order_type in [
    #     mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP] else "sell"
    # order_type_str += " limit" if order_type in [
    #     mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_LIMIT] else " stop"

    # # Construct the comment
    # comment = f"python script {order_type_str} order"

    # print(
    #     f"Placing orderType code ({order_type_str}) code{order_type} order for {symbol} at {entry_price}.")
    # logging.info(
    #     f"Placing orderType code ({order_type_str}) code {order_type} order for {symbol} at {entry_price}.")
    # # point = get_symbol_point(symbol)
    # # print("Point for symbol", symbol, "is", point)
    # try:
    #     # # Adjust entry price to ensure it's within bid-ask spread
    #     # if not is_valid_price(symbol, entry_price, order_type):
    #     #     entry_price = adjust_entry_price(symbol, entry_price, order_type)

    #     # price_normalized = normalize_price(symbol, entry_price)
    #     # sl_normalized = normalize_price(symbol, stop_loss)

    #     # # sl_apply = sl_normalized * point
    #     # fill_type = find_filling_mode(
    #     #     symbol, order_type, price_normalized, sl_normalized)

    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": qty,
        "type": order_type,
        "price": entry_price,
        "sl": stop_loss,
        # "deviation": deviation,
        "magic": 1440,
        "comment": "main function",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN
    }

    print("Order Send request:", request)  # Print the request dictionary
    logging.debug(f"Order Send request: {request}")
    result = mt5.order_send(request)
    print("Order result:", result)  # Print the result of order_send
    logging.debug(f"Order result: {result}")
    logging.info(f"Order result details: {result.comment}")
    
    return result
        # Check if the order placement was successful
    #     if result is not None:
    #         # Check if the order placement was successful
    #         if result.retcode == mt5.TRADE_RETCODE_DONE:
    #             print_trade_executed(request)
    #             msg = f"Order type ({order_type_str}) code# {order_type} order placed successfully."
    #             logging.info(msg)
    #             print(msg)
    #             return result.order  # Return the order ticket
    #         else:
    #             error_msg = f"Failed to place Order type ({order_type_str}) code# {order_type} order: {result.comment}"
    #             logging.error(error_msg)
    #             print(error_msg)
    #     else:
    #         logging.error(
    #             "Failed to place order. No response from MetaTrader.")

    #     return None
    # except Exception as e:
    #     # Handle any exceptions that occur during order placement
    #     error_msg = f"An error occurred while placing ({order_type_str}) code# {order_type} order: {e}"
    #     logging.error(error_msg)
    #     print(error_msg)
    #     return None


def manage_orders(symbol, order_tickets, opening_range_high, opening_range_low, opening_std_dev,
                  SELL_LIMIT_ENABLED=True, BUY_STOP_ENABLED=True, BUY_LIMIT_ENABLED=True, SELL_STOP_ENABLED=True):
    order_tickets = []
    # Place orders based on the strategy
    if SELL_LIMIT_ENABLED:
        stoploss = opening_range_high + opening_std_dev
        sell_limit_ticket = place_order(
            symbol, mt5.ORDER_TYPE_SELL_LIMIT, opening_range_high, stoploss)
        if sell_limit_ticket:
            order_tickets.append(sell_limit_ticket)
    if BUY_STOP_ENABLED:
        stoploss = opening_range_low
        buy_stop_ticket = place_order(
            symbol, mt5.ORDER_TYPE_BUY_STOP, opening_range_high, stoploss)
        if buy_stop_ticket:
            order_tickets.append(buy_stop_ticket)
    if BUY_LIMIT_ENABLED:
        stoploss = opening_range_low - opening_std_dev
        buy_limit_ticket = place_order(
            symbol, mt5.ORDER_TYPE_BUY_LIMIT, opening_range_low, stoploss)
        if buy_limit_ticket:
            order_tickets.append(buy_limit_ticket)
    if SELL_STOP_ENABLED:
        stoploss = opening_range_high
        sell_stop_ticket = place_order(
            symbol, mt5.ORDER_TYPE_SELL_STOP, opening_range_low, stoploss)
        if sell_stop_ticket:
            order_tickets.append(sell_stop_ticket)
    return order_tickets


def modify_orders(symb, ticket, stop_loss, type_order=mt5.ORDER_TYPE_BUY):
    logging.info(f"Modifying order {ticket} with stop loss {stop_loss}.")
    modify_order_request = {

        'action': mt5.TRADE_ACTION_SLTP,
        'symbol':  symb,
        'position': ticket,
        'type': type_order,
        'sl': stop_loss,
        'type_time': mt5.ORDER_TIME_GTC,
        'type_filling': mt5.ORDER_FILLING_FOK
    }

    result = mt5.order_send(modify_order_request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        msg = f"Order modified for {ticket} successfully with stop loss {stop_loss}."
        logging.info(msg)
        print(msg)
    else:
        error_msg = f"Failed to modify order: {result.comment}"
        logging.error(error_msg)
        print(error_msg)


def close_partial_position(order_ticket, volume):
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "type": mt5.ORDER_TYPE_CLOSE_BY,
        "position": order_ticket,
        "volume": volume
    }
    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"Closed {volume} lot(s) successfully.")
        logging.info(f"Closed {volume} lot(s) successfully.")
    else:
        print("Failed to close partial position:", result.comment)
        logging.error(f"Failed to close partial position: {result.comment}")


def remove_pending_orders():
    logging.debug("Removing pending orders.")
    # Fetch all pending orders
    orders = mt5.orders_get()

    # Cancel pending orders
    for order in orders:
        if order.type in [mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_LIMIT,
                          mt5.ORDER_TYPE_BUY_STOP, mt5.ORDER_TYPE_SELL_STOP]:
            # Prepare the request to remove the pending order
            request = {
                'action': mt5.TRADE_ACTION_REMOVE,
                'order': order.ticket
            }

            # Send the request to remove the pending order
            result = mt5.order_send(request)
            logging.debug(f"Order removal result: {result}")
            # Check if the order removal was successful
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                print(
                    f"Failed to delete order {order.ticket}. Retcode: {result.retcode}, Comment: {result.comment}")
                logging.error(
                    f"Failed to delete order {order.ticket}. Retcode: {result.retcode}, Comment: {result.comment}")


def main():
    # Initialize MT5 connection
    initialize_trading()
    # Variable to track if orders are already placed
    orders_placed = False
    # Variable to track the start time of the current total range
    current_total_range_start_time = datetime.utcnow()
    logging.info(
        f"Current total range start time: {current_total_range_start_time}")

    # Initialize order_tickets and opening_std_dev
    order_tickets = []
    opening_std_dev = None

    # Continuously monitor the market
    while True:
        # Get current UTC time
        current_time_utc = datetime.utcnow()
        logging.info("Current time: " + str(current_time_utc))
        current_total_range_end_time = current_total_range_start_time + \
            timedelta(minutes=TOTAL_RANGE_MINUTES)
        current_opening_range_end_time = current_total_range_start_time + \
            timedelta(minutes=OPENING_RANGE_MINUTES)
        # Print the current time
        logging.info(
            f"Current total range end time: {current_total_range_end_time}")
        logging.info(
            f"Current opening range end time: {current_opening_range_end_time}")
        # Check if it's within the trading hours
        if current_time_utc.hour in TRADING_HOURS:
            logging.info("Trading hour: True")
            print("Trading hour: True")

            # Check if it's the end of the current total range
            if current_time_utc >= current_total_range_end_time:
                # Log the closing of total range
                logging.info("Closing of total range.")
                print("Closing of total range.")
                # Cancel all pending orders at the end of the total range
                remove_pending_orders()
                # Reset orders_placed
                orders_placed = False
                # Reset current_total_range_start_time for the new total range
                current_total_range_start_time = current_time_utc
                current_total_range_end_time = current_total_range_start_time + \
                    timedelta(minutes=TOTAL_RANGE_MINUTES)
                current_opening_range_end_time = current_total_range_start_time + \
                    timedelta(minutes=OPENING_RANGE_MINUTES)
                # logging.info("Current time: " + str(current_time_utc))
                logging.info(
                    f"New Current total range end time set: {current_total_range_end_time}")
                logging.info(
                    f"Current opening range end time set: {current_opening_range_end_time}")

            # Check if it's within the opening range
            if current_time_utc >= current_opening_range_end_time:
                # Log the opening of the range
                logging.info("Opening of range.")
                print("Opening of range.")
                # Logic to place orders at the high and low of the opening range
                if not orders_placed:
                    print("Placing orders at the high and low of the opening range.")
                    logging.info(
                        "Placing orders at the high and low of the opening range.")
                    print("Symbol: " + symbol)
                    # Fetch historical price data for the opening range
                    try:
                        # Initialize order data dictionary
                        order_data = {}
                        # Attempt to fetch historical price data
                        opening_range_prices = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1,
                                                                    current_time_utc -
                                                                    timedelta(
                                                                        minutes=OPENING_RANGE_MINUTES),
                                                                    current_time_utc)
                        logging.info(
                            f"Response of mt5.copy_rates_range: {opening_range_prices}")

                        # Check if data is returned
                        if len(opening_range_prices) > 0:  # Check the length of the array
                            # Calculate opening range high and low
                            opening_range_high = max(
                                opening_range_prices["high"])
                            opening_range_low = min(
                                opening_range_prices["low"])
                            logging.info(
                                f"Opening range high: {opening_range_high}, low: {opening_range_low}")
                            print(
                                f"Opening range high: {opening_range_high}, low: {opening_range_low}")

                            # Calculate standard deviation of opening range prices
                            opening_range = opening_range_high - opening_range_low
                            opening_std_dev = opening_range

                            # Call the manage_orders function with toggle variables
                            order_tickets = manage_orders(symbol, order_tickets, opening_range_high, opening_range_low, opening_std_dev,
                                                          SELL_LIMIT_ENABLED, BUY_STOP_ENABLED, BUY_LIMIT_ENABLED, SELL_STOP_ENABLED)
                            logging.info(
                                f"Order tickets after manage_orders: {order_tickets}"
                            )
                            # Set orders_placed to True to prevent placing orders again
                            orders_placed = True
                            for order_ticket in order_tickets:
                                order_data[order_ticket] = opening_std_dev

                            # Save data to file
                            save_data(order_data)
                            logging.info(
                                f"Data saved to file: {order_data}"
                            )
                        else:
                            logging.warning(
                                "No data available for opening range.")
                            print("No data available for opening range.")

                    except Exception as e:
                        print(f"An error occurred: {e}")
                        logging.error(f"An error occurred: {e}")

            # Define a dictionary to keep track of orders and their flags
            order_flags = {}

            # Load data from file
            order_data = load_data(DATA_FILE)
            if order_data:
                logging.info(f"Data loaded from file: {order_data}")
                for order_ticket, opening_std_dev in order_data.items():
                    order_ticket_int = int(order_ticket)
                    logging.info(
                        f"Order ticket: {order_ticket} Opening std dev: {opening_std_dev}")
                    positions = mt5.positions_get(ticket=int(order_ticket_int))
                    if positions:
                        logging.info(f"Positions Get successful")
                        order = positions[0]
                        logging.info(f"Order in Position Get: {order}")
                        # Get the current price
                        current_price = mt5.symbol_info_tick(
                            symbol).bid if order.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(symbol).ask
                        # Get the high and low of the candle
                        candle_high = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1,
                                                        current_time_utc -
                                                        timedelta(
                                                            minutes=1),
                                                        current_time_utc)[0]["high"]
                        candle_low = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1,
                                                        current_time_utc -
                                                        timedelta(
                                                            minutes=1),
                                                        current_time_utc)[0]["low"]
                        order_flags = load_flags()
                        # Check if the order ticket exists in the order_flags dictionary
                        if order_ticket not in order_flags:
                            # If the order is not in the dictionary, add it with initial flags
                            logging.info(
                                f"Order {order_ticket} not in order_flags dictionary, adding it with initial flags.")
                            order_flags[order_ticket] = {
                                'breakeven_set': False,
                                'tp1_reached': False,
                                'tp2_reached': False,
                                'tp3_reached': False
                            }

                        # Calculate TP and BE based on the order type
                        if order.type == mt5.ORDER_TYPE_BUY:
                            TP1_price = calculate_TP(
                                order.price_open, TP1_RR, opening_std_dev)
                            TP2_price = calculate_TP(
                                order.price_open, TP2_RR, opening_std_dev)
                            TP3_price = calculate_TP(
                                order.price_open, TP3_RR, opening_std_dev)
                            RR_level = calculate_RR(
                                order.price_open, BE_RR, opening_std_dev)
                            BE_price = order.price_open
                            print(f"BE: {BE_price}, TP1: {TP1_price}, TP2: {TP2_price}, TP3: {TP3_price}, RR: {RR_level}")
                            logging.info(f'BE: {BE_price}, TP1: {TP1_price}, TP2: {TP2_price}, TP3: {TP3_price}, RR: {RR_level}')
                            # Check if the candle's high crosses the RR for breakeven
                            if candle_high >= RR_level and not order_flags[order_ticket]['breakeven_set']:
                                # Modify order to set SL to breakeven
                                modify_orders(symbol, order.ticket,
                                            BE_price, order.type)
                                order_flags[order_ticket]['breakeven_set'] = True
                            # Partially close position if TP1, TP2, or TP3 is reached
                            elif candle_high >= TP1_price and not order_flags[order_ticket]['tp1_reached']:
                                close_partial_position(
                                    order.ticket, 0.35 * order.volume_current)
                                order_flags[order_ticket]['tp1_reached'] = True
                            elif candle_high >= TP2_price and not order_flags[order_ticket]['tp2_reached']:
                                close_partial_position(
                                    order.ticket, 0.35 * order.volume_current)
                                order_flags[order_ticket]['tp2_reached'] = True
                            elif candle_high >= TP3_price and not order_flags[order_ticket]['tp3_reached']:
                                close_partial_position(
                                    order.ticket, 0.30 * order.volume_current)
                                order_flags[order_ticket]['tp3_reached'] = True
                        elif order.type == mt5.ORDER_TYPE_SELL:
                            TP1_price = calculate_TP(
                                order.price_open, -TP1_RR, opening_std_dev)
                            TP2_price = calculate_TP(
                                order.price_open, -TP2_RR, opening_std_dev)
                            TP3_price = calculate_TP(
                                order.price_open, -TP3_RR, opening_std_dev)
                            RR_level = calculate_RR(
                                order.price_open, -BE_RR, opening_std_dev)
                            BE_price = order.price_open
                            # Check if the candle's low crosses the RR for breakeven
                            logging.info(f'BE: {BE_price}, TP1: {TP1_price}, TP2: {TP2_price}, TP3: {TP3_price}, RR: {RR_level}')
                            print(f"BE: {BE_price}, TP1: {TP1_price}, TP2: {TP2_price}, TP3: {TP3_price}, RR: {RR_level}")
                            if candle_low <= RR_level and not order_flags[order_ticket]['breakeven_set']:
                                # Modify order to set SL to breakeven
                                modify_orders(symbol, order.ticket,
                                            BE_price, order.type)
                                order_flags[order_ticket]['breakeven_set'] = True
                            # Partially close position if TP1, TP2, or TP3 is reached
                            elif candle_low <= TP1_price and not order_flags[order_ticket]['tp1_reached']:
                                close_partial_position(
                                    order.ticket, (TP1_percentage / 100) * order.volume)
                                order_flags[order_ticket]['tp1_reached'] = True
                            elif candle_low <= TP2_price and not order_flags[order_ticket]['tp2_reached']:
                                close_partial_position(
                                    order.ticket, (TP2_percentage / 100) * order.volume)
                                order_flags[order_ticket]['tp2_reached'] = True
                            elif candle_low <= TP3_price and not order_flags[order_ticket]['tp3_reached']:
                                close_partial_position(
                                    order.ticket, (TP3_percentage / 100) * order.volume)
                                order_flags[order_ticket]['tp3_reached'] = True

                        save_flags(order_flags)
                    else:
                        logging.info(f'Failed to retrieve position information for the order ticket: {order_ticket}.')

        else:
            logging.info("Trading hour: False")
            print("Trading hour: False")

        # Sleep for a minute before checking the market again
        time.sleep(60)


if __name__ == "__main__":
    sync_60sec(main)

# Shutdown MT5 connection when done
shutdown_trading()
