"""Constants of the EBaC integration."""

DOMAIN = "ebac"

# The address of ebac-api: http://HOST:PORT/PATH, as the EBaC app
# announces it (Supervisor discovery) or as typed in the setup.
CONF_URL = "url"

# Options
CONF_TRANSLATION = "translation"  # the translation to read from ("AV")
CONF_READ_ON = "read_on"  # how many verses "read on" reads
# What Assist may do beyond reading (see "Permissions" in EBaC's
# readme.architecture): each off unless checked, each needing the one
# before it. Anyone who can talk to a speaker can use them.
CONF_ALLOW_CHANGE = "allow_change"  # change the translation
CONF_ALLOW_ADD = "allow_add"  # add translations (needs change)
CONF_ALLOW_REMOVE = "allow_remove"  # remove translations (needs add)
# The language group: the language "add translation X" looks in (a code,
# as the EBaC app's list of translations has them: en, es, grc)
CONF_LANGUAGE = "language"
# Where "add translation" looks (with the language): one of SOURCES, for
# the whole house; set in Configure, or by voice ("use Gutenberg
# translations"). ebac-admin's source= (EBaC's readme.architecture,
# "Sources by voice").
CONF_SOURCE = "source"
DEFAULT_SOURCE = "scrollmapper"
# Each source: how it is named in Configure and said, its short names'
# suffix (implied when a name is said: "NIV" is NIV-TB), where its
# licenses' details are, and the words that name it by voice
SOURCES: dict[str, dict] = {
    "thiagobodruk": {
        "label": "thiagobodruk/bible on GitHub (names end in -TB)",
        "spoken": "thiagobodruk/bible",
        "suffix": "-TB",
        "details": "on the source's page about its licenses",
        "said": ["thiagobodruk", "thiago bodruk", "thiago", "bodruk", "tb",
                 "thiago bodruk bible", "thiagobodruk bible"],
    },
    "scrollmapper": {
        "label": "scrollmapper's bible_databases on GitHub",
        "spoken": "scrollmapper's bible databases",
        "suffix": "",
        "details": "on CrossWire's page for it",
        "said": ["scrollmapper", "scroll mapper", "scrollmaster", "scroll master",
                 "bible databases", "crosswire"],
    },
    "gutenberg": {
        "label": "Project Gutenberg (by ebook number; names end in -PG)",
        "spoken": "Project Gutenberg",
        "suffix": "-PG",
        "details": "on its page at Project Gutenberg",
        "said": ["gutenberg", "project gutenberg", "guttenberg", "project guttenberg", "pg"],
    },
}

# The voice EBaC voice (tts.py) hands its text to, with EBaC's words said
# another way: a text-to-speech entity ("tts.home_assistant_cloud"); none
# set, Home Assistant Cloud's or Piper's
CONF_SPEAK_WITH = "speak_with"
DEFAULT_LANGUAGE = "en"
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
INTENT_RESULT = "EbacResult"
INTENT_NEXT_RESULT = "EbacNextResult"
INTENT_PREVIOUS_RESULT = "EbacPreviousResult"
INTENT_MORE_RESULTS = "EbacMoreResults"
INTENT_EARLIER_RESULTS = "EbacEarlierResults"
INTENT_BACK_TO_RESULTS = "EbacBackToResults"
INTENT_USE_LANGUAGE = "EbacUseLanguage"
INTENT_LIST_LANGUAGES = "EbacListLanguages"
INTENT_LIST_AVAILABLE = "EbacListAvailable"
INTENT_LIST_ADDED = "EbacListAdded"
INTENT_MORE_LIST = "EbacMoreList"
INTENT_EARLIER_LIST = "EbacEarlierList"
INTENT_ADD = "EbacAdd"
INTENT_REMOVE = "EbacRemove"
INTENT_YES = "EbacYes"
INTENT_NO = "EbacNo"
INTENT_NEXT_CHAPTER = "EbacNextChapter"
INTENT_PREVIOUS_CHAPTER = "EbacPreviousChapter"
INTENT_START_CHAPTER = "EbacStartOfChapter"
INTENT_READ_BACK = "EbacReadBack"
INTENT_NEXT_BOOK = "EbacNextBook"
INTENT_PREVIOUS_BOOK = "EbacPreviousBook"
INTENT_START_BOOK = "EbacStartOfBook"
INTENT_VERSION = "EbacVersion"
INTENT_LICENSE = "EbacLicense"

# How many of a search's results are listed at a time (their references).
RESULTS_PER_LIST = 5

# How many languages or translations are listed at a time, by voice
ITEMS_PER_LIST = 10
# How long a question ("Do you agree?", "Are you sure?") waits for its
# yes, in seconds
CONFIRM_SECONDS = 300
# How often an add's progress is asked for, and for how long at most
ADD_POLL_SECONDS = 10
ADD_MAX_SECONDS = 3600
