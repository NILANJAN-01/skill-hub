"""A text buffer that hides how lines are stored."""


class TextBuffer:
    """Editable text addressed by character offsets.

    Callers never see lines: offsets are counted in characters from the
    start of the text, and ranges are half-open [start, end).
    """

    def __init__(self, text=""):
        self._lines = text.split("\n")

    def insert(self, offset, new_text):
        """Insert new_text so that it starts at offset.

        Offsets past the end are clamped to the end, so there is no
        out-of-range error to handle.
        """
        text = self.text()
        offset = max(0, min(offset, len(text)))
        self._lines = (text[:offset] + new_text + text[offset:]).split("\n")

    def delete(self, start, end):
        """Remove the characters in [start, end); an empty or inverted range does nothing."""
        text = self.text()
        start, end = max(0, start), min(end, len(text))
        if start < end:
            self._lines = (text[:start] + text[end:]).split("\n")

    def text(self):
        """Return the whole text, lines joined with newline characters."""
        return "\n".join(self._lines)

    def is_empty(self):
        """True when the buffer holds no characters."""
        return self.text() == ""


def remove_file(path):
    """Make sure path no longer exists. Missing files are not an error."""
    import os
    try:
        os.remove(path)
    except FileNotFoundError:
        pass  # already gone: the postcondition holds
