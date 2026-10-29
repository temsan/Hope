"""Локальные переходы между полотнами в духе Kling (first/last frame, пустой промпт).

Маршрут — ORDER. Для шага k рендерит assets/transitions/tKK.mp4 (ORDER[k-1] → ORDER[k]):
камера влетает в центр первой картины, та растягивается в лучи и растворяется в цвете
фона следующей; затем мазки следующей картины «прорастают» из центра наружу и
собираются в неё саму.
Первый кадр = картина A, последний = картина B, поэтому клип Kling с теми же
first/last frame можно просто положить на место файла (см. import_kling.py).

Кодирование all-intra (-g 1), чтобы сайт мог плавно скрабить клип скроллом.
Запуск: python gen_transitions.py [номера шагов...]
"""
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ORDER = [5, 8, 9, 7, 6, 4, 3, 2, 1]
W, H = 1600, 900          # 16:9, как у Kling: кадр клипа = кадр портала
FPS, SECONDS = 30, 6
DEPTH = 2.6              # во сколько раз камера влетает в первую картину
STREAK = .4              # длина лучей (радиальный смаз) в середине пролёта
ROOT = Path(__file__).parent
OUT = ROOT / 'assets' / 'transitions'

# Координаты пикселя относительно центра в единицах половины высоты.
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
PX, PY = (xx - W / 2) / (H / 2), (yy - H / 2) / (H / 2)
R = np.hypot(PX, PY)
CORNER = float(R.max())


def backdrop(img):
    """Поля кадра: та же картина, увеличенная до заполнения кадра и размытая — цвета картины, без чёрных полей."""
    h0, w0 = img.shape[:2]
    k = max(W / w0, H / h0)
    big = cv2.resize(img, (round(w0 * k), round(h0 * k)), interpolation=cv2.INTER_AREA)
    x, y = (big.shape[1] - W) // 2, (big.shape[0] - H) // 2
    small = cv2.resize(big[y:y + H, x:x + W], (W // 16, H // 16), interpolation=cv2.INTER_AREA)
    blurred = cv2.GaussianBlur(small, (0, 0), 3)
    return cv2.resize(blurred, (W, H), interpolation=cv2.INTER_LINEAR).astype(np.float32)


def place(img, w, h, bg=None):
    """Кадр W×H: картина w×h по центру без искажения; вокруг неё — bg или размытая копия той же картины."""
    canvas = backdrop(img) if bg is None else bg.copy()
    x, y = (W - w) // 2, (H - h) // 2
    canvas[y:y + h, x:x + w] = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    return canvas


def contain_frame(path):
    """Вся картина без обрезки и без искажения: вписана в кадр W×H, поля — размытая копия картины."""
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    h0, w0 = img.shape[:2]
    k = min(W / w0, H / h0)
    return place(img, round(w0 * k), round(h0 * k))


def sample(img, sx, sy):
    """Выборка по координатам в единицах половины высоты."""
    mx = (sx * (H / 2) + W / 2).astype(np.float32)
    my = (sy * (H / 2) + H / 2).astype(np.float32)
    return cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def zoom_blur(img, z, strength):
    """Вид с приближением z и радиальным смазом: лучи из центра, как при рывке камеры."""
    if strength < .005:
        return sample(img, PX / z, PY / z)
    taps = max(6, int(strength * 48))
    acc = np.zeros_like(img)
    for k in range(taps):
        zk = z * (1 + strength * k / taps)
        acc += sample(img, PX / zk, PY / zk)
    return acc / taps


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def fringe(seed):
    """Рваный край фронта прорастания: зависит от угла, даёт «лучи» краски."""
    rng = np.random.default_rng(seed)
    a = np.arctan2(PY, PX)
    n = np.zeros_like(a)
    for f, amp in ((3, .5), (7, .3), (13, .2), (29, .15), (53, .1)):
        n += amp * np.sin(f * a + rng.uniform(0, 2 * np.pi))
    return (n / 1.25).astype(np.float32)


def render(a_path, b_path, dst, seed):
    A, B = contain_frame(a_path), contain_frame(b_path)
    # Цвет фона B — то, во что растворяется пролёт до появления мазков.
    ground = cv2.GaussianBlur(B, (0, 0), 70)
    # Мазки (детали, отличные от фона) прорастают раньше и дальше ровного фона.
    detail = cv2.GaussianBlur(np.abs(B - ground).mean(axis=2), (0, 0), 6)
    detail = (detail / (np.percentile(detail, 98) + 1e-6)).clip(0, 1)
    edge = fringe(seed)
    frames = round(FPS * SECONDS)
    proc = subprocess.Popen([
        'ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}',
        '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', '24',
        '-g', '1', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', str(dst)],
        stdin=subprocess.PIPE)
    for f in range(frames):
        t = f / (frames - 1)
        # 1. Влёт в A: приближение и лучи нарастают, A растворяется в цвете фона B.
        ua = smooth(0, .6, t) ** 1.6  # разгон медленный, как у Kling
        fa = zoom_blur(A, DEPTH ** ua, STREAK * smooth(.15, .55, t))
        ca = 1 - smooth(.32, .58, t)
        # 2. Прорастание B: фронт идёт из центра, мазки опережают фон; лучи втягиваются.
        g = smooth(.35, .97, t)
        front = g * (CORNER + .3) / .65  # к концу даже самые короткие «лучи» края выходят за углы кадра
        reach = front * (1 + .35 * edge) + .45 * g * detail
        m = smooth(0, .18, reach - R)[..., None]
        fb = zoom_blur(B, 1 + .35 * (1 - g), STREAK * .8 * (1 - smooth(.35, .95, t)))
        fb = ground * (1 - m) + fb * m
        frame = fa * ca + fb * (1 - ca)
        proc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
    proc.stdin.close()
    if proc.wait():
        sys.exit(f'ffmpeg failed on {dst}')



if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    only = {int(x) for x in sys.argv[1:]}
    for step in range(1, len(ORDER)):
        if only and step not in only:
            continue
        a, b = ORDER[step - 1], ORDER[step]
        dst = OUT / f't{step:02d}.mp4'
        render(ROOT / 'images' / f'img_{a:02d}.jpg', ROOT / 'images' / f'img_{b:02d}.jpg', dst, step)
        print(f'{dst.relative_to(ROOT)}  img_{a:02d} -> img_{b:02d}  {dst.stat().st_size / 1e6:.1f} MB')
