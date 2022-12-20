from datetime import datetime

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder


class Register:
    def __init__(self, id, name, description, length):
        self.id = id
        self.name = name
        self.description = description
        self.length = length
        self.value = None
        self.registers = []

    def __str__(self):
        return f"{self.id} {self.name} ({self.description})"

    def set_registers(self, registers):
        self.registers = registers

    def is_null(self):
        return None

    def get_value(self):
        return None


class S16(Register):
    def __init__(self, register_id, name, description, length=1):
        Register.__init__(self, register_id, name, description, length)

    def get_value(self):
        return BinaryPayloadDecoder.fromRegisters(self.registers, byteorder=Endian.Big).decode_16bit_int()

    def is_null(self):
        return self.get_value() == 0x8000


class S32(Register):
    def __init__(self, register_id, name, description, length=2):
        Register.__init__(self, register_id, name, description, length)

    def get_value(self):
        return BinaryPayloadDecoder.fromRegisters(self.registers, byteorder=Endian.Big).decode_32bit_int()

    def is_null(self):
        return self.get_value() == 0x80000000


class U16(Register):
    def __init__(self, register_id, name, description, length=1):
        Register.__init__(self, register_id, name, description, length)

    def get_value(self):
        return BinaryPayloadDecoder.fromRegisters(self.registers, byteorder=Endian.Big).decode_16bit_uint()

    def is_null(self):
        return self.get_value() == 0xFFFF


class U32(Register):
    def __init__(self, register_id, name, description, length=2):
        Register.__init__(self, register_id, name, description, length)

    def get_value(self):
        return BinaryPayloadDecoder.fromRegisters(self.registers, byteorder=Endian.Big).decode_32bit_uint()

    def is_null(self):
        return self.get_value() == 0xFFFFFFFF or self.get_value() == 0xFFFFFD


class U64(Register):
    def __init__(self, register_id, name, description, length=4):
        Register.__init__(self, register_id, name, description, length)

    def get_value(self):
        return BinaryPayloadDecoder.fromRegisters(self.registers, byteorder=Endian.Big).decode_64bit_uint()

    def is_null(self):
        return self.get_value() == 0xFFFFFFFFFFFFFFFF


class STR32(Register):
    def __init__(self, register_id, name, description, length=8):
        Register.__init__(self, register_id, name, description, length)

    def get_value(self):
        return BinaryPayloadDecoder.fromRegisters(self.registers, byteorder=Endian.Big).decode_string()

    def is_null(self):
        return self.get_value() == ""


