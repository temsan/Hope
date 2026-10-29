"""Переходы между картинами локальной видеомоделью: LTX-Video 2B 0.9.6 distilled (GGUF) рисует
пролёт с морфингом по ключевым кадрам — как Kling по первому и последнему, только на этой машине.

  python ltx_transitions.py prompt          — один раз: эмбеддинги промпта (T5-XXL из GGUF, по блоку на видеокарте)
  python ltx_transitions.py <шаг> [<шаг>…]  — переходы assets/transitions/tKK.mp4 (ORDER[k-1] → ORDER[k])
  python ltx_transitions.py flyin [<вариант>…] — латенты влёта из последней картины в комнату галереи
                                              (конечный кадр — снимок комнаты: node capture_room.cjs)
  python ltx_transitions.py flyin-decode      — затем, отдельным процессом: клип t09.mp4 из этих латентов
  Сейчас на сайте t09 — первые 43 кадра варианта 1 (въезд в картину, до появления комнаты; комнату
  открывает растворение клипа на сайте): ffmpeg -i t09_v1.mp4 -frames:v 43 … -g 1 t09.mp4

Под 4 ГБ видеопамяти и ~3 ГБ свободной ОЗУ модели не живут в памяти вместе: VAE кодирует ключевые
кадры → трансформер считает латенты всех шагов → VAE их декодирует.
Пара портретов генерируется как у Kling: сама картина на весь кадр — тогда модель морфит краску,
а не двигает холст целиком, — и клип встаёт в кадр 16:9 с неподвижными полями. Если одна из картин
горизонтальная, общего кадра у них нет: генерируется кадр 16:9 из стоп-кадров сайта (картина с полями).
Концы, как у клипов Kling, сводятся к точным стоп-кадрам (write_seamless).
Модели лежат в ~/ltx-local (переменная LTX_MODELS); файл T5 после `prompt` больше не нужен.
"""
import gc
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault('HF_HUB_DISABLE_XET', '1')  # без кэша чанков xet: места на диске мало

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
from huggingface_hub import hf_hub_download, snapshot_download  # noqa: E402
from PIL import Image  # noqa: E402

from gen_transitions import H, ORDER, OUT, ROOT, W, backdrop, contain_frame, place, smooth  # noqa: E402
from import_kling import write_seamless  # noqa: E402

MODELS = Path(os.environ.get('LTX_MODELS', Path.home() / 'ltx-local'))
CONFIGS = 'Lightricks/LTX-Video-0.9.5'  # конфиги, токенизатор и планировщик в формате diffusers, без весов
T5 = 'city96/t5-v1_1-xxl-encoder-gguf', 't5-v1_1-xxl-encoder-Q4_K_M.gguf'
LTX = 'city96/LTX-Video-0.9.6-distilled-gguf', 'ltxv-2b-0.9.6-distilled-04-25-Q5_K_M.gguf'
VAE = 'city96/LTX-Video-0.9.6-distilled-gguf', 'LTX-Video-0.9.6-VAE-BF16.safetensors'
GW, GH = 1024, 576               # кадр 16:9 с полями: ровно 16:9 и кратно 32, как требует LTX
PW, PH = 640, 928                # кадр самой картины-портрета (~0,69), кратно 32
FRAMES, GFPS = 121, 24           # 5 с
# Ключевые кадры (кадр, картина, приближение). Без промежуточных модель стоит на A, морфит посередине
# и стоит на B — пролёта нет. У портретов камера влетает в A, и A перетекает в B — смену масштаба
# прячет морфинг; в кадре 16:9 после влёта в A издали видна B, и камера летит к ней.
PORTRAIT_KEYS = ((0, 'a', 1), (64, 'a', 1.25), (FRAMES - 1, 'b', 1))
# Кадр 16:9 без «B издали» выходит хуже: резкая смена или странный световой проём посередине.
# Приближение 1,4; у шага 7 (3 → 2) с ним вместо пролёта вспышка — там мягче.
WIDE_ZOOM = {7: 1.15}


