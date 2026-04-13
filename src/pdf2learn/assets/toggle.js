(function () {
    var KEY = 'pdf2learn-theme';
    var root = document.documentElement;
    var stored = null;
    try { stored = localStorage.getItem(KEY); } catch (e) { /* ignore */ }
    if (stored === 'light' || stored === 'dark') root.setAttribute('data-theme', stored);

    var btn = document.getElementById('theme-toggle');
    if (!btn) return;
    btn.hidden = false;
    btn.addEventListener('click', function () {
        var current = root.getAttribute('data-theme');
        if (!current) {
            current = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }
        var next = current === 'dark' ? 'light' : 'dark';
        root.setAttribute('data-theme', next);
        try { localStorage.setItem(KEY, next); } catch (e) { /* ignore */ }
    });
})();
