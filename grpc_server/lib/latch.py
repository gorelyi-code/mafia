class Latch:
    def __init__(self, count, callback):
        self.cur = 0
        self.count = count
        self.callback = callback

    def __call__(self, *args):
        self.cur += 1
        if self.cur == self.count:
            self.cur = 0
            self.callback(*args)