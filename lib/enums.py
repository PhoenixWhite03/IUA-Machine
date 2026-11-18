from enum import Enum

class Formats(Enum):
	formato4_UC_transformadores = 1
	formato5_UC_compensaciones = 2
	formato6_UC_SE = 3
	formato7_UC_lineas = 4
	formato8_UC_eq_linea = 5
	formato9_UC_equipos_SE = 6
	formato10_CC = 7
	formato11_trafos_N1 = 8
	formato12_redes_N1 = 9

class IUAType(Enum):
    SUBSTATION = "SUBESTACIÓN"
    LINE = "LÍNEA"
    BT_NETWORK = "RED BT"
    TRAFO = "TRANSFORMADOR"

class IUAInfrastructure(Enum):
  SUBSTATION = '1'
  LINE = '2'

class IUARegistryState(Enum):
    TAKEN = 'OCUPADO'
    RESERVED = 'RESERVADO'
    
class VoltajeLevel(Enum):
    LOW = 'BAJO'
    HIGH = 'ALTO'

class GlobalRegistryTableColumn(Enum):
    IUA = 'IUA'
    IUX = 'IUL/IUS'
    STATE = 'ESTADO'
    REPORT_YEAR = 'AÑO DE REPORTE'
    BDI_CODES = 'CODIGOS'
    ASSET_TYPE = 'ACTIVO'
    UC = 'UC'
    FORMAT = 'FORMATO'
    OPERATION = 'OPERACIÓN'
