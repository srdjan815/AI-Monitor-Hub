export const methods = [
  ["HTTP", "Direktan URL", "Cenovnik je dostupan preko stabilne internet adrese."],
  ["PORTAL", "Portal sa prijavom", "Sistem se prijavljuje na B2B portal i zatim preuzima cenovnik."],
  ["API", "API dobavljača", "Dobavljač nudi servis za automatsko preuzimanje podataka."],
  ["FTP", "FTP", "Dobavljač ostavlja cenovnik na FTP serveru."],
  ["SFTP", "SFTP", "Bezbedno preuzimanje fajla sa udaljenog servera."],
  ["EMAIL", "Email", "Cenovnik stiže kao prilog email poruke."],
  ["GOOGLE_DRIVE", "Google Drive", "Dobavljač deli fajl ili folder preko Google Drive-a."],
  ["MANUAL_UPLOAD", "Ručno učitavanje", "Zaposleni preuzima fajl i učitava ga u aplikaciju."],
] as const;

export const initialForm = {
  method: "HTTP", name: "", portal_supplier_code: "", format: "AUTO", url: "", endpoint: "",
  login_url: "", login_submit_url: "", username_field: "username", password_field: "password",
  login_form_fields: "", http_method: "GET", login_required: false, placement: "HEADER",
  authentication_type: "NONE", integration_profile: "GENERIC",
  catalog_endpoint: "/B2BService/HTTP/Product/GetProductsList.aspx",
  price_endpoint: "/B2BService/HTTP/Product/GetProductsPriceList.aspx",
  barcode_service_url: "https://b2b.kimtec.rs/B2BService/B2BProductService.asmx",
  pin_shop_id: "4", certificate_password: "", username: "", password: "", imap_username: "",
  imap_password: "", token: "", api_key: "", username_parameter: "username",
  password_parameter: "password", api_key_parameter: "X-API-Key", public_query: "",
  public_headers: "", timeout: "30", verify_tls: true, host: "", port: "", remote_path: "/",
  filename_pattern: "*", mailbox: "", folder: "", sender: "", subject: "", received_hours: "24",
  imap_host: "mail.monitor.rs", imap_port: "993", file_id: "", folder_id: "", shared_drive_id: "",
  maximum_mb: "50", description: "",
};

export type ConnectionForm = typeof initialForm;

export function pairs(value: string): Record<string, string> {
  return Object.fromEntries(value.split("\n").map((line) => line.split("=", 2).map((item) => item.trim())).filter(([key, item]) => key && item));
}

export function withAuthenticationType(form: ConnectionForm, value: string): ConnectionForm {
  return value === "SOAP_BODY"
    ? { ...form, authentication_type: value, integration_profile: "CT_SOAP", placement: "SOAP_BODY", http_method: "POST", format: "JSON", url: form.url || "https://www.ct4partners.com/WS/CTProductsInStock.asmx", endpoint: "", name: form.name || "CT SOAP cenovnik" }
    : { ...form, authentication_type: value, integration_profile: form.integration_profile === "CT_SOAP" ? "GENERIC" : form.integration_profile, placement: form.placement === "SOAP_BODY" ? "HEADER" : form.placement };
}

export function withSoapProfile(form: ConnectionForm, value: string): ConnectionForm {
  return value === "PIN_SOAP"
    ? { ...form, integration_profile: value, authentication_type: "SOAP_BODY", placement: "SOAP_BODY", http_method: "POST", format: "JSON", url: "https://partner.pinsoft.com/b2b/services/stock-webservice", endpoint: "", api_key_parameter: "guid", name: form.name || "PIN / ALSO cenovnik" }
    : { ...form, integration_profile: "CT_SOAP", authentication_type: "SOAP_BODY", placement: "SOAP_BODY", http_method: "POST", format: "JSON", url: "https://www.ct4partners.com/WS/CTProductsInStock.asmx", endpoint: "", api_key_parameter: "X-API-Key" };
}

export function withIntegrationProfile(form: ConnectionForm, value: string): ConnectionForm {
  if (value === "ASBIS_IT4PROFIT") {
    return { ...form, integration_profile: value, authentication_type: "BASIC", placement: "QUERY", url: "https://services.it4profit.com/product/sr/710", endpoint: "", catalog_endpoint: "ProductList.xml", price_endpoint: "PriceAvail.xml", username_parameter: "USERNAME", password_parameter: "PASSWORD", imap_host: "mail.monitor.rs", imap_port: "993", imap_username: "", format: "JSON", name: form.name || "ASBIS - objedinjeni cenovnik" };
  }
  if (value === "KIMTEC_MSAN") {
    return { ...form, integration_profile: value, url: "https://b2b.kimtec.rs", endpoint: "", format: "JSON", barcode_service_url: "https://b2b.kimtec.rs/B2BService/B2BProductService.asmx", name: form.name || "KimTec / M SAN - kompletan cenovnik" };
  }
  return { ...form, integration_profile: value };
}

