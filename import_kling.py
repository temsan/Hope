"""Подкладывает клип Kling на место перехода assets/transitions/tKK.mp4 (кадр 16:9, как у Kling).

  python import_kling.py <шаг> <клип.mp4> [<с> <по>] [back] [nowm] [full] [stretched] [raw]

- <с> <по> — окно исходного видео в секундах (для nine-transitions: один переход между картинами);
  back — проиграть окно задом наперёд (переход в обратную сторону);
  nowm — не затирать водяной знак KlingAI (в nine-transitions его нет);
  full — не обрезать статичные концы: в окне nine-transitions холды и есть картины A и B;
  stretched — кадр растянут на 16:9 (nine-transitions): пропорции картины возвращаются;
  raw — кадры Kling как есть: все, в родном времени, без выравнивания и растворения в картину
  (только поля 16:9 и перекодирование для скраба).
- кадры Kling идут как есть: родное время, без синтетических кадров;
- картина без искажения и без обрезки: вписана в кадр 16:9; поля неподвижны — размытая картина A
  плавно переходит в размытую картину B (если поля повторяют движение клипа, кажется, что анимаций две);
- статичные начало и конец срезаются; на концах геометрия плавно садится на картину (EDGE кадров),
  а кадр за EASE кадров растворяется в точную картину: первый и последний кадры клипа совпадают
  с картинами на сайте, шва нет;
- кодирует для сайта: 1280×720, ключевой кадр каждые 8 кадров — перемотка прокруткой встаёт на любой кадр
  за миллисекунды, а клип вчетверо легче, чем при каждом ключевом (по сети иначе не успевает).
"""
import gc
import os
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

from gen_transitions import FPS, H, ORDER, OUT, ROOT, W, backdrop, contain_frame, place, smooth

MOTION = .9          # средняя разница кадров (0..255 серого), с которой считаем, что движение пошло
LEAD = 6             # кадров покоя оставить перед движением
EDGE = 20            # кадров, за которые геометрия клипа плавно садится на картину на каждом конце
EASE = 6             # кадров растворения в точную картину на концах: не больше LEAD, пока Kling ещё стоит
WATERMARK = (.775, .952, .2, .036)  # x, y, w, h в долях кадра Kling


def extract(src, t0, t1, tmp):
    """Окно клипа сырыми кадрами родного размера во временный файл: длинный клип не держится в памяти."""
    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or FPS
    w0, h0 = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    cmd = ['ffmpeg', '-v', 'error', '-y']
    if t0 is not None:
        cmd += ['-ss', str(t0)]
    if t1 is not None:
        cmd += ['-t', str(t1 - (t0 or 0))]
    cmd += ['-i', str(src), '-f', 'rawvideo', '-pix_fmt', 'bgr24', str(tmp)]
    subprocess.run(cmd, check=True)
    n = os.path.getsize(tmp) // (w0 * h0 * 3)
    return np.memmap(tmp, dtype=np.uint8, mode='r', shape=(n, h0, w0, 3)), fps


def aspect_of(path):
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    return img.shape[1] / img.shape[0]


def motion_of(frames):
    """Средняя разница соседних кадров (0..255 серого)."""
    small = [cv2.resize(cv2.cvtColor(np.asarray(f), cv2.COLOR_BGR2GRAY), (90, 120)).astype(np.float32) for f in frames]
    return [float(np.abs(a - b).mean()) for a, b in zip(small, small[1:])]


def motion_span(frames):
    """Границы движения: статичные хвосты с обоих концов срезаются."""
    diffs = motion_of(frames)
    moving = [i for i in range(len(diffs) - 3) if min(diffs[i:i + 4]) > MOTION]
    if not moving:
        return 0, len(frames)
    return max(0, moving[0] - LEAD), min(len(frames), moving[-1] + 4 + LEAD)


def unmark(f):
    h, w = f.shape[:2]
    x, y, ww, hh = WATERMARK
    mask = np.zeros((h, w), np.uint8)
    mask[round(y * h):round((y + hh) * h), round(x * w):round((x + ww) * w)] = 255
    return cv2.inpaint(f, mask, 5, cv2.INPAINT_TELEA)


