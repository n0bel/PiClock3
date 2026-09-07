from .Provider import Provider


class TextSource(Provider):
    """words from somewhere else.

    A headline, a departure board, a message left for whoever walks past:
    what they share is that the words change without anybody asking, so a
    widget has to be told rather than poll.

    Nothing ships with one.  The role is here so a plugin can be written
    against it and a config can point text-provider: at the result.
    """

    def subscribe(self, fn):
        """call fn() whenever the words change.

        Then the widget asks text() for them, the same way a weather
        widget draws from conditions() when it is told there is something
        new.
        """
        raise NotImplementedError(
            '%s: %s supplies text and has no subscribe'
            % (self.name, type(self).__name__))

    def text(self):
        """the words as they stand.

        Drawn as they are given: a source has already decided what it
        wants to say, and a widget that rewrote it would be guessing.
        """
        raise NotImplementedError(
            '%s: %s supplies text and has no text'
            % (self.name, type(self).__name__))
