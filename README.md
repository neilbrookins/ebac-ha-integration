# EBaC for Assist

Bible verses read aloud by Home Assistant's voice assistant, Assist, from [EBaC (Electronic Bible and Concordance)](https://github.com/neilbrookins/ebac). Say "John 3:16" and hear the verse; then "next verse".

This integration needs the **EBaC app** ([github.com/neilbrookins/ebac-ha-app](https://github.com/neilbrookins/ebac-ha-app)), version 2.6.1 or later, which runs EBaC itself. (Or any web server running EBaC's `ebac-api`.)

## Installing

1. Install the EBaC app, if you haven't, and start it.
2. In HACS, open the menu (⋮) → **Custom repositories**, add `https://github.com/neilbrookins/ebac-ha-integration` as an **Integration**, then download **EBaC (Electronic Bible and Concordance)**.
3. Restart Home Assistant.
4. Under **Settings → Devices & services**, EBaC is shown as discovered: press **Add** and **Submit**. (If it isn't, press **Add integration**, choose EBaC, and keep the address filled in.)

## What to say

| Say | Hears |
|---|---|
| "John 3:16", "John three sixteen", "Genesis one colon one" | that verse |
| "First Corinthians 13:4 to 7" | those verses |
| "Psalm 23", "read Genesis" | the first verses of the chapter or book |
| "Jude 3" | Jude 1:3 (a book of one chapter) |
| "next verse", "previous verse" | the verse after or before the last one heard |
| "read that again" | the last verses again |
| "read on", "keep reading" | the next few verses |
| "search the Bible for jesus wept" | how many verses have those words, and the first |

Books may be said as "First Samuel", "1st Samuel", "1 Samuel" or "I Samuel"; numbers as digits, words ("one hundred nineteen", "a hundred and nineteen") or Roman numerals (speech to text often writes "Genesis I colon I"). Each voice device (a speaker, a phone) keeps its own place, so "next verse" goes on from what that device last read.

A search is in EBaC's own syntax, where words alone are a phrase: "search the Bible for faith hope charity" finds verses with those words together.

## Options

Under **Settings → Devices & services → EBaC → Configure**: the translation to read from (any added in the EBaC app), and how many verses "read on" reads.

## How it works

At setup, the integration asks EBaC for the translation's books and the ways numbers are said, and writes `custom_sentences/en/ebac.yaml` in your configuration folder from them: Assist's sentences for EBaC. (Home Assistant has no other way for an integration to add sentences.) Because the sentences name only real books and numbers, they don't take over other commands. The file is written again when the integration starts or its options change, and removed with the integration; put sentences of your own in another file.

The EBaC app answers on port 8080 of Home Assistant's internal network only, so nothing outside Home Assistant reaches it; it only reads. The design is in EBaC's [readme.architecture](https://github.com/neilbrookins/ebac/blob/main/readme.architecture), under "Voice".

Sentences are in English for now.

## License

GNU General Public License, version 2, as EBaC. See [`LICENSE`](LICENSE).
