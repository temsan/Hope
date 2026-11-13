// Рябь на воде на первом экране: при открытии в воду падают три капли, дальше круги оставляет указатель (и палец),
// сквозь них преломляются картина и буквы названия, по гребням бегут блики. Когда движения нет, вода успокаивается
// и слой гаснет до чистого первого кадра; новое движение снова будит воду. С началом прокрутки рябь гаснет сразу,
// и дальше вступление рисует обычная вёрстка (картина в .portal и буквы в #title).
//
// Волны — разностная схема волнового уравнения на текстуре половинной точности: в канале r высота, в g скорость.
// Кадр собирается так же, как вёрстка: картина «cover» на весь экран, умноженная на маску букв (слой #title
// с multiply), увеличенную от центра экрана, — только с поправкой на наклон воды.
(function () {
    const cv = document.getElementById('ripple'), title = document.getElementById('title'),
        art = document.querySelector('.flight .portal .art');
    if (!cv || !title || !art || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const gl = cv.getContext('webgl2', { alpha: false, antialias: false, depth: false, stencil: false });
    if (!gl || !(gl.getExtension('EXT_color_buffer_float') || gl.getExtension('EXT_color_buffer_half_float'))) return;

    const VS = `#version 300 es
in vec2 p; out vec2 uv;
void main() { uv = p * .5 + .5; gl_Position = vec4(p, 0., 1.); }`;
    const HEAD = `#version 300 es
precision highp float;
in vec2 uv; out vec4 o;
`;
    // капля: поднимает воду куполом радиуса r (в долях высоты экрана)
    const DROP = HEAD + `uniform sampler2D t; uniform vec2 c, asp; uniform float r, s;
void main() {
    vec4 i = texture(t, uv);
    float d = max(0., 1. - length((uv - c) * asp) / r);
    i.r += (.5 - cos(d * 3.14159265) * .5) * s;
    o = i;
}`;
    // шаг волн: скорость тянется к среднему соседей, затухает; высота сдвигается на скорость
    const STEP = HEAD + `uniform sampler2D t; uniform vec2 dt;
void main() {
    vec4 i = texture(t, uv);
    float a = (texture(t, uv - vec2(dt.x, 0.)).r + texture(t, uv + vec2(dt.x, 0.)).r +
               texture(t, uv - vec2(0., dt.y)).r + texture(t, uv + vec2(0., dt.y)).r) * .25;
    i.g = (i.g + (a - i.r) * 2.) * .994;
    i.r += i.g;
    o = i;
}`;
    // кадр: наклон воды сдвигает выборку картины и букв; блик — свет сверху слева на склонах волн
    const DRAW = HEAD + `uniform sampler2D sim, paint, mask; uniform vec2 dt, cover; uniform float scale, op, str;
void main() {
    float h = texture(sim, uv).r;
    vec3 dx = vec3(dt.x, texture(sim, uv + vec2(dt.x, 0.)).r - h, 0.);
    vec3 dy = vec3(0., texture(sim, uv + vec2(0., dt.y)).r - h, dt.y);
    vec2 n = -normalize(cross(dy, dx)).xz;
    vec2 q = uv + n * .022 * str;
    vec3 pc = texture(paint, (q - .5) * cover + .5).rgb;
    vec3 m = texture(mask, (q - .5) / scale + .5).rgb;
    float spec = pow(max(0., dot(n, normalize(vec2(-.6, 1.)))), 4.) * str;
    o = vec4(pc * mix(vec3(1.), m, op) + spec * vec3(1., .96, .88) * .8, 1.);
}`;

    function program(fs) {
        const pr = gl.createProgram();
        for (const [type, src] of [[gl.VERTEX_SHADER, VS], [gl.FRAGMENT_SHADER, fs]]) {
            const sh = gl.createShader(type);
            gl.shaderSource(sh, src);
            gl.compileShader(sh);
            if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(sh));
            gl.attachShader(pr, sh);
        }
        gl.bindAttribLocation(pr, 0, 'p');
        gl.linkProgram(pr);
        if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(pr));
        const u = {};
        for (let k = gl.getProgramParameter(pr, gl.ACTIVE_UNIFORMS); k--;) {
            const name = gl.getActiveUniform(pr, k).name;
            u[name] = gl.getUniformLocation(pr, name);
        }
        return { pr, u };
    }
    let P;
    try { P = { drop: program(DROP), step: program(STEP), draw: program(DRAW) }; } catch (e) { return; }

    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

    function texture(filter) {
        const t = gl.createTexture();
        gl.bindTexture(gl.TEXTURE_2D, t);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, filter);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, filter);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        return t;
    }
    const paintTex = texture(gl.LINEAR), maskTex = texture(gl.LINEAR);
    let sims = [], simW = 0, simH = 0, paintReady = false, maskReady = false;

    // две текстуры волн: читаем из одной, пишем в другую
    function makeSims() {
        sims.forEach(s => { gl.deleteTexture(s.t); gl.deleteFramebuffer(s.f); });
        simH = 256;
        simW = Math.max(64, Math.round(simH * innerWidth / Math.max(1, innerHeight)));
        sims = [0, 1].map(() => {
            const t = texture(gl.LINEAR);
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA16F, simW, simH, 0, gl.RGBA, gl.HALF_FLOAT, null);
            const f = gl.createFramebuffer();
            gl.bindFramebuffer(gl.FRAMEBUFFER, f);
            gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, t, 0);
            return { t, f };
        });
        const ok = gl.checkFramebufferStatus(gl.FRAMEBUFFER) === gl.FRAMEBUFFER_COMPLETE;
        sims.forEach(s => { gl.bindFramebuffer(gl.FRAMEBUFFER, s.f); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT); });
        gl.bindFramebuffer(gl.FRAMEBUFFER, null);
        return ok;
    }

    function pass(p, target, setup) {
        gl.useProgram(p.pr);
        gl.bindFramebuffer(gl.FRAMEBUFFER, target ? target.f : null);
        gl.viewport(0, 0, target ? simW : cv.width, target ? simH : cv.height);
        setup(p.u);
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
    function simPass(p, setup) {
        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, sims[0].t);
        pass(p, sims[1], u => { gl.uniform1i(u.t, 0); setup(u); });
        sims.reverse();
    }

    // Маска букв — те же буквы, что в #title, на месте каждой: цвет буквы — окно в картину, фон слоя — темнота.
    function buildMask() {
        const W = innerWidth, H = innerHeight, d = Math.min(3, (devicePixelRatio || 1) * 1.5);
        const mc = document.createElement('canvas');
        mc.width = Math.round(W * d);
        mc.height = Math.round(H * d);
        const g = mc.getContext('2d');
        g.scale(d, d);
        g.fillStyle = getComputedStyle(title).backgroundColor;
        g.fillRect(0, 0, W, H);
        const was = [title.style.transform, title.style.display];
        title.style.transform = 'none';
        title.style.display = '';
        const f = title.getBoundingClientRect(), r = document.createRange(),
            walk = document.createTreeWalker(title, NodeFilter.SHOW_TEXT);
        for (let node; (node = walk.nextNode());) {
            const cs = getComputedStyle(node.parentElement);
            g.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
            g.fillStyle = cs.color;
            const asc = g.measureText('Н').fontBoundingBoxAscent;
            for (let i = 0; i < node.length; i++) {
                if (!node.data[i].trim()) continue;
                r.setStart(node, i);
                r.setEnd(node, i + 1);
                const b = r.getClientRects()[0];
                if (b) g.fillText(node.data[i], b.left - f.left, b.top - f.top + asc);
            }
        }
        title.style.transform = was[0];
        title.style.display = was[1];
        gl.bindTexture(gl.TEXTURE_2D, maskTex);
        gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, mc);
        maskReady = true;
        wake();
    }

    function uploadPaint() {
        gl.bindTexture(gl.TEXTURE_2D, paintTex);
        gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, art);
        paintReady = true;
        wake();
    }

    function resize() {
        const d = Math.min(2, devicePixelRatio || 1);
        cv.width = Math.round(innerWidth * d);
        cv.height = Math.round(innerHeight * d);
        if (!makeSims()) { sims = []; return; }
        if (document.fonts && document.fonts.status !== 'loaded') document.fonts.ready.then(buildMask);
        else buildMask();
        wake();
    }

    // Указатель: капля на каждый сдвиг, сильнее при быстром движении.
    let last = null;
    function dropAt(x, y, s) {
        if (!sims.length) return;
        simPass(P.drop, u => {
            gl.uniform2f(u.c, x / innerWidth, 1 - y / innerHeight);
            gl.uniform2f(u.asp, innerWidth / innerHeight, 1);
            gl.uniform1f(u.r, .03);
            gl.uniform1f(u.s, s);
        });
    }
    let lastMotion = 0;
    function move(x, y) {
        lastMotion = performance.now();
        wake();
        const dist = last ? Math.hypot(x - last[0], y - last[1]) : 0;
        last = [x, y];
        dropAt(x, y, Math.min(.022, .004 + dist * .0005));
    }
    addEventListener('pointermove', e => move(e.clientX, e.clientY), { passive: true });
    addEventListener('touchmove', e => { const t = e.touches[0]; if (t) move(t.clientX, t.clientY); }, { passive: true });
    addEventListener('pointerdown', e => { lastMotion = performance.now(); dropAt(e.clientX, e.clientY, .04); wake(); }, { passive: true });

    // Рябь видна, пока идёт начало вступления; к четверти его гаснет, и кадр снова рисует вёрстка.
    const smooth = t => { t = Math.min(1, Math.max(0, t)); return t * t * (3 - 2 * t); };
    const fade = k => 1 - smooth(k / .25);
    // Затишье: через CALM мс без движения вода за SETTLE мс успокаивается и слой гаснет до первого кадра;
    // после открытия ждём подольше, чтобы стартовые капли успели разойтись.
    // Отсчёт идёт с минуты, когда картина и буквы готовы (на медленной сети шрифты приходят не сразу).
    const CALM = 1800, CALM_START = 3200, SETTLE = 1800;
    let opened = -1;
    const calm = now => opened < 0 ? 1 : 1 - smooth((now - lastMotion - (lastMotion === opened ? CALM_START : CALM)) / SETTLE);
    // три капли около букв при открытии, вразнобой
    let started = false;
    function startDrops() {
        if (started) return;
        started = true;
        [[.38, .42, 0], [.62, .56, 380], [.5, .34, 820]].forEach(([x, y, t]) =>
            setTimeout(() => { dropAt(innerWidth * x, innerHeight * y, .05); wake(); }, t));
    }
    let active = false, raf = 0;
    function setActive(on) {
        if (on === active) return;
        active = on;
        cv.style.display = on ? 'block' : 'none';
        title.style.visibility = on ? 'hidden' : '';
        if (!on) last = null;
    }
    function frame() {
        raf = 0;
        const st = window.__intro || { k: 0, scale: 1, op: 1 }, str = fade(st.k) * calm(performance.now());
        const ready = paintReady && maskReady && sims.length && !document.hidden;
        setActive(ready && str > .002);
        if (!active) return;
        // стартовые капли и отсчёт затишья — с первого готового кадра; открыли не с начала — капель не будет
        if (opened < 0) {
            opened = lastMotion = performance.now();
            if (st.k < .02) startDrops();
        }
        simPass(P.step, u => gl.uniform2f(u.dt, 1 / simW, 1 / simH));
        simPass(P.step, u => gl.uniform2f(u.dt, 1 / simW, 1 / simH));
        const iw = art.naturalWidth, ih = art.naturalHeight, k = Math.max(innerWidth / iw, innerHeight / ih);
        gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, sims[0].t);
        gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, paintTex);
        gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D, maskTex);
        pass(P.draw, null, u => {
            gl.uniform1i(u.sim, 0);
            gl.uniform1i(u.paint, 1);
            gl.uniform1i(u.mask, 2);
            gl.uniform2f(u.dt, 1 / simW, 1 / simH);
            gl.uniform2f(u.cover, innerWidth / (iw * k), innerHeight / (ih * k));
            gl.uniform1f(u.scale, st.scale);
            gl.uniform1f(u.op, st.op);
            gl.uniform1f(u.str, str);
        });
        wake();
    }
    function wake() { if (!raf) raf = requestAnimationFrame(frame); }
    addEventListener('scroll', wake, { passive: true });
    addEventListener('pointermove', wake, { passive: true });
    document.addEventListener('visibilitychange', wake);
    addEventListener('resize', resize);

    if (art.complete && art.naturalWidth) uploadPaint();
    else art.addEventListener('load', () => { uploadPaint(); wake(); }, { once: true });
    resize();
})();