export function isPortalReady(form: ConnectionForm): boolean {
  return form.method !== "PORTAL" || Boolean(form.url.trim() && form.login_url.trim() && form.username_field.trim() && form.password_field.trim() && form.username.trim() && form.password);
}

export function isCertificateReady(form: ConnectionForm, certificateFile: File | null, credentialsAvailable?: boolean): boolean {
  return form.authentication_type !== "CLIENT_CERTIFICATE" || Boolean((certificateFile && form.certificate_password) || credentialsAvailable);
}

export function sourcePayload(form: ConnectionForm): Record<string, unknown> {
  const timeout_seconds = Number(form.timeout);
  let source_type = form.method;
  let configuration: Record<string, unknown>;
  if (form.method === "PORTAL") {
    source_type = "API";
    configuration = { base_url: form.url, endpoint_path: null, http_method: "GET", authentication_type: "PORTAL_FORM", login_url: form.login_url, login_submit_url: form.login_submit_url || null, username_field: form.username_field, password_field: form.password_field, login_form_fields: pairs(form.login_form_fields), request_headers: pairs(form.public_headers), query_parameters: pairs(form.public_query), timeout_seconds, verify_tls: form.verify_tls };
  } else if (form.method === "HTTP" && form.login_required) {
    source_type = "API";
    configuration = { base_url: form.url, endpoint_path: null, http_method: form.http_method, authentication_type: form.authentication_type, request_headers: pairs(form.public_headers), query_parameters: pairs(form.public_query), timeout_seconds, verify_tls: form.verify_tls };
  } else if (form.method === "HTTP") {
    configuration = { url: form.url, http_method: form.http_method, request_headers: pairs(form.public_headers), query_parameters: pairs(form.public_query), timeout_seconds, verify_tls: form.verify_tls, expected_content_type: form.format };
  } else if (form.method === "API") {
    configuration = {
      base_url: form.url, endpoint_path: form.endpoint || null, http_method: form.http_method,
      authentication_type: form.authentication_type, request_headers: pairs(form.public_headers),
      query_parameters: pairs(form.public_query), timeout_seconds, verify_tls: form.verify_tls,
      integration_profile: form.integration_profile,
      pin_shop_id: form.integration_profile === "PIN_SOAP" ? Number(form.pin_shop_id) : 4,
      catalog_endpoint_path: ["KIMTEC_MSAN", "ASBIS_IT4PROFIT"].includes(form.integration_profile) ? form.catalog_endpoint : null,
      price_endpoint_path: ["KIMTEC_MSAN", "ASBIS_IT4PROFIT"].includes(form.integration_profile) ? form.price_endpoint : null,
      barcode_service_url: form.integration_profile === "KIMTEC_MSAN" ? form.barcode_service_url : null,
      imap_host: form.integration_profile === "ASBIS_IT4PROFIT" ? form.imap_host : null,
      imap_port: form.integration_profile === "ASBIS_IT4PROFIT" ? Number(form.imap_port) : 993,
      imap_allow_legacy_dh: form.integration_profile === "ASBIS_IT4PROFIT",
      imap_folder: "INBOX", imap_subject_filter: "ASBIS",
      imap_sender_filter: form.integration_profile === "ASBIS_IT4PROFIT" ? form.sender || null : null,
      imap_attachment_prefix: "HTML, PO actions, in mail body", imap_received_within_hours: 720,
    };
  } else if (form.method === "FTP") {
    configuration = { host: form.host, port: Number(form.port || 21), username: form.username || null, remote_path: form.remote_path, passive_mode: true, use_tls: form.verify_tls, filename_pattern: form.filename_pattern, timeout_seconds };
  } else if (form.method === "SFTP") {
    configuration = { host: form.host, port: Number(form.port || 22), username: form.username, remote_path: form.remote_path, filename_pattern: form.filename_pattern, timeout_seconds };
  } else if (form.method === "EMAIL") {
    configuration = { mailbox: form.mailbox, folder: form.folder || null, sender_filter: form.sender || null, subject_filter: form.subject || null, attachment_filename_pattern: form.filename_pattern, received_within_hours: Number(form.received_hours) };
  } else if (form.method === "GOOGLE_DRIVE") {
    configuration = { file_id: form.file_id || null, folder_id: form.folder_id || null, filename_pattern: form.filename_pattern || null, shared_drive_id: form.shared_drive_id || null };
  } else {
    configuration = { accepted_file_types: form.format === "AUTO" ? ["CSV", "EXCEL", "XML", "JSON"] : [form.format], maximum_file_size_mb: Number(form.maximum_mb), filename_pattern: form.filename_pattern || null };
  }
  return { name: form.name, portal_supplier_code: form.portal_supplier_code || null, source_type, configuration, description: form.description || null, status: "DRAFT" };
}
