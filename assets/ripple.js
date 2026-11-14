// Рябь на воде — на первом экране и во всей галерее.
//
// Первый экран (#ripple): при открытии в воду падают три капли, дальше круги оставляет указатель (и палец);
// сквозь волны преломляются картина и буквы названия, по гребням бегут блики. Рябь держится весь влёт в буквы
// (прокрутка тоже тревожит воду) и гаснет под его конец; дальше кадр рисует обычная вёрстка (.portal и #title).
//
// Галерея (#galleryRipple): картина на мольберте преломляется сквозь волны (в том числе приближенная),
// на остальном — небе, луне, свечах — видны блики и тени волн: вёрстку WebGL преломить не может.
//
// В обеих сценах, когда движения нет, вода успокаивается и слой гаснет до чистой картинки; новое движение
// снова будит воду. Во время пролёта между картинами ряби нет — там клипы.
//
// Волны — разностная схема волнового уравнения на текстуре половинной точности: в канале r высота, в g скорость.
(function () {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const VS = `#version 300 es
in vec2 p; out vec2 uv;
void main() { uv = p * .5 + .5; gl_Position = vec4(p, 0., 1.); }`;
    const HEAD = `#version 300 es
precision highp float;
#define CAUSTIC ${window.__caustic || 800}.
#define DISPERSION ${window.__dispersion || .6}
#define SPECTRAL ${window.__spectral || .8}
in vec2 uv; out vec4 o;
`;
    // капля: поднимает воду куполом радиуса r (в долях высоты слоя)
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
    i.g = (i.g + (a - i.r) * 2.) * .993;
    i.r += i.g;
    o = i;
}`;
    // наклон воды n и освещённость склона: свет сверху слева
    const SLOPE = `
    float h = texture(sim, uv).r;
    vec3 dx = vec3(dt.x, texture(sim, uv + vec2(dt.x, 0.)).r - h, 0.);
    vec3 dy = vec3(0., texture(sim, uv + vec2(0., dt.y)).r - h, dt.y);
    vec2 n = -normalize(cross(dy, dx)).xz;
    float lit = dot(n, normalize(vec2(-.6, 1.)));
    vec3 glint = pow(max(0., lit), 2.2) * str * vec3(1., .96, .88);
    // радуга на гребнях: оттенок бежит по кругу вместе с направлением склона, как в капле, которая работает призмой
    float tilt = length(n);
    vec3 rainbow = .5 + .5 * cos(6.2832 * (atan(n.y, n.x) / 6.2832 + vec3(0., .33, .67)));
    glint = mix(glint, glint * rainbow * 1.6, SPECTRAL * smoothstep(.02, .25, tilt));
    // каустика: выпуклая волна работает линзой и собирает свет на дне в тёплые прожилки (по кривизне поверхности)
    // кривизна — по соседям через клетку: мелкая рябь сетки не дробит каустику на бусины
    float lap = texture(sim, uv + vec2(2. * dt.x, 0.)).r + texture(sim, uv - vec2(2. * dt.x, 0.)).r +
                texture(sim, uv + vec2(0., 2. * dt.y)).r + texture(sim, uv - vec2(0., 2. * dt.y)).r - 4. * h;
    float caustic = smoothstep(0., 1., max(0., -lap) * CAUSTIC) * str;
    vec3 warm = vec3(1., .92, .74);`;
    // первый экран: картина «cover» на весь экран, умноженная на маску букв (как слой #title с multiply),
    // увеличенную от центра экрана, — с поправкой на наклон воды
    const DRAW_INTRO = HEAD + `uniform sampler2D sim, paint, mask; uniform vec2 dt, cover; uniform float scale, op, str, drip, cols;
float hash(float x) { return fract(sin(x * 127.1) * 43758.5453); }
float noise(float x) { float i = floor(x), f = fract(x); return mix(hash(i), hash(i + 1.), f * f * (3. - 2. * f)); }
void main() {${SLOPE}
    // дисперсия: красный преломляется слабее, синий сильнее — на склонах волн радужная кайма
    vec2 off = n * .014 * str, qr = uv + off * (1. - DISPERSION), qg = uv + off, qb = uv + off * (1. + DISPERSION);
    vec3 pc = vec3(texture(paint, (qr - .5) * cover + .5).r, texture(paint, (qg - .5) * cover + .5).g,
                   texture(paint, (qb - .5) * cover + .5).b);
    vec3 m = vec3(texture(mask, (qr - .5) / scale + .5).r, texture(mask, (qg - .5) / scale + .5).g,
                  texture(mask, (qb - .5) / scale + .5).b);
    // Буквы стекают. У низа букв краска чуть оплывает (короткий смаз), а дальше вниз сбегают струйки:
    // каждая своей длины и толщины, к низу тоньше, на конце — круглая капля. Струйки — по узким столбцам экрана,
    // в каждом столбце своя (или никакой); где над точкой в пределах длины струйки есть буква, там краска.
    if (drip > .001) {
        vec2 q = (qg - .5) / scale + .5;
        float band = noise(uv.x * 22.), hair = noise(uv.x * 230.), len = drip * .22 * (.06 + .94 * pow(band, 1.8)) * (.7 + .3 * hair);
        float lean = (noise(uv.x * 5. + 7.) - .5) * .15;
        vec3 run = vec3(0.);
        for (int j = 1; j <= 28; j++) {
            float t = float(j) / 28.;
            vec3 s = texture(mask, q + vec2(lean * t * len, t * len) / scale).rgb;
            run = max(run, s * (1. - smoothstep(.55, 1., t)) * (1. - .3 * t) * (.35 + .65 * hair));
        }
        m = max(m, run);

        float asp = dt.y / dt.x, N = cols, col = floor(uv.x * N);
        float h1 = hash(col * 1.37 + 2.), h2 = hash(col * 3.11 + 9.), h3 = hash(col * 7.73 + 1.);
        if (h1 > .58) {
            // длина (доли высоты экрана), полуширина (доли ширины) и радиус капли (доли высоты)
            float L = drip * (.12 + .88 * h2 * h2), w = (.16 + .2 * h3) / N, rb = w * 1.5 * asp;
            float ax = abs(fract(uv.x * N) - .5) / N;
            vec2 base = (vec2((col + .5) / N, uv.y) + (qg - uv) - .5) / scale + .5;
            float t0 = -1.;
            vec3 src = vec3(0.);
            for (int j = 0; j <= 36; j++) {
                float t = (L + rb) * float(j) / 36.;
                vec3 sm = texture(mask, base + vec2(0., t) / scale).rgb;
                if (dot(sm, vec3(.333)) > .3) {
                    // цвет — чуть глубже в букве: на сглаженном краю он темнее, и струйка шла бы полосками
                    t0 = t;
                    src = max(sm, max(texture(mask, base + vec2(0., t + 3. * dt.y) / scale).rgb,
                                      texture(mask, base + vec2(0., t + 6. * dt.y) / scale).rgb));
                    break;
                }
            }
            if (t0 >= 0.) {
                float tip = L - rb, wid = w * (1. - .45 * min(1., t0 / max(L, 1e-4)));
                float body = step(t0, tip) * (1. - smoothstep(wid * .55, wid * 1.1, ax));
                float bulb = 1. - smoothstep(rb * .7, rb, length(vec2(ax * asp, t0 - tip)));
                m = max(m, src * max(body, bulb));
            }
        }
    }
    vec3 under = pc * mix(vec3(1.), m, op);
    o = vec4(under * (1. + caustic * .9) + caustic * .05 * warm + glint * .38, 1.);
}`;
    // галерея: в прямоугольнике картины — сама картина со сдвигом, вокруг — только блики и тени (слой прозрачный,
    // цвет с умноженной альфой)
    const DRAW_GALLERY = HEAD + `uniform sampler2D sim, paint; uniform vec2 dt; uniform vec4 rect; uniform float str, hasPaint;
void main() {${SLOPE}
    vec3 light = glint * .34 + caustic * .16 * warm;
    if (hasPaint > .5 && uv.x >= rect.x && uv.x <= rect.z && uv.y >= rect.y && uv.y <= rect.w) {
        vec2 off = n * .012 * str, span = rect.zw - rect.xy;
        vec3 c = vec3(texture(paint, clamp((uv + off * (1. - DISPERSION) - rect.xy) / span, 0., 1.)).r,
                      texture(paint, clamp((uv + off - rect.xy) / span, 0., 1.)).g,
                      texture(paint, clamp((uv + off * (1. + DISPERSION) - rect.xy) / span, 0., 1.)).b);
        o = vec4(c * (1. + caustic * .8) + light, 1.);
    } else {
        float shade = max(0., -lit) * .3 * str;  // впадины волн чуть темнее
        o = vec4(light, clamp(max(light.r, shade), 0., 1.));
    }
}`;

    // Вода на одном холсте: свой WebGL-контекст, волны, капли, кадр.
    function water(cv, alpha, drawFs) {
        const gl = cv.getContext('webgl2', { alpha, premultipliedAlpha: true, antialias: false, depth: false, stencil: false });
        if (!gl || !(gl.getExtension('EXT_color_buffer_float') || gl.getExtension('EXT_color_buffer_half_float'))) return null;
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
        try { P = { drop: program(DROP), step: program(STEP), draw: program(drawFs) }; } catch (e) { return null; }
        gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
        gl.enableVertexAttribArray(0);
        gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

        function texture() {
            const t = gl.createTexture();
            gl.bindTexture(gl.TEXTURE_2D, t);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
            return t;
        }
        let sims = [], simW = 0, simH = 0, aspect = 1;
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
        const W = {
            gl,
            texture,
            get ready() { return sims.length > 0; },
            // холст — в пикселях экрана (не больше двух на точку), волны — 256 по высоте
            resize(w, h) {
                const d = Math.min(2, devicePixelRatio || 1);
                cv.width = Math.max(1, Math.round(w * d));
                cv.height = Math.max(1, Math.round(h * d));
                aspect = w / Math.max(1, h);
                sims.forEach(s => { gl.deleteTexture(s.t); gl.deleteFramebuffer(s.f); });
                simH = 256;
                simW = Math.max(64, Math.round(simH * aspect));
                sims = [0, 1].map(() => {
                    const t = texture();
                    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA16F, simW, simH, 0, gl.RGBA, gl.HALF_FLOAT, null);
                    const f = gl.createFramebuffer();
                    gl.bindFramebuffer(gl.FRAMEBUFFER, f);
                    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, t, 0);
                    return { t, f };
                });
                const ok = gl.checkFramebufferStatus(gl.FRAMEBUFFER) === gl.FRAMEBUFFER_COMPLETE;
                sims.forEach(s => { gl.bindFramebuffer(gl.FRAMEBUFFER, s.f); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT); });
                gl.bindFramebuffer(gl.FRAMEBUFFER, null);
                if (!ok) sims = [];
            },
            // капля в точке (fx, fy) в долях слоя, fy — сверху вниз
            drop(fx, fy, s, r = .055) {
                if (!sims.length) return;
                simPass(P.drop, u => {
                    gl.uniform2f(u.c, fx, 1 - fy);
                    gl.uniform2f(u.asp, aspect, 1);
                    gl.uniform1f(u.r, r);
                    gl.uniform1f(u.s, s);
                });
            },
            // шаг волн и кадр; textures — [единица, текстура] для картины и прочего
            frame(textures, setup) {
                simPass(P.step, u => gl.uniform2f(u.dt, 1 / simW, 1 / simH));
                gl.activeTexture(gl.TEXTURE0);
                gl.bindTexture(gl.TEXTURE_2D, sims[0].t);
                textures.forEach(([unit, t]) => { gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, t); });
                pass(P.draw, null, u => {
                    gl.uniform1i(u.sim, 0);
                    gl.uniform2f(u.dt, 1 / simW, 1 / simH);
                    setup(u);
                });
            },
            upload(t, source) {
                gl.bindTexture(gl.TEXTURE_2D, t);
                gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
                gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source);
            },
        };
        return W;
    }

    const smooth = t => { t = Math.min(1, Math.max(0, t)); return t * t * (3 - 2 * t); };
    // Затишье: через CALM мс без движения вода за SETTLE мс успокаивается и слой гаснет.
    const CALM = 1800, SETTLE = 1800;

    // Звук воды — синтез в браузере, без файлов. Ведёшь указателем — мягкий плеск: шум, пропущенный через полосовой
    // фильтр; чем быстрее движение, тем громче и выше, а остановился — плеск за полсекунды стихает. Касание — «плюх»
    // капли: тон пузырька, что быстро взлетает вверх. Браузер даёт звуку зазвучать только после первого нажатия,
    // поэтому до него тихо. Кнопка «звук» в углу выключает и включает (запоминается).
    const sound = (() => {
        let ac = null, gain = null, bp = null, on = true, lastAt = 0;
        try { on = localStorage.getItem('hope-sound') !== 'off'; } catch (_) { /* хранилище недоступно */ }
        function init() {
            if (ac || !on) return;
            const AC = window.AudioContext || window.webkitAudioContext;
            if (!AC) return;
            ac = new AC();
            // две секунды мягкого («розового») шума по кругу
            const len = ac.sampleRate * 2, buf = ac.createBuffer(1, len, ac.sampleRate), data = buf.getChannelData(0);
            let b0 = 0, b1 = 0, b2 = 0;
            for (let i = 0; i < len; i++) {
                const w = Math.random() * 2 - 1;
                b0 = .99765 * b0 + w * .099; b1 = .963 * b1 + w * .2965; b2 = .57 * b2 + w * 1.0526;
                data[i] = (b0 + b1 + b2 + w * .1848) * .18;
            }
            const src = ac.createBufferSource();
            src.buffer = buf;
            src.loop = true;
            bp = ac.createBiquadFilter();
            bp.type = 'bandpass'; bp.frequency.value = 600; bp.Q.value = 1.1;
            const lp = ac.createBiquadFilter();
            lp.type = 'lowpass'; lp.frequency.value = 1600;
            gain = ac.createGain();
            gain.gain.value = 0;
            src.connect(bp); bp.connect(lp); lp.connect(gain); gain.connect(ac.destination);
            src.start();
        }
        const wake = () => { init(); if (ac && ac.state === 'suspended') ac.resume(); };
        ['pointerdown', 'keydown', 'touchstart'].forEach(ev => addEventListener(ev, wake, { passive: true }));
        const ready = () => ac && on && ac.state === 'running';
        const hold = (param, t) => { if (param.cancelAndHoldAtTime) param.cancelAndHoldAtTime(t); else { param.cancelScheduledValues(t); param.setValueAtTime(param.value, t); } };
        return {
            // dist — сколько точек прошёл указатель с прошлого раза
            stir(dist) {
                if (!ready()) return;
                const now = performance.now(), ms = Math.max(8, Math.min(120, now - lastAt));
                lastAt = now;
                const v = Math.min(1, dist / ms / 2.2), t = ac.currentTime;
                hold(gain.gain, t);
                gain.gain.setTargetAtTime(.015 + .09 * v, t, .07);
                gain.gain.setTargetAtTime(0, t + .14, .3);
                hold(bp.frequency, t);
                bp.frequency.setTargetAtTime(380 + 820 * v + Math.random() * 140, t, .12);
            },
            plip() {
                if (!ready()) return;
                const t = ac.currentTime, o = ac.createOscillator(), g = ac.createGain(), f = 520 + Math.random() * 380;
                o.type = 'sine';
                o.frequency.setValueAtTime(f, t);
                o.frequency.exponentialRampToValueAtTime(f * 2.1, t + .06);
                g.gain.setValueAtTime(0, t);
                g.gain.linearRampToValueAtTime(.06, t + .006);
                g.gain.exponentialRampToValueAtTime(.0001, t + .16);
                o.connect(g); g.connect(ac.destination);
                o.start(t); o.stop(t + .18);
            },
            toggle() {
                on = !on;
                try { localStorage.setItem('hope-sound', on ? 'on' : 'off'); } catch (_) { /* не запомним */ }
                if (on) wake();
                else if (gain) { hold(gain.gain, ac.currentTime); gain.gain.setTargetAtTime(0, ac.currentTime, .05); }
                return on;
            },
            get on() { return on; },
            get state() { return ac ? ac.state : 'none'; },
        };
    })();
    window.__sound = sound;  // для проверки
    // кнопка «звук» — в левом верхнем углу, в той же манере, что «сразу в галерею»
    (function () {
        const st = document.createElement('style');
        st.textContent = `.sound-toggle{position:fixed;z-index:4500;top:clamp(1.4rem,4vw,4rem);left:clamp(1.45rem,4vw,4.05rem);
  padding:.5rem 0;border:0;background:none;color:var(--muted,#efe7d880);text-transform:uppercase;letter-spacing:.19em;font-size:10px;
  font-weight:600;cursor:pointer;display:flex;gap:.5em;align-items:center;transition:color .2s;font-family:inherit}
.sound-toggle:hover,.sound-toggle:focus-visible{color:var(--paper,#efe7d8)}
.sound-toggle svg{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:1.5;stroke-linecap:round}
.sound-toggle[aria-pressed=false] .wave{display:none}
.sound-toggle[aria-pressed=true] .mute{display:none}
.sound-toggle.in-gallery{top:calc(clamp(1.4rem,4vw,4rem) + 3.2rem)}`;
        document.head.appendChild(st);
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'sound-toggle';
        b.setAttribute('aria-pressed', sound.on);
        b.setAttribute('aria-label', 'Звук воды');
        b.innerHTML = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 6h2.5L8 3v10L4.5 10H2z"/><path class="wave" d="M10.5 5.5a3.5 3.5 0 0 1 0 5M12.5 3.5a6.3 6.3 0 0 1 0 9"/><path class="mute" d="M10.5 6l4 4M14.5 6l-4 4"/></svg>звук';
        b.onclick = () => b.setAttribute('aria-pressed', sound.toggle());
        document.body.appendChild(b);
        // в галерее в углу кнопки «пройти ещё раз» и «раскрутить свою» — «звук» уходит под них
        setInterval(() => b.classList.toggle('in-gallery', !!window.__inGallery), 400);
    })();

    // Сцена — вода на холсте плюс то, что она рисует; движение указателя будит её.
    const scenes = [];
    function scene(opts) {
        const s = Object.assign({ active: false, raf: 0, last: null, lastMotion: -1e9 }, opts);
        // координаты — по контейнеру холста: скрытый холст размеров не имеет, а слой занимает контейнер целиком
        s.box = () => s.cv.parentElement.getBoundingClientRect();
        s.wake = () => { if (!s.raf) s.raf = requestAnimationFrame(() => { s.raf = 0; s.tick(); }); };
        s.setActive = on => {
            if (on === s.active) return;
            s.active = on;
            s.cv.style.display = on ? 'block' : 'none';
            if (s.onToggle) s.onToggle(on);
            if (!on) s.last = null;
        };
        // указатель: капля на каждый сдвиг, сильнее при быстром движении
        s.move = (x, y) => {
            if (!s.wants()) return;
            const r = s.box();
            if (!r.width || !r.height) return;
            const dist = s.last ? Math.hypot(x - s.last[0], y - s.last[1]) : 0;
            s.last = [x, y];
            s.lastMotion = performance.now();
            s.w.drop((x - r.left) / r.width, (y - r.top) / r.height, Math.min(.011, .002 + dist * .00025));
            if (dist) sound.stir(dist);
            s.wake();
        };
        s.tap = (x, y) => {
            if (!s.wants()) return;
            const r = s.box();
            if (!r.width || !r.height) return;
            s.lastMotion = performance.now();
            s.w.drop((x - r.left) / r.width, (y - r.top) / r.height, .022, .07);
            sound.plip();
            s.wake();
        };
        s.calm = now => 1 - smooth((now - s.lastMotion - (s.calmExtra ? s.calmExtra() : 0) - CALM) / SETTLE);
        scenes.push(s);
        return s;
    }
    addEventListener('pointermove', e => scenes.forEach(s => s.move(e.clientX, e.clientY)), { passive: true });
    addEventListener('touchmove', e => { const t = e.touches[0]; if (t) scenes.forEach(s => s.move(t.clientX, t.clientY)); }, { passive: true });
    addEventListener('pointerdown', e => scenes.forEach(s => s.tap(e.clientX, e.clientY)), { passive: true });
    addEventListener('scroll', () => scenes.forEach(s => s.wake()), { passive: true });
    addEventListener('resize', () => scenes.forEach(s => s.resize()));
    document.addEventListener('visibilitychange', () => scenes.forEach(s => s.wake()));

    // ── Первый экран ──
    (function intro() {
        const cv = document.getElementById('ripple'), title = document.getElementById('title'),
            art = document.querySelector('.flight .portal .art');
        if (!cv || !title || !art) return;
        const w = water(cv, false, DRAW_INTRO);
        if (!w) return;
        const paintTex = w.texture(), maskTex = w.texture(), maxTex = Math.min(4096, w.gl.getParameter(w.gl.MAX_TEXTURE_SIZE));
        let paintReady = false, glyphs = null, bg = '#050608', maskScale = 0, opened = -1, started = false;
        const st = () => window.__intro || { k: 0, scale: 1, op: 1 };
        // рябь живёт весь влёт в буквы и гаснет только под самый конец, когда букв уже не видно
        const scrollFade = k => 1 - smooth((k - .82) / .18);
        // длина потёков букв (в долях высоты экрана): сколько им позволяет прокрутка; сама краска течёт с конечной
        // скоростью — струйки сбегают у глаз и после того, как листать перестали; назад втягиваются быстро
        const dripOf = k => .45 * smooth(k / .5), DRIP_SPEED = .09;
        let dripNow = 0, dripAt = 0;
        const s = scene({
            cv, w,
            wants: () => st().k < 1 && !window.__inGallery,
            onToggle: on => { title.style.visibility = on ? 'hidden' : ''; },
            // после открытия затишье наступает позже: стартовые капли успевают разойтись
            calmExtra: () => (s.lastMotion === opened ? 1400 : 0),
        });

        // Буквы #title: где каждая стоит и каким шрифтом и цветом нарисована — замеряем один раз (и при смене окна).
        function measureGlyphs() {
            const was = [title.style.transform, title.style.display];
            title.style.transform = 'none';
            title.style.display = '';
            const f = title.getBoundingClientRect(), r = document.createRange(), g = document.createElement('canvas').getContext('2d'),
                walk = document.createTreeWalker(title, NodeFilter.SHOW_TEXT), out = [];
            for (let node; (node = walk.nextNode());) {
                const cs = getComputedStyle(node.parentElement), font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
                g.font = font;
                const asc = g.measureText('Н').fontBoundingBoxAscent;
                for (let i = 0; i < node.length; i++) {
                    if (!node.data[i].trim()) continue;
                    r.setStart(node, i);
                    r.setEnd(node, i + 1);
                    const b = r.getClientRects()[0];
                    if (b) out.push({ ch: node.data[i], x: b.left - f.left, y: b.top - f.top + asc, font, color: cs.color });
                }
            }
            bg = getComputedStyle(title).backgroundColor;
            title.style.transform = was[0];
            title.style.display = was[1];
            glyphs = out;
            maskScale = 0;
            s.wake();
        }
        // Маска букв, увеличенных в scale раз от центра экрана: цвет буквы — окно в картину, фон слоя — темнота.
        // Перерисовывается, когда увеличение ушло от нарисованного больше чем на четверть, — буквы остаются чёткими.
        function drawMask(scale) {
            const W = innerWidth, H = innerHeight,
                d = Math.min(3, (devicePixelRatio || 1) * 1.5, maxTex / W, maxTex / H);
            const mc = document.createElement('canvas');
            mc.width = Math.round(W * d);
            mc.height = Math.round(H * d);
            const g = mc.getContext('2d');
            g.scale(d, d);
            g.fillStyle = bg;
            g.fillRect(0, 0, W, H);
            g.translate(W / 2, H / 2);
            g.scale(scale, scale);
            g.translate(-W / 2, -H / 2);
            for (const q of glyphs) {
                g.font = q.font;
                g.fillStyle = q.color;
                g.fillText(q.ch, q.x, q.y);
            }
            w.upload(maskTex, mc);
            maskScale = scale;
        }
        s.resize = () => {
            w.resize(innerWidth, innerHeight);
            if (document.fonts && document.fonts.status !== 'loaded') document.fonts.ready.then(measureGlyphs);
            else measureGlyphs();
        };
        // Прокрутка во время влёта тоже тревожит воду: мягкие капли в случайных местах, тем сильнее, чем быстрее листают.
        let lastY = scrollY, lastScrollDrop = 0;
        addEventListener('scroll', () => {
            const now = performance.now(), dy = Math.abs(scrollY - lastY);
            lastY = scrollY;
            if (!dy || !s.wants() || opened < 0 || now - lastScrollDrop < 70) return;
            lastScrollDrop = now;
            s.lastMotion = now;
            w.drop(.2 + Math.random() * .6, .25 + Math.random() * .5, Math.min(.016, dy * .0001 + .004), .08);
            s.wake();
        }, { passive: true });
        s.tick = () => {
            const now = performance.now(), i = st(), str = scrollFade(i.k) * (opened < 0 ? 1 : s.calm(now)), goal = dripOf(i.k);
            const ddt = Math.min(.1, (now - (dripAt || now)) / 1000);
            dripAt = now;
            dripNow = goal > dripNow ? Math.min(goal, dripNow + ddt * DRIP_SPEED) : Math.max(goal, dripNow - ddt * 1.5);
            const d = dripNow, flowing = goal > dripNow + 1e-4;
            // потёки держат слой и в затишье: обычная вёрстка их нарисовать не может
            s.setActive(paintReady && glyphs && w.ready && !document.hidden && !window.__inGallery && (str > .002 || d > .001 || goal > .001));
            if (!s.active) return;
            // стартовые капли и отсчёт затишья — с первого готового кадра (на медленной сети шрифты приходят
            // не сразу); открыли страницу не с начала — капель не будет
            if (opened < 0) {
                opened = s.lastMotion = now;
                if (i.k < .02 && !started) {
                    started = true;
                    [[.38, .42, 0], [.62, .56, 380], [.5, .34, 820]].forEach(([x, y, t]) =>
                        setTimeout(() => { w.drop(x, y, .028, .07); s.wake(); }, t));
                }
            }
            if (!maskScale || i.scale / maskScale > 1.25 || i.scale / maskScale < .8) drawMask(i.scale);
            const iw = art.naturalWidth, ih = art.naturalHeight, k = Math.max(innerWidth / iw, innerHeight / ih);
            w.frame([[1, paintTex], [2, maskTex]], u => {
                w.gl.uniform1i(u.paint, 1);
                w.gl.uniform1i(u.mask, 2);
                w.gl.uniform2f(u.cover, innerWidth / (iw * k), innerHeight / (ih * k));
                w.gl.uniform1f(u.scale, i.scale / maskScale);  // остаток увеличения сверх нарисованного в маске
                w.gl.uniform1f(u.op, i.op);
                w.gl.uniform1f(u.str, str);
                w.gl.uniform1f(u.drip, d);
                w.gl.uniform1f(u.cols, Math.max(36, Math.min(130, Math.round(innerWidth / 11))));  // столбец струйки ~11 px
            });
            if (str > .002 || flowing) s.wake();  // вода в покое и краска не течёт — новый кадр нужен только при прокрутке
            else dripAt = 0;
        };
        const uploadPaint = () => { w.upload(paintTex, art); paintReady = true; s.wake(); };
        if (art.complete && art.naturalWidth) uploadPaint();
        else art.addEventListener('load', uploadPaint, { once: true });
        s.resize();
    })();

    // ── Галерея ──
    (function gallery() {
        const cv = document.getElementById('galleryRipple'), modal = document.getElementById('modal'),
            img = document.getElementById('modalImg');
        if (!cv || !modal || !img) return;
        const w = water(cv, true, DRAW_GALLERY);
        if (!w) return;
        const paintTex = w.texture();
        let paintSrc = '', greeted = false;
        const s = scene({ cv, w, wants: () => window.__inGallery === true && !window.__studioOpen });
        // текстура картины — то, что сейчас в <img> (миниатюра, средний размер или оригинал при приближении)
        function uploadPaint() {
            if (!img.complete || !img.naturalWidth || img.currentSrc === paintSrc) return;
            w.upload(paintTex, img);
            paintSrc = img.currentSrc;
            s.wake();
        }
        img.addEventListener('load', uploadPaint);
        s.resize = () => w.resize(modal.clientWidth || innerWidth, modal.clientHeight || innerHeight);
        s.tick = () => {
            const now = performance.now();
            if (window.__inGallery && !greeted && w.ready) {
                // вход в галерею: одна мягкая капля на картину
                greeted = true;
                s.resize();
                uploadPaint();
                const r = img.getBoundingClientRect(), c = s.box();
                if (r.width && c.width) {
                    s.lastMotion = now;
                    w.drop((r.left + r.width * .5 - c.left) / c.width, (r.top + r.height * .45 - c.top) / c.height, .022, .07);
                }
            }
            const str = s.calm(now);
            s.setActive(w.ready && window.__inGallery === true && !document.hidden && str > .002);
            if (!s.active) return;
            uploadPaint();
            const r = img.getBoundingClientRect(), c = s.box();
            // картину рисуем, только когда она проявилась целиком и в текстуре она же
            const hasPaint = paintSrc && paintSrc === img.currentSrc && +getComputedStyle(img).opacity > .99 && r.width > 0;
            w.frame([[1, paintTex]], u => {
                w.gl.uniform1i(u.paint, 1);
                w.gl.uniform4f(u.rect, (r.left - c.left) / c.width, 1 - (r.bottom - c.top) / c.height,
                    (r.right - c.left) / c.width, 1 - (r.top - c.top) / c.height);
                w.gl.uniform1f(u.hasPaint, hasPaint ? 1 : 0);
                w.gl.uniform1f(u.str, str);
            });
            s.wake();
        };
        s.resize();
        // в галерею попадают прокруткой (scroll будит сцену) или кнопкой «сразу в галерею»
        const poll = setInterval(() => { if (window.__inGallery) { s.wake(); clearInterval(poll); } }, 500);
    })();
})();
