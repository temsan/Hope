// Мастерская: своя картина в технике Надежды — раскрутке. Капли и мазки красок на тёмном холсте, потом холст
// вращается, и краску разносит от центра лучами.
//
// Краска — частицы. Капля рисует на холсте лужицу и кладёт в неё частицы; при вращении частица срывается, когда
// центробежное ускорение (ω²·r) пересиливает её вязкость, летит наружу, загибаясь против вращения (Кориолис),
// и оставляет за собой след, теряя массу; изредка отрывает брызги. Холст поворачивается через CSS, частицы живут
// в его собственных координатах — след ложится на вращающийся холст.
//
// Краски смешиваются. Под холстом — сетка мокрой краски (цвет и влажность в клетке 4×4 точки): частица, проходя
// по мокрому, подхватывает его цвет, а клетка — её; капля, упавшая в мокрое, смешивается с ним.
//
// Основа и краска выбираются отдельно. Основа — фактура и цвет (холст, бумага, крафт, доска); смена основы
// начинает работу заново. Краска — как она ложится и течёт: акрил, акварель, масло, гуашь, тушь; краски можно
// менять по ходу и сочетать на одном холсте, каждая частица помнит свою.
(function () {
    const PAINTS = [
        ['красный', '#d6322b'], ['охра', '#d8b13a'], ['розовый', '#f1c6bb'], ['белый', '#f3eee4'], ['кобальт', '#2552b8'],
        ['бирюза', '#2ea596'], ['фиолетовый', '#5c2f8f'], ['золото', '#c8a04b'], ['чёрный', '#121212'],
    ];
    const SIZES = [['мелкая', 9], ['средняя', 16], ['крупная', 26]];
    // Основы: цвет, светлая ли (на светлой акварель кладётся прозрачными слоями) и фактура.
    const GROUNDS = {
        dark: { label: 'тёмный холст', base: '#2a2a2d', light: false, tex: 'canvas' },
        canvas: { label: 'белый холст', base: '#ece6da', light: true, tex: 'canvas' },
        paper: { label: 'акварельная бумага', base: '#f4f0e6', light: true, tex: 'paper' },
        black: { label: 'чёрная бумага', base: '#151517', light: false, tex: 'smooth' },
        kraft: { label: 'крафт-картон', base: '#b98f5f', light: true, tex: 'kraft' },
        wood: { label: 'доска', base: '#c79b68', light: true, tex: 'wood' },
    };
    // Краски. stick — вязкость (позже срывается), drag — трение в полёте, lose — сколько оставляет на пути
    // (меньше — длиннее след), spray — брызги, width — толщина следа, alpha — укрывистость, mix — как охотно
    // смешивается с мокрым, streak — насколько различаются по тону полоски от щетинок. Пиктограммы — 24×24, контуром.
    const MEDIA = {
        acrylic: { label: 'акрил', stick: 1, drag: 2.2, lose: .012, spray: .0015, width: 1, alpha: .92, mix: .07, streak: .1,
            icon: '<path d="M8 3h8l-1 12H9z"/><path d="M8.2 5.5h7.6M10 15h4v2.5h-4zM11 17.5h2V21h-2z"/>' },
        water: { label: 'акварель', stick: .6, drag: 2.2, lose: .012, spray: .0015, width: 1.5, alpha: .4, mix: .1, streak: .06, glaze: true,
            icon: '<path d="M12 3c3 4.4 6 7.6 6 11a6 6 0 0 1-12 0c0-3.4 3-6.6 6-11z"/><path d="M9 15.5c1.2 1.3 3 1.6 4.6.8"/>' },
        oil: { label: 'масло', stick: 1.8, drag: 2.6, lose: .007, spray: .0006, width: 1.25, alpha: 1, mix: .13, streak: .16,
            icon: '<path d="M4 20l5-5"/><path d="M9 15l8.5-10.5c1.6.8 2.4 2.3 1.6 3.8L11 17z"/><circle cx="5.2" cy="18.8" r=".6"/>' },
        gouache: { label: 'гуашь', stick: 1.1, drag: 2.4, lose: .011, spray: .001, width: 1.1, alpha: .97, mix: .09, streak: .05, chalk: true,
            icon: '<path d="M7 9h10v10a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2z"/><path d="M6 5.5h12V9H6zM7 14h10"/>' },
        ink: { label: 'тушь', stick: .35, drag: 1.4, lose: .02, spray: .004, width: .55, alpha: .95, mix: .05, streak: 0,
            icon: '<path d="M12 3l5 8-5 10-5-10z"/><path d="M12 13.5V21"/><circle cx="12" cy="11.5" r="1.2"/>' },
    };
    let material = 'dark', medium = 'acrylic';

    const css = `
.studio{position:fixed;inset:0;z-index:5000;display:grid;grid-template-columns:auto auto;align-items:center;justify-content:center;
  gap:clamp(1rem,4vw,3.5rem);padding:clamp(1rem,3vw,2.5rem);background:radial-gradient(ellipse at 50% 45%,#16131a 0%,#050608 75%);
  color:#efe7d8;font-family:Manrope,sans-serif;opacity:0;transition:opacity .35s}
.studio.open{opacity:1}
.studio[hidden]{display:none}
.studio .board-wrap{position:relative;display:grid;place-items:center;touch-action:none}
.studio .board-wrap.zoomed{overflow:hidden;border-radius:4px}
.studio .view{display:grid;transform-origin:50% 50%}
.studio .view>canvas{grid-area:1/1}
.studio canvas.stroke{box-shadow:none;pointer-events:none}
.studio .acts .instant[aria-pressed=true]{background:#d6b775;color:#050608;border-color:#d6b775}
.studio canvas{display:block;border-radius:4px;box-shadow:0 30px 80px #000c,0 0 0 1px #efe7d814;touch-action:none;cursor:crosshair;
  will-change:transform}
.studio .side{display:grid;gap:1.2rem;justify-items:start;max-width:16rem}
.studio h2{margin:0;font:400 clamp(1.8rem,3.4vw,2.8rem)/.9 Spectral,serif;letter-spacing:-.04em}
.studio h2 em{color:#d6b775}
.studio p{margin:0;color:#efe7d89e;font-size:.82rem;line-height:1.6}
.studio .mats{display:grid;gap:.5rem}
.studio .mats-row,.studio .media-row{display:flex;gap:.4rem;flex-wrap:wrap}
.studio .mat{width:2.25rem;height:2.25rem;border:1px solid #efe7d84d;border-radius:3px;cursor:pointer;padding:0;background-size:cover}
.studio .mat[aria-pressed=true],.studio .med[aria-pressed=true]{outline:2px solid #efe7d8;outline-offset:2px}
.studio .med{width:2.25rem;height:2.25rem;border:1px solid #efe7d84d;border-radius:50%;cursor:pointer;padding:0;background:none;
  color:#efe7d8;display:grid;place-items:center}
.studio .med svg{width:1.3rem;height:1.3rem;fill:none;stroke:currentColor;stroke-width:1.4;stroke-linejoin:round;stroke-linecap:round}
.studio .med[aria-pressed=true]{background:#efe7d8;color:#050608}
.studio .mat-name{font-size:.72rem;color:#efe7d8b3;letter-spacing:.04em}
.studio .paints{display:grid;grid-template-columns:repeat(3,2.6rem);gap:.55rem}
.studio .paint{width:2.6rem;height:2.6rem;border-radius:46% 54% 50% 50%/55% 45% 55% 45%;border:0;cursor:pointer;padding:0;
  box-shadow:inset -4px -5px 8px #0006,inset 3px 3px 6px #fff4;transition:transform .15s}
.studio .paint[aria-pressed=true]{transform:scale(1.18);outline:2px solid #efe7d8;outline-offset:3px}
.studio .sizes{display:flex;gap:.5rem;align-items:center}
.studio .size{border:1px solid #efe7d84d;background:none;border-radius:50%;cursor:pointer;display:grid;place-items:center;
  width:2.3rem;height:2.3rem;padding:0}
.studio .size span{display:block;border-radius:50%;background:#efe7d8}
.studio .size[aria-pressed=true]{border-color:#efe7d8}
.studio .acts{display:flex;flex-wrap:wrap;gap:.55rem}
.studio .acts button{padding:.75rem 1rem;background:transparent;border:1px solid #efe7d8a6;color:inherit;font:inherit;font-size:.8rem;
  cursor:pointer;transition:background .2s,color .2s}
@media (hover:hover){.studio .acts button:hover{background:#efe7d8;color:#050608}}
.studio .acts .play,.studio .acts .stop,.studio .acts .instant{width:3rem;min-height:2.75rem;padding:0;display:grid;place-items:center}
.studio .acts .play svg,.studio .acts .stop svg,.studio .acts .instant svg{width:1rem;height:1rem;fill:currentColor}
.studio .acts .play:not(:disabled){background:#efe7d8;color:#050608}
@media (hover:hover){.studio .acts .play:not(:disabled):hover{background:#d6b775}}
.studio .acts .instant svg{width:1.35rem;height:1.35rem}
.studio .acts button:disabled{opacity:.35;cursor:default;background:transparent;color:inherit}
.studio .close{position:absolute;top:1rem;right:1.2rem;background:none;border:0;color:#efe7d8b0;font-size:1.6rem;cursor:pointer;line-height:1}
@media (max-width:760px){
  .studio{grid-template-columns:1fr;grid-template-rows:auto auto;align-content:center;gap:1rem}
  .studio .side{order:2;max-width:none;justify-items:center;text-align:center;gap:.65rem}
  .studio .mats{justify-items:center}
  .studio .mats-row,.studio .media-row{flex-wrap:nowrap}
  .studio .paints{grid-template-columns:repeat(9,1.9rem);gap:.4rem}
  .studio .paint{width:1.9rem;height:1.9rem}
  .studio h2,.studio p{display:none}
  .studio .acts{flex-wrap:nowrap;gap:.4rem;justify-content:center}
  .studio .acts button{padding:.7rem .65rem;font-size:.76rem}
  .studio .acts .play,.studio .acts .stop,.studio .acts .instant{width:2.6rem;flex:none}
}`;
    const style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);

    const root = document.createElement('section');
    root.className = 'studio';
    root.hidden = true;
    root.setAttribute('aria-label', 'Мастерская: своя картина раскруткой');
    root.innerHTML = `
<button class="close" type="button" aria-label="Закрыть мастерскую">×</button>
<div class="board-wrap"><div class="view"><canvas aria-label="Холст: касание — капля краски, проведение — мазок; колесо или щипок — масштаб"></canvas><canvas class="stroke" aria-hidden="true"></canvas></div></div>
<div class="side">
  <h2>Своя <em>раскрутка</em></h2>
  <p>Наберите краску, капните или проведите по холсту — и раскрутите. Мокрые краски смешиваются; можно добавить ещё
    и докрутить.</p>
  <div class="mats">
    <div class="mats-row" role="group" aria-label="Основа"></div>
    <div class="media-row" role="group" aria-label="Краска"></div>
    <div class="mat-name" aria-live="polite"></div>
  </div>
  <div class="paints" role="group" aria-label="Краски"></div>
  <div class="sizes" role="group" aria-label="Размер капли"></div>
  <div class="acts">
    <button class="play" type="button" aria-label="Раскрутить" title="Раскрутить"><svg viewBox="0 0 16 16"><path d="M4 2.5v11l9.5-5.5z"/></svg></button>
    <button class="stop" type="button" aria-label="Остановить" title="Остановить" disabled><svg viewBox="0 0 16 16"><rect x="3" y="3" width="10" height="10"/></svg></button>
    <button class="instant" type="button" aria-pressed="false" aria-label="Мгновенная раскрутка: каждый мазок сразу раскручивается" title="Мгновенная раскрутка: вкл/выкл"><svg viewBox="0 0 24 24"><path d="M12 2.5a9.5 9.5 0 1 1-9.4 8.1M12 5.5a6.5 6.5 0 1 0 6.3 4.9" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M13 6.5 8.5 13h3l-1 4.5 4.5-6.5h-3z"/></svg></button>
    <button class="clear" type="button">очистить</button>
    <button class="save" type="button">сохранить</button>
  </div>
</div>`;
    document.body.appendChild(root);

    const cv = root.querySelector('canvas'), ctx = cv.getContext('2d'), $ = s => root.querySelector(s);
    const sv = root.querySelector('canvas.stroke'), sctx = sv.getContext('2d'), view = $('.view'), wrap = $('.board-wrap');
    let color = PAINTS[0][1], size = SIZES[1][1];
    PAINTS.forEach(([name, c], i) => {
        const b = document.createElement('button');
        b.className = 'paint';
        b.type = 'button';
        b.style.background = c;
        b.setAttribute('aria-label', name);
        b.setAttribute('aria-pressed', i === 0);
        b.onclick = () => {
            color = c;
            root.querySelectorAll('.paint').forEach(x => x.setAttribute('aria-pressed', x === b));
        };
        $('.paints').appendChild(b);
    });
    SIZES.forEach(([name, r], i) => {
        const b = document.createElement('button');
        b.className = 'size';
        b.type = 'button';
        b.setAttribute('aria-label', name);
        b.setAttribute('aria-pressed', i === 1);
        b.innerHTML = `<span style="width:${4 + i * 5}px;height:${4 + i * 5}px"></span>`;
        b.onclick = () => {
            size = r;
            root.querySelectorAll('.size').forEach(x => x.setAttribute('aria-pressed', x === b));
        };
        $('.sizes').appendChild(b);
    });

    // Холст 3:4: размеры в точках экрана (W×H), рисуем с плотностью d.
    let W = 0, H = 0, d = 1, angle = 0, omega = 0, particles = [];
    const rnd = (a, b) => a + (b - a) * Math.random();
    function layout() {
        const narrow = innerWidth <= 760;
        const maxH = narrow ? innerHeight * .55 : innerHeight * .82, maxW = narrow ? innerWidth * .92 : innerWidth * .6;
        const h = Math.min(maxH, maxW * 4 / 3), w = h * 3 / 4;
        const nd = Math.min(2, devicePixelRatio || 1);
        if (Math.round(w) === W && Math.round(h) === H && nd === d) return;
        // сохраняем нарисованное при смене размера
        const old = W ? (() => { const c = document.createElement('canvas'); c.width = cv.width; c.height = cv.height; c.getContext('2d').drawImage(cv, 0, 0); return c; })() : null;
        const sx = W ? Math.round(w) / W : 1;
        W = Math.round(w); H = Math.round(h); d = nd;
        cv.width = W * d; cv.height = H * d;
        cv.style.width = W + 'px'; cv.style.height = H + 'px';
        ctx.setTransform(d, 0, 0, d, 0, 0);
        sv.width = blotCv.width = cv.width; sv.height = blotCv.height = cv.height;
        sv.style.width = W + 'px'; sv.style.height = H + 'px';
        sctx.setTransform(d, 0, 0, d, 0, 0);
        zoom = 1; panX = panY = 0; applyView();
        ctx.fillStyle = GROUNDS[material].base;
        ctx.fillRect(0, 0, W, H);
        if (old) ctx.drawImage(old, 0, 0, W, H);
        particles.forEach(p => { p.x *= sx; p.y *= sx; p.m *= sx; });
        makeGrid();
    }

    // Сетка мокрой краски: цвет (0..255) и влажность (0..1) в клетке CELL×CELL точек холста.
    const CELL = 4;
    let gw = 0, gh = 0, gR, gG, gB, gWet;
    function makeGrid() {
        gw = Math.ceil(W / CELL); gh = Math.ceil(H / CELL);
        gR = new Float32Array(gw * gh); gG = new Float32Array(gw * gh); gB = new Float32Array(gw * gh); gWet = new Float32Array(gw * gh);
    }
    const cellAt = (x, y) => {
        const i = Math.floor(x / CELL), j = Math.floor(y / CELL);
        return i >= 0 && j >= 0 && i < gw && j < gh ? j * gw + i : -1;
    };
    const hex = c => [parseInt(c.slice(1, 3), 16), parseInt(c.slice(3, 5), 16), parseInt(c.slice(5, 7), 16)];
    const mixInto = (a, b, k) => { a[0] += (b[0] - a[0]) * k; a[1] += (b[1] - a[1]) * k; a[2] += (b[2] - a[2]) * k; return a; };
    const rgba = (c, a) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
    // краска c ложится в клетку: в мокрое — смешиваясь (k — доля новой), в сухое — как есть
    function wet(i, c, k) {
        if (i < 0) return;
        if (gWet[i] > .05) {
            gR[i] += (c[0] - gR[i]) * k; gG[i] += (c[1] - gG[i]) * k; gB[i] += (c[2] - gB[i]) * k;
        } else { gR[i] = c[0]; gG[i] = c[1]; gB[i] = c[2]; }
        gWet[i] = Math.max(gWet[i], .9);
    }
    // Фактура основы: у холста — переплетение нитей (уток и основа с неровной толщиной), у бумаги — зерно
    // холодного прессования (мягкие бугорки) и редкие волокна.
    function texture(g, w, h, mat) {
        const m = GROUNDS[mat];
        g.fillStyle = m.base;
        g.fillRect(0, 0, w, h);
        if (m.tex === 'smooth') {
            // чёрная бумага: гладкая, едва заметное зерно
            for (let i = 0; i < w * h / 70; i++) {
                g.fillStyle = `rgba(255,255,255,${rnd(0, .035)})`;
                g.fillRect(rnd(0, w), rnd(0, h), 1, 1);
            }
        } else if (m.tex === 'kraft') {
            // крафт: короткие тёмные и светлые волокна вразброс
            g.lineWidth = .6;
            for (let i = 0; i < w * h / 60; i++) {
                const x = rnd(0, w), y = rnd(0, h), a = rnd(0, Math.PI), l = rnd(2, 7);
                g.strokeStyle = Math.random() < .6 ? `rgba(70,45,20,${rnd(.06, .16)})` : `rgba(255,235,200,${rnd(.05, .12)})`;
                g.beginPath(); g.moveTo(x, y); g.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l); g.stroke();
            }
        } else if (m.tex === 'wood') {
            // доска: волокна вдоль, волнистые, огибают пару сучков
            const knots = [[rnd(.2, .8) * w, rnd(.1, .9) * h], [rnd(.2, .8) * w, rnd(.1, .9) * h]];
            for (let x = 0; x < w; x += rnd(1.5, 4)) {
                g.strokeStyle = `rgba(90,55,25,${rnd(.05, .2)})`;
                g.lineWidth = rnd(.4, 1.4);
                g.beginPath();
                for (let y = 0; y <= h; y += 6) {
                    let dx = Math.sin(y * .013 + x * .05) * 2.5;
                    for (const [kx, ky] of knots) { const dd = Math.hypot(x - kx, y - ky); dx += (x - kx) / (dd + 1) * 900 / (dd * dd / 30 + 60); }
                    y ? g.lineTo(x + dx, y) : g.moveTo(x + dx, y);
                }
                g.stroke();
            }
            for (const [kx, ky] of knots) {
                g.fillStyle = 'rgba(90,50,20,.35)';
                g.beginPath(); g.ellipse(kx, ky, 3, 6, 0, 0, Math.PI * 2); g.fill();
            }
        } else if (m.tex === 'paper') {
            for (let i = 0; i < w * h / 55; i++) {
                const r = rnd(1.2, 3.6), x = rnd(0, w), y = rnd(0, h), gr = g.createRadialGradient(x, y, 0, x, y, r);
                const a = rnd(.03, .08);
                gr.addColorStop(0, `rgba(120,100,70,${a})`);
                gr.addColorStop(1, 'rgba(120,100,70,0)');
                g.fillStyle = gr;
                g.fillRect(x - r, y - r, r * 2, r * 2);
            }
            g.strokeStyle = 'rgba(140,120,90,.08)';
            g.lineWidth = .5;
            for (let i = 0; i < w * h / 4000; i++) {
                const x = rnd(0, w), y = rnd(0, h), a = rnd(0, Math.PI);
                g.beginPath(); g.moveTo(x, y); g.quadraticCurveTo(x + rnd(-6, 6), y + rnd(-6, 6), x + Math.cos(a) * 14, y + Math.sin(a) * 14); g.stroke();
            }
        } else {
            const light = m.light, step = 2.6;
            for (let y = 0; y < h; y += step) {
                g.fillStyle = light ? `rgba(110,95,70,${rnd(.04, .1)})` : `rgba(255,255,255,${rnd(.015, .045)})`;
                g.fillRect(0, y, w, step * rnd(.35, .55));
            }
            for (let x = 0; x < w; x += step) {
                g.fillStyle = light ? `rgba(110,95,70,${rnd(.03, .08)})` : `rgba(0,0,0,${rnd(.05, .12)})`;
                g.fillRect(x, 0, step * rnd(.35, .55), h);
            }
            for (let i = 0; i < w * h / 120; i++) {
                g.fillStyle = light ? `rgba(90,75,50,${rnd(0, .06)})` : `rgba(255,255,255,${rnd(0, .03)})`;
                g.fillRect(rnd(0, w), rnd(0, h), 1, 1);
            }
        }
    }
    function clearBoard() {
        ctx.globalCompositeOperation = 'source-over';
        texture(ctx, W, H, material);
        makeGrid();
        particles = [];
        angle = 0;
        cv.style.transform = sv.style.transform = '';
        spinK = 1;
    }

    // Кисть. Касание — мягкий отпечаток: плотная середина, растушёванный край и след щетины. Мазок — пучок
    // щетинок, заданный на весь мазок (у каждой своё смещение поперёк, нажим и оттенок): щетинки тянутся за кистью
    // полосками, у края мазка прозрачнее; по мере того как краска на кисти кончается, часть щетинок перестаёт
    // оставлять след, и к концу мазок становится сухим и рваным. Бликов нет: краска матовая.
    //
    // Пока кисть на холсте, мазок живёт на отдельном слое (canvas.stroke) и перерисовывается целиком: каждая
    // щетинка — одна линия, без стыков, которые темнели бы внахлёст. Отпустили — мазок ложится на холст.
    // Второй палец посреди мазка (щипок для масштаба) мазок отменяет.
    let brush = null;   // текущий мазок
    const blotCv = document.createElement('canvas'), bctx = blotCv.getContext('2d');
    function newBrush(r) {
        const M = MEDIA[medium], light = GROUNDS[material].light, n = Math.max(7, Math.min(36, Math.round(r * 1.5)));
        return {
            r, M, mk: medium, pts: [], load: 1, p0: particles.length,
            // акварель на светлом — прозрачные слои («темнее из двух»: сходятся к пигменту, не уходят в чёрное);
            // на тёмном прозрачная краска едва видна, как в жизни
            op: M.glaze && light ? 'darken' : 'source-over',
            A: M.glaze ? (light ? .38 : .22) : M.alpha,
            bristles: Array.from({ length: n }, (_, i) => ({
                o: (i + rnd(.1, .9)) / n * 2 - 1, a: rnd(.55, 1), w: rnd(.8, 1.3), t: rnd(-1, 1), dry: Math.random(),
            })),
        };
    }
    const shade = (c, k) => k > 0 ? mixInto(c.slice(), [255, 255, 255], k) : c.map(v => v * (1 + k));
    // Отпечаток кисти на слое g.
    function blot(g, x, y, r, base, A, M) {
        const gr = g.createRadialGradient(x, y, 0, x, y, r);
        gr.addColorStop(0, rgba(base, A));
        gr.addColorStop(.5, rgba(base, A * .95));
        gr.addColorStop(.8, rgba(base, A * .5));
        gr.addColorStop(1, rgba(base, 0));
        g.fillStyle = gr;
        g.beginPath();
        g.ellipse(x, y, r, r * rnd(.85, 1), rnd(0, Math.PI), 0, Math.PI * 2);
        g.fill();
        // след щетины: кисть прижали и чуть повели
        const a = rnd(0, Math.PI * 2), ux = Math.cos(a), uy = Math.sin(a), n = Math.round(r * 1.2);
        g.lineCap = 'round';
        for (let i = 0; i < n; i++) {
            const o = rnd(-1, 1), ox = -uy * o * r * .7, oy = ux * o * r * .7;
            g.strokeStyle = rgba(shade(base, rnd(-1, 1) * M.streak), A * rnd(.12, .35) * (1 - o * o));
            g.lineWidth = rnd(.5, 1.2);
            g.beginPath();
            g.moveTo(x + ox - ux * r * .4, y + oy - uy * r * .4);
            g.lineTo(x + ox + ux * r * .5, y + oy + uy * r * .5);
            g.stroke();
        }
        if (M.chalk) {
            // в гуаши мел: матовые светлые крупинки
            for (let i = 0; i < r * 2; i++) {
                g.fillStyle = `rgba(255,255,255,${rnd(0, .08)})`;
                const b = rnd(0, Math.PI * 2), q = Math.sqrt(Math.random()) * r * .8;
                g.fillRect(x + Math.cos(b) * q, y + Math.sin(b) * q, 1, 1);
            }
        }
    }
    // Весь мазок на слое g: под щетинками у плотных красок — тело мазка, сверху щетинки отрезками по 8 точек
    // (цвет у отрезка свой: кисть подхватывает мокрое по пути); отрезки сходятся в общей точке — без нахлёста.
    function drawStroke(g, b) {
        const P = b.pts, n = P.length;
        if (n < 2) return;
        const M = b.M, A = b.A, hw = b.r;
        // нормали к пути
        for (let i = 0; i < n; i++) {
            const a = P[Math.max(0, i - 1)], c = P[Math.min(n - 1, i + 1)], dx = c.x - a.x, dy = c.y - a.y, l = Math.hypot(dx, dy) || 1;
            P[i].nx = -dy / l; P[i].ny = dx / l;
        }
        g.lineCap = 'butt';
        g.lineJoin = 'round';
        const runs = (active, off, width, style) => {
            let run = [];
            const flush = () => {
                if (run.length >= 2) {
                    const m = P[run[run.length >> 1]];
                    g.strokeStyle = style(m);
                    g.lineWidth = width;
                    g.beginPath();
                    // в конце мазка щетинки сходятся: кисть отрывается от холста
                    run.forEach((i, j) => { const q = P[i], o = off * (.3 + .7 * Math.min(1, (n - 1 - i) / 6)); g[j ? 'lineTo' : 'moveTo'](q.x + q.nx * o, q.y + q.ny * o); });
                    g.stroke();
                }
            };
            for (let i = 0; i < n; i++) {
                const on = active(P[i]);
                if (on) run.push(i);
                if (!on || run.length >= 8 || i === n - 1) { flush(); run = on ? [i] : []; }
            }
        };
        if (!M.glaze) runs(q => q.load > .3, 0, hw * 1.45, m => rgba(m.c, A * .85 * Math.min(1, m.load + .2)));
        for (const q of b.bristles) {
            runs(m => q.dry <= m.load + .35, q.o * hw, hw * 2 / b.bristles.length * 1.6 * q.w,
                m => rgba(shade(m.c, q.t * M.streak), A * q.a * (1 - .75 * q.o * q.o) * (.6 + .4 * m.load)));
        }
    }
    // Слой мазка: отпечаток касания (готов заранее) и мазок поверх.
    function redrawStroke() {
        sctx.clearRect(0, 0, W, H);
        if (!brush) return;
        sctx.globalCompositeOperation = 'source-over';
        sctx.drawImage(blotCv, 0, 0, W, H);
        drawStroke(sctx, brush);
    }
    function commitStroke() {
        if (!brush) return;
        ctx.globalCompositeOperation = brush.op;
        ctx.drawImage(sv, 0, 0, W, H);
        ctx.globalCompositeOperation = 'source-over';
        sctx.clearRect(0, 0, W, H);
        brush = null;
    }
    function cancelStroke() {
        if (!brush) return;
        if (particles.length >= brush.p0) particles.length = brush.p0;  // краска мазка не полетит при раскрутке
        sctx.clearRect(0, 0, W, H);
        brush = null;
    }
    // Краска под кистью: смешивается с мокрым, мокрит клетки, кладёт частицы для раскрутки.
    function dab(x, y, r, hexColor, first) {
        const c = hex(hexColor), under = cellAt(x, y), M = brush.M;
        if (under >= 0 && gWet[under] > .2) mixInto(c, [gR[under], gG[under], gB[under]], M.glaze ? .35 : .3);
        const base = M.chalk ? mixInto(c.slice(), [245, 240, 230], .08) : c;
        if (first) {
            bctx.setTransform(d, 0, 0, d, 0, 0);
            bctx.clearRect(0, 0, W, H);
            blot(bctx, x, y, r, base, brush.A, M);
        } else {
            const last = brush.pts[brush.pts.length - 1];
            if (last) brush.load = Math.max(.15, brush.load - Math.hypot(x - last.x, y - last.y) / (r * 45));  // краска на кисти кончается
        }
        brush.pts.push({ x, y, c: base, load: brush.load });
        // лужица мокрая
        for (let yy = y - r; yy <= y + r; yy += CELL) {
            for (let xx = x - r; xx <= x + r; xx += CELL) {
                if ((xx - x) ** 2 + (yy - y) ** 2 <= r * r) wet(cellAt(xx, yy), c, .65);
            }
        }
        const n = Math.round(r * 2.2);
        for (let i = 0; i < n; i++) {
            const a = rnd(0, Math.PI * 2), q = Math.sqrt(Math.random()) * r * .75;
            particles.push({
                x: x + Math.cos(a) * q, y: y + Math.sin(a) * q, vx: 0, vy: 0,
                m: rnd(.6, 1.4) * r * .16,               // масса — толщина следа
                stick: rnd(.4, 1.6) * M.stick,            // вязкость: чем больше, тем позже срывается
                c: c.slice(), md: brush.mk,
            });
        }
        if (particles.length > 9000) { particles.splice(0, particles.length - 9000); brush.p0 = 0; }
    }

    // Масштаб: колесо мыши — к курсору, щипок двумя пальцами — к середине между ними (и сдвиг вслед за пальцами).
    let zoom = 1, panX = 0, panY = 0, spinK = 1;
    function applyView() {
        zoom = Math.min(5, Math.max(1, zoom));
        const mx = W * (zoom - 1) / 2, my = H * (zoom - 1) / 2;
        panX = Math.min(mx, Math.max(-mx, panX));
        panY = Math.min(my, Math.max(-my, panY));
        const on = zoom > 1.001;
        view.style.transform = on ? `translate(${panX.toFixed(1)}px,${panY.toFixed(1)}px) scale(${zoom.toFixed(4)})` : '';
        wrap.classList.toggle('zoomed', on);
    }
    // центр холста на экране без масштаба вида — середина обёртки
    const wrapCenter = () => { const r = wrap.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; };
    function zoomAt(x, y, nz) {
        const [cx, cy] = wrapCenter(), ox = x - cx, oy = y - cy;
        nz = Math.min(5, Math.max(1, nz));
        panX = ox - (ox - panX) * nz / zoom;
        panY = oy - (oy - panY) * nz / zoom;
        zoom = nz;
        applyView();
    }
    wrap.addEventListener('wheel', e => {
        e.preventDefault();
        const dy = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 400 : 1);
        zoomAt(e.clientX, e.clientY, zoom * Math.exp(-dy * .0015));
    }, { passive: false });
    wrap.addEventListener('dblclick', () => { zoom = 1; panX = panY = 0; applyView(); });

    // Точка экрана → точка холста с учётом масштаба вида, поворота и того, что на ходу холст чуть отъезжает.
    function toBoard(e) {
        const [cx0, cy0] = wrapCenter(), cx = cx0 + panX, cy = cy0 + panY, k = zoom * spinK;
        const dx = (e.clientX - cx) / k, dy = (e.clientY - cy) / k, c = Math.cos(-angle), s = Math.sin(-angle);
        return [W / 2 + dx * c - dy * s, H / 2 + dx * s + dy * c];
    }
    let drawing = null, pinch = null;
    const touches = new Map();
    const mid = () => { const v = [...touches.values()]; return [(v[0][0] + v[1][0]) / 2, (v[0][1] + v[1][1]) / 2, Math.hypot(v[0][0] - v[1][0], v[0][1] - v[1][1])]; };
    cv.addEventListener('pointerdown', e => {
        e.preventDefault();
        cv.setPointerCapture(e.pointerId);
        touches.set(e.pointerId, [e.clientX, e.clientY]);
        if (touches.size === 2) {
            // второй палец — это щипок, а не мазок
            drawing = null;
            cancelStroke();
            const [x, y, dd] = mid(), [cx, cy] = wrapCenter();
            pinch = { d: Math.max(10, dd), z: zoom, ox: x - cx, oy: y - cy, px: panX, py: panY };
            return;
        }
        if (touches.size > 2) return;
        const [x, y] = toBoard(e);
        drawing = [x, y];
        brush = newBrush(size * .7);
        sv.style.mixBlendMode = brush.op === 'darken' ? 'darken' : 'normal';
        dab(x, y, size * .8, color, true);
        redrawStroke();
    });
    cv.addEventListener('pointermove', e => {
        if (touches.has(e.pointerId)) touches.set(e.pointerId, [e.clientX, e.clientY]);
        if (pinch && touches.size >= 2) {
            const [x, y, dd] = mid(), [cx, cy] = wrapCenter(), nz = Math.min(5, Math.max(1, pinch.z * dd / pinch.d));
            // точка холста, что была под серединой пальцев, остаётся под ней
            panX = (x - cx) - (pinch.ox - pinch.px) * nz / pinch.z;
            panY = (y - cy) - (pinch.oy - pinch.py) * nz / pinch.z;
            zoom = nz;
            applyView();
            return;
        }
        if (!drawing || !brush) return;
        const [x, y] = toBoard(e), step = Math.max(2, size * .3), dist = Math.hypot(x - drawing[0], y - drawing[1]);
        let prev = drawing;
        for (let t = step; t <= dist; t += step) {
            const k = t / dist, pt = [drawing[0] + (x - drawing[0]) * k, drawing[1] + (y - drawing[1]) * k];
            dab(pt[0], pt[1], size * .7, color, false);
            prev = pt;
        }
        if (dist >= step) { drawing = prev; redrawStroke(); }
    });
    const stopDraw = e => {
        touches.delete(e.pointerId);
        if (touches.size < 2) pinch = null;
        if (!drawing) return;
        drawing = null;
        commitStroke();
        if (instantOn && !raf) instant();  // включена мгновенная раскрутка — каждый мазок сразу раскручивается
    };
    cv.addEventListener('pointerup', stopDraw);
    cv.addEventListener('pointercancel', e => { touches.delete(e.pointerId); if (touches.size < 2) pinch = null; drawing = null; cancelStroke(); });

    // Раскрутка как у плеера: ▶ разгоняет холст, и он крутится, пока не нажмут ■; ■ — быстрое торможение.
    // Под конец холст доворачивается до ровного положения — один раз, до конца (rest запоминается): иначе доворот
    // снова разгонял бы холст, тот проскакивал ровное положение, и вращение не кончалось.
    const OMEGA = 15;   // рад/с на полном ходу
    let spinUntil = 0, raf = 0, last = 0, braking = false, rest = null;
    const playBtn = $('.play'), stopBtn = $('.stop');
    const instantBtn = $('.instant');
    const buttons = spinning => { playBtn.disabled = spinning; stopBtn.disabled = !spinning; };
    let instantOn = false;
    // Мгновенная раскрутка — переключатель: пока включена, каждый мазок, едва кисть оторвалась, раскручивается сразу —
    // та же физика, что у ▶, но 4 с вращения и торможение считаются за один кадр, без анимации. Включили —
    // раскручивается и то, что уже лежит на холсте.
    function instant() {
        if (raf) return;
        const dt = 1 / 60;
        omega = OMEGA;
        for (let t = 0; t < 4 && particles.length; t += dt) flow(dt);
        while (omega > .5 && particles.length) { omega -= omega * 1.6 * dt; flow(dt); }
        omega = 0;
    }
    function spin() {
        const now = performance.now();
        spinUntil = Infinity;
        braking = false;
        rest = null;
        buttons(true);
        if (!raf) { last = now; raf = requestAnimationFrame(tick); }
    }
    function stop() {
        if (!raf || braking) return;
        spinUntil = 0;
        braking = true;
        buttons(false);
    }
    function tick(now) {
        const dt = Math.min(.033, (now - last) / 1000);
        last = now;
        const TURN = Math.PI * 2;
        if (now < spinUntil) {
            omega += (OMEGA - omega) * Math.min(1, dt * 3);       // разгон ~0,7 с
            angle += omega * dt;
        } else if (rest === null && omega > 3) {
            omega -= omega * Math.min(1, dt * (braking ? 5 : 1.6));  // замедление: ~1,5 с, по кнопке ~0,4 с
            angle += omega * dt;
        } else {
            // доворот до ближайшего ровного положения впереди
            if (rest === null) rest = Math.ceil(angle / TURN + .05) * TURN;
            const was = angle;
            angle += (rest - angle) * Math.min(1, dt * (braking ? 7 : 3.2));  // по кнопке — быстрее
            omega = (angle - was) / Math.max(dt, 1e-3);
            if (rest - angle < .003) { angle = rest; omega = 0; }
        }
        // на ходу холст чуть отъезжает: повёрнутые углы помещаются в его место
        const k = 1 - .3 * Math.min(1, omega / 4);
        cv.style.transform = sv.style.transform = omega ? `rotate(${angle}rad) scale(${k.toFixed(3)})` : '';
        spinK = omega ? k : 1;
        flow(dt);
        if (omega > 0 || now < spinUntil) raf = requestAnimationFrame(tick);
        else { raf = 0; omega = 0; angle = 0; rest = null; braking = false; buttons(false); }
    }
    function flow(dt) {
        const cx = W / 2, cy = H / 2, scale = Math.min(W, H) / 400, w2 = omega * omega, light = GROUNDS[material].light;
        let cur = null;
        const keep = [], spray = [];
        for (const p of particles) {
            const M = MEDIA[p.md], water = !!M.glaze;
            if (cur !== M) {
                cur = M;
                ctx.globalCompositeOperation = water && light ? 'darken' : 'source-over';
                ctx.lineCap = water ? 'butt' : 'round';  // в акварели скруглённые концы накладывались бы бусинами
            }
            const rx = p.x - cx, ry = p.y - cy, r = Math.hypot(rx, ry) || 1;
            const pull = w2 * r / scale;   // центробежное ускорение в «пикселях холста 400»
            if (pull < p.stick * 900 && Math.hypot(p.vx, p.vy) < 1) { keep.push(p); continue; }  // ещё держится
            // ускорение наружу, Кориолис против вращения, вязкое трение
            const ax = rx / r * pull * scale * .9 - 2 * omega * -p.vy * .35, ay = ry / r * pull * scale * .9 - 2 * omega * p.vx * .35;
            p.vx = (p.vx + ax * dt) * (1 - M.drag * dt);
            p.vy = (p.vy + ay * dt) * (1 - M.drag * dt);
            const nx = p.x + p.vx * dt, ny = p.y + p.vy * dt, len = Math.hypot(nx - p.x, ny - p.y);
            // по мокрому — подхватывает его цвет и оставляет свой
            const i = cellAt(nx, ny);
            if (i >= 0) {
                if (gWet[i] > .05) mixInto(p.c, [gR[i], gG[i], gB[i]], Math.min(.5, M.mix * gWet[i] * (1 + len * .15)));
                wet(i, p.c, .3);
            }
            ctx.strokeStyle = rgba(p.c, water && !light ? .3 : M.alpha);
            ctx.lineWidth = Math.max(.5, p.m * M.width);
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(nx, ny);
            ctx.stroke();
            p.x = nx; p.y = ny;
            p.m -= len * M.lose;                     // краска остаётся на холсте
            if (p.m > .9 && Math.random() < len * M.spray) {  // брызги
                const a = Math.atan2(p.vy, p.vx) + rnd(-.5, .5), v = Math.hypot(p.vx, p.vy) * rnd(.8, 1.4);
                spray.push({ x: p.x, y: p.y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, m: p.m * .45, stick: 0, c: p.c.slice(), md: p.md });
                p.m *= .8;
            }
            if (p.m > .35 && p.x > -20 && p.x < W + 20 && p.y > -20 && p.y < H + 20) keep.push(p);
        }
        particles = keep.concat(spray);
        ctx.globalCompositeOperation = 'source-over';
    }

    // Выбор основы: образцы — кусочки той же фактуры; смена основы начинает работу заново.
    Object.keys(GROUNDS).forEach(key => {
        const b = document.createElement('button'), sw = document.createElement('canvas');
        b.className = 'mat';
        b.type = 'button';
        b.dataset.mat = key;
        b.setAttribute('aria-label', GROUNDS[key].label);
        b.title = GROUNDS[key].label;
        b.setAttribute('aria-pressed', key === material);
        sw.width = sw.height = 100;
        texture(sw.getContext('2d'), 100, 100, key);
        b.style.backgroundImage = `url(${sw.toDataURL()})`;
        b.onclick = () => {
            if (key === material) return;
            material = key;
            root.querySelectorAll('.mat').forEach(x => x.setAttribute('aria-pressed', x === b));
            $('.mat-name').textContent = matName();
            clearBoard();
        };
        $('.mats-row').appendChild(b);
    });
    // Выбор краски: пиктограммы; холст не очищается, краски можно сочетать.
    Object.keys(MEDIA).forEach(key => {
        const b = document.createElement('button');
        b.className = 'med';
        b.type = 'button';
        b.dataset.med = key;
        b.title = MEDIA[key].label;
        b.setAttribute('aria-label', MEDIA[key].label);
        b.setAttribute('aria-pressed', key === medium);
        b.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${MEDIA[key].icon}</svg>`;
        b.onclick = () => {
            medium = key;
            root.querySelectorAll('.med').forEach(x => x.setAttribute('aria-pressed', x === b));
            $('.mat-name').textContent = matName();
        };
        $('.media-row').appendChild(b);
    });
    const matName = () => GROUNDS[material].label + ' · ' + MEDIA[medium].label;
    $('.mat-name').textContent = matName();
    playBtn.onclick = spin;
    stopBtn.onclick = stop;
    instantBtn.onclick = () => {
        instantOn = !instantOn;
        instantBtn.setAttribute('aria-pressed', instantOn);
        if (instantOn && !raf) instant();
    };
    $('.clear').onclick = clearBoard;
    $('.save').onclick = () => {
        // сохраняем как есть, без поворота: холст в своей ориентации
        cv.toBlob(b => {
            if (!b) return;
            const a = document.createElement('a');
            a.href = URL.createObjectURL(b);
            a.download = 'моя-раскрутка.png';
            a.click();
            setTimeout(() => URL.revokeObjectURL(a.href), 4000);
        }, 'image/png');
    };

    let opener = null;
    function open() {
        opener = document.activeElement;
        root.hidden = false;
        document.documentElement.style.overflow = 'hidden';
        window.__studioOpen = true;
        layout();
        if (!particles.length && !root.dataset.used) { clearBoard(); root.dataset.used = 1; }
        requestAnimationFrame(() => root.classList.add('open'));
        $('.paint').focus();
    }
    function close() {
        root.classList.remove('open');
        stop();  // холст крутится, пока не остановят, и закрытая мастерская тоже его останавливает
        window.__studioOpen = false;
        document.documentElement.style.overflow = '';
        setTimeout(() => { root.hidden = true; }, 350);
        if (opener) opener.focus();
    }
    $('.close').onclick = close;
    root.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
    // стрелки и пробел внутри мастерской не листают галерею и пролёт
    root.addEventListener('keydown', e => e.stopPropagation());
    addEventListener('resize', () => { if (!root.hidden) layout(); });

    const btn = document.getElementById('studioOpen');
    if (btn) btn.onclick = open;
    window.__openStudio = open;  // для проверки
})();
