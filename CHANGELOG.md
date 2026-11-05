# Changelog

Each version's notes. A release on GitHub is made from its section here
when its tag (v0.6.2, say) is pushed: see .github/workflows/release.yml.

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
