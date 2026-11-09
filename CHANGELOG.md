# Changelog

Each version's notes. A release on GitHub is made from its section here
by running the Release workflow (Actions tab): see .github/workflows/release.yml.

## 0.8.4

### Changed

- The second source is named as GitHub names it, **scrollmapper/bible_databases** (user/repository), under **Configure** and in the README, as thiagobodruk/bible already was.

## 0.8.3

### Fixed

- **A new address of the EBaC app is followed.** When the app announced itself at another address, Home Assistant turned the announcement away before the integration saw it (the integration was marked as allowing only one setup), so EBaC went on asking the old address. It is still set up only once.
- "Use Gutenberg translations", when that source has none in the language looked in, names the language ("it has none in Spanish"), not its code ("es").

## 0.8.2

### Fixed

- **"Use translation scrollmapper"** (the word "translation" before the name) is understood, for a source or a language; and "SM" for scrollmapper. Said of a translation added ("use translation KJVA"), it reads from it, as "change translation to KJVA" does (if changing is allowed).

## 0.8.1

### Fixed

- **A source's name heard nearly right is understood**: "Thiago Bodruck", "theago bodruck", "Gutenburg", "scroll map her" (speech to text spells names it doesn't know as it hears them). Tried only when no language has that name, and none of the 85 languages' names comes close.
- "Used Thiago Bodruk translations" ("use" heard as "used") is understood.

## 0.8.0

### Added

- **Where to add translations from**: a Source setting under **Configure** (thiagobodruk/bible, scrollmapper's bible_databases, or Project Gutenberg), beside the language, for the whole house; "use Gutenberg translations" or "use translations from Thiago Bodruk" changes it by voice. "Add translation NIV" then looks in that source and language, and both stay until changed, so several can be added one after another by name alone. Needs the EBaC app 2.14.0 or later.
- A name said without its source's ending means that source's: "NIV" is NIV-TB, "DRC" is DRC-PG. Project Gutenberg's texts can be asked for by ebook number too: "add translation 8294".
- Removing a translation by voice uses the importer that added it, whatever the source setting.

## 0.7.2

### Changed

- **EBaC voice compares words without the Hebrew chant marks** (cantillation and meteg), and whatever order a word's marks are stored in. The Westminster Leningrad Codex sets them inside its words, writing the divine name some 500 ways; with the EBaC app 2.12.12's list, all of them are said as tradition reads them (אֲדֹנָי, or אֱלֹהִים), by a Hebrew voice.

## 0.7.1

### Fixed

- **EBaC voice went silent** after its first answer, with "# channels not specified" in the log: it now asks the voice it speaks with for a whole recording, rather than handing on streamed audio.
- **No answer was spoken after "change translation"** through EBaC voice: changing the translation (or another option) set the whole integration up again, and EBaC voice was gone for a moment, just as the answer was being spoken. Now only reading is set up again; EBaC voice stays.

## 0.7.0

### Added

- **EBaC voice.** A text-to-speech voice that says some words another way and hands the text to a voice you already have (Home Assistant Cloud, Piper): יהוה, the divine name with no vowel points, is said as "Adonai" (a Hebrew voice read it as "yo"). Assist still shows the words as the text has them. Choose the voice it speaks with under **Configure**, and choose **EBaC voice** in a voice assistant (**Settings → Voice assistants**). Needs the EBaC app 2.12.11 or later for its list of words. README: "EBaC voice".

## 0.6.3

### Changed

- **When the EBaC app can't be reached.** If EBaC hasn't answered for 15 minutes (the app stopped, or uninstalled), a repair under **Settings → Repairs** says so: start the app again, reinstall it (restoring a backup made before it was removed brings its translations back), or remove this integration. It clears itself when EBaC answers again; **Submit** clears it until EBaC has answered and stopped again.
- README: "If the EBaC app is removed".

## 0.6.2

The first published release of EBaC for Assist: Bible verses read aloud by Home Assistant's voice assistant, from the [EBaC app](https://github.com/neilbrookins/ebac-ha-app) (version 2.7.0 or later; 2.10.4 or later for adding translations safely by voice).

### What it does

- **Reading.** Say "John 3:16", "First Corinthians 13:4 to 7", "Psalm 23" or "read Genesis", and hear the verses. Then "next verse", "previous verse", "next chapter", "previous chapter", "next book", "previous book", "start of chapter", "start of book", or "repeat verse" / "read that again".
- **Introductions.** "Jacob introduction", "the introduction to Alma chapter 5": the text before a chapter's verse 1, where a text has it (such as the Book of Mormon's book headings and summaries, added with the app's **P**).
- **Searching.** "Search the Bible for living water": the verses found, a few at a time, as on EBaC's screens.
- **Translations.** "Which translation is this" names the one in use; "change translation to ..."; "which translations do I have", "what translations can I add in Spanish", a few at a time.
- **Information.** "What version of EBaC is this", and "what is the license of this translation".

### What Assist may do

Beyond reading and searching, each is off unless you check it, at setup or under **Configure**, and each needs the one before it:

- **Allow Assist to change the translation**
- **Allow Assist to add translations**: asks you to agree to the translation's license first, adds it in the background, and says when it is done (or notifies your phone). If it fails, Home Assistant shows a repair saying why, which **Submit** clears.
- **Allow Assist to remove translations**: asks "Are you sure?" first. EBaC's own translations can't be removed.

Adding and removing also need the EBaC app's own options. The app stops adding while less than 1 GB of disk is free, so voice can't fill the disk.

### Since 0.6.1

- The add option no longer warns about filling the disk (the app guards it now).
- The README's installing steps have a button that opens the integration in Marketplace, and say a restart is needed only with HACS (before Home Assistant 2026.11).

### Installing

See the [README](https://github.com/neilbrookins/ebac-ha-integration#installing). Updating from an earlier, unreleased copy: update in Marketplace (or HACS), then restart Home Assistant.
