import math
import MetaTrader5 as mt5
from mt5_connection_module import initialize_trading, shutdown_trading
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

logging.info("========================= ORB_Bot_mt5.py ==========================")
logging.info("Starting the trading script.")
print("Started")
# =================== CONFIGURABLE PARAMETERS ===================
# Demo Account
LOGIN = 62867314
PASSWORD = ""
SERVER = "OANDATMS-MT5"

# Define your configurable parameters here
TRADING_HOURS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17,
                 18, 19, 20, 21, 22, 23]  # Trading hours in UTC
OPENING_RANGE_MINUTES = 4  # The first x minutes of the total range
TOTAL_RANGE_MINUTES = 15  # Total range period
LOT_SIZE = 0.1  # Lot size for orders
deviation = 20
symbol = "US100.pro"
# =================== Management A Parameters ===================
TP1_enabled = True
TP1_RR = 2  # TP1 Risk-Reward ratio
TP1_percentage = 40  # TP1 percentage

TP2_enabled = True
TP2_RR = 3  # TP2 Risk-Reward ratio
TP2_percentage = 30  # TP2 percentage

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

# ========================= Order Flags ============================

# File to store data
DATA_FILE = "order_data.json"
FLAGS_FILE = "order_flags.json"  # Separate file for flags

# Function to save data to file


def save_data(order_data):
    # Load existing orders if the file exists
    existing_orders = load_data(DATA_FILE)

    # Append new orders to the existing list
    existing_orders.update(order_data)

    # Save the updated list back to the file
    with open(DATA_FILE, "w") as file:  # Open the file in write mode
        # Serialize and write the order data to the file with proper indentation
        json.dump(existing_orders, file, indent=4)


# Function to save order flags to file
def save_flags(order_flags):
    with open(FLAGS_FILE, "w") as file:
        json.dump(order_flags, file)
        # file.write('\n')  # Add a new line to separate different orders

# Function to load data from file


def load_data(filename):
    if os.path.exists(filename):
        with open(filename, "r") as file:
            order_data = json.load(file)
        # Return an empty dictionary if "order_data" key doesn't exist
        return order_data
    else:
        return {}  # Return an empty dictionary if the file doesn't exist

# def load_data(filename):
#     data = {}
#     if os.path.exists(filename):
#         with open(filename, "r") as file:
#             for line in file:
#                 order = json.loads(line)
#                 data.update(order)
#     return data


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
    check_request_limit()
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


def check_valid_lot_size(symbol, lot_size):
    # Retrieve symbol information
    symbol_info = mt5.symbol_info(symbol)

    # Check if symbol information is available
    if symbol_info is None:
        print("Failed to retrieve symbol information.")
        logging.error(f"Failed to retrieve symbol information for {symbol}.")
        return False

    # Check if the requested volume is within the allowed volume range
    if not symbol_info.volume_min <= lot_size <= symbol_info.volume_max:
        print("Requested volume is outside the allowed range.")
        logging.error(
            f"Requested volume is outside the allowed range for {symbol}.")
        return False

    # Check if the requested volume is a valid step size
    if int(lot_size / symbol_info.volume_step) * symbol_info.volume_step != lot_size:
        print("Requested volume is not a valid step size.")
        logging.error(
            f"Requested volume is not a valid step size for {symbol}.")
        return False

    # The requested volume is within the allowed range and is a valid step size
    return True


def adjust_to_valid_step_size(symbol, volume):
    # Retrieve symbol information
    symbol_info = mt5.symbol_info(symbol)

    # Check if symbol information is available
    if symbol_info is None:
        print("Failed to retrieve symbol information.")
        logging.error(f"Failed to retrieve symbol information for {symbol}.")
        return None

    # Calculate the adjusted volume to the nearest valid step size
    valid_step_size = symbol_info.volume_step
    adjusted_volume = math.floor(volume / valid_step_size) * valid_step_size

    return adjusted_volume

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


