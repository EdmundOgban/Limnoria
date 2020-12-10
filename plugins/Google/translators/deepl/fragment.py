import time


s = "sopra la panca la capra campa, sotto la panca la capra crepaz"

def fragment(s):
    end = 0
    top = len(s)
    while True:
        end += 5
        yield s[:end]
        if end >= top:
            break
        time.sleep(0.5)

print(list(fragment(s)))
