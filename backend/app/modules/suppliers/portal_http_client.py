from __future__ import annotations

import asyncio
import http.cookiejar
import ssl
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin

from app.modules.suppliers.acquisition_contracts import (
    AcquisitionFailure,
    HttpResponse,
)


async def portal_request(
    *,
    login_url: str,
    login_submit_url: str | None,
    download_url: str,
    username_field: str,
    password_field: str,
    username: str,
    password: str,
    form_fields: dict[str, str],
    headers: dict[str, str],
    query: dict[str, str],
    timeout_seconds: int,
    verify_tls: bool,
) -> HttpResponse:
    return await asyncio.to_thread(
        _portal_request,
        login_url,
        login_submit_url,
        download_url,
        username_field,
        password_field,
        username,
        password,
        form_fields,
        headers,
        query,
        timeout_seconds,
        verify_tls,
    )


def _portal_request(
    login_url: str,
    login_submit_url: str | None,
    download_url: str,
    username_field: str,
    password_field: str,
    username: str,
    password: str,
    form_fields: dict[str, str],
    headers: dict[str, str],
    query: dict[str, str],
    timeout_seconds: int,
    verify_tls: bool,
) -> HttpResponse:
    context = ssl.create_default_context()
    if not verify_tls:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    cookies = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookies),
        urllib.request.HTTPSHandler(context=context),
    )
    try:
        with opener.open(
            urllib.request.Request(login_url, headers=headers),
            timeout=timeout_seconds,
        ) as response:
            login_page = response.read()
        parser = LoginFormParser(username_field)
        parser.feed(login_page.decode("utf-8", errors="replace"))
        if parser.action is None:
            raise AcquisitionFailure(
                "acquisition_portal_form_not_found",
                "Na portalu nije pronađena očekivana forma za prijavu",
            )
        actual_username = (
            username_field
            if username_field in parser.input_names
            else parser.detected_username_field
        )
        actual_password = (
            password_field
            if password_field in parser.input_names
            else parser.detected_password_field
        )
        if not actual_username or not actual_password:
            raise AcquisitionFailure(
                "acquisition_portal_fields_not_found",
                "Na portalu nisu pronađena polja za korisničko ime i lozinku",
            )
        fields = dict(parser.hidden_fields)
        fields.update(form_fields)
        fields[actual_username] = username
        fields[actual_password] = password
        login_headers = {**headers, "Content-Type": "application/x-www-form-urlencoded"}
        submit_url = login_submit_url or urljoin(login_url, parser.action)
        with opener.open(
            urllib.request.Request(
                submit_url,
                data=urllib.parse.urlencode(fields).encode(),
                headers=login_headers,
                method="POST",
            ),
            timeout=timeout_seconds,
        ) as response:
            response.read()
        target = _target(download_url, query)
        with opener.open(
            urllib.request.Request(target, headers=headers, method="GET"),
            timeout=timeout_seconds,
        ) as response:
            return HttpResponse(
                status_code=response.status,
                content=response.read(),
                content_type=response.headers.get_content_type(),
                filename=response.headers.get_filename(),
            )
    except HTTPError as exc:
        message = (
            "Podaci za prijavu na portal nisu prihvaćeni"
            if exc.code in {401, 403}
            else f"Portal dobavljača je vratio status {exc.code}"
        )
        raise AcquisitionFailure("acquisition_portal_login_failed", message) from exc
    except (TimeoutError, URLError) as exc:
        raise AcquisitionFailure(
            "acquisition_portal_unavailable",
            "Portal dobavljača nije odgovorio ili nije dostupan",
        ) from exc


def _target(url: str, query: dict[str, str]) -> str:
    parsed = urllib.parse.urlsplit(url)
    parameters = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    parameters.update(query)
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(parameters), parsed.fragment)
    )


class LoginFormParser(HTMLParser):
    def __init__(self, username_field: str) -> None:
        super().__init__()
        self.username_field = username_field
        self.action: str | None = None
        self.hidden_fields: dict[str, str] = {}
        self.input_names: set[str] = set()
        self.detected_username_field: str | None = None
        self.detected_password_field: str | None = None
        self._action: str | None = None
        self._hidden: dict[str, str] = {}
        self._inputs: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag.lower() == "form":
            self._action = attributes.get("action") or ""
            self._hidden = {}
            self._inputs = {}
        elif tag.lower() == "input" and self._action is not None:
            name = attributes.get("name")
            if not name:
                return
            kind = (attributes.get("type") or "text").lower()
            self._inputs[name] = kind
            if kind == "hidden":
                self._hidden[name] = attributes.get("value") or ""

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "form" or self._action is None:
            return
        has_password = "password" in self._inputs.values()
        if self.username_field in self._inputs or (self.action is None and has_password):
            self.action = self._action
            self.hidden_fields = dict(self._hidden)
            self.input_names = set(self._inputs)
            self.detected_password_field = next(
                (name for name, kind in self._inputs.items() if kind == "password"),
                None,
            )
            self.detected_username_field = next(
                (name for name, kind in self._inputs.items() if kind in {"text", "email"}),
                None,
            )
        self._action = None


__all__ = ["portal_request"]
