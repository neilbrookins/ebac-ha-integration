# EBaC for Assist

Bible verses read aloud by Home Assistant's voice assistant, Assist, from [EBaC (Electronic Bible and Concordance)](https://github.com/neilbrookins/ebac). Say "John 3:16" and hear the verse; then "next verse".

This integration needs the **EBaC app** ([github.com/neilbrookins/ebac-ha-app](https://github.com/neilbrookins/ebac-ha-app)), version 2.7.0 or later, which runs EBaC itself. (Or any web server running EBaC's `ebac-api`.)

## Installing

1. Install the EBaC app, if you haven't, and start it: **[installing the EBaC app](https://github.com/neilbrookins/ebac-ha-app#installing)** has a button that adds it to your Home Assistant in one click, and the steps after it. (Already have it? Make sure it is version 2.7.0 or later, under **Settings → Apps → EBaC**.)
2. In HACS, open the menu (⋮) → **Custom repositories**, add `https://github.com/neilbrookins/ebac-ha-integration` as an **Integration**, then download **EBaC (Electronic Bible and Concordance)**.
3. Restart Home Assistant.
4. Under **Settings → Devices & services**, EBaC is shown as discovered: press **Add** and **Submit**. (If it isn't, press **Add integration**, choose EBaC, and keep the address filled in.)
5. Choose the translation to read from (the King James Version is offered first), the language to add translations in (English unless you choose another), and what Assist may do beyond reading (see [What Assist may do](#what-assist-may-do)). Press **Submit**. You can change these later, under **Configure**.

## What to say

| Say | Hears |
|---|---|
| "John 3:16", "John three sixteen", "Genesis one colon one" | that verse |
| "First Corinthians 13:4 to 7" | those verses |
| "Psalm 23", "read Genesis" | the first verses of the chapter or book |
| "Jude 3" | Jude 1:3 (a book of one chapter) |
| "next verse", "previous verse" | the verse after or before the last one heard |
| "repeat verse", "read that again", "one more time" | the last verses again |
| "read on", "keep reading" | the next few verses |
| "search the Bible for jesus wept 0" | how many verses have those words; one is read, several are listed, five at a time: "1, Matthew 26:75; 2, Mark 14:72; 3, John 11:35" |
| "result two", "the second result" | that result, which "next verse" and "previous verse" then go on from |
| "next result", "previous result" | the result after or before the one you are at |
| "more results", "earlier results" | the next or previous five in the list |
| "back to the results" | the list again, where you left it, as **x** on EBaC's screen |
| "next chapter", "previous chapter", "start of the chapter" | the first verses of that chapter, on into the next book after a book's last |
| "next book", "previous book", "start of the book" | the first verses of that book |
| "read back" | the verses before, as many as "read on" reads |
| "change translation to KJVA", "switch to the Lexham translation" | reads from that translation from now on, in the whole house (if allowed) |
| "which translation is this?" | the translation in use, and the others installed (only the one in use, if changing isn't allowed) |
| "which translations are added?" | the translations installed |
| "what's the license of this translation?" | the license agreed to when it was added |
| "what version of EBaC is this?" | EBaC's version, and where to get help |
| "use Spanish translations", "manipulate translations Spanish" | the language "add translation" looks in, from now on (if adding is allowed) |
| "which languages are there?", "what translations are there (in Spanish)?" | what can be added, ten at a time: "more languages", "more translations" |
| "add translation LITV", "add the Lexham translation" | its license, then "do you agree?": "yes" adds it (if allowed) |
| "remove translation LITV" | "are you sure?": "yes" removes it (if allowed) |

Books may be said as "First Samuel", "1st Samuel", "1 Samuel" or "I Samuel"; numbers as digits, words ("one hundred nineteen", "a hundred and nineteen") or Roman numerals (speech to text often writes "Genesis I colon I"). Each voice device (a speaker, a phone) keeps its own place, so "next verse" goes on from what that device last read.

A translation is named by its short name (letter by letter is fine: "K J V A") or words of its title ("King James", "Reina Valera"); if the words fit more than one, it asks which, and changes nothing. Only translations added in the EBaC app can be chosen. After a change, "next verse" goes on from the same verse in the new translation.

A search is in EBaC's own syntax, where words alone are a phrase: "search the Bible for faith hope charity" finds verses with those words together. As on EBaC's screens, a search has two levels: its list of results, and the verse you picked from it, read with the verses around it. Each device keeps both: going on through a passage doesn't lose your place in the list. After the translation is changed, the list is the same words searched again in the new one.

A search by voice is EBaC's own syntax said literally ("search the Bible for jesus wept 0"): its operators aren't English words, so that "and" can be searched for as a word.

## What Assist may do

Anyone who can talk to a voice assistant, a speaker in a room or the Home Assistant app, can use what you allow here, with no user name or password. So beyond reading and searching, each is off unless you check it, at setup or under **Configure**, and each needs the one above it (**Submit** says so if not):

| Checkbox | The risk |
|---|---|
| **Allow Assist to change the translation** | someone could switch to a translation you keep private (your own diary, imported as one) and hear it read aloud |
| **Allow Assist to add translations** | someone could add every translation of a language and fill Home Assistant's disk |
| **Allow Assist to remove translations** | someone could delete a translation you paid for, such as the NIV |

With changing off, Assist reads only the translation chosen under **Configure**, and names no other. Adding and removing also need the EBaC app's own options, **Allow voice to add translations** and **Allow voice to remove translations** (under **Settings → Apps → EBaC → Configuration**), because the app's address can be reached by anything on Home Assistant's internal network.

**Upgrading from 0.4 or earlier:** every box starts off, changing the translation too, which earlier versions allowed by voice. Check it under **Configure** to allow it again.

### Adding and removing by voice

Adding is one step when the language is already the one you want: "add translation LITV" looks only in that language (English unless chosen otherwise; "use Spanish translations" changes it, for the whole house). A name that fits several translations gets them listed.

1. Assist reads the translation's license and asks whether you agree.
2. Answer "yes" or "no". On a voice speaker, say the wake word first, as for any command: Assist doesn't keep listening after a question when it answers with its own sentences (Home Assistant, as of October 2026). The question waits five minutes, for the same speaker or phone.
3. Adding takes a minute or two (the download, then the index). Assist says it has started; when it is done, a voice speaker announces it, and the Home Assistant app gets a notification. The new translation is then the one read from, here only: the EBaC app still starts with its own. If adding fails, it shows under **Settings → Repairs**, saying why. A failed add leaves nothing behind, so the repair is a notice: open it and press **Submit** to clear it. Adding that translation, or removing it, clears it too.

The same version of a translation already added isn't downloaded again: remove it first. Removing asks "Are you sure?" first. EBaC's own translations, such as the King James Version, can't be removed. If you remove the translation in use, Assist reads from the EBaC app's first translation instead, and says so.

## Options

Under **Settings → Devices & services → EBaC → Configure**: the translation to read from (any added in the EBaC app), how many verses "read on" reads, the language to add translations in, and the three checkboxes above.

## How it works

At setup, the integration asks EBaC for the translation's books and the ways numbers are said, and writes `custom_sentences/en/ebac.yaml` in your configuration folder from them: Assist's sentences for EBaC. (Home Assistant has no other way for an integration to add sentences.) Because the sentences name only real books and numbers, they don't take over other commands. The file is written again when the integration starts or its options change, and removed with the integration; put sentences of your own in another file.

The EBaC app answers on port 8080 of Home Assistant's internal network only, so nothing outside Home Assistant reaches it; it only reads. The design is in EBaC's [readme.architecture](https://github.com/neilbrookins/ebac/blob/main/readme.architecture), under "Voice".

Sentences are in English for now.

## License

GNU General Public License, version 2, as EBaC. See [`LICENSE`](LICENSE).
