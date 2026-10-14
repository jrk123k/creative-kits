# Continuity Checker

> Code created with Cursor and Grok Bots.

CLI checks for draft continuity. Point it at a folder of drafts and `rules.yaml`.
It writes markdown and JSON reports. Sample corpus is fictional (`harbor-waltz`,
`nova-pixel`, `veloria-show`, `crew-voice-bible`).

## Commands

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

continuity-check examples/drafts --rules rules.yaml --md sample_report.md --json sample_report.json

python -m continuity_checker.vo_fit_cli samples/harbor-waltz/SHOTLIST_v2.md \
  --rates vo_rates.yaml --md sample_vo_fit.md --json sample_vo_fit.json

python -m continuity_checker.voice_bible_cli samples/drafts \
  --bible samples/crew-voice-bible/VOICE_BIBLE.md \
  --md sample_voice_bible.md --json sample_voice_bible.json
```

Exit `0` = no error findings. Exit `1` = at least one error. Exit `2` = bad inputs.

## Layout

```
examples/drafts/     fictional drafts that trip sample rules
examples/sources/    fictional bibles / briefs (checksummed)
samples/             vo-fit shot list + crew voice bible + tiny drafts
rules.yaml           editable checks
```

## License

MIT — see `LICENSE`.
