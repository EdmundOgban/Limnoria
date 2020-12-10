lang_strings = (
    "auto:Automatic",
    "EN:English",
    "DE:German",
    "FR:French",
    "ES:Spanish",
    "PT:Portuguese",
    "NL:Dutch",
    "PL:Polish",
    "RU:Russian",
    "JA:Japanese",
    "ZH:Chinese",
)

langs = {lang_code: lang_desc for lang_code, lang_desc in 
    (lang.rsplit(":", 1) for lang in lang_strings)}
