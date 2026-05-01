"""JSON-safe replacement mapping helpers for experimental Yandex uploads (v0.11)."""


def build_upload_replacement_mapping(
    *,
    original_external_id: str,
    local_file_id: int,
    uploaded_external_id: str | None,
    upload_status: str,
    detail: str | None = None,
) -> dict[str, object]:
    """Describe Original track -> Local file -> (optional) uploaded user track surrogate id."""
    return {
        "original_yandex_external_id": original_external_id,
        "local_file_id": int(local_file_id),
        "uploaded_yandex_external_id": uploaded_external_id,
        "upload_status": upload_status,
        "replacement_ready": uploaded_external_id is not None,
        "detail": detail or "",
    }
