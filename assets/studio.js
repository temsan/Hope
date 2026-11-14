// Мастерская: своя картина в технике Надежды — раскрутке. Капли и мазки красок на тёмном холсте, потом холст
// вращается, и краску разносит от центра лучами.
//
// Краска — частицы. Капля рисует на холсте лужицу и кладёт в неё частицы; при вращении частица срывается, когда
// центробежное ускорение (ω²·r) пересиливает её вязкость, летит наружу, загибаясь против вращения (Кориолис),
// и оставляет за собой след, теряя массу; изредка отрывает брызги. Холст поворачивается через CSS, частицы живут
// в его собственных координатах — след ложится на вращающийся холст.
//
// Краски смешиваются. Под холстом — сетка мокрой краски (цвет и влажность в клетке 4×4 точки): частица, проходя
// по мокрому, подхватывает его цвет, а клетка — её; капля, упавшая в мокрое, смешивается с ним. Два режима:
// акрил — плотная краска на тёмном холсте; акварель — прозрачные слои на белой бумаге (слои сходятся к пигменту:
// жёлтый поверх синего — зелёный, но не чёрный), у капли темнеет край.
(function () {
    const PAINTS = [
        ['красный', '#d6322b'], ['охра', '#d8b13a'], ['розовый', '#f1c6bb'], ['белый', '#f3eee4'], ['кобальт', '#2552b8'],
        ['бирюза', '#2ea596'], ['фиолетовый', '#5c2f8f'], ['золото', '#c8a04b'], ['чёрный', '#121212'],
    ];
    const SIZES = [['мелкая', 9], ['средняя', 16], ['крупная', 26]];
    const BOARDS = { acrylic: '#2a2a2d', water: '#f3efe6' };
    let mode = 'acrylic';

    const css = `
.studio{position:fixed;inset:0;z-index:5000;display:grid;grid-template-columns:auto auto;align-items:center;justify-content:center;
  gap:clamp(1rem,4vw,3.5rem);padding:clamp(1rem,3vw,2.5rem);background:radial-gradient(ellipse at 50% 45%,#16131a 0%,#050608 75%);
  color:#efe7d8;font-family:Manrope,sans-serif;opacity:0;transition:opacity .35s}
.studio.open{opacity:1}
.studio[hidden]{display:none}
.studio .board-wrap{position:relative;display:grid;place-items:center}
.studio canvas{display:block;border-radius:4px;box-shadow:0 30px 80px #000c,0 0 0 1px #efe7d814;touch-action:none;cursor:crosshair;
  will-change:transform}
.studio .side{display:grid;gap:1.4rem;justify-items:start;max-width:15rem}
.studio h2{margin:0;font:400 clamp(1.8rem,3.4vw,2.8rem)/.9 Spectral,serif;letter-spacing:-.04em}
.studio h2 em{color:#d6b775}
.studio p{margin:0;color:#efe7d89e;font-size:.82rem;line-height:1.6}
.studio .modes{display:flex;border:1px solid #efe7d84d}
.studio .mode{background:none;border:0;color:#efe7d8b3;font:inherit;font-size:.78rem;padding:.5rem .9rem;cursor:pointer}
.studio .mode[aria-pressed=true]{background:#efe7d8;color:#050608}
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
.studio .acts button:hover,.studio .acts .spin{background:#efe7d8;color:#050608}
.studio .acts .spin:hover{background:#d6b775}
.studio .close{position:absolute;top:1rem;right:1.2rem;background:none;border:0;color:#efe7d8b0;font-size:1.6rem;cursor:pointer;line-height:1}
@media (max-width:760px){
  .studio{grid-template-columns:1fr;grid-template-rows:auto auto;align-content:center;gap:1rem}
  .studio .side{order:2;max-width:none;justify-items:center;text-align:center;gap:.8rem}
  .studio .paints{grid-template-columns:repeat(9,1.9rem);gap:.4rem}
  .studio .paint{width:1.9rem;height:1.9rem}
  .studio h2,.studio p{display:none}
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
<div class="board-wrap"><canvas aria-label="Холст: касание — капля краски, проведение — мазок"></canvas></div>
<div class="side">
  <h2>Своя <em>раскрутка</em></h2>
  <p>Наберите краску, капните или проведите по холсту — и раскрутите. Мокрые краски смешиваются; можно добавить ещё
    и докрутить.</p>
  <div class="modes" role="group" aria-label="Краска">
    <button class="mode" type="button" data-mode="acrylic" aria-pressed="true">акрил</button>
    <button class="mode" type="button" data-mode="water" aria-pressed="false">акварель</button>
  </div>
  <div class="paints" role="group" aria-label="Краски"></div>
  <div class="sizes" role="group" aria-label="Размер капли"></div>
  <div class="acts">
    <button class="spin" type="button">раскрутить</button>
    <button class="clear" type="button">очистить</button>
    <button class="save" type="button">сохранить</button>
  </div>
</div>`;
    document.body.appendChild(root);

    const cv = root.querySelector('canvas'), ctx = cv.getContext('2d'), $ = s => root.querySelector(s);
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
        const maxH = narrow ? innerHeight * .62 : innerHeight * .82, maxW = narrow ? innerWidth * .92 : innerWidth * .6;
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
        ctx.fillStyle = BOARDS[mode];
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
    function clearBoard() {
        ctx.globalCompositeOperation = 'source-over';
        ctx.fillStyle = BOARDS[mode];
        ctx.fillRect(0, 0, W, H);
        // лёгкая фактура: зерно холста или волокна бумаги
        for (let i = 0; i < W * H / 90; i++) {
            ctx.fillStyle = mode === 'water' ? `rgba(90,70,40,${rnd(0, .05)})` : `rgba(255,255,255,${rnd(0, .025)})`;
            ctx.fillRect(rnd(0, W), rnd(0, H), mode === 'water' ? rnd(1, 3) : 1, 1);
        }
        makeGrid();
        particles = [];
        angle = 0;
        cv.style.transform = '';
    }

    // Капля: неровная лужица с бликом, в ней — частицы краски.
    function dab(x, y, r, hexColor) {
        // упала в мокрое — смешивается с ним
        const c = hex(hexColor), under = cellAt(x, y);
        if (under >= 0 && gWet[under] > .2) mixInto(c, [gR[under], gG[under], gB[under]], mode === 'water' ? .35 : .3);
        if (mode === 'water') {
            // акварель: прозрачные слои пигмента («темнее из двух»: слои сходятся к цвету пигмента и не уходят
            // в чёрное), к краю лужицы пигмент собирается темнее
            ctx.globalCompositeOperation = 'darken';
            ctx.fillStyle = rgba(c, .35);
            for (let i = 0; i < 5; i++) {
                ctx.beginPath();
                ctx.arc(x + rnd(-.2, .2) * r, y + rnd(-.2, .2) * r, r * rnd(.7, 1), 0, Math.PI * 2);
                ctx.fill();
            }
            ctx.strokeStyle = rgba(c.map(v => v * .78), .45);
            ctx.lineWidth = r * .12;
            ctx.beginPath();
            ctx.arc(x, y, r * .92, 0, Math.PI * 2);
            ctx.stroke();
            ctx.globalCompositeOperation = 'source-over';
        } else {
            ctx.globalCompositeOperation = 'source-over';
            ctx.fillStyle = rgba(c, 1);
            for (let i = 0; i < 6; i++) {
                ctx.beginPath();
                ctx.arc(x + rnd(-.25, .25) * r, y + rnd(-.25, .25) * r, r * rnd(.55, .85), 0, Math.PI * 2);
                ctx.fill();
            }
            const g = ctx.createRadialGradient(x - r * .3, y - r * .35, 0, x - r * .3, y - r * .35, r * .6);
            g.addColorStop(0, 'rgba(255,255,255,.28)');
            g.addColorStop(1, 'rgba(255,255,255,0)');
            ctx.fillStyle = g;
            ctx.beginPath();
            ctx.arc(x, y, r * .8, 0, Math.PI * 2);
            ctx.fill();
        }
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
                stick: rnd(.4, 1.6),                      // вязкость: чем больше, тем позже срывается
                c: c.slice(),
            });
        }
        if (particles.length > 9000) particles.splice(0, particles.length - 9000);
    }

    // Точка экрана → точка холста с учётом его поворота.
    function toBoard(e) {
        const r = cv.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        const dx = e.clientX - cx, dy = e.clientY - cy, c = Math.cos(-angle), s = Math.sin(-angle);
        return [W / 2 + dx * c - dy * s, H / 2 + dx * s + dy * c];
    }
    let drawing = null;
    cv.addEventListener('pointerdown', e => {
        e.preventDefault();
        cv.setPointerCapture(e.pointerId);
        const [x, y] = toBoard(e);
        drawing = [x, y];
        dab(x, y, size, color);
    });
    cv.addEventListener('pointermove', e => {
        if (!drawing) return;
        const [x, y] = toBoard(e), step = size * .55, dist = Math.hypot(x - drawing[0], y - drawing[1]);
        // мазок — цепочка капель поменьше
        for (let t = step; t <= dist; t += step) {
            const k = t / dist;
            dab(drawing[0] + (x - drawing[0]) * k, drawing[1] + (y - drawing[1]) * k, size * .7, color);
        }
        if (dist >= step) drawing = [x, y];
    });
    const stopDraw = () => { drawing = null; };
    cv.addEventListener('pointerup', stopDraw);
    cv.addEventListener('pointercancel', stopDraw);

    // Раскрутка: разгон, вращение, замедление. Повторное нажатие продлевает.
    const OMEGA = 15;   // рад/с на полном ходу
    let spinUntil = 0, raf = 0, last = 0;
    function spin() {
        const now = performance.now();
        spinUntil = Math.max(spinUntil, now) + 2600;
        if (!raf) { last = now; raf = requestAnimationFrame(tick); }
    }
    function tick(now) {
        const dt = Math.min(.033, (now - last) / 1000);
        last = now;
        // к цели — плавно: разгон ~0,7 с, замедление ~1,5 с; под конец холст доворачивается до ровного положения
        const target = now < spinUntil ? OMEGA : 0, TURN = Math.PI * 2;
        if (target === 0 && omega < 2.5) {
            const rest = Math.ceil(angle / TURN - .02) * TURN, was = angle;
            angle += (rest - angle) * Math.min(1, dt * 2.6);
            omega = (angle - was) / Math.max(dt, 1e-3);
            if (rest - angle < .002) { angle = rest; omega = 0; }
        } else {
            omega += (target - omega) * Math.min(1, dt * (target > omega ? 3 : 1.6));
            angle += omega * dt;
        }
        // на ходу холст чуть отъезжает: повёрнутые углы помещаются в его место
        const k = 1 - .3 * Math.min(1, omega / 4);
        cv.style.transform = omega ? `rotate(${angle}rad) scale(${k.toFixed(3)})` : '';
        flow(dt);
        if (omega > 0 || now < spinUntil) raf = requestAnimationFrame(tick);
        else { raf = 0; omega = 0; angle = 0; }
    }
    function flow(dt) {
        const cx = W / 2, cy = H / 2, scale = Math.min(W, H) / 400, w2 = omega * omega, water = mode === 'water';
        ctx.globalCompositeOperation = water ? 'darken' : 'source-over';
        ctx.lineCap = water ? 'butt' : 'round';  // в акварели скруглённые концы накладывались бы бусинами
        const keep = [], spray = [];
        for (const p of particles) {
            const rx = p.x - cx, ry = p.y - cy, r = Math.hypot(rx, ry) || 1;
            const pull = w2 * r / scale;   // центробежное ускорение в «пикселях холста 400»
            if (pull < p.stick * 900 && Math.hypot(p.vx, p.vy) < 1) { keep.push(p); continue; }  // ещё держится
            // ускорение наружу, Кориолис против вращения, вязкое трение
            const ax = rx / r * pull * scale * .9 - 2 * omega * -p.vy * .35, ay = ry / r * pull * scale * .9 - 2 * omega * p.vx * .35;
            p.vx = (p.vx + ax * dt) * (1 - 2.2 * dt);
            p.vy = (p.vy + ay * dt) * (1 - 2.2 * dt);
            const nx = p.x + p.vx * dt, ny = p.y + p.vy * dt, len = Math.hypot(nx - p.x, ny - p.y);
            // по мокрому — подхватывает его цвет и оставляет свой
            const i = cellAt(nx, ny);
            if (i >= 0) {
                if (gWet[i] > .05) mixInto(p.c, [gR[i], gG[i], gB[i]], Math.min(.5, (water ? .1 : .07) * gWet[i] * (1 + len * .15)));
                wet(i, p.c, .3);
            }
            ctx.strokeStyle = rgba(p.c, water ? .4 : .92);
            ctx.lineWidth = Math.max(.6, p.m * (water ? 1.5 : 1));
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(nx, ny);
            ctx.stroke();
            p.x = nx; p.y = ny;
            p.m -= len * .012;                       // краска остаётся на холсте
            if (p.m > .9 && Math.random() < len * .0015) {  // брызги
                const a = Math.atan2(p.vy, p.vx) + rnd(-.5, .5), v = Math.hypot(p.vx, p.vy) * rnd(.8, 1.4);
                spray.push({ x: p.x, y: p.y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, m: p.m * .45, stick: 0, c: p.c.slice() });
                p.m *= .8;
            }
            if (p.m > .35 && p.x > -20 && p.x < W + 20 && p.y > -20 && p.y < H + 20) keep.push(p);
        }
        particles = keep.concat(spray);
        ctx.globalCompositeOperation = 'source-over';
    }

    root.querySelectorAll('.mode').forEach(b => b.onclick = () => {
        if (b.dataset.mode === mode) return;
        mode = b.dataset.mode;
        root.querySelectorAll('.mode').forEach(x => x.setAttribute('aria-pressed', x === b));
        clearBoard();  // акрил — тёмный холст, акварель — белая бумага
    });
    $('.spin').onclick = spin;
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
