class LogDisplay:
    def __init__(self, viewer):
        self.viewer = viewer

    def print(self, text):
        self.viewer.appendPlainText(text)
