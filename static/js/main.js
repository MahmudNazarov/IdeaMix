/* ==========================================================================
   IdeaMix — front-end behaviour
   Progressive enhancement only: every action keeps working without JS.
   ========================================================================== */

(function () {
    'use strict';

    var MOBILE_BREAKPOINT = 980;

    function ready(fn) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', fn);
        } else {
            fn();
        }
    }

    ready(function () {
        initTheme();
        initHeader();
        initNavigation();
        initDropdowns();
        initConfirmModal();
        initToasts();
        initReactions();
        initCopyLink();
        initCharCounters();
        initFilePreviews();
        initAutoSubmit();
        initReveal();
        initBackToTop();
        initRouteProgress();
        initSearchShortcut();
    });

    /* ----------------------------------------------------------------------
       Light / dark theme
       ---------------------------------------------------------------------- */

    function initTheme() {
        var root = document.documentElement;
        var toggles = document.querySelectorAll('[data-theme-toggle]');
        var media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

        function storedTheme() {
            try {
                var value = localStorage.getItem('ideamix-theme');
                return value === 'dark' || value === 'light' ? value : null;
            } catch (error) {
                return null;
            }
        }

        function currentTheme() {
            return root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
        }

        function applyTheme(theme, persist) {
            var isDark = theme === 'dark';
            root.setAttribute('data-theme', theme);

            if (persist) {
                try {
                    localStorage.setItem('ideamix-theme', theme);
                } catch (error) {
                    /* Storage can be unavailable in private mode. */
                }
            }

            toggles.forEach(function (button) {
                button.setAttribute('aria-pressed', String(isDark));
                button.setAttribute('aria-label', isDark ? 'Включить светлую тему' : 'Включить тёмную тему');
                button.setAttribute('title', isDark ? 'Светлая тема' : 'Тёмная тема');
            });

            var meta = document.querySelector('[data-theme-color]');
            if (meta) {
                meta.setAttribute('content', isDark ? '#0c0b16' : '#f8f7fd');
            }
        }

        applyTheme(currentTheme(), false);

        toggles.forEach(function (button) {
            button.addEventListener('click', function () {
                applyTheme(currentTheme() === 'dark' ? 'light' : 'dark', true);
            });
        });

        if (media) {
            var onSystemThemeChange = function (event) {
                if (!storedTheme()) {
                    applyTheme(event.matches ? 'dark' : 'light', false);
                }
            };

            if (media.addEventListener) {
                media.addEventListener('change', onSystemThemeChange);
            } else if (media.addListener) {
                media.addListener(onSystemThemeChange);
            }
        }
    }

    /* ----------------------------------------------------------------------
       Header state
       ---------------------------------------------------------------------- */

    function initHeader() {
        var header = document.querySelector('[data-header]');
        if (!header) return;

        var ticking = false;

        function update() {
            header.classList.toggle('scrolled', window.scrollY > 8);
            ticking = false;
        }

        window.addEventListener('scroll', function () {
            if (ticking) return;
            ticking = true;
            window.requestAnimationFrame(update);
        }, { passive: true });

        update();
    }

    /* ----------------------------------------------------------------------
       Mobile navigation
       ---------------------------------------------------------------------- */

    function initNavigation() {
        var toggle = document.querySelector('[data-nav-toggle]');
        var nav = document.querySelector('[data-nav]');
        if (!toggle || !nav) return;

        function setOpen(open) {
            nav.classList.toggle('open', open);
            document.body.classList.toggle('nav-open', open);
            toggle.setAttribute('aria-expanded', String(open));
            toggle.setAttribute('aria-label', open ? 'Закрыть меню' : 'Открыть меню');
        }

        toggle.addEventListener('click', function () {
            setOpen(!nav.classList.contains('open'));
        });

        nav.addEventListener('click', function (event) {
            var link = event.target.closest('a');
            if (!link) return;
            if (window.innerWidth <= MOBILE_BREAKPOINT) {
                setOpen(false);
            }
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && nav.classList.contains('open')) {
                setOpen(false);
                toggle.focus();
            }
        });

        window.addEventListener('resize', function () {
            if (window.innerWidth > MOBILE_BREAKPOINT && nav.classList.contains('open')) {
                setOpen(false);
            }
        });
    }

    /* ----------------------------------------------------------------------
       Details-based dropdowns
       ---------------------------------------------------------------------- */

    function initDropdowns() {
        document.addEventListener('click', function (event) {
            document.querySelectorAll('.user-menu[open]').forEach(function (details) {
                if (!details.contains(event.target)) {
                    details.removeAttribute('open');
                }
            });

            if (window.innerWidth > MOBILE_BREAKPOINT) {
                document.querySelectorAll('.nav-dropdown[open]').forEach(function (details) {
                    if (!details.contains(event.target)) {
                        details.removeAttribute('open');
                    }
                });
            }
        });

        document.querySelectorAll('.user-menu-panel a, .user-menu-footer a, .user-menu-footer button').forEach(function (item) {
            item.addEventListener('click', function () {
                var details = item.closest('.user-menu');
                if (details) details.removeAttribute('open');
            });
        });
    }

    /* ----------------------------------------------------------------------
       Confirmation modal (data-confirm on forms and links)
       ---------------------------------------------------------------------- */

    function initConfirmModal() {
        var modal = document.getElementById('confirmModal');
        if (!modal) return;

        var title = modal.querySelector('#confirmTitle');
        var text = modal.querySelector('#confirmText');
        var cancelBtn = modal.querySelector('[data-modal-cancel]');
        var confirmBtn = modal.querySelector('[data-modal-confirm]');
        var pending = null;
        var lastFocused = null;

        function open(message, callback) {
            pending = callback;
            lastFocused = document.activeElement;
            text.textContent = message || 'Это действие нельзя отменить.';
            modal.hidden = false;
            window.requestAnimationFrame(function () {
                modal.classList.add('open');
            });
            document.body.classList.add('no-scroll');
            confirmBtn.focus();
        }

        function close() {
            modal.classList.remove('open');
            document.body.classList.remove('no-scroll');
            pending = null;
            window.setTimeout(function () {
                if (!modal.classList.contains('open')) {
                    modal.hidden = true;
                }
            }, 220);
            if (lastFocused && typeof lastFocused.focus === 'function') {
                lastFocused.focus();
            }
        }

        confirmBtn.addEventListener('click', function () {
            var callback = pending;
            close();
            if (typeof callback === 'function') {
                callback();
            }
        });

        cancelBtn.addEventListener('click', close);

        modal.addEventListener('click', function (event) {
            if (event.target === modal) close();
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && !modal.hidden) {
                close();
            }
        });

        document.addEventListener('submit', function (event) {
            var form = event.target;
            if (!form.matches || !form.matches('form[data-confirm]')) return;
            if (form.dataset.confirmed === '1') return;
            event.preventDefault();
            open(form.getAttribute('data-confirm'), function () {
                form.dataset.confirmed = '1';
                if (typeof form.requestSubmit === 'function') {
                    form.requestSubmit();
                } else {
                    form.submit();
                }
            });
        });

        document.addEventListener('click', function (event) {
            var link = event.target.closest('a[data-confirm]');
            if (!link) return;
            event.preventDefault();
            open(link.getAttribute('data-confirm'), function () {
                window.location.href = link.href;
            });
        });

        if (title) {
            title.textContent = 'Подтвердите действие';
        }
    }

    /* ----------------------------------------------------------------------
       Toasts
       ---------------------------------------------------------------------- */

    function initToasts() {
        document.querySelectorAll('[data-toast]').forEach(scheduleToast);

        document.addEventListener('click', function (event) {
            var closeBtn = event.target.closest('[data-toast-close]');
            if (!closeBtn) return;
            dismissToast(closeBtn.closest('[data-toast]'));
        });
    }

    function scheduleToast(toast) {
        window.setTimeout(function () {
            dismissToast(toast);
        }, 6000);
    }

    function dismissToast(toast) {
        if (!toast || toast.classList.contains('hide')) return;
        toast.classList.add('hide');
        window.setTimeout(function () {
            toast.remove();
        }, 320);
    }

    function createToast(message, type) {
        var stack = document.querySelector('.toast-stack');
        if (!stack) {
            stack = document.createElement('div');
            stack.className = 'toast-stack';
            stack.setAttribute('aria-live', 'polite');
            document.body.appendChild(stack);
        }

        var toast = document.createElement('div');
        toast.className = 'toast toast-' + (type || 'info');
        toast.setAttribute('role', 'status');
        toast.setAttribute('data-toast', '');

        var icon = document.createElement('span');
        icon.className = 'toast-icon';
        icon.setAttribute('aria-hidden', 'true');
        icon.innerHTML = '<i class="bi ' + (
            type === 'success' ? 'bi-check-circle-fill' :
            type === 'error' ? 'bi-exclamation-octagon-fill' :
            type === 'warning' ? 'bi-exclamation-triangle-fill' :
            'bi-info-circle-fill'
        ) + '"></i>';

        var text = document.createElement('span');
        text.className = 'toast-text';
        text.textContent = message;

        var closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'toast-close';
        closeBtn.setAttribute('data-toast-close', '');
        closeBtn.setAttribute('aria-label', 'Закрыть уведомление');
        closeBtn.innerHTML = '<i class="bi bi-x-lg" aria-hidden="true"></i>';

        toast.appendChild(icon);
        toast.appendChild(text);
        toast.appendChild(closeBtn);
        stack.appendChild(toast);
        scheduleToast(toast);
    }

    /* ----------------------------------------------------------------------
       AJAX likes and favorites
       ---------------------------------------------------------------------- */

    function initReactions() {
        document.addEventListener('submit', function (event) {
            var form = event.target;
            if (!form.matches || !form.matches('form[data-reaction]')) return;
            event.preventDefault();

            var button = form.querySelector('.reaction-btn');
            if (!button || button.classList.contains('pending')) return;

            var kind = form.getAttribute('data-kind') || 'like';
            var countEl = button.querySelector('[data-count]');
            var labelEl = button.querySelector('.reaction-label');
            button.classList.add('pending');
            button.setAttribute('aria-busy', 'true');

            fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                credentials: 'same-origin',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json'
                }
            })
                .then(function (response) {
                    return response.json().catch(function () {
                        return {};
                    }).then(function (data) {
                        return { response: response, data: data };
                    });
                })
                .then(function (result) {
                    var response = result.response;
                    var data = result.data;

                    if (response.status === 401 && data.login_url) {
                        window.location.href = data.login_url;
                        return;
                    }

                    if (!response.ok) {
                        throw new Error(data.detail || 'Не удалось выполнить действие.');
                    }

                    var active = Boolean(data.active);
                    button.classList.toggle('active', active);
                    button.setAttribute('aria-pressed', String(active));

                    if (countEl && typeof data.count === 'number') {
                        countEl.textContent = data.count;
                    }

                    if (labelEl) {
                        if (kind === 'favorite') {
                            labelEl.textContent = active ? 'В избранном' : 'В избранное';
                        } else {
                            labelEl.textContent = active ? 'Вам нравится' : 'Нравится';
                        }
                    }

                    createToast(
                        kind === 'favorite'
                            ? (active ? 'Идея добавлена в избранное.' : 'Идея убрана из избранного.')
                            : (active ? 'Спасибо за поддержку идеи!' : 'Лайк снят.'),
                        active ? 'success' : 'info'
                    );
                })
                .catch(function (error) {
                    createToast(error.message || 'Не удалось выполнить действие. Попробуйте ещё раз.', 'error');
                })
                .finally(function () {
                    button.classList.remove('pending');
                    button.removeAttribute('aria-busy');
                });
        });
    }

    /* ----------------------------------------------------------------------
       Copy link
       ---------------------------------------------------------------------- */

    function initCopyLink() {
        document.addEventListener('click', function (event) {
            var button = event.target.closest('[data-copy]');
            if (!button) return;

            var value = button.getAttribute('data-copy');
            if (!value) return;

            copyText(value)
                .then(function () {
                    var label = button.querySelector('.reaction-label');
                    var original = label ? label.textContent : null;
                    button.classList.add('copied');
                    if (label) label.textContent = 'Ссылка скопирована';
                    createToast('Ссылка скопирована в буфер обмена.', 'success');
                    window.setTimeout(function () {
                        button.classList.remove('copied');
                        if (label && original !== null) label.textContent = original;
                    }, 2400);
                })
                .catch(function () {
                    createToast('Не удалось скопировать ссылку. Скопируйте её из адресной строки.', 'warning');
                });
        });
    }

    function copyText(value) {
        if (navigator.clipboard && window.isSecureContext) {
            return navigator.clipboard.writeText(value);
        }

        return new Promise(function (resolve, reject) {
            var area = document.createElement('textarea');
            area.value = value;
            area.setAttribute('readonly', '');
            area.style.position = 'fixed';
            area.style.top = '-1000px';
            area.style.opacity = '0';
            document.body.appendChild(area);
            area.select();
            try {
                var ok = document.execCommand('copy');
                document.body.removeChild(area);
                ok ? resolve() : reject(new Error('copy failed'));
            } catch (error) {
                document.body.removeChild(area);
                reject(error);
            }
        });
    }

    /* ----------------------------------------------------------------------
       Character counters
       ---------------------------------------------------------------------- */

    function initCharCounters() {
        document.querySelectorAll('[data-counter-for]').forEach(function (counter) {
            var id = counter.getAttribute('data-counter-for');
            var field = document.getElementById(id);
            if (!field) return;

            var max = parseInt(field.getAttribute('maxlength'), 10) || 1000;

            function update() {
                var length = field.value.length;
                counter.textContent = length + ' / ' + max;
                counter.classList.toggle('near-limit', length > max * 0.85 && length <= max);
                counter.classList.toggle('over-limit', length > max);
            }

            field.addEventListener('input', update);
            update();
        });
    }

    /* ----------------------------------------------------------------------
       Image previews before upload
       ---------------------------------------------------------------------- */

    function initFilePreviews() {
        document.querySelectorAll('input[type="file"][data-preview-target]').forEach(function (input) {
            var targetSelector = input.getAttribute('data-preview-target');
            var target = document.querySelector(targetSelector);
            if (!target) return;
            var image = target.querySelector('img');
            if (!image) return;
            var objectUrl = null;

            input.addEventListener('change', function () {
                var file = input.files && input.files[0];
                if (!file || !file.type || file.type.indexOf('image/') !== 0) {
                    target.hidden = true;
                    if (objectUrl) {
                        URL.revokeObjectURL(objectUrl);
                        objectUrl = null;
                    }
                    return;
                }

                if (objectUrl) URL.revokeObjectURL(objectUrl);
                objectUrl = URL.createObjectURL(file);
                image.src = objectUrl;
                target.hidden = false;
            });
        });
    }

    /* ----------------------------------------------------------------------
       Auto-submit filter selects
       ---------------------------------------------------------------------- */

    function initAutoSubmit() {
        document.querySelectorAll('form[data-autosubmit]').forEach(function (form) {
            form.querySelectorAll('select').forEach(function (select) {
                select.addEventListener('change', function () {
                    if (typeof form.requestSubmit === 'function') {
                        form.requestSubmit();
                    } else {
                        form.submit();
                    }
                });
            });
        });
    }

    /* ----------------------------------------------------------------------
       Reveal on scroll
       ---------------------------------------------------------------------- */

    function initReveal() {
        var items = document.querySelectorAll('[data-reveal]');
        if (!items.length) return;

        if (!('IntersectionObserver' in window)) {
            items.forEach(function (item) {
                item.classList.add('is-visible');
            });
            return;
        }

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                var el = entry.target;
                var siblings = Array.prototype.slice.call(el.parentElement.children);
                var index = siblings.indexOf(el);
                el.style.transitionDelay = Math.min(index, 6) * 45 + 'ms';
                el.classList.add('is-visible');
                observer.unobserve(el);
            });
        }, {
            threshold: 0.08,
            rootMargin: '0px 0px -40px 0px'
        });

        items.forEach(function (item) {
            observer.observe(item);
        });
    }

    /* ----------------------------------------------------------------------
       Back to top
       ---------------------------------------------------------------------- */

    function initBackToTop() {
        var button = document.querySelector('[data-back-to-top]');
        if (!button) return;
        var ticking = false;

        function update() {
            button.classList.toggle('visible', window.scrollY > 520);
            ticking = false;
        }

        window.addEventListener('scroll', function () {
            if (ticking) return;
            ticking = true;
            window.requestAnimationFrame(update);
        }, { passive: true });

        button.addEventListener('click', function () {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });

        update();
    }

    /* ----------------------------------------------------------------------
       Route progress bar
       ---------------------------------------------------------------------- */

    var progressBar = null;
    var progressTimer = null;

    function startProgress() {
        progressBar = progressBar || document.querySelector('[data-route-progress]');
        if (!progressBar) return;
        window.clearTimeout(progressTimer);
        progressBar.classList.remove('done');
        progressBar.classList.add('active');
    }

    function finishProgress() {
        if (!progressBar) return;
        progressBar.classList.add('done');
        progressTimer = window.setTimeout(function () {
            progressBar.classList.remove('active', 'done');
        }, 500);
    }

    function initRouteProgress() {
        progressBar = document.querySelector('[data-route-progress]');

        document.addEventListener('click', function (event) {
            var link = event.target.closest('a');
            if (!link) return;
            if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            if (link.target && link.target !== '_self') return;
            if (link.hasAttribute('download') || link.hasAttribute('data-confirm')) return;

            var href = link.getAttribute('href');
            if (!href || href.charAt(0) === '#' || href.indexOf('mailto:') === 0 || href.indexOf('tel:') === 0) return;
            if (link.origin !== window.location.origin) return;
            if (link.href === window.location.href) return;

            startProgress();
        });

        document.addEventListener('submit', function (event) {
            if (event.defaultPrevented) return;
            if (!event.target.matches('form[data-reaction]')) {
                startProgress();
            }
        });

        window.addEventListener('pageshow', finishProgress);
    }

    /* ----------------------------------------------------------------------
       "/" keyboard shortcut
       ---------------------------------------------------------------------- */

    function initSearchShortcut() {
        document.addEventListener('keydown', function (event) {
            if (event.key !== '/') return;
            if (event.metaKey || event.ctrlKey || event.altKey) return;

            var active = document.activeElement;
            if (active) {
                var tag = active.tagName;
                if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || active.isContentEditable) {
                    return;
                }
            }

            var search = document.querySelector('.nav-search input');
            var mobileSearch = document.querySelector('.mobile-nav-search input');
            var target = search && search.offsetParent !== null ? search : mobileSearch;
            if (!target) return;

            event.preventDefault();

            if (target === mobileSearch) {
                var toggle = document.querySelector('[data-nav-toggle]');
                if (toggle && toggle.getAttribute('aria-expanded') !== 'true') {
                    toggle.click();
                }
            }

            window.setTimeout(function () {
                target.focus();
                target.select();
            }, 80);
        });
    }
})();
