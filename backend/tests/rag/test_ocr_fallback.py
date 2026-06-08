from app.services.rag.extractors.ocr_fallback import looks_garbled


def test_clean_spanish_text_is_not_garbled():
    text = (
        "Este Trabajo de Fin de Grado se centra en el diseño e implementación "
        "de un sistema inteligente para la indexación y búsqueda semántica de "
        "directorios locales, basado en un LLM local. Acentos: á é í ó ú ñ ü."
    )
    assert looks_garbled(text) is False


def test_clean_english_text_is_not_garbled():
    text = (
        "Rocket League is a 2015 vehicular soccer video game developed and "
        "published by Psyonix, offered as free-to-play since 2020."
    )
    assert looks_garbled(text) is False


def test_control_char_garbage_is_garbled():
    # Capa de texto con códigos de glifo crudos (\x03 como separador).
    text = "\x18\x04dK^\x03\x18\x1c>\x03dZ\x04\x11\x04:K\x03&/E\x03\x18\x1c\x03"
    assert looks_garbled(text) is True


def test_latin_extended_garbage_is_garbled():
    # cmap roto que mapea glifos a Latin Extended (ĞůĂĐŝſŶ en vez de texto).
    text = "ZĞůĂĐŝſŶͬĐŽŶƚƌŝďƵĐŝſŶ ĐŽŶ ůŽƐ KďũĞƚŝǀŽƐ ĚĞ ĞƐĂƌƌŽůůŽ ^ŽƐƚĞŶŝďůĞ"
    assert looks_garbled(text) is True


def test_empty_and_whitespace_are_not_garbled():
    assert looks_garbled("") is False
    assert looks_garbled("   \n\t  ") is False
