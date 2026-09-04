import { describe, expect, it } from "vitest";

import { initialForm, isPortalReady, pairs, sourcePayload, withAuthenticationType, withIntegrationProfile, withSoapProfile } from "./sourceForm";

describe("source form payload", () => {
  it("parses only complete key/value rows", () => {
    expect(pairs("Authorization=Bearer token\ninvalid\nX-Tenant = monitor"))
      .toEqual({ Authorization: "Bearer token", "X-Tenant": "monitor" });
  });

  it("maps portal access to an API source with portal authentication", () => {
    const payload = sourcePayload({
      ...initialForm,
      method: "PORTAL",
      name: "EPI portal",
      portal_supplier_code: "EPI",
      url: "https://supplier.example/home",
      login_url: "https://supplier.example/login",
      login_form_fields: "remember=1",
    });

    expect(payload).toMatchObject({
      name: "EPI portal",
      portal_supplier_code: "EPI",
      source_type: "API",
      configuration: {
        base_url: "https://supplier.example/home",
        authentication_type: "PORTAL_FORM",
        login_url: "https://supplier.example/login",
        login_form_fields: { remember: "1" },
        timeout_seconds: 30,
        verify_tls: true,
      },
    });
  });

  it("keeps legacy TLS compatibility scoped to the ASBIS profile", () => {
    const generic = sourcePayload({ ...initialForm, method: "API" });
    const asbis = sourcePayload({
      ...initialForm,
      method: "API",
      integration_profile: "ASBIS_IT4PROFIT",
    });

    expect(generic.configuration).toMatchObject({ imap_allow_legacy_dh: false });
    expect(asbis.configuration).toMatchObject({ imap_allow_legacy_dh: true });
  });

  it("uses safe protocol defaults for FTP and SFTP", () => {
    const ftp = sourcePayload({ ...initialForm, method: "FTP", port: "" });
    const sftp = sourcePayload({ ...initialForm, method: "SFTP", port: "" });

    expect(ftp.configuration).toMatchObject({ port: 21 });
    expect(sftp.configuration).toMatchObject({ port: 22 });
  });

  it("applies supplier integration presets without overwriting a custom name", () => {
    const asbis = withIntegrationProfile({ ...initialForm, name: "Moj izvor" }, "ASBIS_IT4PROFIT");
    const pin = withSoapProfile(initialForm, "PIN_SOAP");
    const soap = withAuthenticationType(initialForm, "SOAP_BODY");

    expect(asbis).toMatchObject({ name: "Moj izvor", placement: "QUERY", username_parameter: "USERNAME" });
    expect(pin).toMatchObject({ integration_profile: "PIN_SOAP", api_key_parameter: "guid" });
    expect(soap).toMatchObject({ integration_profile: "CT_SOAP", placement: "SOAP_BODY" });
  });

  it("requires every portal login field before allowing a probe", () => {
    const incomplete = { ...initialForm, method: "PORTAL", url: "https://portal.example", login_url: "https://portal.example/login", username: "user", password: "" };
    expect(isPortalReady(incomplete)).toBe(false);
    expect(isPortalReady({ ...incomplete, password: "secret" })).toBe(true);
  });
});
