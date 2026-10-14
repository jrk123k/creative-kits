# Continuity report

Checked **4** file(s) in `examples/drafts` against **41** rule(s) in `rules.yaml`.

**Findings:** 17 (6 error, 8 warning, 3 info).

| Severity | Findings |
|---|---|
| error | 6 |
| warning | 8 |
| info | 3 |

## By rule

| Severity | Rule | Findings | Title |
|---|---|---|---|
| error | `ban-sphero-in-news` | 1 | No Sphero in news |
| error | `harbor-florist-id-imagine` | 1 | Florist identity in Imagine prompt |
| error | `harbor-hero-id-imagine` | 1 | Hero identity in Imagine prompt |
| error | `harbor-sweetheart-id-imagine` | 1 | Sweetheart identity in Imagine prompt |
| error | `nova-gown-not-canon` | 1 | No gown |
| error | `nova-look-v1` | 1 | Nova look line |
| warning | `colin-figment-wardrobe` | 1 | Colin wardrobe |
| warning | `harbor-boss-vest-charcoal` | 1 | Boss vest charcoal |
| warning | `harbor-hero-id-shotlist` | 1 | Hero identity on shot-list cell |
| warning | `harbor-sweetheart-id-shotlist` | 1 | Sweetheart identity on shot-list cell |
| warning | `nova-voice-cfg` | 1 | Voice cfg |
| warning | `nova-voice-exaggeration` | 1 | Voice exaggeration |
| warning | `nova-voice-temperature` | 1 | Voice temperature |
| warning | `sarah-ashford-wardrobe` | 1 | Sarah wardrobe |
| info | `spell-sweetheart` | 3 | Spell Sweetheart |

## Findings

### 1. error — Hero identity in Imagine prompt

**File:** `harbor-waltz/TEST_PROMPTS_3.md`  
**Line:** 3  
**Rule:** `harbor-hero-id-imagine` (required_verbatim)  
**Message:** Hero is named in this prompt, but the locked description is not there word for word. Source: harbor-waltz/bible.  
**Snippet:** `## Prompt: Hero tips his cap`

**Suggested fix:**

> Paste the locked block.
>
> Hero, a lean young man in his mid-twenties, clean-shaven, with dark brown wavy hair curling out under a grey flat tweed newsboy cap. Wide toothy grin, dark brows, warm brown eyes. Cream linen shirt with the sleeves rolled to the forearm, open collar, grey-brown suspenders, dark brown wool trousers.

### 2. error — Sweetheart identity in Imagine prompt

**File:** `harbor-waltz/TEST_PROMPTS_3.md`  
**Line:** 6  
**Rule:** `harbor-sweetheart-id-imagine` (required_verbatim)  
**Message:** Sweetheart is named in this prompt, but the locked description is not there word for word. Source: harbor-waltz/bible.  
**Snippet:** `## Prompt: Sweetheart waits`

**Suggested fix:**

> Paste the locked block.
>
> Sweetheart, a slender flapper in her mid-twenties with a glossy black chin-length bob, blunt bangs and a sleek curl at each cheek. Pale skin, smoky dark eye makeup, deep red lips, a cool level gaze. Emerald-green beaded drop-waist sleeveless dress with gold Art Deco chevrons, emerald felt cloche with a gold-and-green feather brooch, long pearl ropes, emerald bracelet, gold beaded clutch.

### 3. error — Florist identity in Imagine prompt

**File:** `harbor-waltz/TEST_PROMPTS_3.md`  
**Line:** 9  
**Rule:** `harbor-florist-id-imagine` (required_verbatim)  
**Message:** Florist is named in this prompt, but the locked description is not there word for word. Source: harbor-waltz/bible.  
**Snippet:** `## Prompt: Florist`

**Suggested fix:**

> Paste the locked block.
>
> Florist, a kindly man in his late sixties with neat swept-back silver-grey hair, wire-rimmed round glasses and a gentle closed smile. Pale yellow button shirt, maroon bow tie, long tan canvas work apron with a chest pocket holding a pencil.

### 4. error — Nova look line

**File:** `nova-pixel/BRIEF.md`  
**Line:** 3  
**Rule:** `nova-look-v1` (required_verbatim)  
**Message:** Look is named in this prompt, but the locked description is not there word for word. Source: nova-pixel/bible.  
**Snippet:** `Look line paraphrased on purpose so the checker can flag it:`

**Suggested fix:**

> Paste the locked block.
>
> grey-skinned alien woman, long straight silver hair, large black eyes, inverted-triangle forehead mark, silver metallic bodysuit with an inverted-triangle chest emblem, belt with an X-buckle

### 5. error — No gown

**File:** `nova-pixel/BRIEF.md`  
**Line:** 4  
**Rule:** `nova-gown-not-canon` (forbidden_in_context)  
**Message:** 'gown' is not allowed in this context.  
**Snippet:** `silver alien in a shiny suit and a ball gown.`

**Suggested fix:**

> Remove the banned term.

### 6. error — No Sphero in news

**File:** `veloria-show/NEWS_DRAFT.md`  
**Line:** 5  
**Rule:** `ban-sphero-in-news` (forbidden_in_context)  
**Message:** 'Sphero' is not allowed in this context.  
**Snippet:** `Sphero mark appears in the lower third by mistake.`

**Suggested fix:**

> Remove the banned term.

### 7. warning — Hero identity on shot-list cell