def adjust_entry_price(symbol, desired_entry_price, order_type):
    # Get symbol information
    symbol_info = mt5.symbol_info(symbol)

    # Check if symbol information is available
    if symbol_info is None:
        logging.error("Failed to retrieve symbol information.")
        return None

    # Calculate the adjusted entry price based on the spread and order direction
    if order_type == mt5.ORDER_TYPE_SELL_LIMIT:
        # Adjust the entry price to be slightly above the desired entry price
        adjusted_price = desired_entry_price + symbol_info.spread * symbol_info.point
        logging.info(f"Adjusted price for {order_type}: {adjusted_price}")
        return adjusted_price
    elif order_type == mt5.ORDER_TYPE_BUY_STOP:
        # Adjust the entry price to be slightly above the desired entry price
        adjusted_price = desired_entry_price + symbol_info.spread * symbol_info.point
        logging.info(f"Adjusted price for {order_type}: {adjusted_price}")
        return adjusted_price
    elif order_type == mt5.ORDER_TYPE_BUY_LIMIT:
        # Adjust the entry price to be slightly below the desired entry price
        adjusted_price = desired_entry_price - symbol_info.spread * symbol_info.point
        logging.info(f"Adjusted price for {order_type}: {adjusted_price}")
        return adjusted_price
    elif order_type == mt5.ORDER_TYPE_SELL_STOP:
        # Adjust the entry price to be slightly below the desired entry price
        adjusted_price = desired_entry_price - symbol_info.spread * symbol_info.point
        logging.info(f"Adjusted price for {order_type}: {adjusted_price}")
        return adjusted_price


def is_valid_price(symbol, price, order_type):
    # Get symbol information
    symbol_info = mt5.symbol_info(symbol)

    # Check if symbol information is available
    if symbol_info is None:
        logging.error("Failed to retrieve symbol information.")
        return False

    # Check if the given price is within the valid price range for the specified order type
    if order_type in [mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP]:
        if symbol_info.ask <= price:
            logging.info(
                f"Price {price} is within the valid price range for {order_type}.")
            return True
        else:
            logging.info(
                f"Price {price} is outside the valid price range for {order_type}.")
            return False
    elif order_type in [mt5.ORDER_TYPE_BUY_STOP, mt5.ORDER_TYPE_BUY_LIMIT]:
        if symbol_info.bid >= price:
            logging.info(
                f"Price {price} is within the valid price range for {order_type}.")
            return True
        else:
            logging.info(
                f"Price {price} is outside the valid price range for {order_type}.")
            return False


def find_filling_mode(symbol, order_type, entry_price, stop_loss):
    global LOT_SIZE
    logging.info("Entering to find_filling_mode")
    for i in range(4):
        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": LOT_SIZE,
            "type": order_type,
            "price": entry_price,
            "sl": stop_loss,
            "type_filling": i,
            "type_time": mt5.ORDER_TIME_GTC
        }

        result = mt5.order_check(request)
        # logging.debug(result)

        if result.comment == "Done":
            logging.debug(f"Order Fill type Request: Done: {result}")
            logging.debug(f'filling mode is {i}')
            logging.debug(result.comment)
            break
        else:
            logging.debug(
                f"Order Fill type Request Failed to match: {request}")
            i = 0
        #     logging.info(result.comment)
    return i


def check_order(symbol, order_type, entry_price, stop_loss, comment):
    global LOT_SIZE, deviation
    logging.debug(f"Checking order for {symbol}: {order_type}")

    while True:
        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": LOT_SIZE,
            "type": order_type,
            "price": entry_price,
            "sl": stop_loss,
            "deviation": deviation,
            "magic": 1440,
            "comment": comment,
            "type_filling": mt5.ORDER_FILLING_RETURN,
            "type_time": mt5.ORDER_TIME_GTC
        }
        logging.debug(request)

        try:
            start_time = time.time()
            result = mt5.order_check(request)
            end_time = time.time()
            logging.debug(
                f"Order check duration: {end_time - start_time} seconds")
        except Exception as e:
            # An exception occurred, handle it and log the error
            logging.error(f"An error occurred while checking the order: {e}")
            return False, "Exception"

        if result is None:
            # Failed to check order due to no response from the server
            logging.error(
                "No response received from the server. Order check failed.")
            return False, "No response"
        elif result.retcode == 0:
            # Order check successful, no errors found
            logging.debug("Order Check: Successful")
            logging.debug(f"Order Check Result: {result}")
            logging.debug(f"Comment: {result.comment}")
            return True, "Success"
        elif "Invalid price" in result.comment:
            # Adjust the entry price and retry checking the order
            logging.info(
                "Order failed due to invalid price error. Adjusting entry price and retrying.")
            return False, "Invalid price"
        else:
            # Order check failed for a reason other than invalid price error
            logging.error("Order Check: Failed")
            logging.error(f"Order Check Result: {result}")
            logging.error(f"Error Comment: {result.comment}")
            return False, "Other error"

