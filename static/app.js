(function() {
    function getBodyData(name, fallback) {
        if (!document.body) {
            return fallback;
        }
        return document.body.dataset[name] || fallback;
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        localStorage.setItem("theme", theme);

        var lightLabel = getBodyData("themeLightLabel", "Light");
        var darkLabel = getBodyData("themeDarkLabel", "Dark");
        var label = theme === "dark" ? lightLabel : darkLabel;

        var themeButton = document.getElementById("theme-toggle");
        var mobileThemeButton = document.getElementById("theme-toggle-mobile");
        if (themeButton) {
            themeButton.textContent = label;
        }
        if (mobileThemeButton) {
            mobileThemeButton.textContent = label;
        }
    }

    function toggleTheme() {
        var currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
        applyTheme(currentTheme === "dark" ? "light" : "dark");
    }

    function initThemeControls() {
        applyTheme(document.documentElement.getAttribute("data-theme") || "dark");

        var themeButton = document.getElementById("theme-toggle");
        var mobileThemeButton = document.getElementById("theme-toggle-mobile");
        if (themeButton) {
            themeButton.addEventListener("click", toggleTheme);
        }
        if (mobileThemeButton) {
            mobileThemeButton.addEventListener("click", toggleTheme);
        }
    }

    function initPreferenceWidget() {
        var preferenceWidget = document.getElementById("pref-widget");
        var preferenceToggle = document.getElementById("pref-toggle");
        var preferencePanel = document.getElementById("pref-panel");

        if (!preferenceWidget || !preferenceToggle || !preferencePanel) {
            return;
        }

        preferenceToggle.addEventListener("click", function(event) {
            event.stopPropagation();
            preferencePanel.style.display = preferencePanel.style.display === "none" ? "block" : "none";
        });

        document.addEventListener("click", function(event) {
            if (!preferenceWidget.contains(event.target)) {
                preferencePanel.style.display = "none";
            }
        });
    }

    function initHamburgerMenu() {
        var menuToggle = document.getElementById("menu-toggle");
        var navLinks = document.getElementById("nav-links");

        if (!menuToggle || !navLinks) {
            return;
        }

        menuToggle.addEventListener("click", function(event) {
            event.stopPropagation();
            var isOpen = navLinks.classList.toggle("open");
            menuToggle.classList.toggle("open", isOpen);
            menuToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
        });

        document.addEventListener("click", function(event) {
            if (!navLinks.contains(event.target) && !menuToggle.contains(event.target)) {
                navLinks.classList.remove("open");
                menuToggle.classList.remove("open");
                menuToggle.setAttribute("aria-expanded", "false");
            }
        });
    }

    function resolveCopyTarget(button) {
        var selector = button.dataset.copyTarget;
        if (!selector) {
            return null;
        }

        var widgetScope = button.closest(".invoice-widget");
        if (widgetScope) {
            var widgetTarget = widgetScope.querySelector(selector);
            if (widgetTarget) {
                return widgetTarget;
            }
        }

        return document.querySelector(selector);
    }

    function initCopyButtons() {
        document.addEventListener("click", function(event) {
            var button = event.target.closest(".copy-btn[data-copy-target]");
            if (!button) {
                return;
            }

            var target = resolveCopyTarget(button);
            if (!target) {
                return;
            }

            navigator.clipboard.writeText(target.textContent.trim()).then(function() {
                var originalLabel = button.textContent;
                button.textContent = button.dataset.copiedLabel || getBodyData("copiedLabel", "Copied!");
                window.setTimeout(function() {
                    button.textContent = originalLabel;
                }, 2000);
            });
        });
    }

    function initInvoiceWidget(widget) {
        var amountInput = widget.querySelector(".invoice-amount-input");
        var typeSelect = widget.querySelector(".invoice-type-select");
        var createButton = widget.querySelector(".create-invoice-btn");
        var resultBox = widget.querySelector(".invoice-result");
        var typeLabel = widget.querySelector(".invoice-type-label");
        var qrImage = widget.querySelector(".invoice-qr");
        var invoiceCode = widget.querySelector(".invoice-bolt11");
        var status = widget.querySelector(".invoice-status");
        var pollTimer = null;

        widget.querySelectorAll(".preset-btn[data-sats]").forEach(function(button) {
            button.addEventListener("click", function() {
                amountInput.value = button.dataset.sats;
                widget.querySelectorAll(".preset-btn").forEach(function(presetButton) {
                    presetButton.classList.remove("active");
                });
                button.classList.add("active");
            });
        });

        createButton.addEventListener("click", function() {
            var amount = parseInt(amountInput.value, 10);
            if (!amount || amount < 1 || amount > 100000000) {
                window.alert(widget.dataset.invalidAmount);
                return;
            }

            var invoiceType = typeSelect.value;
            createButton.disabled = true;
            createButton.textContent = widget.dataset.generating;

            if (pollTimer) {
                window.clearInterval(pollTimer);
                pollTimer = null;
            }

            fetch(widget.dataset.createUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": widget.dataset.csrfToken
                },
                body: JSON.stringify({ amount_sats: amount, type: invoiceType })
            })
            .then(function(response) {
                return response.json();
            })
            .then(function(data) {
                createButton.disabled = false;
                createButton.textContent = widget.dataset.generateInvoice;

                if (!data.ok) {
                    window.alert(data.error || widget.dataset.failedInvoice);
                    return;
                }

                resultBox.style.display = "block";
                typeLabel.textContent = data.type === "liquid" ? widget.dataset.liquidNetwork : widget.dataset.lightningNetwork;
                typeLabel.className = "invoice-type-label invoice-label-" + data.type;
                qrImage.src = widget.dataset.qrUrl + "?bolt11=" + encodeURIComponent(data.bolt11);
                invoiceCode.textContent = data.bolt11;
                status.textContent = widget.dataset.waitingPayment;
                status.className = "invoice-status invoice-waiting";

                pollTimer = window.setInterval(function() {
                    var checkUrl = widget.dataset.checkUrlTemplate.replace("__HASH__", encodeURIComponent(data.hash));
                    fetch(checkUrl)
                    .then(function(response) {
                        return response.json();
                    })
                    .then(function(invoiceStatus) {
                        if (invoiceStatus.paid) {
                            window.clearInterval(pollTimer);
                            pollTimer = null;
                            status.textContent = widget.dataset.paymentReceived;
                            status.className = "invoice-status invoice-paid";
                        }
                    });
                }, parseInt(widget.dataset.pollIntervalMs || "2000", 10));
            })
            .catch(function() {
                createButton.disabled = false;
                createButton.textContent = widget.dataset.generateInvoice;
                window.alert(widget.dataset.networkError);
            });
        });
    }

    function initInvoiceWidgets() {
        document.querySelectorAll(".invoice-widget").forEach(function(widget) {
            initInvoiceWidget(widget);
        });
    }

    initThemeControls();
    initPreferenceWidget();
    initHamburgerMenu();
    initCopyButtons();
    initInvoiceWidgets();
})();
