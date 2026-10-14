# Voice bible report

Checked **2** file(s) in `samples/drafts` against **8** bot(s) in `samples/crew-voice-bible/VOICE_BIBLE.md`.

**Findings:** 1 (1 error, 0 warning, 0 info).

## Bots

| Bot | voiceId | Status | Retired |
|---|---|---|---|
| Harbor | `liora` | locked | — |
| Ledger | `ara` | locked | carina |
| Quill | `luna` | locked | lumen |
| Lens | `celeste` | locked | altair |
| Stack | `iris` | locked | sirius |
| Index | `naksh` | locked | — |
| Signal | `vega` | locked | — |
| Ember | `ursa` | proposed | — |

## Findings

### 1. error — stale alias

**File:** `stale-alias-example/IDEA.md`  
**Line:** 3  
**Speaker:** Ledger  
**Voice in draft:** carina  
**Locked voiceId:** ara  
**Message:** Ledger is listed as carina, a stale alias. Locked voiceId is ara.  
**Snippet:** `This draft still lists Ledger as 'carina'.`

**Suggested fix:**

> Replace carina with ara.

## Files with no findings

- `crew-tour-idea/IDEA.md`