# Configure logging
logging.basicConfig(level=logging.DEBUG)


def place_order(symbol, order_type, entry_price, stop_loss):
    global LOT_SIZE, deviation
    # Determine the order type string for the comment
    order_type_str = "buy" if order_type in [
        mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP] else "sell"
    order_type_str += " limit" if order_type in [
        mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_LIMIT] else " stop"

    # Construct the comment
    comment = f"Bot {order_type_str} order"

    print(
        f"Placing orderType code ({order_type_str}) code{order_type} order for {symbol} at {entry_price}.")
    logging.info(
        f"Placing orderType code ({order_type_str}) code {order_type} order for {symbol} at {entry_price}.")
    # point = get_symbol_point(symbol)
    # print("Point for symbol", symbol, "is", point)
    try:
        sl_normalized = normalize_price(symbol, stop_loss)
        logging.info(f"Stop loss normalized to {sl_normalized}.")
        # fill_type = find_filling_mode(
        #     symbol, order_type, entry_price, sl_normalized)
        # logging.info(f"Order {order_type_str} filling type is {fill_type}.")
        # Call the function to check the order
        isValidOrder, error_reason = check_order(symbol, order_type, entry_price, stop_loss, comment)

        if not isValidOrder:
            if error_reason == "Invalid price":
                logging.info("Order check failed due to invalid entry price. Adjusting entry price and retrying.")
                # Adjust the entry price here
                entry_price = adjust_entry_price(symbol, entry_price, order_type)
                # Retry checking the order
                isValidOrder, error_reason = check_order(
                    symbol, order_type, entry_price, stop_loss, comment)
                logging.info(f"Order check result: isValidOrder: {isValidOrder} with error reason: {error_reason}.")
            elif error_reason == "Exception":
                logging.error("Order check failed due to an exception.")
            elif error_reason == "No response":
                logging.error("Order check failed due to no response from the server.")
            else:
                logging.error("Order check failed for another reason.")
        
        if isValidOrder:
            request = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": LOT_SIZE,
                "type": order_type,
                "price": entry_price,
                "sl": sl_normalized,
                "deviation": deviation,
                "magic": 1440,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_RETURN
            }

            # Print the request dictionary
            print("Order Send request:", request)
            logging.debug(f"Order Send request: {request}")
            result = mt5.order_send(request)
            print("Order result:", result)  # Print the result of order_send
            logging.debug(f"Order result: {result}")
            logging.info(f"Order result details: {result.comment}")
            # Check if the order placement was successful
            if result is not None:
                # Check if the order placement was successful
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    print_trade_executed(request)
                    msg = f"Order type ({order_type_str}) code# {order_type} order placed successfully."
                    logging.info(msg)
                    print(msg)
                    return result.order  # Return the order ticket
                else:
                    error_msg = f"Failed to place Order type ({order_type_str}) code# {order_type} order: {result.comment}"
                    logging.error(error_msg)
                    print(error_msg)
            else:
                logging.error(
                    "Failed to place order. No response from MetaTrader.")

            return None
        else:
            logging.info("Failed to place order.")
    except Exception as e:
        # Handle any exceptions that occur during order placement
        error_msg = f"An error occurred while placing ({order_type_str}) code# {order_type} order: {e}"
        logging.error(error_msg)
        print(error_msg)
        return None