**File:** `harbor-waltz/SHOTLIST_v2.md`  
**Line:** 6  
**Rule:** `harbor-hero-id-shotlist` (required_verbatim)  
**Message:** Hero is named in this prompt, but the locked description is not there word for word. Source: harbor-waltz/bible.  
**Snippet:** `Hero tips his cap on the sidewalk`

**Suggested fix:**

> Paste the locked block.
>
> Hero, a lean young man in his mid-twenties, clean-shaven, with dark brown wavy hair curling out under a grey flat tweed newsboy cap. Wide toothy grin, dark brows, warm brown eyes. Cream linen shirt with the sleeves rolled to the forearm, open collar, grey-brown suspenders, dark brown wool trousers.

### 8. warning — Sweetheart identity on shot-list cell

**File:** `harbor-waltz/SHOTLIST_v2.md`  
**Line:** 8  
**Rule:** `harbor-sweetheart-id-shotlist` (required_verbatim)  
**Message:** Sweetheart is named in this prompt, but the locked description is not there word for word. Source: harbor-waltz/bible.  
**Snippet:** `Sweetheart spins once under a streetlamp`

**Suggested fix:**

> Paste the locked block.
>
> Sweetheart, a slender flapper in her mid-twenties with a glossy black chin-length bob, blunt bangs and a sleek curl at each cheek. Pale skin, smoky dark eye makeup, deep red lips, a cool level gaze. Emerald-green beaded drop-waist sleeveless dress with gold Art Deco chevrons, emerald felt cloche with a gold-and-green feather brooch, long pearl ropes, emerald bracelet, gold beaded clutch.

### 9. warning — Boss vest charcoal

**File:** `harbor-waltz/SHOTLIST_v2.md`  
**Line:** 9  
**Rule:** `harbor-boss-vest-charcoal` (term_lock)  
**Message:** Locked term is 'charcoal', not 'grey vest'.  
**Snippet:** `| S21 | 2:08.0-2:11.7 | One kick to the gizzard, and she told me to skidoo. | Boss at the desk with a grey vest |`

**Suggested fix:**

> Use the preferred term.

### 10. warning — Voice cfg

**File:** `nova-pixel/BRIEF.md`  
**Line:** 6  
**Rule:** `nova-voice-cfg` (custom)  
**Message:** Voice cfg. Matched 'cfg 0'.  
**Snippet:** `Voice UI draft: temperature 0.8, exaggeration 0.9, cfg 0.9.`

**Suggested fix:**

> Keep cfg at 0.5.

### 11. warning — Voice exaggeration

**File:** `nova-pixel/BRIEF.md`  
**Line:** 6  
**Rule:** `nova-voice-exaggeration` (custom)  
**Message:** Voice exaggeration. Matched 'exaggeration 0'.  
**Snippet:** `Voice UI draft: temperature 0.8, exaggeration 0.9, cfg 0.9.`

**Suggested fix:**

> Keep exaggeration at 0.3.

### 12. warning — Voice temperature

**File:** `nova-pixel/BRIEF.md`  
**Line:** 6  
**Rule:** `nova-voice-temperature` (custom)  
**Message:** Voice temperature. Matched 'temperature 0'.  
**Snippet:** `Voice UI draft: temperature 0.8, exaggeration 0.9, cfg 0.9.`

**Suggested fix:**

> Keep temperature at 0.5.

### 13. warning — Colin wardrobe

**File:** `veloria-show/NEWS_DRAFT.md`  
**Line:** 3  
**Rule:** `colin-figment-wardrobe` (term_lock)  
**Message:** Locked term is 'navy blazer', not 'white-tie'.  
**Snippet:** `Colin wears white-tie evening wear.`

**Suggested fix:**

> Use the preferred term.

### 14. warning — Sarah wardrobe

**File:** `veloria-show/NEWS_DRAFT.md`  
**Line:** 4  
**Rule:** `sarah-ashford-wardrobe` (term_lock)  
**Message:** Locked term is 'charcoal suit', not 'red jacket'.  
**Snippet:** `Sarah Ashford in a red jacket.`

**Suggested fix:**

> Use the preferred term.

### 15. info — Spell Sweetheart

**File:** `harbor-waltz/SHOTLIST_v2.md`  
**Line:** 8  
**Rule:** `spell-sweetheart` (name_spelling)  
**Message:** Spelling 'Sweetheart' is not the locked form 'Sweetheart'.  
**Snippet:** `| S10 | 0:48.0-0:52.0 | Just a little dance | Sweetheart spins once under a streetlamp |`

**Suggested fix:**

> Sweetheart

### 16. info — Spell Sweetheart

**File:** `harbor-waltz/TEST_PROMPTS_3.md`  
**Line:** 6  
**Rule:** `spell-sweetheart` (name_spelling)  
**Message:** Spelling 'Sweetheart' is not the locked form 'Sweetheart'.  
**Snippet:** `## Prompt: Sweetheart waits`

**Suggested fix:**

> Sweetheart

### 17. info — Spell Sweetheart

**File:** `harbor-waltz/TEST_PROMPTS_3.md`  
**Line:** 7  
**Rule:** `spell-sweetheart` (name_spelling)  
**Message:** Spelling 'Sweetheart' is not the locked form 'Sweetheart'.  
**Snippet:** `Sweetheart stands under the marquee in a green dress.`

**Suggested fix:**

> Sweetheart

## Files with no findings

Every scanned file has at least one finding.
