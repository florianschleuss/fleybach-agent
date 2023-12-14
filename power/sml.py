from threading import Timer
import time
import serial
from typing import Any, Dict, Optional

from utils.logging import get_module_logger


logger = get_module_logger()


class EnergyData:

    def __init__(self) -> None:
        """Initialize EnergyData."""
        self.buy: float = 0
        self.sell: float = 0
        self.p_tot: float = 0
        self.p_l1: float = 0
        self.p_l2: float = 0
        self.p_l3: float = 0

    def to_dict(self, decimal_places: int = 4) -> Dict[str, float]:
        """Convert EnergyData attributes to a dictionary with rounded values.

        :param decimal_places: Number of decimal places to round the values to.

        :return: Dictionary with rounded values.
        """
        rounded_values = {
            'bought': round(self.buy, decimal_places),
            'sold': round(self.sell, decimal_places),
            'total': round(self.p_tot, decimal_places),
            'l1': round(self.p_l1, decimal_places),
            'l2': round(self.p_l2, decimal_places),
            'l3': round(self.p_l3, decimal_places),
        }
        return rounded_values


class ParseTimer:
    def __init__(self, timeout: float, user_handler: Any) -> None:
        """
        Initialize ParseTimer.

        :param timeout: The timer duration.
        :param user_handler: Optional user-defined handler function.
        """
        self.timeout: float = timeout
        self.handler: Any = user_handler if user_handler is not None else self.default_handler
        self.timer: Timer = Timer(self.timeout, self.handler)

    def reset(self) -> None:
        """Reset the timer."""
        self.timer.cancel()
        self.timer = Timer(self.timeout, self.handler)
        self.timer.start()

    def stop(self) -> None:
        """Stop the timer."""
        self.timer.cancel()

    def default_handler(self) -> None:
        """Default handler function that raises the ParseTimer exception."""
        raise BaseException


class SMLSerialParser:
    def __init__(self, port='/dev/ttyUSB0', baudrate=9600, timeout: float = 0.1):
        """
        Initialize the SMLSerialParser.

        :param port: The serial port to read data from.
        :param baudrate: The baud rate of the serial port.
        :param timeout: The timeout for the parse timer.
        """
        self.serial_port = serial.Serial(port=port, baudrate=baudrate, parity=serial.PARITY_NONE,
                                         stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, timeout=0)
        self.timeout = timeout
        self.timer: Optional[ParseTimer] = None
        self.input_data = b""
        self.running = True
        self.energy_data: Optional[EnergyData] = None

    def parse_data(self) -> None:
        """
        Parse the SML data and synchronize energy information.
        """
        message = self.input_data
        # try:
        #     message = self.input_data[:-2]
        #     crc_rx = int.from_bytes(self.input_data[-2:], byteorder='big')
        # except IndexError:
        # If message will only be 1 char long, the -2 index fails
        # return

        # crc_calc = self.crc16_x25(message)

        if message[:8] == b'\x1b\x1b\x1b\x1b\x01\x01\x01\x01':
            energy = EnergyData()
            energy.buy = self.signed_int(message[167:175]) * (10 ** -7)
            energy.sell = self.signed_int(message[194:202]) * (10 ** -7)
            energy.p_tot = self.signed_int(message[218:226]) * (10 ** -2)
            energy.p_l1 = self.signed_int(message[242:250]) * (10 ** -2)
            energy.p_l2 = self.signed_int(message[266:274]) * (10 ** -2)
            energy.p_l3 = self.signed_int(message[290:298]) * (10 ** -2)
            self.energy_data = energy
            self.running = False

        self.input_data = b""
        if self.timer is not None:
            self.timer.stop()

    def update_energy_values(self) -> None:
        """
        Read data from the serial port and process SML packets.

        This method reads raw data from the serial port, processes SML packets, and synchronizes energy information.
        """
        self.running = True
        if not self.serial_port.is_open:
            self.serial_port.open()

        # this_time = time.time()

        try:
            self.serial_port.reset_input_buffer()
            self.serial_port.reset_output_buffer()
            self.timer = ParseTimer(self.timeout, self.parse_data)
            self.timer.timer.start()

            while self.running:
                while self.serial_port.in_waiting > 0:
                    self.input_data += self.serial_port.read()
                    self.timer.reset()

        except Exception as e:
            print(f"Error while reading from serial port: {e}")

        finally:
            if self.timer is not None:
                self.timer = None
            self.serial_port.close()

    @staticmethod
    def signed_int(hex_str: bytes) -> int:
        """
        Convert a hexadecimal string to a signed integer.

        :param hex_str: The hexadecimal string.
        :return: The signed integer value.
        """
        x = int.from_bytes(hex_str, byteorder='big')
        if x > 0x7FFFFFFFFFFFFFFF:
            x -= 0x10000000000000000
        return x

    def get_energy_data(self) -> Optional[EnergyData]:
        self.update_energy_values()
        while self.running:
            time.sleep(.1)
        if self.energy_data is None:
            return
        return self.energy_data


if __name__ == "__main__":
    sml_parser = SMLSerialParser()
    start = time.time()
    data = sml_parser.get_energy_data()
    print(f"Took {time.time()-start} sec")
    if data is not None:
        print(data.to_dict())
