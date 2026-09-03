import io
import imaplib
import ssl
import uuid
import zipfile

import pytest

from app.modules.suppliers.acquisition_contracts import AcquisitionFailure
from app.modules.suppliers.asbis_acquisition import _join
from app.modules.suppliers.asbis_ean import (
    AsbisEanStatus,
    is_valid_ean13,
    resolve_asbis_ean,
)
from app.modules.suppliers.asbis_imap import latest_asbis_attachment
from app.modules.suppliers.asbis_imap import _newest_message_ids
from app.modules.suppliers.asbis_parsing import (
    action_records,
    html_from_zip,
    xml_records,
)
from app.modules.suppliers.enums import SupplierSourceType
from app.modules.suppliers.source_probe_schemas import SourceCredentialWrite
from app.modules.suppliers.source_validation_service import (
    SupplierSourceValidationService,
)
from app.modules.suppliers.schema_type_inference import SchemaFieldInferer


def test_asbis_configuration_and_two_credential_pairs() -> None:
    parsed = SupplierSourceValidationService.normalize_configuration(
        SupplierSourceType.API,
        {
            "base_url": "https://services.it4profit.com/product/sr/710",
            "authentication_type": "BASIC",
            "integration_profile": "ASBIS_IT4PROFIT",
            "catalog_endpoint_path": "ProductList.xml",
            "price_endpoint_path": "PriceAvail.xml",
            "imap_host": "mail.monitor.rs",
            "imap_allow_legacy_dh": True,
        },
    )
    assert parsed["imap_port"] == 993
    assert parsed["imap_allow_legacy_dh"] is True
    credentials = SourceCredentialWrite(
        placement="QUERY",
        username="api-user",
        password="api-password",
        username_parameter="USERNAME",
        password_parameter="PASSWORD",
        imap_username="luka@monitor.rs",
        imap_password="imap-password",
    )
    assert credentials.imap_username == "luka@monitor.rs"


def test_asbis_notes_length_does_not_depend_on_empty_schema_sample() -> None:
    inferred = SchemaFieldInferer.fields(uuid.uuid4(), [{"NOTES": ""}])
    assert inferred[0].entity.name == "NOTES"
    assert inferred[0].entity.max_length == 5_000
    assert inferred[0].entity.nullable is True


@pytest.mark.parametrize(
    ("primary", "secondary", "value", "status"),
    [
        ("0743878066494", "0743878066494", "0743878066494", AsbisEanStatus.MATCH),
        ("0743878066494", "", "0743878066494", AsbisEanStatus.PRIMARY_ONLY),
        ("743878066494", "", "0743878066494", AsbisEanStatus.PRIMARY_ONLY),
        (
            "743878066494",
            "0743878066494",
            "0743878066494",
            AsbisEanStatus.MATCH,
        ),
        ("", "4711174723669", "4711174723669", AsbisEanStatus.SECONDARY_ONLY),
        (
            "1111111111111",
            "4711174723669",
            "4711174723669",
            AsbisEanStatus.SECONDARY_VALID_PRIMARY_INVALID,
        ),
        (
            "4711174726028",
            "0",
            "4711174726028",
            AsbisEanStatus.PRIMARY_VALID_SECONDARY_INVALID,
        ),
        ("4006381333931", "5901234123457", "", AsbisEanStatus.CONFLICT),
        ("", "", "", AsbisEanStatus.MISSING),
        ("97855165893", "1", "", AsbisEanStatus.INVALID),
    ],
)
def test_asbis_ean_resolution_uses_shared_gtin_policy_deterministically(
    primary: str,
    secondary: str,
    value: str,
    status: AsbisEanStatus,
) -> None:
    result = resolve_asbis_ean(primary, secondary)
    assert result.value == value
    assert result.status == status


def test_asbis_ean13_validation_preserves_leading_zero_and_checks_checksum() -> None:
    assert is_valid_ean13("0743878066494") is True
    assert is_valid_ean13(" 0743878066494 ") is True
    assert is_valid_ean13("743878066494") is False
    assert is_valid_ean13("0743878066495") is False
    assert is_valid_ean13("1111111111111") is False


