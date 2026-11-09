"""
Initial local language knowledge for SENSE-1.

This is intentionally small and conservative.

It is not intended to represent the complete vocabulary of any
language or dialect. Future verified knowledge can be added through
the BAIG knowledge/learning system.
"""

ENGLISH_MARKERS = {
    "the",
    "is",
    "are",
    "was",
    "were",
    "what",
    "why",
    "how",
    "when",
    "where",
    "who",
    "which",
    "with",
    "and",
    "or",
    "this",
    "that",
    "these",
    "those",
    "price",
    "market",
    "company",
    "business",
    "research",
    "analysis",
    "gold",
    "oil",
    "revenue",
    "increased",
    "decreased",
    "today",
}


NIGERIAN_PIDGIN_WORDS = {
    "abeg",
    "dey",
    "don",
    "wetin",
    "una",
    "sef",
    "abi",
    "wey",
    "wan",
    "fit",
    "gist",
    "pikin",
    "oga",
    "chop",
}


NIGERIAN_PIDGIN_PHRASES = {
    "how much",
    "wetin dey happen",
    "wetin happen",
    "how e be",
    "make we",
    "abeg check",
}


ENGLISH_SLANG = {
    "gonna",
    "wanna",
    "gotta",
    "kinda",
    "sorta",
    "yeah",
    "yep",
    "nope",
    "bro",
    "lol",
}


SPELLING_CORRECTIONS = {
    "teh": "the",
    "recieve": "receive",
    "recieved": "received",
    "seperate": "separate",
    "definately": "definitely",
    "occured": "occurred",
}


# These are not treated as proof of a language by themselves.
# They are useful supporting signals when combined with other evidence.
IGBO_MARKERS = {
    "ndi",
    "onye",
    "biko",
    "kedu",
    "mba",
}


YORUBA_MARKERS = {
    "bawo",
    "se",
    "mo",
    "o",
    "ni",
}


HAUSA_MARKERS = {
    "ina",
    "yaya",
    "sannu",
    "na",
    "kai",
}


SPANISH_MARKERS = {
    "hola",
    "gracias",
    "porque",
    "pero",
    "como",
    "estoy",
    "esta",
    "son",
    "precio",
    "mercado",
    "empresa",
    "ingresos",
    "aumento",
}

FRENCH_MARKERS = {
    "bonjour",
    "merci",
    "pourquoi",
    "mais",
    "avec",
    "suis",
    "est",
    "sont",
    "prix",
    "marche",
    "entreprise",
    "revenus",
}

GERMAN_MARKERS = {
    "hallo",
    "danke",
    "warum",
    "aber",
    "mit",
    "ist",
    "sind",
    "preis",
    "markt",
    "unternehmen",
    "umsatz",
}

PORTUGUESE_MARKERS = {
    "ola",
    "obrigado",
    "porque",
    "mas",
    "com",
    "estou",
    "esta",
    "sao",
    "preco",
    "mercado",
    "empresa",
    "receita",
}

ITALIAN_MARKERS = {
    "ciao",
    "grazie",
    "perche",
    "ma",
    "con",
    "sono",
    "prezzo",
    "mercato",
    "azienda",
    "ricavi",
}

BRITISH_ENGLISH_MARKERS = {
    "colour",
    "centre",
    "organise",
    "analyse",
    "travelling",
    "favour",
    "cheque",
}

AMERICAN_ENGLISH_MARKERS = {
    "color",
    "center",
    "organize",
    "analyze",
    "traveling",
    "favor",
    "check",
}