def wide_keys(z):
    return (0, 'a', 1), (40, 'a', z), (80, 'b', 1 / z), (FRAMES - 1, 'b', 1)


ROOM = ROOT / 'assets' / 'stills' / 'room.jpg'  # конечный кадр влёта — комната галереи (capture_room.cjs)
FLYIN = len(ORDER)                               # влёт в галерею — клип t09, после восьми переходов
# Влёт: последняя картина → комната. Варианты ключей (кадр, 'a' — картина | 'room' — комната, приближение);
# 1,18 — во столько раз картина в комнате (763 px из 900) меньше картины на весь кадр.
FLYIN_KEYS = {
    1: ((0, 'a', 1), (40, 'a', 1.4), (80, 'room', 1 / 1.4), (FRAMES - 1, 'room', 1)),  # сквозь картину к комнате
    2: ((0, 'a', 1), (36, 'room', 1.18), (FRAMES - 1, 'room', 1)),  # та же картина уже в комнате, камера отъезжает
    3: ((0, 'a', 1), (64, 'a', 1.25), (FRAMES - 1, 'room', 1)),     # краска картины перетекает в комнату
    # Без комнаты: камера уходит вглубь самой картины, а живую комнату на сайте открывает растворение клипа —
    # снимка галереи (застывшая луна, другая раскладка) в кадре нет.
    4: ((0, 'a', 1), (64, 'a', 1.3), (FRAMES - 1, 'a', 1.8)),
    5: ((0, 'a', 1), (40, 'a', 1.4), (FRAMES - 1, 'a', 2.4)),
}
TIMESTEPS = [1000, 993, 987, 981, 975, 909, 725, 0.03]  # 8 шагов дистиллированной модели
DECODE_T, DECODE_NOISE = .05, .025
TOKENS = 256                     # длина промпта, как в пайплайне
DT = torch.bfloat16
PROMPT = (
    'An abstract acrylic pour painting fills the frame. The camera flies smoothly forward into the center '
    'of the painting and passes through it: splashes, rays and drips of paint stream past like a tunnel of '
    'color, liquid paint swirls and flows, and the colors and shapes morph seamlessly into a different '
    'abstract painting that settles into place. Continuous fluid motion, vivid saturated colors, glossy wet '
    'paint texture, cinematic, highly detailed.'
)
T5_NAMES = {  # параметр блока T5 в transformers → тензор в GGUF (имена llama.cpp)
    'layer.0.layer_norm.weight': 'attn_norm.weight',
    'layer.0.SelfAttention.q.weight': 'attn_q.weight',
    'layer.0.SelfAttention.k.weight': 'attn_k.weight',
    'layer.0.SelfAttention.v.weight': 'attn_v.weight',
    'layer.0.SelfAttention.o.weight': 'attn_o.weight',
    'layer.0.SelfAttention.relative_attention_bias.weight': 'attn_rel_b.weight',
    'layer.1.layer_norm.weight': 'ffn_norm.weight',
    'layer.1.DenseReluDense.wi_0.weight': 'ffn_gate.weight',
    'layer.1.DenseReluDense.wi_1.weight': 'ffn_up.weight',
    'layer.1.DenseReluDense.wo.weight': 'ffn_down.weight',
}


def fetch(repo, name):
    return str(hf_hub_download(repo, name, local_dir=MODELS))


def configs():
    return snapshot_download(CONFIGS, local_dir=MODELS / 'configs',
                             allow_patterns=['model_index.json', 'scheduler/*', 'tokenizer/*', '*/config.json'])


def flush():
    gc.collect()
    torch.cuda.empty_cache()