def manage_orders(symbol, order_tickets, opening_range_high, opening_range_low, opening_std_dev,
                  SELL_LIMIT_ENABLED=True, BUY_STOP_ENABLED=True, BUY_LIMIT_ENABLED=True, SELL_STOP_ENABLED=True):
    order_tickets = []
    # Place orders based on the strategy
    if SELL_LIMIT_ENABLED:
        stop_loss = opening_range_high + opening_std_dev
        sell_limit_ticket = place_order(
            symbol, mt5.ORDER_TYPE_SELL_LIMIT, opening_range_high, stop_loss)
        if sell_limit_ticket:
            order_tickets.append(sell_limit_ticket)
    if BUY_STOP_ENABLED:
        stop_loss = opening_range_low
        buy_stop_ticket = place_order(
            symbol, mt5.ORDER_TYPE_BUY_STOP, opening_range_high, stop_loss)
        if buy_stop_ticket:
            order_tickets.append(buy_stop_ticket)
    if BUY_LIMIT_ENABLED:
        stop_loss = opening_range_low - opening_std_dev
        buy_limit_ticket = place_order(
            symbol, mt5.ORDER_TYPE_BUY_LIMIT, opening_range_low, stop_loss)
        if buy_limit_ticket:
            order_tickets.append(buy_limit_ticket)
    if SELL_STOP_ENABLED:
        stop_loss = opening_range_high
        sell_stop_ticket = place_order(
            symbol, mt5.ORDER_TYPE_SELL_STOP, opening_range_low, stop_loss)
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


def close_partial_position(symbol, position, volume):
    logging.info(f"Closing partial position {position} with volume {volume}.")
    tick = mt5.symbol_info_tick(symbol)
    is_LotSizeValid = check_valid_lot_size(symbol, volume)
    
    if not is_LotSizeValid:
        volume = adjust_to_valid_step_size(
            symbol, volume)
        logging.info(f"Adjusted volume to valid lot size: {volume}.")
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": position.ticket,
        "symbol": position.symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY if position.type == 1 else mt5.ORDER_TYPE_SELL,
        "price": tick.ask if position.type == 1 else tick.bid,  
        "deviation": 20,
        "magic": 100,
        "comment": "python script close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    
    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"Closed {volume} lot(s) successfully.")
        logging.info(f"Closed {volume} lot(s) successfully.")
    else:
        print("Failed to close partial position:", result.comment)
        logging.error(f"Failed to close partial position: {result.comment}")


def fetch_open_orders():
    # Fetch the list of open orders
    orders = mt5.orders_get()
    open_order_tickets = [order.ticket for order in orders]
    return open_order_tickets


def fetch_current_positions():
    # Fetch the list of current positions
    positions = mt5.positions_get()
    current_position_tickets = [position.ticket for position in positions]
    return current_position_tickets


def fetch_opening_range_prices(symbol, current_time_utc):
    max_retries = 3
    retry_delay_seconds = 10
    retries = 0

    while retries < max_retries:
        try:
            # Attempt to fetch historical price data
            opening_range_prices = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1,
                                                        current_time_utc -
                                                        timedelta(
                                                            minutes=OPENING_RANGE_MINUTES),
                                                        current_time_utc)

            # Check if data is returned
            if len(opening_range_prices) > 0:  # Check the length of the array
                # Calculate opening range high and low
                opening_range_high = max(opening_range_prices["high"])
                opening_range_low = min(opening_range_prices["low"])
                logging.info(
                    f"Opening range high: {opening_range_high}, low: {opening_range_low}")
                print(
                    f"Opening range high: {opening_range_high}, low: {opening_range_low}")
                return opening_range_high, opening_range_low
            else:
                logging.warning("No data available for opening range.")
                print("No data available for opening range.")
                return None, None
        except Exception as e:
            retries += 1
            print(f"Error fetching opening range prices: {e}")
            logging.error(f"Error fetching opening range prices: {e}")

            if retries < max_retries:
                logging.info(f"Retrying in {retry_delay_seconds} seconds...")
                print(f"Retrying in {retry_delay_seconds} seconds...")
                time.sleep(retry_delay_seconds)
            else:
                logging.error(
                    "Max retries exceeded. Unable to fetch opening range prices.")
                print("Max retries exceeded. Unable to fetch opening range prices.")
                return None, None

    return None, None