def test_asbis_xml_and_action_html_use_product_code() -> None:
    xml = b"<ProductCatalog><Product><ProductCode>AVSB20X30</ProductCode><Image>https://example.test/primary.jpg</Image><AttrList><element Name='Model' Value='X'/></AttrList><Images><Image>https://example.test/1.jpg</Image><Image>https://example.test/2.jpg</Image></Images></Product></ProductCatalog>"
    catalog = xml_records(xml, "catalog")[0]
    assert catalog["ProductCode"] == "AVSB20X30"
    assert catalog["ATTR_Model"] == "X"
    assert catalog["ATTRIBUTES"] == {"Model": "X"}
    assert catalog["PRIMARY_IMAGE_URL"] == "https://example.test/primary.jpg"
    assert catalog["IMAGE_URLS"] == [
        "https://example.test/1.jpg",
        "https://example.test/2.jpg",
    ]
    assert catalog["IMAGE_URL_2"] == "https://example.test/2.jpg"
    price_xml = b"<CONTENT><PRICES><PRICE><WIC>AVSB20X30</WIC><MY_PRICE>654.56</MY_PRICE></PRICE></PRICES></CONTENT>"
    assert xml_records(price_xml, "price")[0]["WIC"] == "AVSB20X30"
    html = b"""<table><tr class="tddiv"><td><a>AVSB20X30</a></td><td><img src="https://www.it4profit.com/theme/asbis-new/img/lite/hot.gif"><img src="https://www.it4profit.com/theme/asbis-new/img/lite/new.gif"><img src="https://www.it4profit.com/theme/asbis-new/img/lite/sale.gif">Opis</td><td>Novo</td><td>24</td><td>Zemun</td><td>8</td><td>900</td><td><input name="PRICE_LST_AVSB20X30" value="654.56"></td></tr></table>"""
    rows = action_records(html)
    assert rows == [
        {
            "ASBIS_PRODUCT_CODE": "AVSB20X30",
            "NOTES": "HOT, NEW, SALE",
            "PROMOTION_DESCRIPTION": "Opis",
            "PROMOTION_CONDITION": "Novo",
            "PROMOTION_WARRANTY": "24",
            "PROMOTION_WAREHOUSE": "Zemun",
            "PROMOTION_STOCK": "8",
            "PROMOTION_RETAIL_PRICE": "900",
            "PROMOTION_PRICE": "654.56",
        }
    ]
    joined, summary = _join(
        [catalog],
        [xml_records(price_xml, "price")[0]],
        rows,
    )
    assert joined[0]["PROMOTION_ACTIVE"] is True
    assert joined[0]["NOTES"] == "HOT, NEW, SALE"
    assert joined[0]["PROMOTION_PRICE"] == "654.56"
    assert summary["unmatched_promotion_records"] == 0

    without_action, _ = _join([{"ProductCode": "NO-ACTION"}], [], [])
    assert without_action[0]["PROMOTION_ACTIVE"] is False
    assert without_action[0]["NOTES"] == ""


def test_asbis_join_exposes_resolved_ean_without_changing_original_fields() -> None:
    joined, summary = _join(
        [
            {
                "ProductCode": "A",
                "ATTR_EAN Code": "4711174723669",
            },
            {
                "ProductCode": "B",
                "ATTR_EAN Code": "5901234123457",
            },
        ],
        [
            {"WIC": "A", "EAN": "1111111111111"},
            {"WIC": "B", "EAN": "4006381333931"},
        ],
        [],
    )
    assert joined[0]["EAN"] == "1111111111111"
    assert joined[0]["ATTR_EAN Code"] == "4711174723669"
    assert joined[0]["ASBIS_VALID_EAN"] == "4711174723669"
    assert joined[0]["ASBIS_EAN_STATUS"] == "SECONDARY_VALID_PRIMARY_INVALID"
    assert joined[1]["ASBIS_VALID_EAN"] == ""
    assert joined[1]["ASBIS_EAN_STATUS"] == "CONFLICT"
    assert summary["valid_ean_records"] == 1
    assert summary["ean_status_counts"] == {
        "CONFLICT": 1,
        "SECONDARY_VALID_PRIMARY_INVALID": 1,
    }


def test_asbis_rejects_duplicate_join_keys_and_unsafe_zip() -> None:
    with pytest.raises(AcquisitionFailure) as duplicate:
        _join(
            [{"ProductCode": "ABC"}],
            [{"WIC": "ABC"}, {"WIC": " abc "}],
            [],
        )
    assert duplicate.value.code == "acquisition_asbis_price_duplicate_code"

    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("readme.txt", "nije cenovnik")
    with pytest.raises(AcquisitionFailure) as invalid:
        html_from_zip(payload.getvalue(), 1024)
    assert invalid.value.code == "acquisition_asbis_zip_invalid"


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ssl.SSLError("DH_KEY_TOO_SMALL"), "acquisition_asbis_imap_tls_failed"),
        (OSError("connection refused"), "acquisition_asbis_imap_unavailable"),
    ],
)
def test_asbis_imap_reports_connection_failures_precisely(
    monkeypatch: pytest.MonkeyPatch, error: Exception, code: str
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr("imaplib.IMAP4_SSL", fail)
    with pytest.raises(AcquisitionFailure) as failure:
        latest_asbis_attachment(
            {"imap_host": "mail.example.test", "imap_port": 993},
            "user",
            "password",
            1024,
        )
    assert failure.value.code == code


def test_asbis_imap_reports_authentication_failure_precisely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Client:
        def __enter__(self) -> "Client":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def login(self, username: str, password: str) -> None:
            raise imaplib.IMAP4.error("authentication failed")

    monkeypatch.setattr("imaplib.IMAP4_SSL", lambda *args, **kwargs: Client())
    with pytest.raises(AcquisitionFailure) as failure:
        latest_asbis_attachment(
            {"imap_host": "mail.example.test", "imap_port": 993},
            "user",
            "password",
            1024,
        )
    assert failure.value.code == "acquisition_asbis_imap_authentication_failed"


def test_asbis_imap_orders_candidates_by_internal_date_not_listing_order() -> None:
    class Client:
        dates = {
            "90": b'90 (INTERNALDATE "31-Aug-2026 19:00:00 +0200")',
            "12": b'12 (INTERNALDATE "01-Sep-2026 17:37:08 +0200")',
            "150": b'150 (INTERNALDATE "01-Sep-2026 08:00:00 +0200")',
            "bad": b"bad (FLAGS (\\Seen))",
        }

        def fetch(self, message_id: str, query: str) -> tuple[str, list[bytes]]:
            assert query == "(INTERNALDATE)"
            return "OK", [self.dates[message_id]]

    assert _newest_message_ids(Client(), ["90", "12", "150", "bad"]) == [
        "12",
        "150",
        "90",
        "bad",
    ]
