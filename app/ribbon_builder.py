class RibbonBuilder:
    """Adapter that owns ribbon construction entrypoint.

    The detailed ribbon composition still lives in `PDFReaderApp._build_toolbar_impl`
    to keep this refactor behavior-preserving; future changes can move groups from
    the impl into this builder incrementally.
    """

    def __init__(self, window):
        self.window = window

    def build(self):
        return self.window._build_toolbar_impl()
