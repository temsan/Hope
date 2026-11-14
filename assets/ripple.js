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
    vec3 glint = pow(max(0., lit), 2.2) * str * vec3(1., .96, .88);`;
    // первый экран: картина «cover» на весь экран, умноженная на маску букв (как слой #title с multiply),
    // увеличенную от центра экрана, — с поправкой на наклон воды
    const DRAW_INTRO = HEAD + `uniform sampler2D sim, paint, mask; uniform vec2 dt, cover; uniform float scale, op, str;
void main() {${SLOPE}
    vec2 q = uv + n * .014 * str;
    vec3 pc = texture(paint, (q - .5) * cover + .5).rgb;
    vec3 m = texture(mask, (q - .5) / scale + .5).rgb;
    o = vec4(pc * mix(vec3(1.), m, op) + glint * .38, 1.);
}`;
    // галерея: в прямоугольнике картины — сама картина со сдвигом, вокруг — только блики и тени (слой прозрачный,
    // цвет с умноженной альфой)
    const DRAW_GALLERY = HEAD + `uniform sampler2D sim, paint; uniform vec2 dt; uniform vec4 rect; uniform float str, hasPaint;
void main() {${SLOPE}
    vec3 light = glint * .34;
    if (hasPaint > .5 && uv.x >= rect.x && uv.x <= rect.z && uv.y >= rect.y && uv.y <= rect.w) {
        vec2 q = uv + n * .012 * str;
        o = vec4(texture(paint, clamp((q - rect.xy) / (rect.zw - rect.xy), 0., 1.)).rgb + light, 1.);
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
            s.wake();
        };
        s.tap = (x, y) => {
            if (!s.wants()) return;
            const r = s.box();
            if (!r.width || !r.height) return;
            s.lastMotion = performance.now();
            s.w.drop((x - r.left) / r.width, (y - r.top) / r.height, .022, .07);
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
            const now = performance.now(), i = st(), str = scrollFade(i.k) * (opened < 0 ? 1 : s.calm(now));
            s.setActive(paintReady && glyphs && w.ready && !document.hidden && !window.__inGallery && str > .002);
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
            });
            s.wake();
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
        const s = scene({ cv, w, wants: () => window.__inGallery === true });
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
