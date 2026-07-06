(() => {
    const stage = document.getElementById('stage');
    const slides = [...document.querySelectorAll('.slide')];
    if (!stage || !slides.length) return;

    const progress = document.createElement('div');
    progress.className = 'promo-progress';
    progress.innerHTML = '<div class="promo-progress-bar"></div>';
    stage.appendChild(progress);

    const dots = document.createElement('div');
    dots.className = 'promo-dots';
    slides.forEach((_, i) => {
        const d = document.createElement('span');
        d.dataset.i = String(i);
        dots.appendChild(d);
    });
    stage.appendChild(dots);

    const bar = progress.querySelector('.promo-progress-bar');
    const dotEls = [...dots.querySelectorAll('span')];

    let idx = 0;
    let timer = null;
    let tick = null;
    let started = 0;
    let totalMs = slides.reduce((s, el) => s + Number(el.dataset.duration || 3500), 0);

    function setDot(i) {
        dotEls.forEach((d, j) => d.classList.toggle('on', j === i));
    }

    function show(i) {
        slides.forEach((s, j) => {
            s.classList.remove('active', 'leaving');
            if (j === i) s.classList.add('active');
        });
        setDot(i);
        idx = i;
    }

    function next() {
        const cur = slides[idx];
        cur.classList.add('leaving');
        cur.classList.remove('active');

        const n = (idx + 1) % slides.length;
        if (n === 0 && !window.PROMO_LOOP) {
            stage.dataset.done = '1';
            window.dispatchEvent(new Event('promo-done'));
            if (bar) bar.style.width = '100%';
            return;
        }

        setTimeout(() => {
            cur.classList.remove('leaving');
            show(n);
            schedule();
        }, 320);
    }

    function schedule() {
        clearTimeout(timer);
        clearInterval(tick);
        const ms = Number(slides[idx].dataset.duration || 3500);
        timer = setTimeout(next, ms);

        const slideStart = Date.now();
        tick = setInterval(() => {
            const elapsed = Date.now() - started;
            const pct = Math.min(100, (elapsed / totalMs) * 100);
            if (bar) bar.style.width = pct + '%';
        }, 80);
    }

    show(0);
    started = Date.now();
    schedule();

    window.promoRestart = () => {
        clearTimeout(timer);
        clearInterval(tick);
        delete stage.dataset.done;
        started = Date.now();
        if (bar) bar.style.width = '0%';
        show(0);
        schedule();
    };
})();
