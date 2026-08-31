from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ShortText = Annotated[str, Field(min_length=1, max_length=255)]
PathText = Annotated[str, Field(min_length=1, max_length=1024)]

_SECRET_TOKENS = (
    "api_key",
    "authorization",
    "bearer",
    "client_secret",
    "password",
    "private_key",
    "service_account_json",
    "token",
)


class StrictConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def reject_credential_fields(cls, value: Any) -> Any:
        if isinstance(value, dict):
            for key in value:
                normalized = str(key).lower().replace("-", "_")
                if any(token in normalized for token in _SECRET_TOKENS):
                    raise ValueError(
                        "Poverljivi podaci nisu dozvoljeni u konfiguraciji"
                    )
        return value


class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"


class AuthenticationType(StrEnum):
    NONE = "NONE"
    API_KEY = "API_KEY"
    BASIC = "BASIC"
    BEARER = "BEARER"
    PORTAL_FORM = "PORTAL_FORM"
    OAUTH2_CLIENT_CREDENTIALS = "OAUTH2_CLIENT_CREDENTIALS"
    CLIENT_CERTIFICATE = "CLIENT_CERTIFICATE"
    SOAP_BODY = "SOAP_BODY"


class ExpectedContentType(StrEnum):
    CSV = "CSV"
    EXCEL = "EXCEL"
    XML = "XML"
    JSON = "JSON"
    BINARY = "BINARY"
    AUTO = "AUTO"


class DeliveryMethod(StrEnum):
    FTP = "FTP"
    SFTP = "SFTP"
    HTTP = "HTTP"
    GOOGLE_DRIVE = "GOOGLE_DRIVE"
    EMAIL = "EMAIL"
    MANUAL_UPLOAD = "MANUAL_UPLOAD"


class ManualFileType(StrEnum):
    CSV = "CSV"
    EXCEL = "EXCEL"
    XML = "XML"
    JSON = "JSON"


BoundedParameters = Annotated[dict[str, str], Field(max_length=50)]

_APPROVED_INSECURE_HTTP_ENDPOINTS = {
    ("apicatalog.ewe.rs", 5001, "/api"),
}


def _validate_parameters(values: dict[str, str]) -> dict[str, str]:
    for key, value in values.items():
        if not 1 <= len(key) <= 128 or len(value) > 2048:
            raise ValueError(
                "Ključ ili vrednost parametra nisu u dozvoljenim granicama"
            )
        normalized = key.lower().replace("-", "_")
        if any(token in normalized for token in _SECRET_TOKENS):
            raise ValueError("Poverljivi podaci nisu dozvoljeni u parametrima")
    return values


def _secure_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL nije ispravan")
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"} or (
        parsed.hostname.startswith(("10.", "192.168.", "172."))
    )
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("URL nije ispravan") from exc
    normalized_path = parsed.path.rstrip("/") or "/"
    approved_http_endpoint = (
        parsed.hostname.lower(),
        port,
        normalized_path,
    ) in _APPROVED_INSECURE_HTTP_ENDPOINTS
    if approved_http_endpoint and (
        parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "EWE URL ne sme sadržati pristupne ili javne parametre"
        )
    if parsed.scheme != "https" and not local and not approved_http_endpoint:
        raise ValueError("HTTPS je obavezan za javne adrese")
    if len(value) > 2048:
        raise ValueError("URL je predugačak")
    return value


class ApiSourceConfiguration(StrictConfiguration):
    base_url: str
    endpoint_path: str | None = Field(default=None, max_length=1024)
    http_method: HttpMethod = HttpMethod.GET
    authentication_type: AuthenticationType = AuthenticationType.NONE
    request_headers: BoundedParameters = Field(default_factory=dict)
    query_parameters: BoundedParameters = Field(default_factory=dict)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    verify_tls: bool = True
    login_url: str | None = None
    login_submit_url: str | None = None
    username_field: str | None = Field(default=None, min_length=1, max_length=128)
    password_field: str | None = Field(default=None, min_length=1, max_length=128)
    login_form_fields: BoundedParameters = Field(default_factory=dict)
    integration_profile: Literal[
        "GENERIC", "KIMTEC_MSAN", "CT_SOAP", "PIN_SOAP"
    ] = "GENERIC"
    pin_shop_id: int = Field(default=4, ge=1, le=2_147_483_647)
    catalog_endpoint_path: str | None = Field(default=None, max_length=1024)
    price_endpoint_path: str | None = Field(default=None, max_length=1024)
    barcode_service_url: str | None = None
    barcode_soap_action: str = Field(
        default="http://www.msan.hr/B2B/GetProductsBarcodes",
        min_length=1,
        max_length=1024,
    )

    _url = field_validator("base_url")(_secure_url)
    _login_url = field_validator("login_url")(
        lambda value: _secure_url(value) if value else value
    )
    _login_submit_url = field_validator("login_submit_url")(
        lambda value: _secure_url(value) if value else value
    )
    _barcode_service_url = field_validator("barcode_service_url")(
        lambda value: _secure_url(value) if value else value
    )
    _headers = field_validator("request_headers")(_validate_parameters)
    _query = field_validator("query_parameters")(_validate_parameters)
    _form_fields = field_validator("login_form_fields")(_validate_parameters)

    @model_validator(mode="after")
    def portal_form_is_complete(self) -> ApiSourceConfiguration:
        if self.authentication_type != AuthenticationType.PORTAL_FORM:
            return self
        if not self.login_url or not self.username_field or not self.password_field:
            raise ValueError(
                "Portal prijava zahteva login URL i nazive polja za korisnika i lozinku"
            )
        return self

    @model_validator(mode="after")
    def integration_profile_is_complete(self) -> ApiSourceConfiguration:
        if self.integration_profile in {"CT_SOAP", "PIN_SOAP"}:
            if self.authentication_type != AuthenticationType.SOAP_BODY:
                raise ValueError(
                    "SOAP profil zahteva pristupni podatak u SOAP telu"
                )
            if self.http_method != HttpMethod.POST:
                raise ValueError("SOAP profil zahteva POST metod")
            if (
                self.integration_profile == "CT_SOAP"
                and not self.base_url.casefold().endswith(".asmx")
            ):
                raise ValueError("CT SOAP profil zahteva .asmx adresu servisa")
            return self
        if self.integration_profile != "KIMTEC_MSAN":
            return self
        if self.authentication_type != AuthenticationType.CLIENT_CERTIFICATE:
            raise ValueError(
                "KimTec / M SAN profil zahteva klijentski sertifikat"
            )
        if (
            not self.catalog_endpoint_path
            or not self.price_endpoint_path
            or not self.barcode_service_url
        ):
            raise ValueError(
                "KimTec / M SAN profil zahteva katalog, cenovnik i barcode servis"
            )
        return self