def align(frame, target):
    """Аффинная поправка (ECC): геометрия кадра Kling против картины, чуть крупнее или сдвинута."""
    g = lambda x: cv2.GaussianBlur(cv2.cvtColor(np.clip(x, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY), (0, 0), 2).astype(np.float32)
    M = np.eye(2, 3, dtype=np.float32)
    try:
        _, M = cv2.findTransformECC(g(target), g(frame), M, cv2.MOTION_AFFINE,
                                    (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), None, 5)
    except cv2.error:
        pass
    return M


def warp_by(f, M):
    return cv2.warpAffine(f, M, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT)


def encode(dst, frames, fps):
    """Кадры BGR W×H в mp4 для сайта: 1280×720, ключевой кадр каждые 8 кадров, без B-кадров."""
    proc = subprocess.Popen([
        'ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}',
        '-r', f'{fps:g}', '-i', '-', '-vf', 'scale=1280:720:flags=lanczos', '-c:v', 'libx264', '-preset', 'slow',
        '-crf', '26', '-g', '8', '-bf', '0', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', str(dst)],
        stdin=subprocess.PIPE)
    for f in frames:
        proc.stdin.write(np.clip(f, 0, 255).astype(np.uint8).tobytes())
    proc.stdin.close()
    if proc.wait():
        sys.exit('ffmpeg failed')


def write_seamless(dst, n, frame, A, B, fps):
    """Кадры frame(0..n-1) в mp4 (encode). На концах геометрия плавно садится на картины A и B
    (EDGE кадров), а кадр растворяется в них (EASE кадров): первый и последний кадры клипа совпадают
    со стоп-кадрами на сайте."""
    I = np.eye(2, 3, dtype=np.float32)
    first, last = frame(0), frame(n - 1)
    Ma, Mb = align(first, A), align(last, B)
    print(f'  геометрия концов до выравнивания: начало {np.abs(first - A).mean():.1f}, конец {np.abs(last - B).mean():.1f}')
    k, e = min(EDGE, n // 2), min(EASE, n // 2)

    def frames():
        for j in range(n):
            f = frame(j)
            if j < k:  # начало: геометрия плавно садится на картину A за k кадров
                f = warp_by(f, I + (Ma - I) * (1 - smooth(0, k, j)))
            if j >= n - k:  # конец: геометрия плавно садится на картину B за k кадров
                f = warp_by(f, I + (Mb - I) * smooth(n - 1 - k, n - 1, j))
            ka, kb = 1 - smooth(0, e, j), smooth(n - 1 - e, n - 1, j)  # у самых концов — точные картины A и B
            yield f * (1 - ka - kb) + A * ka + B * kb

    encode(dst, frames(), fps)


def main(step, src, t0=None, t1=None, reverse=False, wm=True, trim=True, stretched=False, raw=False):
    a, b = ORDER[step - 1], ORDER[step]
    pa, pb = ROOT / 'images' / f'img_{a:02d}.jpg', ROOT / 'images' / f'img_{b:02d}.jpg'
    A, B = contain_frame(pa), contain_frame(pb)
    FA, FB = (backdrop(cv2.imread(str(p), cv2.IMREAD_COLOR)) for p in (pa, pb))  # поля стоп-кадров A и B
    dst = OUT / f't{step:02d}.mp4'
    tmp = OUT / f'_frames{step:02d}.raw'
    fr, fps = extract(src, t0, t1, tmp)
    start, end = motion_span(fr) if trim and not raw else (0, len(fr))
    seq = list(range(start, end))
    if reverse:
        seq = seq[::-1]
    n = len(seq)
    native = fr.shape[2] / fr.shape[1]
    asp_a, asp_b = aspect_of(pa), aspect_of(pb)

    def frame(j):
        """Кадр клипа как он есть: вписан в 16:9 без искажения (для растянутых — пропорции картины)."""
        if stretched:
            u = j / max(1, n - 1)
            asp = (1 - u) * asp_a + u * asp_b
        else:
            asp = native
        f = np.ascontiguousarray(fr[seq[j]])
        if wm:
            f = unmark(f)
        u = smooth(0, n - 1, j)
        return place(f, round(H * asp), H, bg=FA * (1 - u) + FB * u)

    if raw:  # кадры Kling как есть: без выравнивания и растворения в картину
        print(f'  разница с картинами: начало {np.abs(frame(0) - A).mean():.1f}, конец {np.abs(frame(n - 1) - B).mean():.1f}')
        encode(dst, (frame(j) for j in range(n)), fps)
    else:
        write_seamless(dst, n, frame, A, B, fps)

    del fr
    gc.collect()
    tmp.unlink()
    print(f'{dst.relative_to(ROOT)}  img_{a:02d} -> img_{b:02d}  осталось {n} кадров ({n / fps:.1f} с)  {dst.stat().st_size / 1e6:.1f} MB')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    args = sys.argv[1:]
    flags = {x for x in args if x in ('back', 'nowm', 'full', 'stretched', 'raw')}
    nums = [x for x in args if x not in flags]
    if len(nums) < 2:
        sys.exit(__doc__)
    step, src = int(nums[0]), Path(nums[1])
    t0 = float(nums[2]) if len(nums) > 2 else None
    t1 = float(nums[3]) if len(nums) > 3 else None
    main(step, src, t0, t1, reverse='back' in flags, wm='nowm' not in flags,
         trim='full' not in flags, stretched='stretched' in flags, raw='raw' in flags)