def encode_prompt():
    """Эмбеддинги промпта. T5-XXL целиком (9,5 ГБ) не влезает ни в ОЗУ, ни в видеопамять, поэтому
    каждый блок распаковывается из GGUF прямо перед своим вызовом и выгружается сразу после."""
    import gguf
    from accelerate import init_empty_weights
    from accelerate.utils import set_module_tensor_to_device
    from transformers import T5Config, T5EncoderModel, T5Tokenizer

    cfg = configs()
    tensors = {t.name: t for t in gguf.GGUFReader(fetch(*T5)).tensors}
    with init_empty_weights():
        model = T5EncoderModel(T5Config.from_pretrained(cfg, subfolder='text_encoder')).eval()

    def load(module, names):
        for name, gname in names.items():
            t = tensors[gname]
            w = torch.from_numpy(gguf.quants.dequantize(t.data, t.tensor_type).copy()).float()
            set_module_tensor_to_device(module, name, 'cuda', value=w)

    def free(module, names):
        for name in names:
            set_module_tensor_to_device(module, name, 'meta')
        torch.cuda.empty_cache()

    def stream(module, names):
        missing = sorted(set(names.values()) - tensors.keys())
        if missing:
            sys.exit(f'в GGUF нет {missing[:3]}…; есть, например: {sorted(tensors)[:12]}')
        module.register_forward_pre_hook(lambda m, args: load(m, names))
        module.register_forward_hook(lambda m, args, out: free(m, names))

    stream(model.encoder.embed_tokens, {'weight': 'token_embd.weight'})
    for i, block in enumerate(model.encoder.block):
        stream(block, {n: f'enc.blk.{i}.{g}' for n, g in T5_NAMES.items() if i == 0 or 'relative' not in n})
    stream(model.encoder.final_layer_norm, {'weight': 'enc.output_norm.weight'})

    tok = T5Tokenizer.from_pretrained(cfg, subfolder='tokenizer')
    ids = tok(PROMPT, padding='max_length', max_length=TOKENS, truncation=True, add_special_tokens=True,
              return_tensors='pt')
    mask = ids.attention_mask.bool()
    with torch.no_grad():
        embeds = model(input_ids=ids.input_ids.cuda(), attention_mask=mask.cuda()).last_hidden_state
    torch.save({'embeds': embeds.to(DT).cpu(), 'mask': mask}, MODELS / 'prompt.pt')
    print(f'prompt.pt: {tuple(embeds.shape)}, токенов {int(mask.sum())}, '
          f'норма {embeds[0, :int(mask.sum())].norm(dim=-1).mean():.3f}')


def painting(k):
    return cv2.imread(str(ROOT / 'images' / f'img_{k:02d}.jpg'), cv2.IMREAD_COLOR)


def crop(f, aspect, part=1):
    """Середина кадра f с пропорциями aspect; part < 1 — её часть (камера ближе)."""
    h, w = f.shape[:2]
    cw, ch = (h * aspect, h) if w / h > aspect else (w, w / aspect)
    cw, ch = round(cw * part), round(ch * part)
    x, y = (w - cw) // 2, (h - ch) // 2
    return f[y:y + ch, x:x + cw]


