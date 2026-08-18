(() => {
    const applyCircularFavicon = () => {
        const faviconLinks = document.querySelectorAll("[data-circular-favicon]");
        if (!faviconLinks.length) return;

        const logo = new Image();
        logo.addEventListener("load", () => {
            const size = 128;
            const canvas = document.createElement("canvas");
            const context = canvas.getContext("2d");
            if (!context) return;

            canvas.width = size;
            canvas.height = size;
            context.beginPath();
            context.arc(size / 2, size / 2, size / 2, 0, Math.PI * 2);
            context.clip();

            const sourceSize = Math.min(logo.naturalWidth, logo.naturalHeight);
            const sourceX = (logo.naturalWidth - sourceSize) / 2;
            const sourceY = (logo.naturalHeight - sourceSize) / 2;
            context.drawImage(logo, sourceX, sourceY, sourceSize, sourceSize, 0, 0, size, size);

            const circularFavicon = canvas.toDataURL("image/png");
            faviconLinks.forEach(link => {
                link.type = "image/png";
                link.href = circularFavicon;
            });
        });
        logo.src = faviconLinks[0].href;
    };

    const pad = value => String(value).padStart(2, "0");
    const setupPasswordToggles = () => {
        document.querySelectorAll("[data-password-toggle]").forEach(button => {
            button.addEventListener("click", () => {
                const input = button.parentElement.querySelector("input");
                if (!input) return;
                const showPassword = input.type === "password";
                input.type = showPassword ? "text" : "password";
                button.setAttribute("aria-pressed", String(showPassword));
                button.setAttribute(
                    "aria-label",
                    `${showPassword ? "Hide" : "Show"} ${input.labels?.[0]?.textContent.trim() || "password"}`,
                );
                const icon = button.querySelector("i");
                if (icon) icon.className = `bi ${showPassword ? "bi-eye-slash" : "bi-eye"}`;
            });
        });
    };
    const updateElapsed = () => {
        document.querySelectorAll("[data-elapsed]").forEach(node => {
            const started = Date.parse(node.dataset.checkIn);
            if (Number.isNaN(started)) return;
            const seconds = Math.max(0, Math.floor((Date.now() - started) / 1000));
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const remaining = seconds % 60;
            node.textContent = `${hours}h ${pad(minutes)}m ${pad(remaining)}s`;
        });
        const clock = document.getElementById("local-clock");
        if (clock) clock.textContent = new Intl.DateTimeFormat("en-KE", {timeZone: "Africa/Nairobi", hour: "2-digit", minute: "2-digit", second: "2-digit"}).format(new Date());
    };
    applyCircularFavicon();
    setupPasswordToggles();
    updateElapsed();
    window.setInterval(updateElapsed, 1000);
})();
