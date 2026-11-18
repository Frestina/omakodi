"""English names for the language codes Kodi gives audio tracks
(SPEC "Audio tracks"). Kodi reports ISO 639-2 codes (both the
terminology and the older bibliographic forms), sometimes ISO 639-1, and
add-ons often a 639-1 code with a region ("en-US")."""

import re

# 639-1, 639-2/T, 639-2/B (when it differs), English name.
_TABLE = """
af afr - Afrikaans
sq sqi alb Albanian
am amh - Amharic
ar ara - Arabic
hy hye arm Armenian
az aze - Azerbaijani
eu eus baq Basque
be bel - Belarusian
bn ben - Bengali
bs bos - Bosnian
bg bul - Bulgarian
my mya bur Burmese
ca cat - Catalan
zh zho chi Chinese
hr hrv - Croatian
cs ces cze Czech
da dan - Danish
nl nld dut Dutch
en eng - English
eo epo - Esperanto
et est - Estonian
fo fao - Faroese
fi fin - Finnish
fr fra fre French
gl glg - Galician
ka kat geo Georgian
de deu ger German
el ell gre Greek
kl kal - Greenlandic
gu guj - Gujarati
ha hau - Hausa
he heb - Hebrew
hi hin - Hindi
hu hun - Hungarian
is isl ice Icelandic
id ind - Indonesian
ga gle - Irish
it ita - Italian
ja jpn - Japanese
kn kan - Kannada
kk kaz - Kazakh
km khm - Khmer
ko kor - Korean
ku kur - Kurdish
ky kir - Kyrgyz
lo lao - Lao
la lat - Latin
lv lav - Latvian
lt lit - Lithuanian
lb ltz - Luxembourgish
mk mkd mac Macedonian
ms msa may Malay
ml mal - Malayalam
mt mlt - Maltese
mi mri mao Maori
mr mar - Marathi
mn mon - Mongolian
ne nep - Nepali
se sme - Northern Sami
no nor - Norwegian
nb nob - Norwegian Bokmål
nn nno - Norwegian Nynorsk
ps pus - Pashto
fa fas per Persian
pl pol - Polish
pt por - Portuguese
pa pan - Punjabi
ro ron rum Romanian
ru rus - Russian
gd gla - Scottish Gaelic
sr srp - Serbian
si sin - Sinhala
sk slk slo Slovak
sl slv - Slovenian
so som - Somali
es spa - Spanish
sw swa - Swahili
sv swe - Swedish
tl tgl - Tagalog
tg tgk - Tajik
ta tam - Tamil
tt tat - Tatar
te tel - Telugu
th tha - Thai
bo bod tib Tibetan
tr tur - Turkish
tk tuk - Turkmen
uk ukr - Ukrainian
ur urd - Urdu
uz uzb - Uzbek
vi vie - Vietnamese
cy cym wel Welsh
yi yid - Yiddish
yo yor - Yoruba
xh xho - Xhosa
zu zul - Zulu
"""

NAMES = {}
for _line in _TABLE.strip().splitlines():
    _two, _t, _b, _name = _line.split(" ", 3)
    for _code in (_two, _t, _b):
        if _code != "-":
            NAMES[_code] = _name
NAMES.update({"fil": "Filipino", "yue": "Cantonese", "cmn": "Mandarin", "sgn": "Sign language"})

NONE = {"", "und", "unk", "mul", "zxx", "mis", "qaa", "xx", "none"}
MAX_CODE = 20
MAX_NAME = 40
_CODE = re.compile(r"^([A-Za-z]{2,3})(?:[-_]([A-Za-z0-9]{2,8}))?$")


def name(code):
    """"eng", "en", "en-US" → "English", "English (US)"; an unknown code as
    it is (letters, digits and "-" only); "" for none."""
    if not isinstance(code, str):
        return ""
    c = code.strip()
    if c.lower() in NONE:
        return ""
    m = _CODE.match(c)
    if m and m.group(1).lower() in NAMES:
        base = NAMES[m.group(1).lower()]
        region = m.group(2) or ""
        # A region in capitals (BR, 419); a script as written (Hant).
        region = region.upper() if len(region) <= 3 else region.title()
        return (f"{base} ({region})" if region else base)[:MAX_NAME]
    return re.sub(r"[^A-Za-z0-9-]", "", c)[:MAX_CODE]