# Function to fetch candle data with retry logic


def fetch_candle_data(symbol, current_time_utc, MAX_RETRIES=3, RETRY_DELAY=1):
    for attempt in range(MAX_RETRIES):
        try:
            # Attempt to fetch historical price data
            candle_data = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1,
                                               current_time_utc -
                                               timedelta(minutes=1),
                                               current_time_utc)

            # Check if data is available
            if candle_data:
                # Get the high and low of the candle
                candle_high = candle_data[0]["high"]
                candle_low = candle_data[0]["low"]
                logging.info(f"Candle high: {candle_high}, low: {candle_low}")
                return candle_high, candle_low  # Return the data if successful
            else:
                logging.warning("No candle data available.")
        except Exception as e:
            print(
                f"An error occurred while fetching candle data (attempt {attempt+1}): {e}")
            logging.error(
                f"An error occurred while fetching candle data (attempt {attempt+1}): {e}")

        # If not successful, wait for the retry delay before the next attempt
        time.sleep(RETRY_DELAY)

    # If all retries are exhausted, return None
    return None, None


# def remove_unmatched_orders(order_data, combined_orders):
#     # Remove unmatched orders from the loaded order data
#     for ticket in list(order_data.keys()):
#         if ticket not in combined_orders:
#             del order_data[ticket]
#             logging.info(f"Removed unmatched order: {ticket}")

# Modify the remove_unmatched_orders function to modify the order_data in place
def remove_unmatched_orders(order_data, combined_orders):
    # Convert combined_orders to a set of strings
    combined_orders = set(map(str, combined_orders))
    # Create a list of keys to delete
    keys_to_delete = [ticket for ticket in order_data.keys()
                      if ticket not in combined_orders]

    # Remove the unmatched orders
    for ticket in keys_to_delete:
        del order_data[ticket]
        logging.info(f"Removed unmatched order: {ticket}")


def save_order_data(order_data, filename):
    # Save the updated order data back to the JSON file
    with open(filename, "w") as file:
        json.dump(order_data, file, indent=4)


def process_orders():
    # Fetch open orders and current positions
    open_order_tickets = fetch_open_orders()
    current_position_tickets = fetch_current_positions()

    # Combine open orders and current positions
    combined_orders = set(open_order_tickets + current_position_tickets)

    # Load order data from JSON file
    order_data = load_data(DATA_FILE)

    # Remove unmatched orders from the loaded order data
    remove_unmatched_orders(order_data, combined_orders)

    # Save the updated order data back to the JSON file
    save_order_data(order_data, DATA_FILE)


def remove_pending_orders():
    logging.debug("Removing pending orders.")

    # Fetch all pending orders
    orders = mt5.orders_get()

    # Load existing order data from the JSON file
    existing_order_data = load_data(DATA_FILE)

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
            else:
                # Remove the order ticket and corresponding opening std dev from the loaded data
                if str(order.ticket) in existing_order_data:
                    del existing_order_data[str(order.ticket)]
                    logging.info(
                        f"Order removed successfully for {order.ticket}.")
    # Save the updated data back to the JSON file
    save_data(existing_order_data)
    logging.info(
        'Order Data JSON file updated after removal of pending orders.')