class HttpSourceConfiguration(StrictConfiguration):
    url: str
    http_method: HttpMethod = HttpMethod.GET
    request_headers: BoundedParameters = Field(default_factory=dict)
    query_parameters: BoundedParameters = Field(default_factory=dict)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    verify_tls: bool = True
    expected_content_type: ExpectedContentType = ExpectedContentType.AUTO

    _url = field_validator("url")(_secure_url)
    _headers = field_validator("request_headers")(_validate_parameters)
    _query = field_validator("query_parameters")(_validate_parameters)


class CsvSourceConfiguration(StrictConfiguration):
    delivery_method: DeliveryMethod
    filename_pattern: ShortText
    encoding: str = Field(default="utf-8", min_length=1, max_length=64)
    delimiter: str = Field(default=",", min_length=1, max_length=1)
    quote_character: str = Field(default='"', min_length=1, max_length=1)
    decimal_separator: Literal[".", ","] = "."
    has_header: bool = True
    expected_currency: str | None = Field(default=None, min_length=3, max_length=3)


class ExcelSourceConfiguration(StrictConfiguration):
    delivery_method: DeliveryMethod
    filename_pattern: ShortText
    sheet_name: str | None = Field(default=None, min_length=1, max_length=255)
    header_row: int = Field(default=1, ge=1, le=1_000_000)
    data_start_row: int = Field(default=2, ge=1, le=1_000_001)
    decimal_separator: Literal[".", ","] = "."
    expected_currency: str | None = Field(default=None, min_length=3, max_length=3)

    @model_validator(mode="after")
    def rows_are_ordered(self) -> ExcelSourceConfiguration:
        if self.data_start_row <= self.header_row:
            raise ValueError("Početni red podataka mora biti posle zaglavlja")
        return self


class XmlSourceConfiguration(StrictConfiguration):
    delivery_method: DeliveryMethod
    filename_pattern: ShortText
    root_path: PathText | None = None
    item_path: PathText
    namespace_mode: Literal["NONE", "AUTO", "EXPLICIT"] = "AUTO"
    expected_currency: str | None = Field(default=None, min_length=3, max_length=3)


class FtpSourceConfiguration(StrictConfiguration):
    host: ShortText
    port: int = Field(default=21, ge=1, le=65535)
    username: str | None = Field(default=None, min_length=1, max_length=255)
    remote_path: PathText = "/"
    passive_mode: bool = True
    use_tls: bool = False
    filename_pattern: ShortText
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class SftpSourceConfiguration(StrictConfiguration):
    host: ShortText
    port: int = Field(default=22, ge=1, le=65535)
    username: ShortText
    remote_path: PathText = "/"
    host_key_fingerprint: str | None = Field(
        default=None, min_length=16, max_length=255
    )
    filename_pattern: ShortText
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class GoogleDriveSourceConfiguration(StrictConfiguration):
    file_id: ShortText | None = None
    folder_id: ShortText | None = None
    filename_pattern: ShortText | None = None
    service_account_reference: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )
    shared_drive_id: ShortText | None = None

    @model_validator(mode="after")
    def file_or_folder(self) -> GoogleDriveSourceConfiguration:
        if not self.file_id and not self.folder_id:
            raise ValueError("file_id ili folder_id je obavezan")
        return self


class EmailSourceConfiguration(StrictConfiguration):
    mailbox: str = Field(min_length=3, max_length=320)
    folder: str | None = Field(default=None, min_length=1, max_length=255)
    sender_filter: str | None = Field(default=None, min_length=1, max_length=320)
    subject_filter: ShortText | None = None
    attachment_filename_pattern: ShortText
    received_within_hours: int = Field(default=24, ge=1, le=8760)


class ManualUploadSourceConfiguration(StrictConfiguration):
    accepted_file_types: list[ManualFileType] = Field(min_length=1, max_length=4)
    maximum_file_size_mb: int = Field(default=50, ge=1, le=1024)
    filename_pattern: ShortText | None = None


CONFIGURATION_MODELS: dict[str, type[StrictConfiguration]] = {
    "API": ApiSourceConfiguration,
    "CSV": CsvSourceConfiguration,
    "EXCEL": ExcelSourceConfiguration,
    "XML": XmlSourceConfiguration,
    "FTP": FtpSourceConfiguration,
    "SFTP": SftpSourceConfiguration,
    "HTTP": HttpSourceConfiguration,
    "GOOGLE_DRIVE": GoogleDriveSourceConfiguration,
    "EMAIL": EmailSourceConfiguration,
    "MANUAL_UPLOAD": ManualUploadSourceConfiguration,
}

__all__ = ["CONFIGURATION_MODELS", "AuthenticationType", "StrictConfiguration"]
