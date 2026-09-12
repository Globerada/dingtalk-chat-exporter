class DingTalkExporterError(Exception):
    """Base exception for expected exporter failures."""


class DiscoveryError(DingTalkExporterError):
    pass


class CompatibilityError(DingTalkExporterError):
    pass


class DatabaseReconstructionError(DingTalkExporterError):
    pass


class SchemaError(DingTalkExporterError):
    pass


class ExportError(DingTalkExporterError):
    pass