def key_frame(k, z, wide):
    """Ключевой кадр картины k в размере генерации, RGB. В кадре 16:9 — стоп-кадр сайта (картина
    с размытыми полями), иначе — сама картина на весь кадр. z > 1 — камера ближе (центр крупнее),
    z < 1 — дальше (картина меньше, вокруг те же поля)."""
    img = painting(k)
    if wide:
        s = min(W / img.shape[1], H / img.shape[0]) * min(z, 1)
        f, size = place(img, round(img.shape[1] * s), round(img.shape[0] * s)), (GW, GH)
    else:
        f, size = crop(img, PW / PH), (PW, PH)
    if z > 1:
        f = crop(f, size[0] / size[1], 1 / z)
    f = cv2.resize(f, size, interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(np.clip(f, 0, 255).astype(np.uint8), cv2.COLOR_BGR2RGB)


def room_frame(z):
    """Ключевой кадр комнаты в размере генерации, RGB: z > 1 — камера ближе, z < 1 — комната меньше,
    вокруг её размытая копия (как картина на полях)."""
    img = cv2.resize(cv2.imread(str(ROOM), cv2.IMREAD_COLOR), (W, H), interpolation=cv2.INTER_AREA)
    f = place(img, round(W * z), round(H * z)) if z < 1 else crop(img, W / H, 1 / z)
    f = cv2.resize(np.clip(f, 0, 255).astype(np.uint8), (GW, GH), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(f, cv2.COLOR_BGR2RGB)


def load_vae(cfg):
    from accelerate import init_empty_weights
    from diffusers import AutoencoderKLLTXVideo
    from diffusers.loaders.single_file_utils import convert_ltx_vae_checkpoint_to_diffusers
    from safetensors.torch import load_file

    # Веса читаются из файла по одному тензору (pread) сразу в видеопамять, и модель берёт их без копий:
    # 2,5 ГБ целиком в ОЗУ при занятой памяти не помещаются — Windows падает с нарушением доступа.
    # В файле city96 ключи без префикса «vae.», а конвертер diffusers берёт только ключи с ним.
    sd = {f'vae.{k}': v for k, v in load_file(fetch(*VAE), device='cuda', backend='pread').items()}
    with init_empty_weights():
        vae = AutoencoderKLLTXVideo.from_config(AutoencoderKLLTXVideo.load_config(cfg, subfolder='vae'))
    vae.load_state_dict(convert_ltx_vae_checkpoint_to_diffusers(sd), assign=True)
    del sd
    vae = vae.to('cuda', DT)
    vae.enable_tiling()
    vae.use_framewise_decoding = True  # декодирует кусками по 16 кадров — влезает в 4 ГБ
    return vae


def load_transformer(cfg):
    from diffusers import GGUFQuantizationConfig, LTXVideoTransformer3DModel

    return LTXVideoTransformer3DModel.from_single_file(
        fetch(*LTX), quantization_config=GGUFQuantizationConfig(compute_dtype=DT),
        config=cfg, subfolder='transformer', torch_dtype=DT).to('cuda')


class CachedVAE:
    """VAE для пайплайна вместо настоящего: латенты ключевых кадров уже посчитаны, а веса VAE (2,5 ГБ)
    рядом с трансформером в 4 ГБ не помещаются. Пайплайн кодирует условия по очереди — так и отдаём."""
    spatial_compression_ratio, temporal_compression_ratio = 32, 8
    dtype = DT

    def __init__(self, latents_mean, latents_std):
        self.latents_mean, self.latents_std, self.queue = latents_mean, latents_std, []

    def encode(self, data):
        return SimpleNamespace(latents=self.queue.pop(0).to(data.device, data.dtype))


def decode(vae, latents, seed):
    """Латенты пайплайна (нормированные) → кадры RGB uint8 — так же, как пайплайн при output_type='pil'."""
    mean = vae.latents_mean.view(1, -1, 1, 1, 1).to('cuda', torch.float32)
    std = vae.latents_std.view(1, -1, 1, 1, 1).to('cuda', torch.float32)
    lat = (latents.to('cuda', torch.float32) * std / vae.config.scaling_factor + mean).to(DT)
    timestep = None
    if vae.config.timestep_conditioning:
        noise = torch.randn(lat.shape, generator=torch.Generator('cuda').manual_seed(seed), device='cuda', dtype=DT)
        lat = (1 - DECODE_NOISE) * lat + DECODE_NOISE * noise
        timestep = torch.tensor([DECODE_T], device='cuda', dtype=DT)
    with torch.no_grad():
        video = vae.decode(lat, timestep, return_dict=False)[0][0]  # [3, F, H, W] в [-1, 1]
    return [((video[:, j].float().clamp(-1, 1) + 1) * 127.5).round().byte().permute(1, 2, 0).cpu().numpy()
            for j in range(video.size(1))]


def encode_keys(cfg, images):
    """Ключевые кадры (RGB в размере генерации) → латенты. VAE сразу выгружается: рядом
    с трансформером в 4 ГБ он не помещается."""
    vae = load_vae(cfg)
    with torch.no_grad():
        lat = {k: vae.encode(torch.from_numpy(rgb).permute(2, 0, 1)[None, :, None].to('cuda', DT) / 127.5 - 1)
               .latent_dist.mode().cpu() for k, rgb in images.items()}
    stats = vae.latents_mean.cpu(), vae.latents_std.cpu()
    del vae
    flush()
    return lat, stats


def sample(cfg, stats, jobs):
    """Латенты клипов по ключевым кадрам. jobs: имя → (ключи [(кадр, RGB, латент)], (ширина, высота), seed)."""
    from diffusers import FlowMatchEulerDiscreteScheduler, LTXConditionPipeline
    from diffusers.pipelines.ltx.pipeline_ltx_condition import LTXVideoCondition

    prompt = torch.load(MODELS / 'prompt.pt')
    scheduler = FlowMatchEulerDiscreteScheduler.from_pretrained(cfg, subfolder='scheduler')
    pipe = LTXConditionPipeline(scheduler=scheduler, vae=CachedVAE(*stats), text_encoder=None, tokenizer=None,
                                transformer=load_transformer(cfg))
    out = {}
    for name, (keys, (gw, gh), seed) in jobs.items():
        pipe.vae.queue = [lat for _, _, lat in keys]
        out[name] = pipe(
            conditions=[LTXVideoCondition(image=Image.fromarray(rgb), frame_index=i) for i, rgb, _ in keys],
            prompt_embeds=prompt['embeds'].cuda(), prompt_attention_mask=prompt['mask'].cuda(),
            width=gw, height=gh, num_frames=FRAMES, frame_rate=GFPS, timesteps=TIMESTEPS, guidance_scale=1.0,
            output_type='latent', generator=torch.Generator('cuda').manual_seed(seed),
        ).frames.cpu()
    del pipe
    flush()
    return out


def generate(steps):
    cfg = configs()
    pairs = {s: (ORDER[s - 1], ORDER[s]) for s in steps}
    aspect = {k: painting(k).shape[1] / painting(k).shape[0] for pair in pairs.values() for k in pair}
    wide = {s: max(aspect[a], aspect[b]) >= 1 for s, (a, b) in pairs.items()}  # пара портретов — кадр картины
    plans = {s: [(i, a if who == 'a' else b, z)
                 for i, who, z in (wide_keys(WIDE_ZOOM.get(s, 1.4)) if wide[s] else PORTRAIT_KEYS)]
             for s, (a, b) in pairs.items()}
    keys = {(wide[s], k, z): key_frame(k, z, wide[s]) for s, plan in plans.items() for _, k, z in plan}

    # 1–2. ключевые кадры → латенты → латенты переходов: первый кадр — картина A, последний — картина B
    lat, stats = encode_keys(cfg, keys)
    latents = sample(cfg, stats, {
        s: ([(i, keys[(wide[s], k, z)], lat[(wide[s], k, z)]) for i, k, z in plan],
            (GW, GH) if wide[s] else (PW, PH), s)
        for s, plan in plans.items()})

    # 3. латенты → кадры → клип, концы сведены к стоп-кадрам
    vae = load_vae(cfg)
    for s, (a, b) in pairs.items():
        frames = [cv2.cvtColor(f, cv2.COLOR_RGB2BGR) for f in decode(vae, latents[s], s)]
        n = len(frames)
        A, B = (contain_frame(ROOT / 'images' / f'img_{k:02d}.jpg') for k in (a, b))
        if wide[s]:
            def frame(j):
                return cv2.resize(frames[j], (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float32)
        else:  # картина на месте картины стоп-кадра, поля неподвижны: размытая A переходит в размытую B
            FA, FB = backdrop(painting(a)), backdrop(painting(b))

            def frame(j):
                u = smooth(0, n - 1, j)
                return place(frames[j], round(H * PW / PH), H, bg=FA * (1 - u) + FB * u)
        dst = OUT / f't{s:02d}.mp4'
        write_seamless(dst, n, frame, A, B, GFPS)
        print(f'{dst.relative_to(ROOT)}  img_{a:02d} -> img_{b:02d}  {n} кадров ({n / GFPS:.1f} с)  '
              f'{dst.stat().st_size / 1e6:.1f} MB')


FLYIN_LATENTS = MODELS / 'flyin_latents.pt'


def generate_flyin(variants):
    """Влёт в галерею: последняя картина → комната (t09.mp4; несколько вариантов — t09_vN.mp4 для выбора).
    Латенты вариантов сохраняются на диск, а клипы из них собирает следующий запуск (flyin-decode):
    трансформер и CUDA этого процесса держат столько памяти, что на сборку клипа её может не хватить."""
    cfg = configs()
    last = ORDER[-1]
    keys = {(who, z): key_frame(last, z, True) if who == 'a' else room_frame(z)
            for v in variants for _, who, z in FLYIN_KEYS[v]}
    lat, stats = encode_keys(cfg, keys)
    seed = {v: FLYIN * 10 + v for v in variants}
    latents = sample(cfg, stats, {
        v: ([(i, keys[(who, z)], lat[(who, z)]) for i, who, z in FLYIN_KEYS[v]], (GW, GH), seed[v])
        for v in variants})
    torch.save({'latents': latents, 'seed': seed}, FLYIN_LATENTS)
    print(f'латенты вариантов {list(latents)} → {FLYIN_LATENTS}', flush=True)


def decode_flyin():
    """Сохранённые латенты влёта → клипы. Концы сведены к стоп-кадру картины и к снимку комнаты:
    на сайте клип растворяется в живую комнату."""
    saved = torch.load(FLYIN_LATENTS)
    vae = load_vae(configs())
    last = ORDER[-1]
    A = contain_frame(ROOT / 'images' / f'img_{last:02d}.jpg')
    for v, latents in saved['latents'].items():
        _, who, z = FLYIN_KEYS[v][-1]  # конечный кадр — снимок комнаты или картина крупным планом
        B = (cv2.resize(cv2.imread(str(ROOM), cv2.IMREAD_COLOR), (W, H), interpolation=cv2.INTER_AREA) if who == 'room'
             else cv2.resize(crop(A, W / H, 1 / z), (W, H), interpolation=cv2.INTER_CUBIC)).astype(np.float32)
        frames = decode(vae, latents, saved['seed'][v])  # RGB

        def frame(j):
            bgr = np.ascontiguousarray(frames[j][..., ::-1])
            return cv2.resize(bgr, (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float32)
        dst = OUT / (f't{FLYIN:02d}.mp4' if len(saved['latents']) == 1 else f't{FLYIN:02d}_v{v}.mp4')
        write_seamless(dst, len(frames), frame, A, B, GFPS)
        print(f'{dst.relative_to(ROOT)}  img_{last:02d} -> комната, вариант {v}  {len(frames)} кадров  '
              f'{dst.stat().st_size / 1e6:.1f} MB', flush=True)
        del frames
        gc.collect()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    args = sys.argv[1:]
    if args == ['prompt']:
        encode_prompt()
    elif args[:1] == ['flyin'] and all(x.isdigit() for x in args[1:]):
        generate_flyin([int(x) for x in args[1:]] or [1])
    elif args == ['flyin-decode']:
        decode_flyin()
    elif args and all(x.isdigit() for x in args):
        generate([int(x) for x in args])
    else:
        sys.exit(__doc__)