def main():
    # Initialize MT5 connection
    initialize_trading()
    # Variable to track if orders are already placed
    orders_placed = False
    
    is_LotSizeValid = check_valid_lot_size(symbol, LOT_SIZE)
    # Check if the lot size is valid for the symbol
    if is_LotSizeValid:
        print("Lot size is valid.")
        logging.info("Lot size is valid.")
    else:
        print("Lot size is not valid.")
        adjusted_lot_size = adjust_to_valid_step_size(symbol, LOT_SIZE)
        print(f"The Lot Size should be adjusted to the lot size according to the step: {adjusted_lot_size}")
    
    # Variable to track the start time of the current total range
    current_total_range_start_time = datetime.utcnow() + timedelta(hours=6)
    logging.info(
        f"Current total range start time: {current_total_range_start_time}")

    # Initialize order_tickets and opening_std_dev
    order_tickets = []
    opening_std_dev = None

    # Continuously monitor the market
    while True:
        # Get current UTC time
        current_time_utc = datetime.utcnow() + timedelta(hours=6)
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

            # Update data file for orders closed by stop loss
            process_orders()
            # Define a dictionary to keep track of orders and their flags
            order_flags = {}
            current_time_utc = datetime.utcnow() + timedelta(hours=6)
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
                        candle_high, candle_low = fetch_candle_data(
                            symbol, current_time_utc)
                        
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
                                'tp3_reached': False,
                                'initial_stop_reached': False
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
                            print(
                                f"BE: {BE_price}, TP1: {TP1_price}, TP2: {TP2_price}, TP3: {TP3_price}, RR: {RR_level}")
                            logging.info(
                                f'BE: {BE_price}, TP1: {TP1_price}, TP2: {TP2_price}, TP3: {TP3_price}, RR: {RR_level}')
                            # Check if the candle's high crosses the RR for breakeven
                            if candle_high >= RR_level and not order_flags[order_ticket]['breakeven_set']:
                                # Modify order to set SL to breakeven
                                modify_orders(symbol, order.ticket,
                                              BE_price, order.type)
                                order_flags[order_ticket]['breakeven_set'] = True
                            # Partially close position if TP1, TP2, or TP3 is reached
                            elif candle_high >= TP1_price and not order_flags[order_ticket]['tp1_reached']:
                                close_partial_position(
                                    symbol, order, (TP1_percentage / 100) * LOT_SIZE)
                                order_flags[order_ticket]['tp1_reached'] = True
                            elif candle_high >= TP2_price and not order_flags[order_ticket]['tp2_reached']:
                                close_partial_position(
                                    symbol, order, (TP2_percentage / 100) * LOT_SIZE)
                                order_flags[order_ticket]['tp2_reached'] = True
                            elif candle_high >= TP3_price and not order_flags[order_ticket]['tp3_reached']:
                                close_partial_position(
                                    symbol, order, (TP3_percentage / 100) * LOT_SIZE)
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
                            logging.info(
                                f'BE: {BE_price}, TP1: {TP1_price}, TP2: {TP2_price}, TP3: {TP3_price}, RR: {RR_level}')
                            print(
                                f"BE: {BE_price}, TP1: {TP1_price}, TP2: {TP2_price}, TP3: {TP3_price}, RR: {RR_level}")
                            if candle_low <= RR_level and not order_flags[order_ticket]['breakeven_set']:
                                # Modify order to set SL to breakeven
                                modify_orders(symbol, order.ticket,
                                              BE_price, order.type)
                                order_flags[order_ticket]['breakeven_set'] = True
                            # Partially close position if TP1, TP2, or TP3 is reached
                            elif candle_low <= TP1_price and not order_flags[order_ticket]['tp1_reached']:
                                close_partial_position(
                                    symbol, order, (TP1_percentage / 100) * LOT_SIZE)
                                order_flags[order_ticket]['tp1_reached'] = True
                            elif candle_low <= TP2_price and not order_flags[order_ticket]['tp2_reached']:
                                close_partial_position(
                                    symbol, order, (TP2_percentage / 100) * LOT_SIZE)
                                order_flags[order_ticket]['tp2_reached'] = True
                            elif candle_low <= TP3_price and not order_flags[order_ticket]['tp3_reached']:
                                close_partial_position(
                                    symbol, order, (TP3_percentage / 100) * LOT_SIZE)
                                order_flags[order_ticket]['tp3_reached'] = True

                        save_flags(order_flags)
                    else:
                        logging.info(
                            f'Failed to retrieve position information for the order ticket: {order_ticket}.')

        else:
            logging.info("Trading hour: False")
            print("Trading hour: False")

        # Sleep for a minute before checking the market again
        time.sleep(60)


if __name__ == "__main__":
    sync_60sec(main)

# Shutdown MT5 connection when done
shutdown_trading()
