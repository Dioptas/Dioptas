"""The EOSMAT boundary between Peritheos files and Dioptas's editable state."""

from peritheos import convert_eosmat


def normalize_material_document(document: dict) -> dict:
    """Expand native v4 through Peritheos; keep legacy v2/v3 state unchanged.

    Conversion preserves numerical values, observations and unknown extensions.
    Only the layout changes: downstream editors and calculations consume v3.
    """
    if document.get("format_version") == 4:
        return convert_eosmat(document, version=3)
    return document
