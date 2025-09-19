"""Status note for Codex hand-off."""

note = """
Latest work:
- Firehose fullscreen toggle wired up; only starts during step 2 processing and now stays visible when processing finishes.
- Setup layout tightened: import/processing sub-sections share a narrower max width and centered buttons; typography uses new root font scale variables.
- `DataManager.load_exported_data` now tolerates legacy list/dict export shapes to avoid AttributeError during dashboard loads.

Next prompt:
"""

prompt = (
    "Review the setup page styling in a browser to confirm the centered layout and larger fonts, "
    "then run the processing flow end-to-end to ensure the firehose stays visible post-completion. "
    "If that looks good, consider adding regression tests for the new export normalization."
)

if __name__ == "__main__":
    print(note.strip())
    print()
    print(prompt)