registers = {"30051": U32(30051, "Nameplate.MainModel", "Geräteklasse"),
    "30053": U32(30053, "Nameplate.Model", "Gerätetyp"),
    "30055": U32(30055, "Nameplate.Vendor", "Hersteller"),
    "30057": U32(30057, "Nameplate.SerNum", "Seriennummer"),
    "30059": U32(30059, "Nameplate.PkgRev", "Softwarepaket"),
    "30199": U32(30199, "Operation.RmgTms", "Wartezeit bis Einspeisung"),
    "30201": U32(30201, "Operation.Health", "Zustand"),
    "30203": U32(30203, "Operation.HealthStt.Ok", "Nennleistung im Zustand Ok"),
    "30205": U32(30205, "Operation.HealthStt.Wrn", "Nennleistung im Zustand Warnung"),
    "30207": U32(30207, "Operation.HealthStt.Alm", "Nennleistung im Zustand Fehler"),
    "30211": U32(30211, "Operation.Evt.Prio", "Empfohlene Aktion"),
    "30213": U32(30213, "Operation.Evt.Msg", "Meldung"),
    "30215": U32(30215, "Operation.Evt.Dsc", "Fehlerbehebungsmaßnahme"),
    "30217": U32(30217, "Operation.GriSwStt", "Netzrelais/-schütz"),
    "30219": U32(30219, "Operation.DrtStt", "Leistungsreduzierung"),
    "30225": U32(30225, "Isolation.LeakRis", "Isolationswiderstand"),
    "30231": U32(30231, "Inverter.WLim", "Maximale Gerätewirkleistung"),
    "30233": U32(30233, "Inverter.WMax", "Eingestellte Wirkleistungsgrenze"),
    "30247": U32(30247, "Operation.Evt.EvtNo", "Aktuelle Ereignisnummer für Hersteller"),
    "30513": U64(30513, "Metering.TotWhOut", "Gesamtertrag"),
    "30521": U64(30521, "Metering.TotOpTms", "Betriebszeit"),
    "30525": U64(30525, "Metering.TotFeedTms", "Einspeisezeit"),
    "30529": U32(30529, "Metering.TotWhOut", "Gesamtertrag Wh"),
    "30531": U32(30531, "Metering.TotWhOut", "Gesamtertrag kWh"),
    "30533": U32(30533, "Metering.TotWhOut", "Gesamtertrag MWh"),
    "30541": U32(30541, "Metering.TotOpTms", "Betriebszeit"),
    "30543": U32(30543, "Metering.TotFeedTms", "Einspeisezeit"),
    "30559": U32(30559, "Operation.EvtCntUsr", "Anzahl Ereignisse für Benutzer"),
    "30561": U32(30561, "Operation.EvtCntIstl", "Anzahl Ereignisse für Installateur"),
    "30563": U32(30563, "Operation.EvtCntSvc", "Anzahl Ereignisse für Service"),
    "30581": U32(30581, "Metering.GridMs.TotWhIn", "Zählerstand Bezugszähler"),
    "30583": U32(30583, "Metering.GridMs.TotWhOut", "Zählerstand Einspeisezähler"),
    "30599": U32(30599, "Operation.GriSwCnt", "Anzahl Netzzuschaltungen"),
    "30769": S32(30769, "DcMs.Amp", "DC Strom Eingang"),
    "30771": S32(30771, "DcMs.Vol", "DC Spannung Eingang"),
    "30773": S32(30773, "DcMs.Watt", "DC Leistung Eingang"),
    "30775": S32(30775, "GridMs.TotW", "Leistung"),
    "30777": S32(30777, "GridMs.W.phsA", "Leistung L1"),
    "30779": S32(30779, "GridMs.W.phsB", "Leistung L2"),
    "30781": S32(30781, "GridMs.W.phsC", "Leistung L3"),
    "30783": U32(30783, "GridMs.PhV.phsA", "Netzspannung Phase L1"),
    "30785": U32(30785, "GridMs.PhV.phsB", "Netzspannung Phase L2"),
    "30787": U32(30787, "GridMs.PhV.phsC", "Netzspannung Phase L3"),
    "30789": U32(30789, "GridMs.PhV.phsA2B", "Netzspannung Phase L1 gegen L2"),
    "30791": U32(30791, "GridMs.PhV.phsB2C", "Netzspannung Phase L2 gegen L3"),
    "30793": U32(30793, "GridMs.PhV.phsC2A", "Netzspannung Phase L3 gegen L1"),
    "30795": U32(30795, "GridMs.TotA", "Netzstrom"),
    "30803": U32(30803, "GridMs.Hz", "Netzfrequenz"),
    "30805": S32(30805, "GridMs.TotVAr", "Blindleistung"),
    "30807": S32(30807, "GridMs.VAr.phsA", "Blindleistung L1"),
    "30809": S32(30809, "GridMs.VAr.phsB", "Blindleistung L2"),
    "30811": S32(30811, "GridMs.VAr.phsC", "Blindleistung L3"),
    "30813": S32(30813, "GridMs.TotVA", "Scheinleistung"),
    "30815": S32(30815, "GridMs.VA.phsA", "Scheinleistung L1"),
    "30817": S32(30817, "GridMs.VA.phsB", "Scheinleistung L2"),
    "30819": S32(30819, "GridMs.VA.phsC", "Scheinleistung L3"),
    "30825": U32(30825, "Inverter.VArModCfg.VArMod", "Betriebsart der statischen Spannungshaltung, Konfiguration der statischen Spannungshaltung"),
    "30829": S32(30829, "Inverter.VArModCfg.VArCnstCfg.VArNom", "Blindleistungssollwert in %"),
    "30831": S32(30831, "Inverter.VArModCfg.PFCnstCfg.PF", "Sollwert des cos Phi, Konfiguration des cos Phi, direkte Vorgabe"),
    "30833": U32(30833, "Inverter.VArModCfg.PFCnstCfg.PFExt", "Erregungsart des cos Phi, Konfiguration des cos Phi, direkte Vorgabe"),
    "30835": U32(30835, "Inverter.WModCfg.WMod", "Betriebsart des Einspeisemanagements"),
    "30837": U32(30837, "Inverter.WModCfg.WCnstCfg.W", "Wirkleistungsbegrenzung in W"),
    "30839": U32(30839, "Inverter.WModCfg.WCnstCfg.WNom", "Wirkleistungsbegrenzung in %"),
    "30865": S32(30865, "Metering.GridMs.TotWIn", "Leistung Bezug"),
    "30867": S32(30867, "Metering.GridMs.TotWOut", "Leistung Einspeisung"),
    "30875": U32(30875, "MltFncSw.Stt", "Status des Multifunktionsrelais"),
    "30881": U32(30881, "Operation.PvGriConn", "Netzanbindung der Anlage"),
    "30925": U32(30925, "Spdwr.ComSocA.ConnSpd", "Verbindungsgeschwindigkeit von SMACOM A"),
    "30927": U32(30927, "Spdwr.ComSocA.DpxMode", "Duplexmodus von SMACOM A"),
    "30929": U32(30929, "Spdwr.ComSocA.Stt", "Speedwire-Verbindungsstatus von SMACOM A"),
    "30931": U32(30931, "Spdwr.ComSocB.ConnSpd", "Verbindungsgeschwindigkeit von SMACOM B"),
    "30933": U32(30933, "Spdwr.ComSocB.DpxMode", "Duplexmodus von SMACOM B"),
    "30935": U32(30935, "Spdwr.ComSocB.Stt", "Speedwire-Verbindungsstatus von SMACOM B"),
    "30949": U32(30949, "GridMs.TotPFPrc", "Verschiebungsfaktor"),
    "30953": S32(30953, "Coolsys.Cab.TmpVal", "Innentemperatur"),
    "30957": S32(30957, "DcMs.Amp", "DC Strom Eingang"),
    "30959": S32(30959, "DcMs.Vol", "DC Spannung Eingang"),
    "30961": S32(30961, "DcMs.Watt", "DC Leistung Eingang"),
    "30975": S32(30975, "Inverter.DclVol", "Zwischenkreisspannung"),
    "30977": S32(30977, "GridMs.A.phsA", "Netzstrom Phase L1"),
    "30979": S32(30979, "GridMs.A.phsB", "Netzstrom Phase L2"),
    "30981": S32(30981, "GridMs.A.phsC", "Netzstrom Phase L3"),
    "31017": STR32(31017, "Spdwr.ActlIp", "-"),
    "31025": STR32(31025, "Spdwr.ActlSnetMsk", "-"),
    "31033": STR32(31033, "Spdwr.ActlGwIp", "-"),
    "31041": STR32(31041, "Spdwr.ActlDnsSrvIp", "-"),
    "31061": U32(31061, "Bat.ChaCtlComAval", "Steuerung der Batterieladung über Kommunikation verfügbar"),
    "31085": U32(31085, "Operation.HealthStt.Ok", "Nennleistung im Zustand Ok"),
    "31159": S32(31159, "Operation.Dmd.VArCtl", "Aktuelle Vorgabe Blindleistung Q"),
    "31221": S32(31221, "GridMs.TotPFEEI", "EEI-Verschiebungsfaktor"),
    "31247": S32(31247, "Isolation.FltA", "Fehlerstrom"),
    "31253": U32(31253, "Metering.GridMs.PhV.phsA", "Netzspannung Phase L1"),
    "31255": U32(31255, "Metering.GridMs.PhV.phsB", "Netzspannung Phase L2"),
    "31257": U32(31257, "Metering.GridMs.PhV.phsC", "Netzspannung Phase L3"),
    "31259": U32(31259, "Metering.GridMs.W.phsA", "Leistung Netzeinspeisung L1"),
    "31261": U32(31261, "Metering.GridMs.W.phsB", "Leistung Netzeinspeisung L2"),
    "31263": U32(31263, "Metering.GridMs.W.phsC", "Leistung Netzeinspeisung L3"),
    "31265": U32(31265, "Metering.GridMs.WIn.phsA", "Leistung Netzbezug Phase L1"),
    "31267": U32(31267, "Metering.GridMs.WIn.phsB", "Leistung Netzbezug Phase L2"),
    "31269": U32(31269, "Metering.GridMs.WIn.phsC", "Leistung Netzbezug Phase L3"),
    "31271": S32(31271, "Metering.GridMs.VAr.phsA", "Blindleistung Netzeinspeisung Phase L1"),
    "31273": S32(31273, "Metering.GridMs.VAr.phsB", "Blindleistung Netzeinspeisung Phase L2"),
    "31275": S32(31275, "Metering.GridMs.VAr.phsC", "Blindleistung Netzeinspeisung Phase L3"),
    "31277": S32(31277, "Metering.GridMs.TotVAr", "Blindleistung Netzeinspeisung"),
    "31405": U32(31405, "Operation.Dmd.WCtl", "Aktuelle Vorgabe Wirkleistungsbegrenzung P"),
    "31407": U32(31407, "Operation.Dmd.PFCtl", "Aktuelle Vorgabe cos Phi"),
    "31409": U32(31409, "Operation.Dmd.PFExtCtl", "Aktuelle Vorgabe Erregungsart cos Phi"),
    "31411": S32(31411, "Operation.Dmd.VArCtl", "Aktuelle Vorgabe Blindleistung Q"),
    "31793": S32(31793, "DcMs.Amp", "DC Strom Eingang"),
    "31795": S32(31795, "DcMs.Amp", "DC Strom Eingang"),
    "34113": S32(34113, "Coolsys.Cab.TmpVal", "Innentemperatur"),
    "34609": S32(34609, "Env.TmpVal", "Außentemperatur"),
    "34611": S32(34611, "Env.TmpValMax", "Höchste gemessene Außentemperatur"),
    "34615": U32(34615, "Env.HorWSpd", "Windgeschwindigkeit"),
    "34621": S32(34621, "Mdul.TmpVal", "Modultemperatur"),
    "34623": U32(34623, "Env.ExInsol", "Einstrahlung auf externen Sensor"),
    "34625": S32(34625, "Env.TmpVal", "Außentemperatur"),
    "34627": S32(34627, "Env.TmpVal", "Außentemperatur"),
    "34629": S32(34629, "Mdul.TmpVal", "Modultemperatur"),
    "34631": S32(34631, "Mdul.TmpVal", "Modultemperatur"),
    "34633": U32(34633, "Env.HorWSpd", "Windgeschwindigkeit"),
    "34635": U32(34635, "Env.HorWSpd", "Windgeschwindigkeit"),
    "34669": U32(34669, "Bat.ChaCtlComAval", "Steuerung der Batterieladung über Kommunikation verfügbar"),
    "35377": U64(35377, "Operation.EvtCntUsr", "Anzahl Ereignisse für Benutzer"),
    "35381": U64(35381, "Operation.EvtCntIstl", "Anzahl Ereignisse für Installateur"),
    "35385": U64(35385, "Operation.EvtCntSvc", "Anzahl Ereignisse für Service"),
    "40003": U32(40003, "DtTm.TmZn", "Zeitzone"),
    "40005": U32(40005, "DtTm.DlSvIsOn", "Automatische Sommer-/Winterzeitumstellung eingeschaltet"),
    "40009": U32(40009, "Operation.OpMod", "Betriebszustand"),
    "40013": U32(40013, "CntrySettings.Lang", "Sprache der Oberfläche"),
    "40015": S16(40015, "Inverter.VArModCfg.VArCtlComCfg.VArNom", "Normierte Blindleistungsvorgabe durch Anlagensteuerung"),
    "40016": S16(40016, "Inverter.WModCfg.WCtlComCfg.WNom", "Normierte Wirkleistungsbegrenzung durch Anlagensteuerung"),
    "40018": U32(40018, "Inverter.FstStop", "Schnellabschaltung"),
    "40022": S16(40022, "Inverter.VArModCfg.VArCtlComCfg.VArNomPrc", "Normierte Blindleistungsbegrenzung durch Anlagensteuerung"),
    "40023": S16(40023, "Inverter.WModCfg.WCtlComCfg.WNomPrc", "Normierte Wirkleistungsbegrenzung durch Anlagensteuerung"),
    "40024": U16(40024, "Inverter.VArModCfg.PFCtlComCfg.PF", "Verschiebungsfaktor durch Anlagensteuerung"),
    "40025": U32(40025, "Inverter.VArModCfg.PFCtlComCfg.PFExt", "Erregungsart durch Anlagensteuerung"),
    "40029": U32(40029, "Operation.OpStt", "Betriebsstatus"),
    "40063": U32(40063, "Nameplate.CmpMain.SwRev", "Firmware-Version des Hauptprozessors"),
    "40067": U32(40067, "Nameplate.SerNum", "Seriennummer"),
    "40077": U32(40077, "Sys.DevRstr", "Geräteneustart auslösen"),
    "40095": U32(40095, "GridGuard.Cntry.VolCtl.Max", "Spannungsüberwachung obere Maximalschwelle"),
    "40109": U32(40109, "GridGuard.Cntry", "Eingestellte Ländernorm"),
    "40133": U32(40133, "GridGuard.Cntry.VRtg", "Netz-Nennspannung"),
    "40135": U32(40135, "GridGuard.Cntry.HzRtg", "Nennfrequenz"),
    "40149": S32(40149, "Inverter.WModCfg.WCtlComCfg.WSpt", "Wirkleistungsvorgabe"),
    "40151": U32(40151, "Inverter.WModCfg.WCtlComCfg.WCtlComAct", "Wirk- und Blindleistungsregelung über Kommunikation"),
    "40157": U32(40157, "Spdwr.AutoCfgIsOn", "Automatische Speedwire-Konfiguration eingeschaltet"),
    "40159": STR32(40159, "Spdwr.Ip", "-"),
    "40167": STR32(40167, "Spdwr.SnetMsk", "-"),
    "40175": STR32(40175, "Spdwr.GwIp", "-"),
    "40185": U32(40185, "Inverter.VALim", "Maximale Gerätescheinleistung"),
    "40195": U32(40195, "Inverter.VAMax", "Eingestellte Scheinleistungsgrenze"),
    "40200": U32(40200, "Inverter.VArModCfg.VArMod", "Betriebsart der statischen Spannungshaltung, Konfiguration der statischen Spannungshaltung"),
    "40204": S32(40204, "Inverter.VArModCfg.VArCnstCfg.VArNom", "Blindleistungssollwert in %"),
    "40206": S32(40206, "Inverter.VArModCfg.PFCnstCfg.PF", "Sollwert des cos Phi, Konfiguration des cos Phi, direkte Vorgabe"),
    "40208": U32(40208, "Inverter.VArModCfg.PFCnstCfg.PFExt", "Erregungsart des cos Phi, Konfiguration des cos Phi, direkte Vorgabe"),
    "40210": U32(40210, "Inverter.WModCfg.WMod", "Betriebsart des Einspeisemanagements"),
    "40212": U32(40212, "Inverter.WModCfg.WCnstCfg.W", "Wirkleistungsbegrenzung in W"),
    "40214": U32(40214, "Inverter.WModCfg.WCnstCfg.WNom", "Wirkleistungsbegrenzung in %"),
    "40216": U32(40216, "Inverter.WCtlHzModCfg.WCtlHzMod", "Betriebsart der Wirkleistungsreduktion bei Überfrequenz P(f)"),
    "40218": U32(40218, "Inverter.WCtlHzModCfg.WCtlHzCfg.HzStr", "Abstand der Startfrequenz zur Netzfrequenz, Konfiguration des linearen Gradienten der Momentanleistung"),
    "40220": U32(40220, "Inverter.WCtlHzModCfg.WCtlHzCfg.HzStop", "Abstand der Rücksetzfrequenz zur Netzfrequenz, Konfiguration des linearen Gradienten der Momentanleistung"),
    "40222": U32(40222, "Inverter.VArModCfg.PFCtlWCfg.PFStr", "cos Phi des Startpunktes, Konfiguration der cos Phi(P)-Kennlinie"),
    "40224": U32(40224, "Inverter.VArModCfg.PFCtlWCfg.PFExtStr", "Erregungsart des Startpunktes, Konfiguration der cos Phi(P)-Kennlinie"),
    "40226": U32(40226, "Inverter.VArModCfg.PFCtlWCfg.PFStop", "cos Phi des Endpunktes, Konfiguration der cos Phi(P)-Kennlinie"),
    "40228": U32(40228, "Inverter.VArModCfg.PFCtlWCfg.PFExtStop", "Erregungsart des Endpunktes, Konfiguration der cos Phi(P)-Kennlinie"),
    "40230": U32(40230, "Inverter.VArModCfg.PFCtlWCfg.WNomStr", "Wirkleistung des Startpunktes, Konfiguration der cos Phi(P)-Kennlinie"),
    "40232": U32(40232, "Inverter.VArModCfg.PFCtlWCfg.WNomStop", "Wirkleistung des Endpunktes, Konfiguration der cos Phi(P)-Kennlinie"),
    "40234": U32(40234, "Inverter.WGra", "Wirkleistungsgradient"),
    "40238": U32(40238, "Inverter.WCtlHzModCfg.WCtlHzCfg.WGra", "Wirkleistungsgradient, Konfiguration des linearen Gradienten der Momentanleistung"),
    "40240": U32(40240, "Inverter.WCtlHzModCfg.WCtlHzCfg.HystEna", "Aktivierung der Schleppzeigerfunktion, Konfiguration des linearen Gradienten der Momentanleistung"),
    "40242": U32(40242, "Inverter.WCtlHzModCfg.WCtlHzCfg.HzStopWGra", "Wirkleistungsgradient nach Rücksetzfrequenz, Konfiguration des linearen Gradienten der Momentanleistung"),
    "40244": U32(40244, "Inverter.DGSModCfg.DGSFlCfg.ArGraMod", "Blindstromstatik, Konfiguration der vollständigen dynamischen Netzstützung"),
    "40246": U32(40246, "Inverter.DGSModCfg.DGSFlCfg.ArGraSag", "Gradient K der Blindstromstatik für Unterpannung bei dynamischer Netzstützung"),
    "40248": U32(40248, "Inverter.DGSModCfg.DGSFlCfg.ArGraSwell", "Gradient K der Blindstromstatik für Überpannung bei dynamischer Netzstützung"),
    "40250": U32(40250, "Inverter.DGSModCfg.DGSMod", "Betriebsart der dynamischen Netzstützung, Konfiguration der dynamischen Netzstützung"),
    "40252": S32(40252, "Inverter.DGSModCfg.DGSFlCfg.DbVolNomMin", "Untergrenze Spannungstotband, Konfiguration der vollständigen dynamischen Netzstützung"),
    "40254": U32(40254, "Inverter.DGSModCfg.DGSFlCfg.DbVolNomMax", "Obergrenze Spannungstotband, Konfiguration der vollständigen dynamischen Netzstützung"),
    "40256": U32(40256, "Inverter.DGSModCfg.PwrCirInopVolNom", "PWM-Sperrspannung, Konfiguration der dynamischen Netzstützung"),
    "40258": U32(40258, "Inverter.DGSModCfg.PwrCirInopTms", "PWM-Sperrverzögerung, Konfiguration der dynamischen Netzstützung"),
    "40262": U32(40262, "Inverter.UtilCrvCfg.Crv0.NumPt", "Kennlinie, Anzahl der zu verwendenden Punkte der Kennlinie"),
    "40264": U32(40264, "Inverter.UtilCrvCfg.Crv0.NumPt", "Kennlinie, Anzahl der zu verwendenden Punkte der Kennlinie"),
    "40266": U32(40266, "Inverter.UtilCrvCfg.Crv0.NumPt", "Kennlinie, Anzahl der zu verwendenden Punkte der Kennlinie"),
    "40282": S32(40282, "Inverter.UtilCrvCfg.CrvPt1.XVal", "X-Werte der Kennlinie 1"),
    "40284": S32(40284, "Inverter.UtilCrvCfg.CrvPt1.XVal", "X-Werte der Kennlinie 1"),
    "40286": S32(40286, "Inverter.UtilCrvCfg.CrvPt1.XVal", "X-Werte der Kennlinie 1"),
    "40288": S32(40288, "Inverter.UtilCrvCfg.CrvPt1.XVal", "X-Werte der Kennlinie 1"),
    "40290": S32(40290, "Inverter.UtilCrvCfg.CrvPt1.XVal", "X-Werte der Kennlinie 1"),
    "40292": S32(40292, "Inverter.UtilCrvCfg.CrvPt1.XVal", "X-Werte der Kennlinie 1"),
    "40294": S32(40294, "Inverter.UtilCrvCfg.CrvPt1.XVal", "X-Werte der Kennlinie 1"),
    "40296": S32(40296, "Inverter.UtilCrvCfg.CrvPt1.XVal", "X-Werte der Kennlinie 1"),
    "40306": S32(40306, "Inverter.UtilCrvCfg.CrvPt1.YVal", "Y-Werte der Kennlinie 1"),
    "40308": S32(40308, "Inverter.UtilCrvCfg.CrvPt1.YVal", "Y-Werte der Kennlinie 1"),
    "40310": S32(40310, "Inverter.UtilCrvCfg.CrvPt1.YVal", "Y-Werte der Kennlinie 1"),
    "40312": S32(40312, "Inverter.UtilCrvCfg.CrvPt1.YVal", "Y-Werte der Kennlinie 1"),
    "40314": S32(40314, "Inverter.UtilCrvCfg.CrvPt1.YVal", "Y-Werte der Kennlinie 1"),
    "40316": S32(40316, "Inverter.UtilCrvCfg.CrvPt1.YVal", "Y-Werte der Kennlinie 1"),
    "40318": S32(40318, "Inverter.UtilCrvCfg.CrvPt1.YVal", "Y-Werte der Kennlinie 1"),
    "40320": S32(40320, "Inverter.UtilCrvCfg.CrvPt1.YVal", "Y-Werte der Kennlinie 1"),
    "40330": S32(40330, "Inverter.UtilCrvCfg.CrvPt2.XVal", "X-Werte der Kennlinie 2"),
    "40332": S32(40332, "Inverter.UtilCrvCfg.CrvPt2.XVal", "X-Werte der Kennlinie 2"),
    "40334": S32(40334, "Inverter.UtilCrvCfg.CrvPt2.XVal", "X-Werte der Kennlinie 2"),
    "40336": S32(40336, "Inverter.UtilCrvCfg.CrvPt2.XVal", "X-Werte der Kennlinie 2"),
    "40338": S32(40338, "Inverter.UtilCrvCfg.CrvPt2.XVal", "X-Werte der Kennlinie 2"),
    "40340": S32(40340, "Inverter.UtilCrvCfg.CrvPt2.XVal", "X-Werte der Kennlinie 2"),
    "40342": S32(40342, "Inverter.UtilCrvCfg.CrvPt2.XVal", "X-Werte der Kennlinie 2"),
    "40344": S32(40344, "Inverter.UtilCrvCfg.CrvPt2.XVal", "X-Werte der Kennlinie 2"),
    "40354": S32(40354, "Inverter.UtilCrvCfg.CrvPt2.YVal", "Y-Werte der Kennlinie 2"),
    "40356": S32(40356, "Inverter.UtilCrvCfg.CrvPt2.YVal", "Y-Werte der Kennlinie 2"),
    "40358": S32(40358, "Inverter.UtilCrvCfg.CrvPt2.YVal", "Y-Werte der Kennlinie 2"),
    "40360": S32(40360, "Inverter.UtilCrvCfg.CrvPt2.YVal", "Y-Werte der Kennlinie 2"),
    "40362": S32(40362, "Inverter.UtilCrvCfg.CrvPt2.YVal", "Y-Werte der Kennlinie 2"),
    "40364": S32(40364, "Inverter.UtilCrvCfg.CrvPt2.YVal", "Y-Werte der Kennlinie 2"),
    "40366": S32(40366, "Inverter.UtilCrvCfg.CrvPt2.YVal", "Y-Werte der Kennlinie 2"),
    "40368": S32(40368, "Inverter.UtilCrvCfg.CrvPt2.YVal", "Y-Werte der Kennlinie 2"),
    "40378": S32(40378, "Inverter.UtilCrvCfg.CrvPt3.XVal", "X-Werte der Kennlinie 3"),
    "40380": S32(40380, "Inverter.UtilCrvCfg.CrvPt3.XVal", "X-Werte der Kennlinie 3"),
    "40382": S32(40382, "Inverter.UtilCrvCfg.CrvPt3.XVal", "X-Werte der Kennlinie 3"),
    "40384": S32(40384, "Inverter.UtilCrvCfg.CrvPt3.XVal", "X-Werte der Kennlinie 3"),
    "40386": S32(40386, "Inverter.UtilCrvCfg.CrvPt3.XVal", "X-Werte der Kennlinie 3"),
    "40388": S32(40388, "Inverter.UtilCrvCfg.CrvPt3.XVal", "X-Werte der Kennlinie 3"),
    "40390": S32(40390, "Inverter.UtilCrvCfg.CrvPt3.XVal", "X-Werte der Kennlinie 3"),
    "40392": S32(40392, "Inverter.UtilCrvCfg.CrvPt3.XVal", "X-Werte der Kennlinie 3"),
    "40402": S32(40402, "Inverter.UtilCrvCfg.CrvPt3.YVal", "Y-Werte der Kennlinie 3"),
    "40404": S32(40404, "Inverter.UtilCrvCfg.CrvPt3.YVal", "Y-Werte der Kennlinie 3"),
    "40406": S32(40406, "Inverter.UtilCrvCfg.CrvPt3.YVal", "Y-Werte der Kennlinie 3"),
    "40408": S32(40408, "Inverter.UtilCrvCfg.CrvPt3.YVal", "Y-Werte der Kennlinie 3"),
    "40410": S32(40410, "Inverter.UtilCrvCfg.CrvPt3.YVal", "Y-Werte der Kennlinie 3"),
    "40412": S32(40412, "Inverter.UtilCrvCfg.CrvPt3.YVal", "Y-Werte der Kennlinie 3"),
    "40414": S32(40414, "Inverter.UtilCrvCfg.CrvPt3.YVal", "Y-Werte der Kennlinie 3"),
    "40416": S32(40416, "Inverter.UtilCrvCfg.CrvPt3.YVal", "Y-Werte der Kennlinie 3"),
    "40428": U32(40428, "GridGuard.Cntry.FrqCtl.hhLim", "Frequenzüberwachung mittlere Maximalschwelle"),
    "40430": U32(40430, "GridGuard.Cntry.FrqCtl.hhLimTmms", "Frequenzüberwachung mittlere Maximalschwelle Auslösezeit"),
    "40432": U32(40432, "GridGuard.Cntry.FrqCtl.hLim", "Frequenzüberwachung untere Maximalschwelle"),
    "40434": U32(40434, "GridGuard.Cntry.FrqCtl.hLimTmms", "Frequenzüberwachung untere Maximalschwelle Auslösezeit"),
    "40436": U32(40436, "GridGuard.Cntry.FrqCtl.lLim", "Frequenzüberwachung obere Minimalschwelle"),
    "40438": U32(40438, "GridGuard.Cntry.FrqCtl.lLimTmms", "Frequenzüberwachung obere Minimalschwelle Auslösezeit"),
    "40440": U32(40440, "GridGuard.Cntry.FrqCtl.llLim", "Frequenzüberwachung mittlere Minimalschwelle"),
    "40442": U32(40442, "GridGuard.Cntry.FrqCtl.llLimTmms", "Frequenzüberwachung mittlere Minimalschwelle Auslösezeit"),
    "40446": U32(40446, "GridGuard.Cntry.VolCtl.MaxTmms", "Spannungsüberwachung obere Maximalschwelle Auslösezeit"),
    "40448": U32(40448, "GridGuard.Cntry.VolCtl.hhLim", "Spannungsüberwachung mittlere Maximalschwelle"),
    "40450": U32(40450, "GridGuard.Cntry.VolCtl.hhLimTmms", "Spannungsüberwachung mittlere Maximalschwelle Auslösezeit"),
    "40452": U32(40452, "GridGuard.Cntry.VolCtl.hLim", "Spannungsüberwachung untere Maximalschwelle"),
    "40456": U32(40456, "GridGuard.Cntry.VolCtl.hLimTmms", "Spannungsüberwachung untere Maximalschwelle Auslösezeit"),
    "40458": U32(40458, "GridGuard.Cntry.VolCtl.lLim", "Spannungsüberwachung obere Minimalschwelle"),
    "40462": U32(40462, "GridGuard.Cntry.VolCtl.lLimTmms", "Spannungsüberwachung obere Minimalschwelle Auslösezeit"),
    "40464": U32(40464, "GridGuard.Cntry.VolCtl.llLim", "Spannungsüberwachung mittlere Minimalschwelle"),
    "40466": U32(40466, "GridGuard.Cntry.VolCtl.llLimTmms", "Spannungsüberwachung mittlere Minimalschwelle Auslösezeit"),
    "40472": U32(40472, "Inverter.PlntCtl.VRef", "Referenzspannung"),
    "40474": S32(40474, "Inverter.PlntCtl.VRefOfs", "Referenzkorrekturspannung"),
    "40480": U32(40480, "Nameplate.ARtg", "Nennstrom über alle Phasen"),
    "40482": U32(40482, "Inverter.VArGra", "Blindleistungsgradient"),
    "40484": U32(40484, "Inverter.WGraEna", "Aktivierung des Wirkleistungsgradienten"),
    "40490": U32(40490, "Inverter.VArModCfg.VArCtlVolCfg.VArGraNom", "Blindleistungsgradient, Konfiguration der Blindleistungs-/Spannungskennlinie Q(U)"),
    "40497": STR32(40497, "Nameplate.MacId", "-"),
    "40513": STR32(40513, "Spdwr.DnsSrvIp", "-"),
    "40575": U32(40575, "MltFncSw.OpMode", "Betriebsart des Multifunktionsrelais"),
    "40577": U32(40577, "MltFncSw.OpMode", "Betriebsart des Multifunktionsrelais"),
    "40631": STR32(40631, "Nameplate.Location", "-"),
    "40647": U32(40647, "Upd.AutoUpdIsOn", "Automatische Updates eingeschaltet"),
    "40789": U32(40789, "Nameplate.ComRev", "Kommunikationsversion"),
    "40791": U32(40791, "Inverter.PlntCtl.IntvTmsMax", "Timeout für Kommunikationsfehlermeldung"),
    "40855": U32(40855, "Inverter.UtilCrvCfg.Crv0.RmpDec", "Kennlinie, Absenkungsrampe für Erreichung des Kennlinienarbeitspunktes"),
    "40857": U32(40857, "Inverter.UtilCrvCfg.Crv0.RmpDec", "Kennlinie, Absenkungsrampe für Erreichung des Kennlinienarbeitspunktes"),
    "40859": U32(40859, "Inverter.UtilCrvCfg.Crv0.RmpDec", "Kennlinie, Absenkungsrampe für Erreichung des Kennlinienarbeitspunktes"),
    "40875": U32(40875, "Inverter.UtilCrvCfg.Crv0.RmpInc", "Kennlinie, Steigerungsrampe für Erreichung des Kennlinienarbeitspunktes"),
    "40877": U32(40877, "Inverter.UtilCrvCfg.Crv0.RmpInc", "Kennlinie, Steigerungsrampe für Erreichung des Kennlinienarbeitspunktes"),
    "40879": U32(40879, "Inverter.UtilCrvCfg.Crv0.RmpInc", "Kennlinie, Steigerungsrampe für Erreichung des Kennlinienarbeitspunktes"),
    "40895": U32(40895, "Inverter.UtilCrvCfg.Crv0.CrvTms", "Kennlinie, Einstellzeit des Kennlinienarbeitspunktes"),
    "40897": U32(40897, "Inverter.UtilCrvCfg.Crv0.CrvTms", "Kennlinie, Einstellzeit des Kennlinienarbeitspunktes"),
    "40899": U32(40899, "Inverter.UtilCrvCfg.Crv0.CrvTms", "Kennlinie, Einstellzeit des Kennlinienarbeitspunktes"),
    "40915": U32(40915, "Inverter.WMax", "Eingestellte Wirkleistungsgrenze"),
    "40917": U32(40917, "Inverter.UtilCrvCfg.CrvModCfg.CrvNum", "Kennliniennummer, Konfiguration des Kennlinienmodus"),
    "40919": U32(40919, "Inverter.UtilCrvCfg.CrvModCfg.CrvNum", "Kennliniennummer, Konfiguration des Kennlinienmodus"),
    "40921": U32(40921, "Inverter.UtilCrvCfg.CrvModCfg.CrvNum", "Kennliniennummer, Konfiguration des Kennlinienmodus"),
    "40937": U32(40937, "Inverter.UtilCrvCfg.CrvModCfg.CrvEna", "Aktivierung der Kennlinie, Konfiguration des Kennlinienmodus"),
    "40939": U32(40939, "Inverter.UtilCrvCfg.CrvModCfg.CrvEna", "Aktivierung der Kennlinie, Konfiguration des Kennlinienmodus"),
    "40941": U32(40941, "Inverter.UtilCrvCfg.CrvModCfg.CrvEna", "Aktivierung der Kennlinie, Konfiguration des Kennlinienmodus"),
    "40957": U32(40957, "Inverter.UtilCrvCfg.Crv0.XRef", "Kennlinie X-Achsen Referenz"),
    "40959": U32(40959, "Inverter.UtilCrvCfg.Crv0.XRef", "Kennlinie X-Achsen Referenz"),
    "40961": U32(40961, "Inverter.UtilCrvCfg.Crv0.XRef", "Kennlinie X-Achsen Referenz"),
    "40977": U32(40977, "Inverter.UtilCrvCfg.Crv0.YRef", "Kennlinie Y-Achsen Referenz"),
    "40979": U32(40979, "Inverter.UtilCrvCfg.Crv0.YRef", "Kennlinie Y-Achsen Referenz"),
    "40981": U32(40981, "Inverter.UtilCrvCfg.Crv0.YRef", "Kennlinie Y-Achsen Referenz"),
    "40997": U32(40997, "Inverter.DGSModCfg.HystVolNom", "Hysteresespannung, Konfiguration der dynamischen Netzstützung"),
    "40999": S32(40999, "Inverter.VArModCfg.PFCtlComCfg.PFEEI", "Sollwert cos(Phi) gemäß EEI-Konvention"),
    "41121": U32(41121, "GridGuard.CntrySet", "Setze Ländernorm"),
    "41123": U32(41123, "GridGuard.Cntry.VolCtl.ReconMin", "Min. Spannung zur Wiederzuschaltung"),
    "41125": U32(41125, "GridGuard.Cntry.VolCtl.ReconMax", "Max. Spannung zur Wiederzuschaltung"),
    "41127": U32(41127, "GridGuard.Cntry.FrqCtl.ReconMin", "Untere Frequenz für Wiederzuschaltung"),
    "41129": U32(41129, "GridGuard.Cntry.FrqCtl.ReconMax", "Obere Frequenz für Wiederzuschaltung"),
    "41131": U32(41131, "DcCfg.StrVol", "minimale Spannung Eingang "),
    "41133": U32(41133, "DcCfg.StrVol", "minimale Spannung Eingang "),
    "41155": U32(41155, "DcCfg.StrTms", "Startverzögerung Eingang "),
    "41157": U32(41157, "DcCfg.StrTms", "Startverzögerung Eingang "),
    "41169": U32(41169, "GridGuard.Cntry.LeakRisMin", "Minimaler Isolationswiderstand"),
    "41171": U32(41171, "Metering.TotkWhOutSet", "Setze Gesamtertrag"),
    "41173": U32(41173, "Metering.TotOpTmhSet", "Setze Gesamte Betriebszeit am Netzanschlusspunkt"),
    "41187": U32(41187, "Inverter.CtlComCfg.CtlMsSrc", "Quelle der Referenzmessung zur Blind-/Wirkleistungsregelung"),
    "41193": U32(41193, "Inverter.CtlComCfg.WCtlCom.CtlComMssMod", "Betriebsart für ausbleibende Wirkleistungsbegrenzung"),
    "41195": U32(41195, "Inverter.CtlComCfg.WCtlCom.TmsOut", "Timeout für ausbleibende Wirkleistungsbegrenzung"),
    "41197": U32(41197, "Inverter.CtlComCfg.WCtlCom.FlbWNom", "Fallback Wirkleistungsbegrenzung P in % von WMax für ausbleibende Wirkleistungsbegrenzung"),
    "41199": U32(41199, "PCC.WMaxNom", "Eingestellte Wirkleistungsgrenze am Netzanschlusspunkt"),
    "41203": U32(41203, "Plnt.DcWRtg", "Anlagen-Nennleistung"),
    "41215": S32(41215, "Inverter.WModCfg.WCtlComCfg.FlbWSpt", "Fallback Leistung für Betriebsart WCtlCom"),
    "41217": U32(41217, "PCC.WMax", "Eingestellte Wirkleistungsgrenze am Netzanschlusspunkt"),
    "41219": U32(41219, "Inverter.CtlComCfg.VArCtlCom.CtlComMssMod", "Betriebsart für ausbleibende Blindleistungsregelung"),
    "41221": U32(41221, "Inverter.CtlComCfg.VArCtlCom.TmsOut", "Timeout für ausbleibende Blindleistungsregelung"),
    "41223": S32(41223, "Inverter.CtlComCfg.VArCtlCom.FlbVArNom", "Fallback Blindleistung Q in % von WMax für ausbleibende Blindleistungsregelung"),
    "41225": U32(41225, "Inverter.CtlComCfg.PFCtlCom.CtlComMssMod", "Betriebsart für ausbleibende cos Phi-Vorgabe"),
    "41227": U32(41227, "Inverter.CtlComCfg.PFCtlCom.TmsOut", "Timeout für ausbleibende cos Phi-Vorgabe"),
    "41229": S32(41229, "Inverter.CtlComCfg.PFCtlCom.FlbPF", "Fallback cos Phi für ausbleibende cos Phi-Vorgabe"),
    "41253": U32(41253, "Inverter.FstStop", "Schnellabschaltung"),
    "41255": S16(41255, "Inverter.WModCfg.WCtlComCfg.WNomPrc", "Normierte Wirkleistungsbegrenzung durch Anlagensteuerung"),
    "41256": S16(41256, "Inverter.VArModCfg.VArCtlComCfg.VArNomPrc", "Normierte Blindleistungsbegrenzung durch Anlagensteuerung"),
    "41257": S32(41257, "Inverter.VArModCfg.PFCtlComCfg.PFEEI", "Sollwert cos(Phi) gemäß EEI-Konvention")}
