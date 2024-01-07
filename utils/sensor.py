from enum import Enum
import time
from typing import Dict, List, Optional


class Sensor:
    def __init__(self,
                 device_id: str,
                 name: str,
                 unit: Optional[str] = None,
                 type: Optional[str] = None,
                 offset: float = 0,
                 enabled: bool = True,
                 upper_bound: int = 50,
                 lower_bound: int = -20
                 ) -> None:
        self.device_id: str = device_id
        self.name: str = name
        self.unit: Optional[str] = unit
        self.type: Optional[str] = type
        self.offset: float = offset
        self.enabled: bool = enabled
        self.upper_bound: int = upper_bound
        self.lower_bound: int = lower_bound
        self.disconnected_cycles: int = 0
        self.present_in_database: bool = False
        self.update_timeout: float = 0

    @classmethod
    def from_object(
            cls,
            object: Dict
    ):
        if 'name' not in object:
            raise Exception("No name given")
        if 'deviceId' not in object:
            raise Exception("No deviceId given")
        sensor = cls(
            name=object['name'],
            device_id=object['deviceId'],
        )
        if 'type' in object:
            sensor.type = object['type']
        if 'unit' in object:
            sensor.unit = object['unit']
        if 'offset' in object:
            sensor.offset = object['offset']
        if 'enabled' in object:
            sensor.enabled = object['enabled']
        if 'upperBound' in object:
            sensor.upper_bound = object['upperBound']
        if 'lowerBound' in object:
            sensor.lower_bound = object['lowerBound']

        return sensor

    def on_timeout(self) -> bool:
        return self.update_timeout > time.time()


class Routine:
    def __init__(self,
                 name: str,
                 type: str,
                 sensor_names: List[str],
                 interval_seconds: float = 0,
                 ) -> None:
        self.name: str = name
        self.type: str = type
        self.sensor_names: List[str] = sensor_names
        self.interval_seconds: float = interval_seconds
        self.last_run: float = time.time()
        if self.interval_seconds == 86400:
            # If once per day do first on startup with 20 sec delay
            self.last_run = self.last_run - 86380

    @classmethod
    def from_object(
            cls,
            object: Dict
    ):
        if 'name' not in object:
            raise Exception("No name given")
        if 'type' not in object:
            raise Exception("No type given")
        if 'sensorNames' not in object:
            raise Exception("No sensorNames given")
        routine = cls(
            name=object['name'],
            type=object['type'],
            sensor_names=object['sensorNames'],
        )
        if 'intervalSeconds' in object:
            routine.interval_seconds = object['intervalSeconds']

        return routine

    def due(self) -> bool:
        if len(self.sensor_names) == 0:
            return False
        return self.last_run < time.time() - self.interval_seconds


class SensorConfig:
    def __init__(self,
                 sensors: List[Sensor],
                 routines: List[Routine]) -> None:
        self.sensors: List[Sensor] = sensors
        self.routines: List[Routine] = routines

    @classmethod
    def from_object(
            cls,
            object: Dict
    ):
        sensors: List[Sensor] = []
        for sensor in object.get('sensors', []):
            sensors.append(Sensor.from_object(sensor))

        routines: List[Routine] = []
        for routine in object.get('routines', []):
            routines.append(Routine.from_object(routine))

        return cls(sensors=sensors, routines=routines)

    def get_sensor(self, device_id: str) -> Sensor:
        return next(s for s in self.sensors if s.device_id == device_id)


class CalculationOperand(Enum):
    DIV = '/'
    MULT = '*'

    @classmethod
    def from_str(cls, str: str):
        if str == '/':
            return cls.DIV
        elif str == '*':
            return cls.MULT
        raise Exception("No matching device type given")


class ModbusRegister:
    """
    {
        "register": "30513",
        "unit": "kWh",
        "name": "totalProduction",
        "calculationFactor": 1000,
        "calculationOperand": "/",
        "type": "solar"
    }
    """

    def __init__(self,
                 register: int,
                 name: str,
                 unit: str,
                 calculation_factor: int = 1,
                 calculation_operand: CalculationOperand = CalculationOperand.DIV,
                 type: str = 'solar',
                 ) -> None:
        self.register: int = register
        self.name: str = name
        self.unit: str = unit
        self.calculation_factor: int = calculation_factor
        self.calculation_operand: CalculationOperand = calculation_operand
        self.type: str = type

    @classmethod
    def from_object(
            cls,
            object: Dict
    ):
        if 'name' not in object:
            raise Exception("No name given")
        if 'register' not in object:
            raise Exception("No register given")
        if 'unit' not in object:
            raise Exception("No unit given")
        register: ModbusRegister = cls(
            name=object['name'],
            register=object['register'],
            unit=object['unit'],
        )
        if 'type' in object:
            register.type = object['type']
        if 'calculationFactor' in object:
            register.calculation_factor = object['calculationFactor']
        if 'calculationOperand' in object:
            register.calculation_operand = CalculationOperand.from_str(
                object['calculationOperand'])

        return register

    def transform_value(self, value):
        if self.calculation_operand is CalculationOperand.DIV:
            return value / self.calculation_factor
        elif self.calculation_operand is CalculationOperand.MULT:
            return value * self.calculation_factor
        return value
