"""Constants of the EBaC integration."""

DOMAIN = "ebac"

# The address of ebac-api: http://HOST:PORT/PATH, as the EBaC app
# announces it (Supervisor discovery) or as typed in the setup.
CONF_URL = "url"

# Options
CONF_TRANSLATION = "translation"  # the translation to read from ("AV")
CONF_READ_ON = "read_on"  # how many verses "read on" reads
DEFAULT_READ_ON = 5
MAX_READ_ON = 20

# The EBaC app's address on Home Assistant's internal network, for the
# manual setup's default (the app's host name is its slug, with "-").
DEFAULT_URL = "http://bda2b308-ebac:8080/cgi-bin/ebac"

# The sentence file written for Assist (config/custom_sentences/LANG/).
SENTENCES_FILE = "ebac.yaml"
LANGUAGE = "en"

# Where each voice device's place (the last verses read) is kept.
STORAGE_KEY = "ebac.places"
STORAGE_VERSION = 1

# The intents
INTENT_READ = "EbacRead"
INTENT_NEXT = "EbacNext"
INTENT_PREVIOUS = "EbacPrevious"
INTENT_REPEAT = "EbacRepeat"
INTENT_READ_ON = "EbacReadOn"
INTENT_SEARCH = "EbacSearch"
INTENT_TRANSLATION = "EbacTranslation"
INTENT_WHICH_TRANSLATION = "EbacWhichTranslation"

# How many verses a search reads aloud, after saying how many it found.
SEARCH_READ = 1
