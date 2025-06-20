from constants import MAX_INTENSITY


def palette_electric():
    palette = []
    for i in range(MAX_INTENSITY + 1):
        t = i / MAX_INTENSITY
        r = 0
        g = 0
        b = 0
        if t < 0.5:
            r = int(30 * t * 2)  # 0 → 30
            g = 0
            b = int(50 + 205 * t * 2)  # 50 → 255
        else:
            scale = (t - 0.5) * 2
            r = int(80 * scale)  # 0 → 80
            g = int(180 * scale)  # 0 → 180
            b = 255
        palette.append([r, g, b])
    return palette


def palette_toxic():
    palette = []
    for i in range(MAX_INTENSITY + 1):
        t = i / MAX_INTENSITY
        r = 0
        g = 0
        b = 0
        if t < 0.5:
            r = 0
            g = int(30 + 225 * t * 2)  # 30 → 255
            b = 0
        else:
            scale = (t - 0.5) * 2
            r = int(100 * scale)  # 0 → 100
            g = 255
            b = int(50 * (1 - scale))  # 50 → 0
        palette.append([r, g, b])
    return palette


def palette_sunset():
    palette = []
    for i in range(MAX_INTENSITY + 1):
        t = i / MAX_INTENSITY
        r = 0
        g = 0
        b = 0
        if t < 0.33:
            r = int(50 + 610 * (t / 0.33))  # 50 → 255
            g = 0
            b = int(80 + 130 * (t / 0.33))  # 80 → 210
        elif t < 0.66:
            scale = (t - 0.33) / 0.33
            r = 255
            g = int(100 * scale)
            b = int(150 * (1 - scale))
        else:
            scale = (t - 0.66) / 0.34
            r = 255
            g = int(210 * (1 - scale) + 80 * scale)  # fade orange to yellow
            b = int(80 * (1 - scale))
        palette.append([r, g, b])
    return palette


def palette_cold_fire():
    palette = []
    for i in range(MAX_INTENSITY + 1):
        t = i / MAX_INTENSITY
        r = 0
        g = 0
        b = 0
        if t < 0.5:
            r = 0
            g = 0
            b = int(20 + 230 * t * 2)  # 20 → 255
        else:
            scale = (t - 0.5) * 2
            r = int(200 * scale)  # 0 → 200
            g = 255
            b = 255
        palette.append([r, g, b])
    return palette


def palette_fire():
    palette = []
    for i in range(MAX_INTENSITY + 1):
        t = i / MAX_INTENSITY
        r = 0
        g = 0
        b = 0
        if t < 0.33:
            r = int(255 * t * 3)
            g = 0
            b = 0
        elif t < 0.66:
            r = 255
            g = int(255 * (t - 0.33) * 3)
            b = 0
        else:
            r = 255
            g = 255
            b = int(255 * (t - 0.66) * 3)
        palette.append([r, g, b])
    return palette


def palette_gray():
    palette = []
    for i in range(MAX_INTENSITY + 1):
        t = i / MAX_INTENSITY
        v = int(255 * t)
        palette.append([v, v, v])
    return palette


def palette_cyber():
    palette = []
    for i in range(MAX_INTENSITY + 1):
        t = i / MAX_INTENSITY
        r = 0
        g = 0
        b = 0
        if t < 0.33:
            r = int(255 * (t / 0.33))
            g = 0
            b = int(255 * (t / 0.33))
        elif t < 0.66:
            scale = (t - 0.33) / 0.33
            r = int(255 * (1 - scale * 0.5))
            g = int(100 * scale)
            b = int(255 * (0.5 + scale * 0.5))
        else:
            scale = (t - 0.66) / 0.34
            r = 0
            g = int(180 + 75 * scale)
            b = 255
        palette.append([r, g, b])
    return palette
